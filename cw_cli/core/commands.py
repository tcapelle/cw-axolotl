#!/usr/bin/env python3
"""Refactored command implementations using new abstractions."""

import sys
from typing import Dict, Any, List
from pathlib import Path

from .framework import TrainingJob, TrainingType
from .registry import get_framework
from .configuration import get_config_manager
from ..utils import console
from ..commands import parse_overrides, _follow_job_logs


class TrainingCommandHandler:
    """Handles training command operations."""
    
    def __init__(self):
        self.config_manager = get_config_manager()
    
    def handle_training_command(self, framework_name: str, training_type: TrainingType,
                               config_path: str, pull_latest: bool = False, 
                               services_only: bool = False) -> int:
        """Handle training command with new abstractions."""
        try:
            # Validate inputs
            config_file_path = Path(config_path)
            if not config_file_path.exists():
                console.print(f"❌ Error: Config file {config_file_path} not found", style="red")
                return 1
            
            # Get framework
            framework = get_framework(framework_name)
            if framework is None:
                console.print(f"❌ Error: Unsupported framework '{framework_name}'", style="red")
                return 1
            
            # Load and validate configuration
            try:
                config_data = self.config_manager.load_config(config_file_path)
                validated_config = self.config_manager.validate_config(config_data, framework_name)
            except Exception as e:
                console.print(f"❌ Error loading configuration: {e}", style="red")
                return 1
            
            # Parse command line overrides
            overrides = self._parse_command_overrides(config_file_path)
            if overrides:
                config_data = self.config_manager.merge_overrides(config_data, overrides)
                # Re-validate after overrides
                try:
                    validated_config = self.config_manager.validate_config(config_data, framework_name)
                except Exception as e:
                    console.print(f"❌ Error validating configuration with overrides: {e}", style="red")
                    return 1
            
            # Create training job
            job = TrainingJob(
                name=framework.get_job_name(training_type),
                config_path=config_file_path,
                training_type=training_type,
                config_data=config_data,
                pull_latest=pull_latest,
                services_only=services_only
            )
            
            # Deploy the job
            result = framework.deploy(job)
            
            if not result.success:
                console.print(f"❌ Deployment failed: {result.error_message}", style="red")
                return 1
            
            # Show success message and follow logs if appropriate
            if services_only:
                console.print("💡 Check services: [cyan]cw pods[/]")
            else:
                self._follow_job_logs_if_requested(result.job_name)
            
            return 0
            
        except Exception as e:
            console.print(f"❌ Unexpected error: {e}", style="red")
            return 1
    
    def _parse_command_overrides(self, config_path: Path) -> Dict[str, Any]:
        """Parse command line overrides from sys.argv."""
        try:
            # Find config file position in argv
            config_idx = sys.argv.index(str(config_path))
            override_args = sys.argv[config_idx + 1:]
        except ValueError:
            try:
                config_idx = sys.argv.index(config_path.name)
                override_args = sys.argv[config_idx + 1:]
            except ValueError:
                override_args = []
        
        overrides = parse_overrides(override_args)
        
        # Display overrides
        for key, value in overrides.items():
            console.print(f"🔧 Override: {key} = {value}", style="yellow")
        
        return overrides
    
    def _follow_job_logs_if_requested(self, job_name: str):
        """Follow job logs automatically after deployment."""
        if not job_name:
            return
        
        console.print(f"\n🔄 Following logs for {job_name}... (Press Ctrl+C to stop)")
        
        try:
            _follow_job_logs(job_name)
        except KeyboardInterrupt:
            console.print("\n⏹️ Log following stopped.", style="yellow")
            console.print(f"💡 To resume monitoring: [cyan]cw logs -j {job_name}[/]")
        except Exception as e:
            console.print(f"❌ Could not follow logs: {e}", style="red")
            console.print(f"💡 Try manually: [cyan]cw logs -j {job_name}[/]")


class RestartCommandHandler:
    """Handles service restart operations."""
    
    def handle_grpo_restart(self, framework_name: str, service_name: str) -> int:
        """Handle GRPO service restart."""
        try:
            # Validate service name
            if service_name.lower() not in ['vllm', 'rewards']:
                console.print(f"❌ Error: Service must be 'vllm' or 'rewards', got '{service_name}'", style="red")
                return 1
            
            # Get framework for service naming
            framework = get_framework(framework_name)
            if framework is None:
                console.print(f"❌ Error: Unsupported framework '{framework_name}'", style="red")
                return 1
            
            # Use existing restart logic
            from ..commands import grpo_restart_command
            return grpo_restart_command(service_name)
            
        except Exception as e:
            console.print(f"❌ Error restarting service: {e}", style="red")
            return 1


# Command factory functions for backward compatibility
def create_training_handler() -> TrainingCommandHandler:
    """Create a training command handler."""
    return TrainingCommandHandler()


def create_restart_handler() -> RestartCommandHandler:
    """Create a restart command handler."""
    return RestartCommandHandler()


# Simplified command functions that use the new handlers
def train_sft_command(framework_name: str, config_path: str, pull_latest: bool = False) -> int:
    """Train SFT model using new abstractions."""
    handler = create_training_handler()
    return handler.handle_training_command(
        framework_name=framework_name,
        training_type=TrainingType.SFT,
        config_path=config_path,
        pull_latest=pull_latest
    )


def train_grpo_command(framework_name: str, config_path: str, pull_latest: bool = False, 
                      services_only: bool = False) -> int:
    """Train GRPO model using new abstractions."""
    handler = create_training_handler()
    return handler.handle_training_command(
        framework_name=framework_name,
        training_type=TrainingType.GRPO,
        config_path=config_path,
        pull_latest=pull_latest,
        services_only=services_only
    )


def restart_grpo_service_command(framework_name: str, service_name: str) -> int:
    """Restart GRPO service using new abstractions."""
    handler = create_restart_handler()
    return handler.handle_grpo_restart(framework_name, service_name)