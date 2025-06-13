#!/usr/bin/env python3
"""Status command implementation."""

import yaml
import json
import time
from rich.live import Live
from rich.layout import Layout

from .utils import console, kubectl
from .display import create_table, get_age_string, get_pod_status_emoji, format_resources


def get_status_data(job_name: str) -> tuple:
    """Get job and pod status data."""
    try:
        # Get job status
        job_result = kubectl("get", "job", job_name, "-o", "yaml", capture_output=True)
        job_data = yaml.safe_load(job_result.stdout)
        
        # Get pod status
        pod_result = kubectl("get", "pods", "-l", f"job-name={job_name}", "-o", "yaml", capture_output=True)
        pod_data = yaml.safe_load(pod_result.stdout)
        
        return job_data, pod_data
    except:
        return {}, {}


def create_status_layout(job_data: dict, pod_data: dict, job_name: str) -> Layout:
    """Create status display layout."""
    layout = Layout()
    
    # Job status table
    job_table = create_table("📊 Job Status", [
        ("Metric", "cyan"),
        ("Value", "magenta")
    ])
    
    status = job_data.get('status', {})
    job_table.add_row("Job Name", job_name)
    job_table.add_row("Active", str(status.get('active', 0)))
    job_table.add_row("Succeeded", str(status.get('succeeded', 0)))
    job_table.add_row("Failed", str(status.get('failed', 0)))
    job_table.add_row("Updated", time.strftime("%H:%M:%S"))
    
    # Pod status table
    if pod_data.get('items'):
        pod_table = create_table("🏃 Pods", [
            ("Pod Name", "cyan"),
            ("Status", "green"),
            ("Node", "blue"),
            ("Resources", "green")
        ])
        
        for pod in pod_data['items']:
            name = pod['metadata']['name']
            phase = pod.get('status', {}).get('phase', 'Unknown')
            node = pod['spec'].get('nodeName', 'N/A')
            containers = pod['spec'].get('containers', [])
            
            pod_table.add_row(
                name,
                get_pod_status_emoji(phase),
                node,
                format_resources(containers)
            )
        
        layout.split_column(Layout(job_table), Layout(pod_table))
    else:
        layout.update(job_table)
    
    return layout


def handle_status_output(job: str, watch: bool, output: str) -> int:
    """Handle status command with different output formats."""
    # Get initial data
    job_data, pod_data = get_status_data(job)
    
    if not job_data:
        console.print(f"❌ Job '{job}' not found", style="red")
        console.print("💡 Try: [cyan]cw list[/] to see available jobs", style="yellow")
        return 1
    
    # Handle different output formats
    if output in ["yaml", "json"]:
        if output == "yaml":
            console.print("# Job Data")
            console.print(yaml.dump(job_data, default_flow_style=False))
            console.print("# Pod Data")
            console.print(yaml.dump(pod_data, default_flow_style=False))
        else:
            console.print("# Job Data")
            console.print(json.dumps(job_data, indent=2))
            console.print("# Pod Data")
            console.print(json.dumps(pod_data, indent=2))
        return 0
    
    # Handle watch mode
    if watch:
        console.print("🔄 Watching job status... (Press Ctrl+C to stop)", style="blue")
        
        with Live(console=console, refresh_per_second=2) as live:
            try:
                while True:
                    job_data, pod_data = get_status_data(job)
                    if not job_data:
                        console.print(f"❌ Job '{job}' not found", style="red")
                        return 1
                    
                    layout = create_status_layout(job_data, pod_data, job)
                    live.update(layout)
                    time.sleep(2)
            except KeyboardInterrupt:
                console.print("\n⏹️ Stopped watching.", style="yellow")
                return 0
    else:
        # Single status check
        layout = create_status_layout(job_data, pod_data, job)
        console.print(layout)
    
    return 0