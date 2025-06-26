#!/usr/bin/env python3
"""Unit tests for configuration management."""

import pytest
import tempfile
import yaml
from pathlib import Path
from pydantic import ValidationError

from cw_cli.core.configuration import (
    ConfigurationManager,
    TrainingConfig,
    ResourceRequirements,
    TrainingFramework,
    get_config_manager
)


class TestResourceRequirements:
    """Test ResourceRequirements model."""

    def test_valid_resource_requirements(self):
        """Test valid resource requirements."""
        resources = ResourceRequirements(
            limits={"nvidia.com/gpu": "8", "cpu": "32", "memory": "1000Gi"},
            requests={"nvidia.com/gpu": "8", "cpu": "32", "memory": "1000Gi"}
        )
        
        assert resources.limits["nvidia.com/gpu"] == "8"
        assert resources.requests["cpu"] == "32"

    def test_empty_resource_requirements(self):
        """Test empty resource requirements."""
        resources = ResourceRequirements()
        assert resources.limits == {}
        assert resources.requests == {}

    def test_invalid_gpu_count(self):
        """Test invalid GPU count validation."""
        with pytest.raises(ValidationError, match="Invalid GPU count"):
            ResourceRequirements(
                limits={"nvidia.com/gpu": "invalid"}
            )

    def test_non_dict_resources(self):
        """Test non-dictionary resources validation."""
        with pytest.raises(ValidationError, match="Input should be a valid dictionary"):
            ResourceRequirements(limits="not-a-dict")


class TestTrainingConfig:
    """Test TrainingConfig model."""

    def test_minimal_config(self):
        """Test minimal valid configuration."""
        config = TrainingConfig(base_model="test/model")
        assert config.base_model == "test/model"
        assert config.learning_rate is None
        assert config.gpu is None

    def test_full_config(self):
        """Test full configuration with all fields."""
        config_data = {
            "base_model": "microsoft/DialoGPT-medium",
            "model_type": "GPT2LMHeadModel",
            "tokenizer_type": "GPT2Tokenizer",
            "datasets": [{"path": "dataset1", "type": "text"}],
            "learning_rate": 2e-5,
            "lr_scheduler": "cosine",
            "num_epochs": 3,
            "micro_batch_size": 4,
            "gradient_accumulation_steps": 8,
            "output_dir": "/model-checkpoints/test",
            "image": "test:latest",
            "gpu": 8,
            "cpu": "32",
            "memory": "1000Gi",
            "rl": "grpo"
        }
        
        config = TrainingConfig(**config_data)
        
        assert config.base_model == "microsoft/DialoGPT-medium"
        assert config.learning_rate == 2e-5
        assert config.num_epochs == 3
        assert config.gpu == 8
        assert config.rl == "grpo"

    def test_extra_fields_allowed(self):
        """Test that extra fields are allowed."""
        config = TrainingConfig(
            base_model="test/model",
            custom_field="custom_value",
            another_field=123
        )
        
        assert config.base_model == "test/model"
        # Extra fields should be accessible
        assert hasattr(config, 'custom_field')

    def test_resources_field(self):
        """Test resources field with ResourceRequirements."""
        resources = ResourceRequirements(
            limits={"nvidia.com/gpu": "4"},
            requests={"nvidia.com/gpu": "4"}
        )
        
        config = TrainingConfig(
            base_model="test/model",
            resources=resources
        )
        
        assert config.resources == resources


