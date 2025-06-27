#!/usr/bin/env python3
import subprocess
import yaml
import time
import json
from pathlib import Path
from typing import Dict, Any, Tuple, List
from rich.console import Console
from rich.table import Table
from rich.layout import Layout
from rich import box

# Initialize rich console
console = Console()


def kubectl(*args, input_data: str = None, capture_output: bool = False) -> subprocess.CompletedProcess:
    """Helper function to run kubectl commands."""
    cmd = ["kubectl"] + list(args)
    
    # Print the command in dimmed grey
    cmd_str = " ".join(cmd)
    if input_data:
        # Truncate long input data for display
        input_preview = input_data[:100] + "..." if len(input_data) > 100 else input_data
        input_preview = input_preview.replace('\n', ' ')
        console.print(f"$ {cmd_str} <<< {input_preview}", style="dim white")
    else:
        console.print(f"$ {cmd_str}", style="dim white")
    
    return subprocess.run(
        cmd,
        input=input_data,
        text=True,
        capture_output=capture_output,
        check=True
    )


def create_configmap_yaml(config_data: Dict[str, Any], configmap_name: str) -> str:
    """Create a ConfigMap YAML string from the config data."""
    # Remove cluster-specific fields that shouldn't be passed to axolotl
    clean_config = config_data.copy()
    
    # Remove fields that are used for cluster deployment but not axolotl training
    cluster_fields = ['image', 'gpu', 'cpu', 'memory', 'resources']
    for field in cluster_fields:
        clean_config.pop(field, None)
    
    configmap = {
        'apiVersion': 'v1',
        'kind': 'ConfigMap',
        'metadata': {
            'name': configmap_name
        },
        'data': {
            'config.yaml': yaml.dump(clean_config, default_flow_style=False)
        }
    }
    return yaml.dump(configmap, default_flow_style=False)


def update_job_yaml_with_resources(job_yaml_path: Path, config_data: Dict[str, Any], pull_latest: bool = False) -> str:
    """Update the job YAML with resource requirements from the config."""
    with open(job_yaml_path, 'r') as f:
        yaml_content = f.read()
    
    # Parse the YAML first
    job_data = yaml.safe_load(yaml_content)
    
    # Extract and apply container image from config
    if 'image' in config_data:
        container = job_data['spec']['template']['spec']['containers'][0]
        container['image'] = config_data['image']
    
    # Extract resource requirements from config if they exist
    resources = {}
    if 'resources' in config_data:
        resources = config_data['resources']
    elif any(key in config_data for key in ['gpu', 'cpu', 'memory']):
        # Map common resource fields
        if 'gpu' in config_data:
            resources.setdefault('limits', {})['nvidia.com/gpu'] = str(config_data['gpu'])
            resources.setdefault('requests', {})['nvidia.com/gpu'] = str(config_data['gpu'])
        if 'cpu' in config_data:
            resources.setdefault('limits', {})['cpu'] = str(config_data['cpu'])  
            resources.setdefault('requests', {})['cpu'] = str(config_data['cpu'])
        if 'memory' in config_data:
            resources.setdefault('limits', {})['memory'] = str(config_data['memory'])
            resources.setdefault('requests', {})['memory'] = str(config_data['memory'])
    
    # Update job resources if specified in config
    if resources:
        container = job_data['spec']['template']['spec']['containers'][0]
        container['resources'] = resources
    
    # Add PULL_LATEST environment variable if requested
    if pull_latest:
        container = job_data['spec']['template']['spec']['containers'][0]
        if 'env' not in container:
            container['env'] = []
        container['env'].append({
            'name': 'PULL_LATEST',
            'value': 'true'
        })
    
    return yaml.dump(job_data, default_flow_style=False)


