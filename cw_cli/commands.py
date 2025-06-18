#!/usr/bin/env python3
"""Command implementations for CW CLI."""

import subprocess
import yaml
import time
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timezone

from .utils import console, kubectl, create_configmap_yaml, update_job_yaml_with_resources, run_kubectl_command, deploy_grpo_services, cleanup_grpo_services
from .display import create_table, create_summary, get_age_string, get_pod_status_emoji, get_job_status_emoji


def _get_available_jobs() -> List[str]:
    """Get list of available CW jobs in the cluster (jobs with cw- prefix)."""
    try:
        result = kubectl("get", "jobs", "-o", "json", capture_output=True)
        jobs_data = json.loads(result.stdout)
        # Only return jobs that start with 'cw-'
        cw_jobs = [job['metadata']['name'] for job in jobs_data.get('items', []) 
                   if job['metadata']['name'].startswith('cw-')]
        return cw_jobs
    except Exception:
        return []


def _is_grpo_job(job_name: str) -> bool:
    """Check if the given job is a GRPO job based on its name."""
    return job_name == "cw-axolotl-train-grpo"


def _prompt_job_selection(jobs: List[str], action: str) -> str:
    """Prompt user to select a job from available jobs."""
    if not jobs:
        console.print(f"❌ No jobs found in cluster", style="red")
        return ""
    
    if len(jobs) == 1:
        job_name = jobs[0]
        response = console.input(f"Do you want to {action} [cyan]{job_name}[/]? (y/N): ").strip().lower()
        return job_name if response in ['y', 'yes'] else ""
    
    console.print(f"📋 Available jobs:", style="blue")
    for i, job in enumerate(jobs, 1):
        console.print(f"  {i}. {job}")
    
    try:
        choice = console.input(f"\nSelect job to {action} (1-{len(jobs)} or name): ").strip()
        
        # Try to parse as number
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(jobs):
                return jobs[idx]
        except ValueError:
            pass
        
        # Try to match by name
        if choice in jobs:
            return choice
        
        # Partial match
        matches = [job for job in jobs if choice.lower() in job.lower()]
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            console.print(f"❌ Multiple matches found: {', '.join(matches)}", style="red")
        else:
            console.print(f"❌ No job found matching '{choice}'", style="red")
        
    except KeyboardInterrupt:
        console.print("\n⏹️ Cancelled", style="yellow")
    
    return ""


def _follow_job_logs(job_name: str):
    """Follow job logs with wait for pod readiness."""
    console.print("📡 Waiting for pod to be ready...", style="blue")
    
    # Wait for pod to be ready (up to 5 minutes)
    max_wait = 300  # 5 minutes
    wait_time = 0
    
    while wait_time < max_wait:
        try:
            # Check if pod is ready
            result = kubectl("get", "pods", "-l", f"job-name={job_name}", "-o", "json", capture_output=True)
            pods_data = json.loads(result.stdout)
            
            if pods_data.get('items'):
                pod = pods_data['items'][0]
                phase = pod.get('status', {}).get('phase')
                
                if phase == 'Running':
                    console.print("📡 Following logs... (Press Ctrl+C to stop)", style="blue")
                    kubectl("logs", "-f", f"job/{job_name}")
                    return
                elif phase in ['Failed', 'Succeeded']:
                    console.print(f"📡 Pod finished with status: {phase}. Showing logs...", style="yellow")
                    kubectl("logs", f"job/{job_name}")
                    return
                else:
                    console.print(f"⏳ Pod status: {phase}, waiting...", style="yellow")
            
        except Exception as e:
            console.print(f"⏳ Waiting for pod... ({e})", style="yellow")
        
        time.sleep(5)
        wait_time += 5
    
    console.print("❌ Timeout waiting for pod to be ready. Try 'cw logs' later.", style="red")


