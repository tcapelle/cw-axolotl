#!/usr/bin/env python3
"""Cluster info command implementation."""

import yaml
from .utils import console, kubectl
from .display import create_table


def show_cluster_info(show_nodes: bool = False) -> int:
    """Show cluster information and capabilities."""
    try:
        # Get nodes
        nodes_result = kubectl("get", "nodes", "-o", "json", capture_output=True)
        nodes_data = yaml.safe_load(nodes_result.stdout)
        
        if not nodes_data.get('items'):
            console.print("❌ No nodes found in cluster", style="red")
            return 1
        
        # Calculate totals
        total_gpus = 0
        total_cpus = 0
        total_memory = 0
        gpu_types = set()
        ready_nodes = 0
        
        for node in nodes_data['items']:
            conditions = node.get('status', {}).get('conditions', [])
            ready_condition = next((c for c in conditions if c['type'] == 'Ready'), {})
            if ready_condition.get('status') == 'True':
                ready_nodes += 1
            
            capacity = node.get('status', {}).get('capacity', {})
            labels = node['metadata'].get('labels', {})
            
            # GPU info
            gpu_capacity = capacity.get('nvidia.com/gpu', '0')
            total_gpus += int(gpu_capacity) if gpu_capacity.isdigit() else 0
            
            # CPU info  
            cpu_capacity = capacity.get('cpu', '0')
            total_cpus += int(cpu_capacity) if cpu_capacity.isdigit() else 0
            
            # Memory info
            memory_capacity = capacity.get('memory', '0Ki')
            memory_gb = int(memory_capacity.replace('Ki', '')) // 1024 // 1024 if 'Ki' in memory_capacity else 0
            total_memory += memory_gb
            
            # GPU types
            for label_key, label_value in labels.items():
                if 'gpu' in label_key.lower() or 'accelerator' in label_key.lower():
                    if 'h100' in label_value.lower():
                        gpu_types.add("H100")
                    elif 'a100' in label_value.lower():
                        gpu_types.add("A100")
                    elif 'v100' in label_value.lower():
                        gpu_types.add("V100")
                    elif 'rtx' in label_value.lower():
                        gpu_types.add("RTX")
                    break
            
            if not gpu_types and int(gpu_capacity) > 0:
                gpu_types.add("GPU")
        
        # Display cluster overview
        console.print(f"[bold cyan]🏗️ Cluster Overview[/]")
        console.print(f"  Nodes: {ready_nodes}/{len(nodes_data['items'])} ready")
        console.print(f"  GPUs: [green]{total_gpus}[/green] total ({', '.join(sorted(gpu_types)) if gpu_types else 'None'})")
        console.print(f"  CPUs: {total_cpus} total")
        console.print(f"  Memory: {total_memory}GB total")
        console.print()
        
        # Node details table
        columns = [
            ("Node", "cyan"),
            ("Status", "green"),
            ("GPU", "green"),
            ("CPU", "blue"),
            ("Memory", "magenta")
        ]
        
        if show_nodes:
            columns.append(("OS", "yellow"))
        
        nodes_table = create_table("🖥️ Nodes", columns)
        
        for node in nodes_data['items']:
            node_name = node['metadata']['name']
            
            # Get node status
            conditions = node.get('status', {}).get('conditions', [])
            ready_condition = next((c for c in conditions if c['type'] == 'Ready'), {})
            status = "✅" if ready_condition.get('status') == 'True' else "❌"
            
            # Get resources
            capacity = node.get('status', {}).get('capacity', {})
            labels = node['metadata'].get('labels', {})
            
            # GPU info
            gpu_capacity = capacity.get('nvidia.com/gpu', '0')
            gpu_display = f"[green]{gpu_capacity}[/green]" if int(gpu_capacity) > 0 else "0"
            
            # Get GPU type
            gpu_type = ""
            for label_key, label_value in labels.items():
                if 'gpu' in label_key.lower() or 'accelerator' in label_key.lower():
                    if 'h100' in label_value.lower():
                        gpu_type = " H100"
                    elif 'a100' in label_value.lower():
                        gpu_type = " A100"
                    elif 'v100' in label_value.lower():
                        gpu_type = " V100"
                    elif 'rtx' in label_value.lower():
                        gpu_type = " RTX"
                    break
            
            gpu_display += gpu_type
            
            # CPU and Memory
            cpu_capacity = capacity.get('cpu', '0')
            memory_capacity = capacity.get('memory', '0Ki')
            memory_gb = int(memory_capacity.replace('Ki', '')) // 1024 // 1024 if 'Ki' in memory_capacity else 0
            
            row_data = [node_name, status, gpu_display, cpu_capacity, f"{memory_gb}GB"]
            
            if show_nodes:
                node_info = node.get('status', {}).get('nodeInfo', {})
                os_info = node_info.get('osImage', 'N/A').split()[0]  # Just first part
                row_data.append(os_info)
            
            nodes_table.add_row(*row_data)
        
        console.print(nodes_table)
        
        return 0
        
    except Exception as e:
        console.print(f"❌ Failed to get cluster info: {e}", style="red")
        return 1