def run_kubectl_command(yaml_content: str, apply: bool = True) -> bool:
    """Run kubectl command with the provided YAML content."""
    action = "apply" if apply else "delete"
    
    try:
        result = kubectl(action, "-f", "-", input_data=yaml_content, capture_output=True)
        console.print(f"✅ kubectl {action} successful", style="green")
        if result.stdout.strip():
            console.print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"❌ kubectl {action} failed", style="red")
        console.print(e.stderr, style="red")
        return False


def get_status_data(job_name: str) -> Tuple[dict, dict]:
    """Get job and pod status data."""
    try:
        # Get job status
        job_result = kubectl("get", "job", job_name, "-o", "yaml", capture_output=True)
        job_data = yaml.safe_load(job_result.stdout)
        
        # Get pod status
        pod_result = kubectl("get", "pods", "-l", f"job-name={job_name}", "-o", "yaml", capture_output=True)
        pod_data = yaml.safe_load(pod_result.stdout)
        
        return job_data, pod_data
    except subprocess.CalledProcessError:
        # Job doesn't exist, return empty data
        return {}, {}


def create_status_layout(job_data: dict, pod_data: dict, job_name: str) -> Layout:
    """Create the status dashboard layout."""
    layout = Layout()
    
    # Extract status information
    status = job_data.get('status', {})
    conditions = status.get('conditions', [])
    
    # Create job status table
    job_table = Table(box=box.ROUNDED, title="📊 Job Status")
    job_table.add_column("Metric", style="cyan", no_wrap=True)
    job_table.add_column("Value", style="magenta")
    
    job_table.add_row("Job Name", job_name)
    job_table.add_row("Active", str(status.get('active', 0)))
    job_table.add_row("Succeeded", str(status.get('succeeded', 0)))
    job_table.add_row("Failed", str(status.get('failed', 0)))
    job_table.add_row("Updated", time.strftime("%H:%M:%S"))
    
    # Create conditions table if available
    conditions_renderable = ""
    if conditions:
        conditions_table = Table(box=box.ROUNDED, title="🔍 Job Conditions")
        conditions_table.add_column("Type", style="cyan")
        conditions_table.add_column("Status", style="green")
        conditions_table.add_column("Reason", style="yellow")
        
        for condition in conditions:
            conditions_table.add_row(
                condition.get('type', 'N/A'),
                condition.get('status', 'N/A'),
                condition.get('reason', 'N/A')
            )
        conditions_renderable = conditions_table
    
    # Create pods table
    pods_renderable = ""
    if pod_data.get('items'):
        pods_table = Table(box=box.ROUNDED, title="🏃 Pods & Resources")
        pods_table.add_column("Pod Name", style="cyan")
        pods_table.add_column("Status", style="green")
        pods_table.add_column("Resources", style="yellow")
        pods_table.add_column("Node", style="blue")
        
        for pod in pod_data['items']:
            pod_name = pod['metadata']['name']
            pod_status = pod['status']['phase']
            node_name = pod['spec'].get('nodeName', 'N/A')
            
            # Extract resource information
            containers = pod['spec'].get('containers', [])
            resource_info = []
            
            for container in containers:
                resources = container.get('resources', {})
                requests = resources.get('requests', {})
                limits = resources.get('limits', {})
                
                # Get GPU info
                gpu_req = requests.get('nvidia.com/gpu', limits.get('nvidia.com/gpu', '0'))
                if gpu_req and gpu_req != '0':
                    resource_info.append(f"[green]{gpu_req}x GPU[/green]")
                
                # Get CPU info
                cpu_req = requests.get('cpu', limits.get('cpu', ''))
                if cpu_req:
                    resource_info.append(f"{cpu_req} CPU")
                
                # Get Memory info
                mem_req = requests.get('memory', limits.get('memory', ''))
                if mem_req:
                    resource_info.append(f"{mem_req} RAM")
            
            resource_str = ", ".join(resource_info) if resource_info else "N/A"
            pods_table.add_row(pod_name, pod_status, resource_str, node_name)
        
        pods_renderable = pods_table
    
    # Create layout structure
    if conditions_renderable and pods_renderable:
        layout.split_column(
            Layout(job_table, name="job"),
            Layout(conditions_renderable, name="conditions"),
            Layout(pods_renderable, name="pods")
        )
    elif pods_renderable:
        layout.split_column(
            Layout(job_table, name="job"),
            Layout(pods_renderable, name="pods")
        )
    else:
        layout.update(job_table)
    
    return layout


