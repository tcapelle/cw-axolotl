#!/usr/bin/env python3
"""Configuration classes for CW CLI."""

from dataclasses import dataclass
from simple_parsing import field


@dataclass
class TrainConfig:
    """Train a model with Axolotl"""
    config: str = field(positional=True, help="Path to the SFT config YAML file")
    pull: bool = field(default=False, alias="--pull", help="Pull latest axolotl_dev code before training")


@dataclass
class GrpoConfig:
    """Train a model with GRPO (requires multi-service deployment)"""
    config: str = field(positional=True, help="Path to the GRPO config YAML file")
    pull: bool = field(default=False, alias="--pull", help="Pull latest axolotl_dev code before training")


@dataclass
class GrpoRestartConfig:
    """Restart GRPO services"""
    service: str = field(positional=True, help="Service to restart: 'vllm' or 'rewards'")


@dataclass 
class LogsConfig:
    """View job logs"""
    job: str = field(default="", alias="-j", help="Job name (optional)")
    no_follow: bool = field(default=False, alias="-n", help="Don't follow logs")


@dataclass
class StatusConfig:
    """Check job status"""
    job: str = field(default="", alias="-j", help="Job name (optional)")
    watch: bool = field(default=False, alias="-w", help="Watch for changes")
    output: str = field(default="table", alias="-o", help="Output format: table, yaml, json")


@dataclass
class DeleteConfig:
    """Delete job and associated resources"""
    job: str = field(default="", help="Job name (optional - if not provided, shows all CW resources for selection)")


@dataclass
class ListConfig:
    """List all axolotl jobs"""
    pass


@dataclass
class JobsConfig:
    """List all jobs in the cluster"""
    namespace: str = field(default="default", alias="-n", help="Kubernetes namespace")
    all_namespaces: bool = field(default=False, alias="-A", help="List jobs across all namespaces")


@dataclass
class PodsConfig:
    """List all pods in the cluster"""
    namespace: str = field(default="default", alias="-n", help="Kubernetes namespace")
    all_namespaces: bool = field(default=False, alias="-A", help="List pods across all namespaces")
    show_resources: bool = field(default=False, alias="-r", help="Show resource requests/limits")
    watch: bool = field(default=False, alias="-w", help="Watch for changes (live updates)")


@dataclass
class InfoConfig:
    """Show cluster information and capabilities"""
    nodes: bool = field(default=False, alias="-n", help="Show detailed node information")


@dataclass
class ResourcesConfig:
    """Show available cluster resources"""
    pass


@dataclass
class GpuConfig:
    """Watch GPU usage on training nodes"""
    job: str = field(default="", help="Job name (optional - will prompt if not provided)")
    interval: int = field(default=2, alias="-i", help="Update interval in seconds (default: 2)")