#!/usr/bin/env python3
"""Deployment strategy abstractions for different training types."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import time
import yaml
from pathlib import Path

from .framework import BaseTrainingFramework, TrainingJob, DeploymentResult, TrainingType
from ..utils import console, run_kubectl_command, create_configmap_yaml


class BaseDeploymentStrategy(ABC):
    """Abstract base class for deployment strategies."""
    
    @abstractmethod
    def deploy(self, framework: BaseTrainingFramework, job: TrainingJob) -> DeploymentResult:
        """Deploy a training job using this strategy."""
        pass
    
    def create_and_deploy_configmap(self, framework: BaseTrainingFramework, job: TrainingJob) -> bool:
        """Create and deploy ConfigMap for the job."""
        configmap_name = framework.get_configmap_name(job.training_type)
        clean_config = framework.prepare_config(job.config_data)
        
        console.print("📝 Creating ConfigMap...", style="blue")
        configmap_yaml = create_configmap_yaml(clean_config, configmap_name)
        
        return run_kubectl_command(configmap_yaml)
    
    def deploy_yaml_template(self, template_path: Path, context: Dict[str, Any]) -> bool:
        """Deploy a single YAML template with resource injection."""
        if not template_path.exists():
            console.print(f"❌ Error: {template_path} not found", style="red")
            return False
        
        try:
            from .templating import render_template
            rendered_yaml = render_template(template_path, context)
            return run_kubectl_command(rendered_yaml)
        except Exception as e:
            console.print(f"❌ Error processing template {template_path}: {e}", style="red")
            return False


class SFTDeploymentStrategy(BaseDeploymentStrategy):
    """Deployment strategy for SFT (Supervised Fine-Tuning) jobs."""
    
    def deploy(self, framework: BaseTrainingFramework, job: TrainingJob) -> DeploymentResult:
        """Deploy SFT training job."""
        # Validate configuration
        if not framework.validate_config(job.config_data, job.training_type):
            return DeploymentResult(
                success=False,
                error_message="Configuration validation failed"
            )
        
        # Create ConfigMap
        if not self.create_and_deploy_configmap(framework, job):
            return DeploymentResult(
                success=False,
                error_message="Failed to create ConfigMap"
            )
        
        # Get template and deploy job
        templates = framework.get_yaml_templates(job.training_type)
        if not templates:
            return DeploymentResult(
                success=False,
                error_message="No YAML templates found for SFT"
            )
        
        context = framework.get_template_context(job)
        job_template = templates[0]  # SFT should have only one template
        
        console.print("🚀 Creating Job...", style="blue")
        if not self.deploy_yaml_template(job_template, context):
            console.print("❌ Job creation failed, cleaning up ConfigMap...", style="yellow")
            # TODO: Implement cleanup
            return DeploymentResult(
                success=False,
                error_message="Failed to create Job"
            )
        
        job_name = framework.get_job_name(job.training_type)
        console.print("🎉 SFT job submitted successfully!", style="green bold")
        
        return DeploymentResult(
            success=True,
            job_name=job_name
        )


class GRPODeploymentStrategy(BaseDeploymentStrategy):
    """Deployment strategy for GRPO (multi-service) jobs."""
    
    def deploy(self, framework: BaseTrainingFramework, job: TrainingJob) -> DeploymentResult:
        """Deploy GRPO training job with services."""
        # Validate configuration (only for training, not services-only)
        if not job.services_only and not framework.validate_config(job.config_data, job.training_type):
            return DeploymentResult(
                success=False,
                error_message="Configuration validation failed"
            )
        
        # Create ConfigMap
        if not self.create_and_deploy_configmap(framework, job):
            return DeploymentResult(
                success=False,
                error_message="Failed to create ConfigMap"
            )
        
        # Get templates
        templates = framework.get_yaml_templates(job.training_type)
        if len(templates) < 2:
            return DeploymentResult(
                success=False,
                error_message="GRPO requires multiple service templates"
            )
        
        context = framework.get_template_context(job)
        
        # Deploy services in order: VLLM, Rewards, Training (skip training if services_only)
        service_names = []
        templates_to_deploy = templates[:-1] if job.services_only else templates
        service_labels = ["VLLM Server", "Rewards Server", "Training Job"]
        
        for i, template in enumerate(templates_to_deploy):
            service_name = service_labels[i] if i < len(service_labels) else f"Service {i+1}"
            console.print(f"🚀 Deploying {service_name}...", style="blue")
            
            if not self.deploy_yaml_template(template, context):
                return DeploymentResult(
                    success=False,
                    error_message=f"Failed to deploy {service_name}"
                )
            
            console.print(f"✅ {service_name} deployed successfully", style="green")
            service_names.append(service_name)
            
            # Add delay between services for proper startup order
            if i < len(templates_to_deploy) - 1:
                console.print("⏳ Waiting for service to initialize...", style="yellow")
                time.sleep(10)
        
        if job.services_only:
            console.print("🎉 GRPO services deployed successfully!", style="green bold")
            return DeploymentResult(
                success=True,
                services=service_names
            )
        else:
            job_name = framework.get_job_name(job.training_type)
            console.print("🎉 GRPO training started successfully!", style="green bold")
            return DeploymentResult(
                success=True,
                job_name=job_name,
                services=service_names
            )


# Strategy registry
_strategies: Dict[TrainingType, BaseDeploymentStrategy] = {
    TrainingType.SFT: SFTDeploymentStrategy(),
    TrainingType.GRPO: GRPODeploymentStrategy()
}


def get_deployment_strategy(training_type: TrainingType) -> BaseDeploymentStrategy:
    """Get deployment strategy for a training type."""
    strategy = _strategies.get(training_type)
    if strategy is None:
        raise ValueError(f"No deployment strategy found for training type: {training_type}")
    return strategy


def register_deployment_strategy(training_type: TrainingType, strategy: BaseDeploymentStrategy):
    """Register a custom deployment strategy."""
    _strategies[training_type] = strategy