def update_grpo_yaml_with_resources(yaml_path: Path, config_data: Dict[str, Any], pull_latest: bool = False) -> str:
    """Update GRPO YAML files with resource requirements from the config."""
    with open(yaml_path, 'r') as f:
        yaml_content = f.read()
    
    # Split multi-document YAML if needed
    yaml_docs = list(yaml.safe_load_all(yaml_content))
    
    # For GRPO, resources are typically full nodes, so we use standard values
    # unless overridden in the config
    resources = {
        'limits': {
            'nvidia.com/gpu': str(config_data.get('gpu', 8)),
            'cpu': str(config_data.get('cpu', '32')),
            'memory': str(config_data.get('memory', '1000Gi'))
        },
        'requests': {
            'nvidia.com/gpu': str(config_data.get('gpu', 8)),
            'cpu': str(config_data.get('cpu', '32')),
            'memory': str(config_data.get('memory', '1000Gi'))
        }
    }
    
    # Update resources and image in all container specs
    for doc in yaml_docs:
        if doc and doc.get('kind') in ['Deployment', 'Job']:
            containers = doc.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
            for container in containers:
                # Apply image from config if specified
                if 'image' in config_data:
                    container['image'] = config_data['image']
                
                # Apply resources
                if 'resources' in container:
                    container['resources'] = resources
                
                # Add PULL_LATEST environment variable if requested
                if pull_latest:
                    if 'env' not in container:
                        container['env'] = []
                    container['env'].append({
                        'name': 'PULL_LATEST',
                        'value': 'true'
                    })
    
    # Convert back to YAML string
    return '---\n'.join(yaml.dump(doc, default_flow_style=False) for doc in yaml_docs if doc)


def deploy_grpo_services(config_data: Dict[str, Any], pull_latest: bool = False, services_only: bool = False) -> bool:
    """Deploy all GRPO services in the correct order."""
    grpo_dir = Path(__file__).parent / "kubeconfigs" / "axolotl" / "grpo"
    
    # Create ConfigMap for GRPO config
    configmap_name = "cw-axolotl-train-grpo-config"
    console.print("📝 Creating GRPO ConfigMap...", style="blue")
    configmap_yaml = create_configmap_yaml(config_data, configmap_name)
    
    if not run_kubectl_command(configmap_yaml):
        return False
    
    # Deploy services in order: VLLM, Rewards, Training (skip training if services_only)
    services = [
        ("VLLM Server", "vllm-deployment.yaml"),
        ("Rewards Server", "rewards-deployment.yaml"),
    ]
    
    if not services_only:
        services.append(("Training Job", "training-job.yaml"))
    
    for service_name, yaml_file in services:
        console.print(f"🚀 Deploying {service_name}...", style="blue")
        
        yaml_path = grpo_dir / yaml_file
        if not yaml_path.exists():
            console.print(f"❌ Error: {yaml_path} not found", style="red")
            return False
        
        try:
            updated_yaml = update_grpo_yaml_with_resources(yaml_path, config_data, pull_latest)
            if not run_kubectl_command(updated_yaml):
                console.print(f"❌ Failed to deploy {service_name}", style="red")
                return False
            
            console.print(f"✅ {service_name} deployed successfully", style="green")
            
            # Add delay between services to ensure proper startup order
            if service_name != "Training Job":
                console.print("⏳ Waiting for service to initialize...", style="yellow")
                time.sleep(10)
                
        except Exception as e:
            console.print(f"❌ Error deploying {service_name}: {e}", style="red")
            return False
    
    return True


