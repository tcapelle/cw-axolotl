#!/usr/bin/env python3
"""Abstract base classes for training frameworks."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class TrainingType(Enum):
    """Supported training types."""
    SFT = "sft"
    GRPO = "grpo"


@dataclass
class TrainingJob:
    """Represents a training job configuration."""
    name: str
    config_path: Path
    training_type: TrainingType
    config_data: Dict[str, Any]
    pull_latest: bool = False
    services_only: bool = False


@dataclass
class DeploymentResult:
    """Result of a deployment operation."""
    success: bool
    job_name: Optional[str] = None
    services: List[str] = None
    error_message: Optional[str] = None


class BaseTrainingFramework(ABC):
    """Abstract base class for training frameworks."""
    
    def __init__(self, name: str, kubeconfig_dir: Path):
        self.name = name
        self.kubeconfig_dir = kubeconfig_dir
    
    @abstractmethod
    def validate_config(self, config_data: Dict[str, Any], training_type: TrainingType) -> bool:
        """Validate framework-specific configuration."""
        pass
    
    @abstractmethod
    def prepare_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare and clean config for training."""
        pass
    
    @abstractmethod
    def get_configmap_name(self, training_type: TrainingType) -> str:
        """Get ConfigMap name for this framework and training type."""
        pass
    
    @abstractmethod
    def get_job_name(self, training_type: TrainingType) -> str:
        """Get Job name for this framework and training type."""
        pass
    
    @abstractmethod
    def get_yaml_templates(self, training_type: TrainingType) -> List[Path]:
        """Get list of Kubernetes YAML template paths for deployment."""
        pass
    
    @abstractmethod
    def get_default_image(self) -> str:
        """Get default container image for this framework."""
        pass
    
    def deploy(self, job: TrainingJob) -> DeploymentResult:
        """Deploy training job for this framework."""
        from .deployment import get_deployment_strategy
        
        strategy = get_deployment_strategy(job.training_type)
        return strategy.deploy(self, job)
    
    def get_template_context(self, job: TrainingJob) -> Dict[str, Any]:
        """Get template context for YAML generation."""
        return {
            'framework': self.name,
            'training_type': job.training_type.value,
            'job_name': self.get_job_name(job.training_type),
            'configmap_name': self.get_configmap_name(job.training_type),
            'config_data': job.config_data,
            'pull_latest': job.pull_latest,
            'services_only': job.services_only,
            'image': job.config_data.get('image', self.get_default_image())
        }


class AxolotlFramework(BaseTrainingFramework):
    """Axolotl training framework implementation."""
    
    def __init__(self, kubeconfig_dir: Path):
        super().__init__("axolotl", kubeconfig_dir)
    
    def validate_config(self, config_data: Dict[str, Any], training_type: TrainingType) -> bool:
        """Validate Axolotl-specific configuration."""
        if training_type == TrainingType.GRPO:
            return config_data.get('rl') == 'grpo'
        return True
    
    def prepare_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove Axolotl-specific cluster fields."""
        clean_config = config_data.copy()
        cluster_fields = ['image', 'gpu', 'cpu', 'memory', 'resources']
        for field in cluster_fields:
            clean_config.pop(field, None)
        return clean_config
    
    def get_configmap_name(self, training_type: TrainingType) -> str:
        """Get ConfigMap name for Axolotl."""
        if training_type == TrainingType.SFT:
            return "cw-axolotl-train-sft-config"
        elif training_type == TrainingType.GRPO:
            return "cw-axolotl-train-grpo-config"
        else:
            raise ValueError(f"Unsupported training type: {training_type}")
    
    def get_job_name(self, training_type: TrainingType) -> str:
        """Get Job name for Axolotl."""
        if training_type == TrainingType.SFT:
            return "cw-axolotl-train-sft"
        elif training_type == TrainingType.GRPO:
            return "cw-axolotl-train-grpo"
        else:
            raise ValueError(f"Unsupported training type: {training_type}")
    
    def get_yaml_templates(self, training_type: TrainingType) -> List[Path]:
        """Get YAML templates for Axolotl."""
        if training_type == TrainingType.SFT:
            return [self.kubeconfig_dir / "axolotl" / "sft_job.yaml"]
        elif training_type == TrainingType.GRPO:
            grpo_dir = self.kubeconfig_dir / "axolotl" / "grpo"
            return [
                grpo_dir / "vllm-deployment.yaml",
                grpo_dir / "rewards-deployment.yaml", 
                grpo_dir / "training-job.yaml"
            ]
        else:
            raise ValueError(f"Unsupported training type: {training_type}")
    
    def get_default_image(self) -> str:
        """Get default image for Axolotl."""
        return 'ghcr.io/tcapelle/triton_eval:1906'


class VerifiersFramework(BaseTrainingFramework):
    """Verifiers training framework implementation."""
    
    def __init__(self, kubeconfig_dir: Path):
        super().__init__("verifiers", kubeconfig_dir)
    
    def validate_config(self, config_data: Dict[str, Any], training_type: TrainingType) -> bool:
        """Validate Verifiers-specific configuration."""
        # Verifiers doesn't require special validation currently
        return True
    
    def prepare_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove Verifiers-specific cluster fields."""
        clean_config = config_data.copy()
        cluster_fields = ['image', 'gpu', 'cpu', 'memory', 'resources']
        for field in cluster_fields:
            clean_config.pop(field, None)
        return clean_config
    
    def get_configmap_name(self, training_type: TrainingType) -> str:
        """Get ConfigMap name for Verifiers."""
        if training_type == TrainingType.GRPO:
            return "cw-verifiers-train-grpo-config"
        else:
            raise ValueError(f"Unsupported training type: {training_type}")
    
    def get_job_name(self, training_type: TrainingType) -> str:
        """Get Job name for Verifiers."""
        if training_type == TrainingType.GRPO:
            return "cw-verifiers-train-grpo"
        else:
            raise ValueError(f"Unsupported training type: {training_type}")
    
    def get_yaml_templates(self, training_type: TrainingType) -> List[Path]:
        """Get YAML templates for Verifiers."""
        if training_type == TrainingType.GRPO:
            return [
                self.kubeconfig_dir / "verifiers" / "vllm-deployment.yaml",
                self.kubeconfig_dir / "verifiers" / "rewards-deployment.yaml",
                self.kubeconfig_dir / "verifiers" / "training-job.yaml"
            ]
        else:
            raise ValueError(f"Unsupported training type: {training_type}")
    
    def get_default_image(self) -> str:
        """Get default image for Verifiers."""
        return 'ghcr.io/tcapelle/triton_eval:1906'