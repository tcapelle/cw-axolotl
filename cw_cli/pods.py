#!/usr/bin/env python3
"""Pods command implementation."""

import yaml
import time
from rich.live import Live
from rich.layout import Layout

from .utils import console, kubectl
from .display import create_table, get_age_string, get_pod_status_emoji, format_resources, create_summary


def group_pods_by_type(pods: list) -> dict:
    """Group pods by their owner type."""
    groups = {
        'Jobs': [],
        'Deployments': [],
        'DaemonSets': [],
        'StatefulSets': [],
        'Standalone': []
    }
    
    for pod in pods:
        owner_refs = pod['metadata'].get('ownerReferences', [])
        
        if not owner_refs:
            groups['Standalone'].append(pod)
        else:
            owner_kind = owner_refs[0].get('kind', 'Unknown')
            
            if owner_kind == 'Job':
                groups['Jobs'].append(pod)
            elif owner_kind in ['ReplicaSet', 'Deployment']:
                groups['Deployments'].append(pod)
            elif owner_kind == 'DaemonSet':
                groups['DaemonSets'].append(pod)
            elif owner_kind == 'StatefulSet':
                groups['StatefulSets'].append(pod)
            else:
                groups['Standalone'].append(pod)
    
    return groups


def create_pods_display(pods_data: dict, namespace: str, all_namespaces: bool, show_resources: bool):
    """Create and print pods display directly."""
    if not pods_data.get('items'):
        ns_info = "all namespaces" if all_namespaces else f"namespace '{namespace}'"
        console.print(f"📋 No pods found in {ns_info}", style="yellow")
        return
    
    pod_groups = group_pods_by_type(pods_data['items'])
    
    for group_name, pods in pod_groups.items():
        if not pods:
            continue
        
        # Create table columns
        columns = []
        if all_namespaces:
            columns.append(("Namespace", "blue"))
        
        columns.extend([
            ("Pod Name", "cyan"),
            ("Status", "green"),
            ("Ready", "blue"),
            ("Age", "yellow"),
            ("Node", "white"),
            ("Resources", "green")
        ])
        
        table = create_table(f"🏷️ {group_name} ({len(pods)} pods)", columns)
        
        for pod in pods:
            name = pod['metadata']['name']
            namespace_name = pod['metadata']['namespace']
            status = pod.get('status', {})
            creation_time = pod['metadata']['creationTimestamp']
            node_name = pod['spec'].get('nodeName', 'N/A')
            
            # Calculate ready containers
            container_statuses = status.get('containerStatuses', [])
            ready_count = sum(1 for cs in container_statuses if cs.get('ready', False))
            total_containers = len(container_statuses)
            ready_str = f"{ready_count}/{total_containers}"
            
            phase = status.get('phase', 'Unknown')
            pod_status = get_pod_status_emoji(phase)
            age = get_age_string(creation_time)
            
            row_data = []
            if all_namespaces:
                row_data.append(namespace_name)
            
            # Always show resources now
            containers = pod['spec'].get('containers', [])
            resources_str = format_resources(containers)
            
            row_data.extend([name, pod_status, ready_str, age, node_name, resources_str])
            
            table.add_row(*row_data)
        
        console.print(table)
    
    # Add summary
    total_pods = len(pods_data['items'])
    running_pods = sum(1 for pod in pods_data['items'] if pod.get('status', {}).get('phase') == 'Running')
    completed_pods = sum(1 for pod in pods_data['items'] if pod.get('status', {}).get('phase') == 'Succeeded')
    failed_pods = sum(1 for pod in pods_data['items'] if pod.get('status', {}).get('phase') == 'Failed')
    
    ns_info = "all namespaces" if all_namespaces else f"'{namespace}'"
    timestamp = time.strftime("%H:%M:%S")
    
    console.print(f"\n📊 Pods in {ns_info}: {total_pods} total, {running_pods} running, {completed_pods} completed, {failed_pods} failed (Updated: {timestamp})", style="cyan")


def handle_pods_display(namespace: str, all_namespaces: bool, show_resources: bool, watch: bool) -> int:
    """Handle pods display with optional watch mode."""
    try:
        cmd_args = ["get", "pods", "-o", "json"]
        if all_namespaces:
            cmd_args.append("--all-namespaces")
        else:
            cmd_args.extend(["-n", namespace])
        
        if watch:
            console.print("🔄 Watching pods... (Press Ctrl+C to stop)", style="blue")
            
            try:
                while True:
                    # Clear screen for watch mode
                    console.clear()
                    console.print("🔄 Watching pods... (Press Ctrl+C to stop)", style="blue")
                    console.print()
                    
                    result = kubectl(*cmd_args, capture_output=True)
                    pods_data = yaml.safe_load(result.stdout)
                    
                    create_pods_display(pods_data, namespace, all_namespaces, show_resources)
                    time.sleep(2)
            except KeyboardInterrupt:
                console.print("\n⏹️ Stopped watching.", style="yellow")
                return 0
        else:
            # Single display
            result = kubectl(*cmd_args, capture_output=True)
            pods_data = yaml.safe_load(result.stdout)
            
            create_pods_display(pods_data, namespace, all_namespaces, show_resources)
        
        return 0
        
    except Exception as e:
        console.print(f"❌ Failed to list pods: {e}", style="red")
        return 1