def deploy_verifiers_services(config_data: Dict[str, Any], pull_latest: bool = False, services_only: bool = False) -> bool:
    """Deploy all Verifiers GRPO services in the correct order."""
    verifiers_dir = Path(__file__).parent / "kubeconfigs" / "verifiers"
    
    # Create ConfigMap for Verifiers config
    configmap_name = "cw-verifiers-train-grpo-config"
    console.print("📝 Creating Verifiers ConfigMap...", style="blue")
    configmap_yaml = create_configmap_yaml(config_data, configmap_name)
    
    if not run_kubectl_command(configmap_yaml):
        return False
    
    # Deploy services in order: VLLM, Rewards, Training (skip training if services_only)
    services = [
        ("Verifiers VLLM Server", "vllm-deployment.yaml"),
        ("Verifiers Rewards Server", "rewards-deployment.yaml"),
    ]
    
    if not services_only:
        services.append(("Verifiers Training Job", "training-job.yaml"))
    
    for service_name, yaml_file in services:
        console.print(f"🚀 Deploying {service_name}...", style="blue")
        
        yaml_path = verifiers_dir / yaml_file
        if not yaml_path.exists():
            console.print(f"❌ Error: {yaml_path} not found", style="red")
            return False
        
        try:
            updated_yaml = update_grpo_yaml_with_resources(yaml_path, config_data, pull_latest)
            if not run_kubectl_command(updated_yaml):
                console.print(f"❌ Failed to deploy {service_name}", style="red")
                return False
            
            console.print(f"✅ {service_name} deployed successfully", style="green")
            
            # Add delay between services to ensure proper startup order
            if service_name != "Verifiers Training Job":
                console.print("⏳ Waiting for service to initialize...", style="yellow")
                time.sleep(10)
                
        except Exception as e:
            console.print(f"❌ Error deploying {service_name}: {e}", style="red")
            return False
    
    return True


def cleanup_grpo_services() -> bool:
    """Clean up all GRPO services (deployments and services)."""
    success = True
    
    # Clean up all resources with cw-vllm and cw-rewards prefixes
    resource_prefixes = ["cw-vllm", "cw-rewards"]
    resource_types = ["deployment", "service"]
    
    for resource_type in resource_types:
        try:
            # Get all resources of this type
            result = kubectl("get", resource_type, "-o", "json", capture_output=True)
            resources_data = yaml.safe_load(result.stdout)
            
            # Filter resources with cw-vllm or cw-rewards prefixes
            for item in resources_data.get("items", []):
                resource_name = item["metadata"]["name"]
                if any(resource_name.startswith(prefix) for prefix in resource_prefixes):
                    try:
                        kubectl("delete", resource_type, resource_name)
                        console.print(f"✅ {resource_type.capitalize()} {resource_name} deleted", style="green")
                    except subprocess.CalledProcessError:
                        console.print(f"⚠️  Failed to delete {resource_type} {resource_name}", style="yellow")
                        success = False
        except subprocess.CalledProcessError:
            console.print(f"ℹ️  No {resource_type}s found", style="cyan")
    
    return success


def get_default_image() -> str:
    """Get the default container image (fallback)."""
    return 'ghcr.io/tcapelle/triton_eval:1906'


def get_available_ssh_keys() -> List[str]:
    """Get list of available SSH keys from ~/.ssh directory."""
    ssh_dir = Path.home() / ".ssh"
    if not ssh_dir.exists():
        return []
    
    ssh_keys = []
    # Look for public key files
    for key_file in ssh_dir.glob("*.pub"):
        ssh_keys.append(str(key_file))
    
    return sorted(ssh_keys)


