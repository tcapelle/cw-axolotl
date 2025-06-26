#!/usr/bin/env python3
"""Centralized configuration management with validation."""

import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path
from pydantic import BaseModel, ValidationError, Field, validator
from enum import Enum


class TrainingFramework(str, Enum):
    """Supported training frameworks."""
    AXOLOTL = "axolotl"
    VERIFIERS = "verifiers"


class ResourceRequirements(BaseModel):
    """Kubernetes resource requirements."""
    limits: Dict[str, str] = Field(default_factory=dict)
    requests: Dict[str, str] = Field(default_factory=dict)
    
    @validator('limits', 'requests')
    def validate_resource_format(cls, v):
        """Validate resource format."""
        if not isinstance(v, dict):
            raise ValueError("Resources must be a dictionary")
        
        # Validate GPU format if present
        gpu_key = 'nvidia.com/gpu'
        if gpu_key in v:
            try:
                int(v[gpu_key])
            except ValueError:
                raise ValueError(f"Invalid GPU count: {v[gpu_key]}")
        
        return v


class TrainingConfig(BaseModel):
    """Base training configuration."""
    # Core training parameters
    base_model: str
    model_type: Optional[str] = None
    tokenizer_type: Optional[str] = None
    
    # Dataset configuration
    datasets: Optional[List[Dict[str, Any]]] = None
    
    # Training parameters
    learning_rate: Optional[float] = None
    lr_scheduler: Optional[str] = None
    num_epochs: Optional[int] = None
    micro_batch_size: Optional[int] = None
    gradient_accumulation_steps: Optional[int] = None
    
    # Output configuration
    output_dir: Optional[str] = None
    
    # Container and resource configuration
    image: Optional[str] = None
    gpu: Optional[int] = None
    cpu: Optional[str] = None
    memory: Optional[str] = None
    resources: Optional[ResourceRequirements] = None
    
    # Framework-specific fields (flexible)
    rl: Optional[str] = None  # For GRPO
    
    class Config:
        extra = "allow"  # Allow additional fields for framework flexibility


class ConfigurationManager:
    """Manages configuration loading, validation, and processing."""
    
    def __init__(self):
        """Initialize configuration manager."""
        self.schema_cache: Dict[str, BaseModel] = {}
    
    def load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file: {e}")
    
    def validate_config(self, config_data: Dict[str, Any], 
                       framework: str = None) -> TrainingConfig:
        """Validate configuration data."""
        try:
            # Create Pydantic model for validation
            validated_config = TrainingConfig(**config_data)
            return validated_config
        except ValidationError as e:
            raise ValueError(f"Configuration validation failed: {e}")
    
    def merge_overrides(self, config_data: Dict[str, Any], 
                       overrides: Dict[str, Any]) -> Dict[str, Any]:
        """Merge command-line overrides into configuration."""
        merged_config = config_data.copy()
        
        for key, value in overrides.items():
            # Type conversion for known numeric fields
            if key in ['gpu', 'num_epochs', 'micro_batch_size', 'gradient_accumulation_steps']:
                try:
                    merged_config[key] = int(value)
                except (ValueError, TypeError):
                    merged_config[key] = value
            elif key in ['learning_rate']:
                try:
                    merged_config[key] = float(value)
                except (ValueError, TypeError):
                    merged_config[key] = value
            else:
                merged_config[key] = value
        
        return merged_config
    
    def prepare_for_deployment(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare configuration for deployment by removing cluster-specific fields."""
        deployment_config = config_data.copy()
        
        # Remove cluster/infrastructure-specific fields
        cluster_fields = ['image', 'gpu', 'cpu', 'memory', 'resources']
        for field in cluster_fields:
            deployment_config.pop(field, None)
        
        return deployment_config
    
    def extract_resource_requirements(self, config_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract resource requirements from configuration."""
        if 'resources' in config_data:
            return config_data['resources']
        
        # Build resources from individual fields
        resources = {}
        
        if any(key in config_data for key in ['gpu', 'cpu', 'memory']):
            if 'gpu' in config_data:
                resources.setdefault('limits', {})['nvidia.com/gpu'] = str(config_data['gpu'])
                resources.setdefault('requests', {})['nvidia.com/gpu'] = str(config_data['gpu'])
            
            if 'cpu' in config_data:
                resources.setdefault('limits', {})['cpu'] = str(config_data['cpu'])
                resources.setdefault('requests', {})['cpu'] = str(config_data['cpu'])
            
            if 'memory' in config_data:
                resources.setdefault('limits', {})['memory'] = str(config_data['memory'])
                resources.setdefault('requests', {})['memory'] = str(config_data['memory'])
        
        return resources if resources else None
    
    def validate_framework_requirements(self, config_data: Dict[str, Any], 
                                      framework: str, training_type: str) -> bool:
        """Validate framework-specific requirements."""
        if framework == "axolotl" and training_type == "grpo":
            # GRPO requires rl: grpo in config
            return config_data.get('rl') == 'grpo'
        
        # Add other framework-specific validations here
        return True
    
    def get_config_summary(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get a summary of configuration for display."""
        summary = {
            'model': config_data.get('base_model', 'Unknown'),
            'training_type': 'GRPO' if config_data.get('rl') == 'grpo' else 'SFT',
            'learning_rate': config_data.get('learning_rate'),
            'epochs': config_data.get('num_epochs'),
            'batch_size': config_data.get('micro_batch_size'),
            'image': config_data.get('image'),
            'resources': {
                'gpu': config_data.get('gpu'),
                'cpu': config_data.get('cpu'),
                'memory': config_data.get('memory')
            }
        }
        
        # Remove None values
        summary = {k: v for k, v in summary.items() if v is not None}
        summary['resources'] = {k: v for k, v in summary['resources'].items() if v is not None}
        
        return summary


# Global configuration manager instance
_config_manager: Optional[ConfigurationManager] = None


def get_config_manager() -> ConfigurationManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager