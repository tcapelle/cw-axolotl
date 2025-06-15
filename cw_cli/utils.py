#!/usr/bin/env python3
import subprocess
import yaml
import time
from pathlib import Path
from typing import Dict, Any, Tuple
from rich.console import Console
from rich.table import Table
from rich.layout import Layout
from rich import box

# Initialize rich console
console = Console()


def kubectl(*args, input_data: str = None, capture_output: bool = False) -> subprocess.CompletedProcess:
    """Helper function to run kubectl commands."""
    cmd = ["kubectl"] + list(args)
    return subprocess.run(
        cmd,
        input=input_data,
        text=True,
        capture_output=capture_output,
        check=True
    )


def create_configmap_yaml(config_data: Dict[str, Any], configmap_name: str) -> str:
    """Create a ConfigMap YAML string from the config data."""
    configmap = {
        'apiVersion': 'v1',
        'kind': 'ConfigMap',
        'metadata': {
            'name': configmap_name
        },
        'data': {
            'config.yaml': yaml.dump(config_data, default_flow_style=False)
        }
    }
    return yaml.dump(configmap, default_flow_style=False)


def update_job_yaml_with_resources(job_yaml_path: Path, config_data: Dict[str, Any]) -> str:
    """Update the job YAML with resource requirements from the config."""
    with open(job_yaml_path, 'r') as f:
        yaml_content = f.read()
    
    # Substitute the default image
    yaml_content = substitute_image_in_yaml(yaml_content)
    
    # Parse the updated YAML
    job_data = yaml.safe_load(yaml_content)
    
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


def update_grpo_yaml_with_resources(yaml_path: Path, config_data: Dict[str, Any]) -> str:
    """Update GRPO YAML files with resource requirements from the config."""
    with open(yaml_path, 'r') as f:
        yaml_content = f.read()
    
    # Substitute the default image
    yaml_content = substitute_image_in_yaml(yaml_content)
    
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
    
    # Update resources in all container specs
    for doc in yaml_docs:
        if doc and doc.get('kind') in ['Deployment', 'Job']:
            containers = doc.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
            for container in containers:
                if 'resources' in container:
                    container['resources'] = resources
    
    # Convert back to YAML string
    return '---\n'.join(yaml.dump(doc, default_flow_style=False) for doc in yaml_docs if doc)


def deploy_grpo_services(config_data: Dict[str, Any]) -> bool:
    """Deploy all GRPO services in the correct order."""
    grpo_dir = Path(__file__).parent / "kubeconfigs" / "grpo"
    
    # Create ConfigMap for GRPO config
    configmap_name = "cw-axolotl-train-grpo-config"
    console.print("📝 Creating GRPO ConfigMap...", style="blue")
    configmap_yaml = create_configmap_yaml(config_data, configmap_name)
    
    if not run_kubectl_command(configmap_yaml):
        return False
    
    # Deploy services in order: VLLM, Rewards, Training
    services = [
        ("VLLM Server", "vllm-deployment.yaml"),
        ("Rewards Server", "rewards-deployment.yaml"),
        ("Training Job", "training-job.yaml")
    ]
    
    for service_name, yaml_file in services:
        console.print(f"🚀 Deploying {service_name}...", style="blue")
        
        yaml_path = grpo_dir / yaml_file
        if not yaml_path.exists():
            console.print(f"❌ Error: {yaml_path} not found", style="red")
            return False
        
        try:
            updated_yaml = update_grpo_yaml_with_resources(yaml_path, config_data)
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
    """Get the default container image from config."""
    try:
        config_path = Path(__file__).parent / "config" / "default_image.yaml"
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            return config.get('default_image', 'ghcr.io/tcapelle/triton_eval:1506')
    except Exception:
        return 'ghcr.io/tcapelle/triton_eval:1506'


def substitute_image_in_yaml(yaml_content: str, image: str = None) -> str:
    """Replace placeholder images in YAML content."""
    if image is None:
        image = get_default_image()
    
    # Replace common image patterns
    yaml_content = yaml_content.replace('ghcr.io/tcapelle/triton_eval:1306', image)
    yaml_content = yaml_content.replace('ghcr.io/tcapelle/triton_eval:1506', image)
    
    # Also replace any ${DEFAULT_IMAGE} placeholders if we add them later
    yaml_content = yaml_content.replace('${DEFAULT_IMAGE}', image)
    
    return yaml_content