def prompt_ssh_key_selection() -> str:
    """Prompt user to select an SSH key from available keys."""
    ssh_keys = get_available_ssh_keys()
    
    if not ssh_keys:
        console.print("❌ No SSH public keys found in ~/.ssh", style="red")
        return ""
    
    if len(ssh_keys) == 1:
        key_path = ssh_keys[0]
        console.print(f"🔑 Using SSH key: [cyan]{key_path}[/]", style="blue")
        return key_path
    
    console.print("🔑 Available SSH keys:", style="blue")
    for i, key_path in enumerate(ssh_keys, 1):
        # Show just the filename
        key_name = Path(key_path).name
        console.print(f"  {i}. {key_name}")
    
    try:
        choice = console.input(f"\nSelect SSH key (1-{len(ssh_keys)}): ").strip()
        idx = int(choice) - 1
        if 0 <= idx < len(ssh_keys):
            return ssh_keys[idx]
        else:
            console.print("❌ Invalid selection", style="red")
            return ""
    except (ValueError, KeyboardInterrupt):
        console.print("\n⏹️ Cancelled", style="yellow")
        return ""


def get_available_devpods() -> List[str]:
    """Get list of available devpods in the cluster."""
    try:
        result = kubectl("get", "statefulsets", "-o", "json", capture_output=True)
        sts_data = json.loads(result.stdout)
        devpods = [sts['metadata']['name'] for sts in sts_data.get('items', []) 
                   if sts['metadata']['name'].startswith('devpod-')]
        return devpods
    except Exception:
        return []


def prompt_devpod_selection(action: str) -> str:
    """Prompt user to select a devpod from available devpods."""
    devpods = get_available_devpods()
    
    if not devpods:
        console.print(f"❌ No devpods found in cluster", style="red")
        return ""
    
    if len(devpods) == 1:
        devpod_name = devpods[0]
        response = console.input(f"Do you want to {action} [cyan]{devpod_name}[/]? (y/N): ").strip().lower()
        return devpod_name if response in ['y', 'yes'] else ""
    
    console.print(f"📋 Available devpods:", style="blue")
    for i, devpod in enumerate(devpods, 1):
        console.print(f"  {i}. {devpod}")
    
    try:
        choice = console.input(f"\nSelect devpod to {action} (1-{len(devpods)} or name): ").strip()
        
        # Try to parse as number
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(devpods):
                return devpods[idx]
        except ValueError:
            pass
        
        # Try to match by name
        if choice in devpods:
            return choice
        
        # Partial match
        matches = [devpod for devpod in devpods if choice.lower() in devpod.lower()]
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            console.print(f"❌ Multiple matches found: {', '.join(matches)}", style="red")
        else:
            console.print(f"❌ No devpod found matching '{choice}'", style="red")
        
    except KeyboardInterrupt:
        console.print("\n⏹️ Cancelled", style="yellow")
    
    return ""


def create_devpod_yaml(name: str, ssh_key_path: str, gpu: int = 8, cpu: int = 64, memory: str = "1200Gi") -> str:
    """Create devpod YAML with parameterized values."""
    devpod_template_path = Path(__file__).parent / "kubeconfigs" / "dev-pod" / "devpod.yaml"
    
    with open(devpod_template_path, 'r') as f:
        yaml_content = f.read()
    
    # Read SSH public key content
    try:
        with open(ssh_key_path, 'r') as f:
            ssh_key_content = f.read().strip()
    except Exception as e:
        console.print(f"❌ Failed to read SSH key {ssh_key_path}: {e}", style="red")
        return ""
    
    # Replace placeholders in the YAML content
    yaml_content = yaml_content.replace("devpod-2", f"devpod-{name}")
    yaml_content = yaml_content.replace("parasail-devpod-2", f"parasail-devpod-{name}")
    
    # Parse YAML to update resources and SSH key
    yaml_docs = list(yaml.safe_load_all(yaml_content))
    
    for doc in yaml_docs:
        if not doc:
            continue
            
        # Update StatefulSet resources
        if doc.get('kind') == 'StatefulSet':
            containers = doc.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
            for container in containers:
                if container.get('name') == 'devpod':
                    container['resources'] = {
                        'limits': {
                            'nvidia.com/gpu': str(gpu),
                            'cpu': str(cpu),
                            'memory': memory
                        },
                        'requests': {
                            'nvidia.com/gpu': str(gpu),
                            'cpu': str(cpu),
                            'memory': memory
                        }
                    }
        
        # Update ConfigMap with SSH key
        elif doc.get('kind') == 'ConfigMap':
            config_name = doc.get('metadata', {}).get('name', '')
            if config_name.startswith('devpod-') and config_name.endswith('-ssh-keys'):
                doc['data']['authorized_keys'] = ssh_key_content
    
    # Convert back to YAML string
    return '---\n'.join(yaml.dump(doc, default_flow_style=False) for doc in yaml_docs if doc)