def parse_overrides(args: List[str]) -> Dict[str, Any]:
    """Parse --key value pairs from command line arguments."""
    overrides = {}
    i = 0
    while i < len(args):
        if args[i].startswith('--'):
            key = args[i][2:]  # Remove '--'
            if i + 1 < len(args) and not args[i + 1].startswith('--'):
                value = args[i + 1]
                # Try to convert to appropriate type
                try:
                    # Try int first
                    if value.isdigit():
                        overrides[key] = int(value)
                    # Try float
                    elif '.' in value and value.replace('.', '').isdigit():
                        overrides[key] = float(value)
                    # Keep as string
                    else:
                        overrides[key] = value
                except ValueError:
                    overrides[key] = value
                i += 2
            else:
                # Boolean flag
                overrides[key] = True
                i += 1
        else:
            i += 1
    return overrides


def apply_overrides(config_data: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Apply command line overrides to config data."""
    for key, value in overrides.items():
        console.print(f"🔧 Override: {key} = {value}", style="yellow")
        config_data[key] = value
    return config_data


def train_command(train_config) -> int:
    """Train a model with Axolotl."""
    import sys
    
    config_path = Path(train_config.config)
    
    if not config_path.exists():
        console.print(f"❌ Error: Config file {config_path} not found", style="red")
        return 1
    
    # Load the SFT config
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
    except Exception as e:
        console.print(f"❌ Error reading config file: {e}", style="red")
        return 1
    
    # Parse and apply command line overrides
    # Find where config file is in argv and get args after it
    try:
        config_idx = sys.argv.index(str(config_path))
        override_args = sys.argv[config_idx + 1:]
    except ValueError:
        # Try with just filename
        try:
            config_idx = sys.argv.index(config_path.name)
            override_args = sys.argv[config_idx + 1:]
        except ValueError:
            override_args = []
    
    overrides = parse_overrides(override_args)
    if overrides:
        config_data = apply_overrides(config_data, overrides)
    
    # Generate unique names for this run
    configmap_name = "cw-axolotl-train-sft-config"
    
    # Create ConfigMap YAML
    configmap_yaml = create_configmap_yaml(config_data, configmap_name)
    
    # Load and update job YAML
    job_yaml_path = Path(__file__).parent / "kubeconfigs" / "sft_job.yaml"
    try:
        job_yaml = update_job_yaml_with_resources(job_yaml_path, config_data, train_config.pull)
    except Exception as e:
        console.print(f"❌ Error processing job YAML: {e}", style="red")
        return 1
    
    # Apply ConfigMap first
    console.print("📝 Creating ConfigMap...", style="blue")
    if not run_kubectl_command(configmap_yaml):
        return 1
    
    # Apply Job
    console.print("🚀 Creating Job...", style="blue")
    if not run_kubectl_command(job_yaml):
        console.print("❌ Job creation failed, cleaning up ConfigMap...", style="yellow")
        run_kubectl_command(configmap_yaml, apply=False)
        return 1
    
    console.print("🎉 SFT job submitted successfully!", style="green bold")
    
    # Automatically follow logs
    job_name = "cw-axolotl-train-sft"
    console.print(f"\n🔄 Following logs for {job_name}... (Press Ctrl+C to stop)")
    
    try:
        _follow_job_logs(job_name)
    except KeyboardInterrupt:
        console.print("\n⏹️ Log following stopped.", style="yellow")
        console.print(f"💡 To resume monitoring: [cyan]cw logs -j {job_name}[/]")
    except Exception as e:
        console.print(f"❌ Could not follow logs: {e}", style="red")
        console.print(f"💡 Try manually: [cyan]cw logs -j {job_name}[/]")
    
    return 0


def grpo_command(grpo_config) -> int:
    """Train a model with GRPO (multi-service deployment)."""
    import sys
    
    config_path = Path(grpo_config.config)
    
    if not config_path.exists():
        console.print(f"❌ Error: Config file {config_path} not found", style="red")
        return 1
    
    # Load the GRPO config
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
    except Exception as e:
        console.print(f"❌ Error reading config file: {e}", style="red")
        return 1
    
    # Parse and apply command line overrides
    try:
        config_idx = sys.argv.index(str(config_path))
        override_args = sys.argv[config_idx + 1:]
    except ValueError:
        try:
            config_idx = sys.argv.index(config_path.name)
            override_args = sys.argv[config_idx + 1:]
        except ValueError:
            override_args = []
    
    overrides = parse_overrides(override_args)
    if overrides:
        config_data = apply_overrides(config_data, overrides)
    
    # Validate GRPO config
    if config_data.get('rl') != 'grpo':
        console.print("❌ Error: Config must have 'rl: grpo' for GRPO training", style="red")
        return 1
    
    # Deploy GRPO services
    console.print("🚀 Deploying GRPO services...", style="blue")
    if not deploy_grpo_services(config_data, grpo_config.pull):
        return 1
    
    console.print("🎉 GRPO training started successfully!", style="green bold")
    
    # Automatically follow training logs
    job_name = "cw-axolotl-train-grpo"
    console.print(f"\n🔄 Following training logs for {job_name}... (Press Ctrl+C to stop)")
    console.print(f"💡 Check all services: [cyan]cw pods -A[/]")
    
    try:
        _follow_job_logs(job_name)
    except KeyboardInterrupt:
        console.print("\n⏹️ Log following stopped.", style="yellow")
        console.print(f"💡 To resume monitoring: [cyan]cw logs -j {job_name}[/]")
    except Exception as e:
        console.print(f"❌ Could not follow logs: {e}", style="red")
        console.print(f"💡 Try manually: [cyan]cw logs -j {job_name}[/]")
    
    return 0


def logs_command(job: str, no_follow: bool = False) -> int:
    """View job logs."""
    try:
        # If no job specified, prompt user to select
        if not job:
            available_jobs = _get_available_jobs()
            job = _prompt_job_selection(available_jobs, "view logs for")
            if not job:
                return 1
        
        # Safety check: only allow viewing logs for jobs with cw- prefix
        if not job.startswith('cw-'):
            console.print(f"❌ Error: This CLI can only view logs for jobs with 'cw-' prefix. '{job}' is not a CW-managed job.", style="red")
            return 1
        
        if no_follow:
            kubectl("logs", f"job/{job}")
        else:
            _follow_job_logs(job)
        return 0
    except subprocess.CalledProcessError as e:
        console.print(f"❌ Failed to get logs: {e}", style="red")
        return 1
    except KeyboardInterrupt:
        console.print("\n⏹️ Log following stopped.", style="yellow")
        return 0


def status_command(job: str, watch: bool = False, output: str = "table") -> int:
    """Check job status."""
    try:
        # If no job specified, prompt user to select
        if not job:
            available_jobs = _get_available_jobs()
            job = _prompt_job_selection(available_jobs, "check status for")
            if not job:
                return 1
        
        # Safety check: only allow checking status for jobs with cw- prefix
        if not job.startswith('cw-'):
            console.print(f"❌ Error: This CLI can only check status for jobs with 'cw-' prefix. '{job}' is not a CW-managed job.", style="red")
            return 1
        
        from .status import get_status_data, create_status_layout, handle_status_output
        return handle_status_output(job, watch, output)
    except subprocess.CalledProcessError as e:
        console.print(f"❌ Failed to get status: {e}", style="red")
        return 1


def resources_command() -> int:
    """Show available cluster resources (CPU, Memory, GPU)."""
    try:
        from rich.table import Table
        from rich import box
        import concurrent.futures
        
        # Get nodes data
        result = kubectl("get", "nodes", "-o", "json", capture_output=True)
        nodes_data = yaml.safe_load(result.stdout)
        
        # Create main summary table
        summary_table = Table(box=box.ROUNDED, title="🖥️ Cluster Resource Summary")
        summary_table.add_column("Node", style="cyan")
        summary_table.add_column("Status", style="yellow")
        summary_table.add_column("GPUs", style="green")
        summary_table.add_column("CPU", style="blue")
        summary_table.add_column("Memory", style="magenta")
        summary_table.add_column("Availability", style="white")
        
        total_gpus_free = 0
        total_nodes_available = 0
        gpu_nodes = []
        
        # Helper function to get node describe data
        def get_node_describe_data(node_name):
            try:
                describe_result = kubectl("describe", "node", node_name, capture_output=True)
                return node_name, describe_result.stdout
            except Exception as e:
                return node_name, None
        
        # Get all GPU-enabled nodes for parallel describe calls
        gpu_node_names = []
        node_info_map = {}
        
        for node in nodes_data.get("items", []):
            node_name = node["metadata"]["name"]
            node_info_map[node_name] = node
            
            capacity = node.get("status", {}).get("capacity", {})
            gpu_capacity = capacity.get("nvidia.com/gpu", "0")
            if gpu_capacity != "0" and gpu_capacity is not None:
                gpu_node_names.append(node_name)
        
        # Run kubectl describe in parallel for all GPU nodes
        describe_results = {}
        if gpu_node_names:
            console.print(f"🔍 Checking {len(gpu_node_names)} GPU nodes in parallel...", style="dim")
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(gpu_node_names))) as executor:
                future_to_node = {executor.submit(get_node_describe_data, node_name): node_name for node_name in gpu_node_names}
                for future in concurrent.futures.as_completed(future_to_node):
                    node_name, describe_text = future.result()
                    describe_results[node_name] = describe_text
        
        # Process all nodes with the describe data
        for node in nodes_data.get("items", []):
            node_name = node["metadata"]["name"]
            
            # Get node status
            conditions = node.get("status", {}).get("conditions", [])
            ready_condition = next((c for c in conditions if c["type"] == "Ready"), {})
            is_ready = ready_condition.get("status") == "True"
            
            # Check if scheduling is disabled
            spec = node.get("spec", {})
            unschedulable = spec.get("unschedulable", False)
            
            if unschedulable:
                status = "SchedulingDisabled"
            elif not is_ready:
                status = "NotReady"
            else:
                status = "Ready"
            
            # Get resource capacity and allocatable
            capacity = node.get("status", {}).get("capacity", {})
            allocatable = node.get("status", {}).get("allocatable", {})
            
            # Parse GPU info
            gpu_capacity = capacity.get("nvidia.com/gpu", "0")
            if gpu_capacity == "0" or gpu_capacity is None:
                gpu_info = "No GPUs"
                gpu_free = 0
            else:
                # Use pre-fetched describe data
                describe_text = describe_results.get(node_name)
                if describe_text:
                    # Extract GPU usage from describe output
                    gpu_used = 0
                    for line in describe_text.split('\n'):
                        if 'nvidia.com/gpu' in line and 'Allocated resources' in describe_text[describe_text.find(line)-500:describe_text.find(line)]:
                            parts = line.strip().split()
                            if len(parts) >= 3:
                                try:
                                    gpu_used = int(parts[1])
                                    break
                                except:
                                    pass
                    
                    gpu_total = int(gpu_capacity)
                    gpu_free = max(0, gpu_total - gpu_used)
                    gpu_info = f"{gpu_free}/{gpu_total} free"
                    
                    if gpu_total > 0:
                        gpu_nodes.append((node_name, gpu_free, gpu_total, status))
                        if status == "Ready":
                            total_gpus_free += gpu_free
                else:
                    gpu_info = f"?/{gpu_capacity}"
                    gpu_free = 0
            
            # Parse CPU and Memory
            cpu_allocatable = allocatable.get("cpu", "0")
            memory_allocatable = allocatable.get("memory", "0Ki")
            
            # Convert CPU (e.g., "127960m" -> "127.96")
            if cpu_allocatable.endswith('m'):
                cpu_cores = float(cpu_allocatable[:-1]) / 1000
                cpu_info = f"{cpu_cores:.1f} cores"
            else:
                cpu_info = f"{cpu_allocatable} cores"
            
            # Convert Memory (e.g., "2111839476Ki" -> "2062 Gi")
            if memory_allocatable.endswith('Ki'):
                memory_gi = int(memory_allocatable[:-2]) / (1024 * 1024)
                memory_info = f"{memory_gi:.0f}Gi"
            else:
                memory_info = memory_allocatable
            
            # Determine availability
            if status != "Ready":
                availability = "❌ Unavailable"
            elif gpu_free >= 8:
                availability = "✅ Full node (8+ GPUs)"
                total_nodes_available += 1
            elif gpu_free > 0:
                availability = f"⚠️  Partial ({gpu_free} GPUs)"
            elif gpu_capacity != "0":
                availability = "🔴 GPUs occupied"
            else:
                availability = "💻 CPU-only node"
            
            summary_table.add_row(
                node_name,
                status,
                gpu_info,
                cpu_info,
                memory_info,
                availability
            )
        
        console.print(summary_table)
        
        # Show summary stats
        console.print(f"\n📊 **Summary:**")
        console.print(f"• **Available full nodes** (8+ GPUs): {total_nodes_available}")
        console.print(f"• **Total free GPUs**: {total_gpus_free}")
        console.print(f"• **GPU nodes**: {len([n for n in gpu_nodes if n[2] > 0])}")
        
        # Always show detailed GPU breakdown
        if gpu_nodes:
            console.print(f"\n🎯 **GPU Availability Details:**")
            gpu_table = Table(box=box.SIMPLE)
            gpu_table.add_column("Node", style="cyan")
            gpu_table.add_column("Free/Total GPUs", style="green") 
            gpu_table.add_column("Status", style="yellow")
            
            # Sort by available GPUs (most available first)
            for node_name, gpu_free, gpu_total, status in sorted(gpu_nodes, key=lambda x: x[1], reverse=True):
                gpu_table.add_row(node_name, f"{gpu_free}/{gpu_total}", status)
            
            console.print(gpu_table)
        
        return 0
        
    except subprocess.CalledProcessError as e:
        console.print(f"❌ Failed to get cluster resources: {e}", style="red")
        return 1
    except Exception as e:
        console.print(f"❌ Error processing cluster resources: {e}", style="red")
        return 1


def _force_delete_resources() -> int:
    """Force delete any CW resources (jobs, deployments, services)."""
    from rich.prompt import Prompt
    import subprocess
    
    # Get all CW resources
    cw_resources = []
    
    # Get jobs
    try:
        result = kubectl("get", "jobs", "-o", "json", capture_output=True)
        jobs_data = yaml.safe_load(result.stdout)
        for item in jobs_data.get("items", []):
            name = item["metadata"]["name"]
            if name.startswith("cw-"):
                cw_resources.append(("job", name))
    except subprocess.CalledProcessError:
        pass
    
    # Get deployments
    try:
        result = kubectl("get", "deployments", "-o", "json", capture_output=True)
        deployments_data = yaml.safe_load(result.stdout)
        for item in deployments_data.get("items", []):
            name = item["metadata"]["name"]
            if name.startswith("cw-"):
                cw_resources.append(("deployment", name))
    except subprocess.CalledProcessError:
        pass
    
    # Get services
    try:
        result = kubectl("get", "services", "-o", "json", capture_output=True)
        services_data = yaml.safe_load(result.stdout)
        for item in services_data.get("items", []):
            name = item["metadata"]["name"]
            if name.startswith("cw-"):
                cw_resources.append(("service", name))
    except subprocess.CalledProcessError:
        pass
    
    if not cw_resources:
        console.print("✅ No CW resources found to delete", style="green")
        return 0
    
    # Display available resources
    console.print("🗑️  Found CW resources:", style="bold blue")
    for i, (resource_type, name) in enumerate(cw_resources, 1):
        console.print(f"  {i}. {resource_type}: {name}")
    
    # Prompt for selection
    try:
        choice = Prompt.ask(
            "Select resource to delete (number) or 'all' to delete all",
            choices=[str(i) for i in range(1, len(cw_resources) + 1)] + ["all", "q"]
        )
    except KeyboardInterrupt:
        console.print("\n⏹️ Cancelled", style="yellow")
        return 0
    
    if choice == "q":
        return 0
    
    # Confirm deletion
    if choice == "all":
        response = console.input("⚠️  Are you sure you want to delete ALL CW resources? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            console.print("⏹️ Deletion cancelled", style="yellow")
            return 0
        
        # Delete all resources
        for resource_type, name in cw_resources:
            try:
                kubectl("delete", resource_type, name)
                console.print(f"✅ {resource_type.capitalize()} {name} deleted", style="green")
            except subprocess.CalledProcessError as e:
                console.print(f"❌ Failed to delete {resource_type} {name}: {e}", style="red")
    else:
        # Delete selected resource
        idx = int(choice) - 1
        resource_type, name = cw_resources[idx]
        
        response = console.input(f"⚠️  Are you sure you want to delete {resource_type} {name}? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            console.print("⏹️ Deletion cancelled", style="yellow")
            return 0
        
        try:
            kubectl("delete", resource_type, name)
            console.print(f"✅ {resource_type.capitalize()} {name} deleted", style="green")
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to delete {resource_type} {name}: {e}", style="red")
            return 1
    
    return 0


def delete_command(job: str, force: bool = False) -> int:
    """Delete job and associated resources."""
    try:
        # If force flag is used, show all CW resources for selection
        if force:
            return _force_delete_resources()
        
        # If no job specified, prompt user to select
        if not job:
            available_jobs = _get_available_jobs()
            job = _prompt_job_selection(available_jobs, "delete")
            if not job:
                return 1
        
        # Safety check: only allow deleting jobs with cw- prefix
        if not job.startswith('cw-'):
            console.print(f"❌ Error: This CLI can only delete jobs with 'cw-' prefix. '{job}' is not a CW-managed job.", style="red")
            return 1
        
        # Check if this is a GRPO job based on job name
        is_grpo_job = _is_grpo_job(job)
        
        # Confirm deletion with appropriate warning
        if is_grpo_job:
            response = console.input(f"⚠️  Are you sure you want to delete GRPO job [red]{job}[/] and all associated services? (y/N): ").strip().lower()
        else:
            response = console.input(f"⚠️  Are you sure you want to delete job [red]{job}[/]? (y/N): ").strip().lower()
        
        if response not in ['y', 'yes']:
            console.print("⏹️ Deletion cancelled", style="yellow")
            return 0
        
        kubectl("delete", "job", job)
        console.print(f"✅ Job [bold]{job}[/] deleted successfully", style="green")
        
        # If this is a GRPO job, clean up associated services
        if is_grpo_job:
            console.print("🧹 Cleaning up GRPO services...", style="blue")
            if cleanup_grpo_services():
                console.print("✅ GRPO services cleaned up successfully", style="green")
            else:
                console.print("⚠️  Some GRPO services may not have been cleaned up", style="yellow")
        
        # Try to delete associated ConfigMap (may not exist)
        configmap_name = "cw-axolotl-config" if is_grpo_job else "cw-axolotl-train-config"
        try:
            kubectl("delete", "configmap", configmap_name)
            console.print(f"✅ ConfigMap [bold]{configmap_name}[/] deleted successfully", style="green")
        except subprocess.CalledProcessError:
            console.print(f"ℹ️  No associated ConfigMap {configmap_name} found to delete", style="cyan")
        
        return 0
    except subprocess.CalledProcessError as e:
        console.print(f"❌ Failed to delete resources: {e}", style="red")
        return 1


def list_command() -> int:
    """List CW-managed jobs only."""
    try:
        result = kubectl("get", "jobs", "-o", "json", capture_output=True)
        jobs_data = yaml.safe_load(result.stdout)
        
        # Filter only jobs with cw- prefix
        cw_jobs = [job for job in jobs_data.get('items', []) 
                   if job['metadata']['name'].startswith('cw-')]
        
        if not cw_jobs:
            console.print("📋 No CW-managed jobs found", style="yellow")
            return 0
        
        # Create table
        table = create_table("🚀 CW-Managed Jobs", [
            ("Job Name", "cyan"),
            ("Status", "green"), 
            ("Active", "blue"),
            ("Succeeded", "green"),
            ("Failed", "red"),
            ("Age", "yellow")
        ])
        
        for job in cw_jobs:
            name = job['metadata']['name']
            status = job.get('status', {})
            creation_time = job['metadata']['creationTimestamp']
            
            overall_status = get_job_status_emoji(status)
            age = get_age_string(creation_time)
            
            table.add_row(
                name,
                overall_status,
                str(status.get('active', 0)),
                str(status.get('succeeded', 0)),
                str(status.get('failed', 0)),
                age
            )
        
        console.print(table)
        return 0
        
    except subprocess.CalledProcessError as e:
        console.print(f"❌ Failed to list jobs: {e}", style="red")
        return 1


def jobs_command(namespace: str = "default", all_namespaces: bool = False) -> int:
    """List all jobs in cluster."""
    try:
        cmd_args = ["get", "jobs", "-o", "json"]
        if all_namespaces:
            cmd_args.append("--all-namespaces")
        else:
            cmd_args.extend(["-n", namespace])
        
        result = kubectl(*cmd_args, capture_output=True)
        jobs_data = yaml.safe_load(result.stdout)
        
        if not jobs_data.get('items'):
            ns_info = "all namespaces" if all_namespaces else f"namespace '{namespace}'"
            console.print(f"📋 No jobs found in {ns_info}", style="yellow")
            return 0
        
        # Create table
        columns = []
        if all_namespaces:
            columns.append(("Namespace", "blue"))
        columns.extend([
            ("Job Name", "cyan"),
            ("Status", "green"),
            ("Completions", "magenta"),
            ("Age", "yellow")
        ])
        
        table = create_table("🏗️ All Cluster Jobs", columns)
        
        for job in jobs_data['items']:
            name = job['metadata']['name']
            ns = job['metadata']['namespace']
            status = job.get('status', {})
            spec = job.get('spec', {})
            creation_time = job['metadata']['creationTimestamp']
            
            overall_status = get_job_status_emoji(status)
            age = get_age_string(creation_time)
            
            # Completions
            completions = spec.get('completions')
            succeeded = status.get('succeeded', 0)
            if completions:
                completion_info = f"{succeeded}/{completions}"
            else:
                completion_info = f"{succeeded}/1"
            
            row_data = []
            if all_namespaces:
                row_data.append(ns)
            row_data.extend([name, overall_status, completion_info, age])
            
            table.add_row(*row_data)
        
        console.print(table)
        
        # Summary
        total = len(jobs_data['items'])
        running = sum(1 for job in jobs_data['items'] if job.get('status', {}).get('active', 0) > 0)
        completed = sum(1 for job in jobs_data['items'] if job.get('status', {}).get('succeeded', 0) > 0)
        
        ns_info = "all namespaces" if all_namespaces else f"'{namespace}'"
        console.print(create_summary(f"Jobs in {ns_info}", total, running, completed))
        
        return 0
        
    except subprocess.CalledProcessError as e:
        console.print(f"❌ Failed to list jobs: {e}", style="red")
        return 1


def pods_command(namespace: str = "default", all_namespaces: bool = False, 
                show_resources: bool = False, watch: bool = False) -> int:
    """List all pods in cluster."""
    try:
        from .pods import handle_pods_display
        return handle_pods_display(namespace, all_namespaces, show_resources, watch)
    except subprocess.CalledProcessError as e:
        console.print(f"❌ Failed to list pods: {e}", style="red")
        return 1


def info_command(nodes: bool = False) -> int:
    """Show cluster information."""
    try:
        from .cluster import show_cluster_info
        return show_cluster_info(nodes)
    except subprocess.CalledProcessError as e:
        console.print(f"❌ Failed to get cluster info: {e}", style="red")
        return 1