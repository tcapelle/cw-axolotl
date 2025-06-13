#!/usr/bin/env python3
"""Display utilities for CW CLI."""

from rich.table import Table
from rich import box
from datetime import datetime, timezone
from typing import List, Tuple


def create_table(title: str, columns: List[Tuple[str, str]], show_header: bool = True) -> Table:
    """Create a standardized table."""
    table = Table(box=box.ROUNDED, title=title, show_header=show_header)
    
    for col_name, style in columns:
        table.add_column(col_name, style=style)
    
    return table


def get_age_string(creation_time: str) -> str:
    """Calculate age string from creation timestamp."""
    try:
        created = datetime.fromisoformat(creation_time.replace('Z', '+00:00'))
        age_seconds = (datetime.now(timezone.utc) - created).total_seconds()
        
        if age_seconds < 3600:  # Less than 1 hour
            return f"{int(age_seconds // 60)}m"
        elif age_seconds < 86400:  # Less than 1 day
            return f"{int(age_seconds // 3600)}h"
        else:
            return f"{int(age_seconds // 86400)}d"
    except:
        return "Unknown"


def get_job_status_emoji(status: dict) -> str:
    """Get emoji status for jobs."""
    if status.get('succeeded', 0) > 0:
        return "✅ Complete"
    elif status.get('failed', 0) > 0:
        return "❌ Failed"
    elif status.get('active', 0) > 0:
        return "🔄 Running"
    else:
        return "⏸️ Pending"


def get_pod_status_emoji(phase: str) -> str:
    """Get emoji status for pods."""
    if phase == 'Running':
        return "🔄 Running"
    elif phase == 'Succeeded':
        return "✅ Completed"
    elif phase == 'Failed':
        return "❌ Failed"
    elif phase == 'Pending':
        return "⏸️ Pending"
    else:
        return f"❓ {phase}"


def create_summary(context: str, total: int, running: int, completed: int, failed: int = 0) -> str:
    """Create a summary string."""
    if failed > 0:
        return f"📊 {context}: {total} total, {running} running, {completed} completed, {failed} failed"
    else:
        return f"📊 {context}: {total} total, {running} running, {completed} completed"


def format_resources(containers: List[dict]) -> str:
    """Format resource information for display."""
    resource_info = []
    
    for container in containers:
        resources = container.get('resources', {})
        requests = resources.get('requests', {})
        limits = resources.get('limits', {})
        
        # GPU info
        gpu_req = requests.get('nvidia.com/gpu', limits.get('nvidia.com/gpu', '0'))
        if gpu_req and gpu_req != '0':
            resource_info.append(f"[green]{gpu_req}G[/green]")
        
        # CPU info (compact format)
        cpu_req = requests.get('cpu', limits.get('cpu', ''))
        if cpu_req:
            # Convert to compact format (e.g. "64" -> "64C")
            cpu_val = cpu_req.replace('m', 'mC') if 'm' in str(cpu_req) else f"{cpu_req}C"
            resource_info.append(cpu_val)
        
        # Memory info (compact format)
        mem_req = requests.get('memory', limits.get('memory', ''))
        if mem_req:
            # Keep original format but make it more compact
            mem_val = str(mem_req).replace('Gi', 'G').replace('Mi', 'M')
            resource_info.append(mem_val)
    
    return ", ".join(resource_info) if resource_info else "N/A"