def deploy_devpod(name: str, ssh_key_path: str, gpu: int = 8, cpu: int = 64, memory: str = "1200Gi") -> bool:
    """Deploy a new devpod with the specified configuration."""
    console.print(f"🚀 Deploying devpod-{name}...", style="blue")
    
    # Check if devpod already exists
    existing_devpods = get_available_devpods()
    if f"devpod-{name}" in existing_devpods:
        console.print(f"❌ Devpod 'devpod-{name}' already exists", style="red")
        return False
    
    # Create the YAML configuration
    yaml_content = create_devpod_yaml(name, ssh_key_path, gpu, cpu, memory)
    if not yaml_content:
        return False
    
    # Apply the configuration
    return run_kubectl_command(yaml_content)


def ssh_to_devpod(devpod_name: str) -> bool:
    """SSH to a devpod."""
    console.print(f"🔐 Connecting to {devpod_name} via SSH...", style="blue")
    
    try:
        # Get the service port-forward command
        cmd = ["kubectl", "port-forward", f"service/{devpod_name}", "2222:22"]
        console.print(f"$ {' '.join(cmd)}", style="dim white")
        
        # Start port-forward in background
        port_forward_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Give port-forward time to establish
        time.sleep(2)
        
        # SSH to localhost:2222
        ssh_cmd = ["ssh", "-p", "2222", "root@localhost"]
        console.print(f"$ {' '.join(ssh_cmd)}", style="dim white")
        
        # Execute SSH interactively
        result = subprocess.run(ssh_cmd)
        
        # Clean up port-forward
        port_forward_proc.terminate()
        port_forward_proc.wait()
        
        return result.returncode == 0
        
    except Exception as e:
        console.print(f"❌ SSH connection failed: {e}", style="red")
        return False


def cleanup_devpod(devpod_name: str) -> bool:
    """Clean up a devpod and all its resources."""
    console.print(f"🗑️ Deleting devpod {devpod_name}...", style="blue")
    
    success = True
    
    # Resources to clean up
    resources = [
        ("statefulset", devpod_name),
        ("service", devpod_name),
        ("configmap", f"{devpod_name}-ssh-keys"),
        ("ingressroutetcp", f"{devpod_name}-ssh"),
    ]
    
    for resource_type, resource_name in resources:
        try:
            kubectl("delete", resource_type, resource_name, capture_output=True)
            console.print(f"✅ {resource_type.capitalize()} {resource_name} deleted", style="green")
        except subprocess.CalledProcessError:
            console.print(f"⚠️  {resource_type.capitalize()} {resource_name} not found or failed to delete", style="yellow")
            success = False
    
    # Also clean up PVCs
    try:
        result = kubectl("get", "pvc", "-o", "json", capture_output=True)
        pvcs_data = json.loads(result.stdout)
        
        for pvc in pvcs_data.get('items', []):
            pvc_name = pvc['metadata']['name']
            if devpod_name in pvc_name:
                try:
                    kubectl("delete", "pvc", pvc_name, capture_output=True)
                    console.print(f"✅ PVC {pvc_name} deleted", style="green")
                except subprocess.CalledProcessError:
                    console.print(f"⚠️  PVC {pvc_name} failed to delete", style="yellow")
                    success = False
    except Exception:
        pass
    
    return success