class TestConfigurationManager:
    """Test ConfigurationManager functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config_manager = ConfigurationManager()

    def test_load_config_valid_yaml(self):
        """Test loading valid YAML configuration."""
        config_data = {
            "base_model": "test/model",
            "learning_rate": 0.001,
            "gpu": 4
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            loaded_config = self.config_manager.load_config(config_path)
            assert loaded_config == config_data
        finally:
            config_path.unlink()

    def test_load_config_file_not_found(self):
        """Test loading non-existent configuration file."""
        with pytest.raises(FileNotFoundError):
            self.config_manager.load_config(Path("/nonexistent/config.yaml"))

    def test_load_config_invalid_yaml(self):
        """Test loading invalid YAML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            config_path = Path(f.name)
        
        try:
            with pytest.raises(ValueError, match="Invalid YAML"):
                self.config_manager.load_config(config_path)
        finally:
            config_path.unlink()

    def test_validate_config_valid(self):
        """Test validating valid configuration."""
        config_data = {
            "base_model": "test/model",
            "learning_rate": 0.001,
            "gpu": 4
        }
        
        validated_config = self.config_manager.validate_config(config_data)
        assert isinstance(validated_config, TrainingConfig)
        assert validated_config.base_model == "test/model"
        assert validated_config.learning_rate == 0.001
        assert validated_config.gpu == 4

    def test_validate_config_invalid(self):
        """Test validating invalid configuration."""
        # Missing required base_model field
        config_data = {
            "learning_rate": 0.001
        }
        
        with pytest.raises(ValueError, match="Configuration validation failed"):
            self.config_manager.validate_config(config_data)

    def test_merge_overrides_basic(self):
        """Test basic override merging."""
        config_data = {
            "base_model": "test/model",
            "learning_rate": 0.001,
            "gpu": 8
        }
        
        overrides = {
            "learning_rate": 0.002,
            "gpu": 4,
            "new_field": "new_value"
        }
        
        merged = self.config_manager.merge_overrides(config_data, overrides)
        
        assert merged["base_model"] == "test/model"  # unchanged
        assert merged["learning_rate"] == 0.002     # overridden
        assert merged["gpu"] == 4                   # overridden
        assert merged["new_field"] == "new_value"   # added

    def test_merge_overrides_type_conversion(self):
        """Test type conversion during override merging."""
        config_data = {"base_model": "test/model"}
        
        overrides = {
            "gpu": "8",           # string -> int
            "num_epochs": "3",    # string -> int
            "learning_rate": "0.001"  # string -> float
        }
        
        merged = self.config_manager.merge_overrides(config_data, overrides)
        
        assert merged["gpu"] == 8
        assert merged["num_epochs"] == 3
        assert merged["learning_rate"] == 0.001

    def test_merge_overrides_invalid_conversion(self):
        """Test invalid type conversion in overrides."""
        config_data = {"base_model": "test/model"}
        
        overrides = {
            "gpu": "invalid_number"
        }
        
        merged = self.config_manager.merge_overrides(config_data, overrides)
        
        # Should keep as string if conversion fails
        assert merged["gpu"] == "invalid_number"

    def test_prepare_for_deployment(self):
        """Test preparing config for deployment."""
        config_data = {
            "base_model": "test/model",
            "learning_rate": 0.001,
            "gpu": 8,
            "cpu": "32",
            "memory": "1000Gi",
            "image": "test:latest",
            "resources": {"limits": {}},
            "training_field": "keep_this"
        }
        
        deployment_config = self.config_manager.prepare_for_deployment(config_data)
        
        # Training fields should remain
        assert deployment_config["base_model"] == "test/model"
        assert deployment_config["learning_rate"] == 0.001
        assert deployment_config["training_field"] == "keep_this"
        
        # Cluster fields should be removed
        assert "gpu" not in deployment_config
        assert "cpu" not in deployment_config
        assert "memory" not in deployment_config
        assert "image" not in deployment_config
        assert "resources" not in deployment_config

    def test_extract_resource_requirements_individual(self):
        """Test extracting resources from individual fields."""
        config_data = {
            "base_model": "test/model",
            "gpu": 4,
            "cpu": "32",
            "memory": "500Gi"
        }
        
        resources = self.config_manager.extract_resource_requirements(config_data)
        
        assert resources is not None
        assert resources["limits"]["nvidia.com/gpu"] == "4"
        assert resources["limits"]["cpu"] == "32"
        assert resources["limits"]["memory"] == "500Gi"
        assert resources["requests"]["nvidia.com/gpu"] == "4"
        assert resources["requests"]["cpu"] == "32"
        assert resources["requests"]["memory"] == "500Gi"

    def test_extract_resource_requirements_explicit(self):
        """Test extracting explicit resources block."""
        config_data = {
            "base_model": "test/model",
            "resources": {
                "limits": {"nvidia.com/gpu": "8", "memory": "1000Gi"},
                "requests": {"nvidia.com/gpu": "8", "memory": "1000Gi"}
            }
        }
        
        resources = self.config_manager.extract_resource_requirements(config_data)
        
        assert resources == config_data["resources"]

    def test_extract_resource_requirements_none(self):
        """Test extracting resources when none specified."""
        config_data = {
            "base_model": "test/model",
            "learning_rate": 0.001
        }
        
        resources = self.config_manager.extract_resource_requirements(config_data)
        assert resources is None

    def test_validate_framework_requirements_axolotl_grpo(self):
        """Test Axolotl GRPO framework requirements."""
        config_data = {"base_model": "test/model", "rl": "grpo"}
        
        is_valid = self.config_manager.validate_framework_requirements(
            config_data, "axolotl", "grpo"
        )
        assert is_valid is True

    def test_validate_framework_requirements_axolotl_grpo_invalid(self):
        """Test invalid Axolotl GRPO framework requirements."""
        config_data = {"base_model": "test/model"}  # Missing rl: grpo
        
        is_valid = self.config_manager.validate_framework_requirements(
            config_data, "axolotl", "grpo"
        )
        assert is_valid is False

    def test_validate_framework_requirements_other(self):
        """Test other framework requirements (should pass)."""
        config_data = {"base_model": "test/model"}
        
        is_valid = self.config_manager.validate_framework_requirements(
            config_data, "other", "sft"
        )
        assert is_valid is True

    def test_get_config_summary(self):
        """Test getting configuration summary."""
        config_data = {
            "base_model": "test/model",
            "learning_rate": 0.001,
            "num_epochs": 3,
            "micro_batch_size": 4,
            "image": "test:latest",
            "gpu": 8,
            "cpu": "32",
            "memory": "1000Gi",
            "rl": "grpo"
        }
        
        summary = self.config_manager.get_config_summary(config_data)
        
        assert summary["model"] == "test/model"
        assert summary["training_type"] == "GRPO"
        assert summary["learning_rate"] == 0.001
        assert summary["epochs"] == 3
        assert summary["batch_size"] == 4
        assert summary["image"] == "test:latest"
        assert summary["resources"]["gpu"] == 8
        assert summary["resources"]["cpu"] == "32"
        assert summary["resources"]["memory"] == "1000Gi"

    def test_get_config_summary_sft(self):
        """Test config summary for SFT (no rl field)."""
        config_data = {
            "base_model": "test/model",
            "learning_rate": 0.001
        }
        
        summary = self.config_manager.get_config_summary(config_data)
        
        assert summary["model"] == "test/model"
        assert summary["training_type"] == "SFT"
        assert summary["learning_rate"] == 0.001

    def test_get_config_summary_filters_none(self):
        """Test that config summary filters out None values."""
        config_data = {
            "base_model": "test/model"
            # Most fields missing (will be None)
        }
        
        summary = self.config_manager.get_config_summary(config_data)
        
        assert summary["model"] == "test/model"
        assert summary["training_type"] == "SFT"
        assert "learning_rate" not in summary  # None values filtered out
        assert "epochs" not in summary
        assert summary["resources"] == {}  # Empty dict, all None values filtered


class TestGlobalConfigManager:
    """Test global configuration manager."""

    def test_get_config_manager_singleton(self):
        """Test that get_config_manager returns the same instance."""
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        assert manager1 is manager2

    def test_get_config_manager_type(self):
        """Test that get_config_manager returns ConfigurationManager."""
        manager = get_config_manager()
        assert isinstance(manager, ConfigurationManager)