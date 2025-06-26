#!/usr/bin/env python3
"""Integration tests to verify the new architecture works end-to-end."""

import tempfile
import yaml
from pathlib import Path
import pytest

from cw_cli.core import get_framework, get_config_manager, TrainingType, TrainingJob


class TestArchitectureIntegration:
    """Test that the refactored architecture works as expected."""

    def test_framework_registry(self):
        """Test framework registry functionality."""
        # Test getting frameworks
        axolotl = get_framework("axolotl")
        verifiers = get_framework("verifiers")
        
        assert axolotl is not None, "Axolotl framework should be registered"
        assert verifiers is not None, "Verifiers framework should be registered"
        assert axolotl.name == "axolotl", "Axolotl framework name should be correct"
        assert verifiers.name == "verifiers", "Verifiers framework name should be correct"

    def test_configuration_manager(self):
        """Test configuration manager functionality."""
        config_manager = get_config_manager()
        
        # Test config validation
        test_config = {
            "base_model": "test/model",
            "learning_rate": 0.001,
            "gpu": 8,
            "memory": "1000Gi"
        }
        
        validated_config = config_manager.validate_config(test_config)
        assert validated_config.base_model == "test/model"
        assert validated_config.learning_rate == 0.001
        assert validated_config.gpu == 8

    def test_override_merging(self):
        """Test configuration override merging."""
        config_manager = get_config_manager()
        
        test_config = {
            "base_model": "test/model",
            "learning_rate": 0.001,
            "gpu": 8
        }
        
        # Test override merging
        overrides = {"learning_rate": 0.002, "gpu": 4}
        merged_config = config_manager.merge_overrides(test_config, overrides)
        assert merged_config["learning_rate"] == 0.002
        assert merged_config["gpu"] == 4
        assert merged_config["base_model"] == "test/model"  # unchanged

    def test_training_job_creation(self):
        """Test training job creation."""
        # Create a temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config_data = {
                "base_model": "test/model",
                "learning_rate": 0.001,
                "gpu": 4
            }
            yaml.dump(config_data, f)
            temp_config_path = Path(f.name)
        
        try:
            # Create training job
            job = TrainingJob(
                name="test-job",
                config_path=temp_config_path,
                training_type=TrainingType.SFT,
                config_data=config_data,
                pull_latest=False,
                services_only=False
            )
            
            assert job.name == "test-job"
            assert job.training_type == TrainingType.SFT
            assert job.config_data["base_model"] == "test/model"
        
        finally:
            # Cleanup
            temp_config_path.unlink()

    def test_framework_methods(self):
        """Test framework method implementations."""
        axolotl = get_framework("axolotl")
        
        # Test job naming
        sft_job_name = axolotl.get_job_name(TrainingType.SFT)
        grpo_job_name = axolotl.get_job_name(TrainingType.GRPO)
        
        assert sft_job_name == "cw-axolotl-train-sft"
        assert grpo_job_name == "cw-axolotl-train-grpo"
        
        # Test configmap naming
        sft_configmap = axolotl.get_configmap_name(TrainingType.SFT)
        grpo_configmap = axolotl.get_configmap_name(TrainingType.GRPO)
        
        assert sft_configmap == "cw-axolotl-train-sft-config"
        assert grpo_configmap == "cw-axolotl-train-grpo-config"

    def test_config_preparation(self):
        """Test framework config preparation."""
        axolotl = get_framework("axolotl")
        
        test_config = {
            "base_model": "test/model",
            "gpu": 8,
            "image": "test:latest",
            "learning_rate": 0.001,
            "memory": "1000Gi"
        }
        
        clean_config = axolotl.prepare_config(test_config)
        
        # Cluster fields should be removed
        assert "gpu" not in clean_config
        assert "image" not in clean_config
        assert "memory" not in clean_config
        
        # Training fields should remain
        assert clean_config["base_model"] == "test/model"
        assert clean_config["learning_rate"] == 0.001

    def test_yaml_template_paths(self):
        """Test that YAML template paths exist."""
        axolotl = get_framework("axolotl")
        verifiers = get_framework("verifiers")
        
        # Test Axolotl paths
        sft_templates = axolotl.get_yaml_templates(TrainingType.SFT)
        grpo_templates = axolotl.get_yaml_templates(TrainingType.GRPO)
        
        assert len(sft_templates) == 1
        assert len(grpo_templates) == 3
        
        # Check that files exist
        for template_path in sft_templates + grpo_templates:
            assert template_path.exists(), f"Template file {template_path} should exist"
        
        # Test Verifiers paths
        verifiers_templates = verifiers.get_yaml_templates(TrainingType.GRPO)
        assert len(verifiers_templates) == 3
        
        for template_path in verifiers_templates:
            assert template_path.exists(), f"Template file {template_path} should exist"

    def test_framework_validation(self):
        """Test framework-specific validation."""
        axolotl = get_framework("axolotl")
        
        # Valid SFT config
        sft_config = {"base_model": "test/model"}
        assert axolotl.validate_config(sft_config, TrainingType.SFT) is True
        
        # Valid GRPO config
        grpo_config = {"base_model": "test/model", "rl": "grpo"}
        assert axolotl.validate_config(grpo_config, TrainingType.GRPO) is True
        
        # Invalid GRPO config (missing rl: grpo)
        invalid_grpo_config = {"base_model": "test/model"}
        assert axolotl.validate_config(invalid_grpo_config, TrainingType.GRPO) is False

    def test_verifiers_framework(self):
        """Test Verifiers framework specifics."""
        verifiers = get_framework("verifiers")
        
        # Test basic properties
        assert verifiers.name == "verifiers"
        assert verifiers.get_default_image() == 'ghcr.io/tcapelle/triton_eval:1906'
        
        # Test job naming
        job_name = verifiers.get_job_name(TrainingType.GRPO)
        assert job_name == "cw-verifiers-train-grpo"
        
        # Test configmap naming
        configmap_name = verifiers.get_configmap_name(TrainingType.GRPO)
        assert configmap_name == "cw-verifiers-train-grpo-config"

    def test_training_types(self):
        """Test TrainingType enum."""
        assert TrainingType.SFT.value == "sft"
        assert TrainingType.GRPO.value == "grpo"
        
        # Test enum iteration
        types = list(TrainingType)
        assert len(types) == 2
        assert TrainingType.SFT in types
        assert TrainingType.GRPO in types


@pytest.mark.integration
class TestConfigurationValidation:
    """Test configuration validation with various scenarios."""

    def test_valid_configurations(self):
        """Test that valid configurations pass validation."""
        config_manager = get_config_manager()
        
        valid_configs = [
            {
                "base_model": "microsoft/DialoGPT-medium",
                "learning_rate": 2e-5,
                "num_epochs": 3,
                "gpu": 4
            },
            {
                "base_model": "gpt2",
                "tokenizer_type": "GPT2Tokenizer",
                "datasets": [{"path": "dataset1", "type": "text"}],
                "resources": {
                    "limits": {"nvidia.com/gpu": "8", "memory": "1000Gi"},
                    "requests": {"nvidia.com/gpu": "8", "memory": "1000Gi"}
                }
            }
        ]
        
        for config in valid_configs:
            validated = config_manager.validate_config(config)
            assert validated.base_model == config["base_model"]

    def test_resource_extraction(self):
        """Test resource requirements extraction."""
        config_manager = get_config_manager()
        
        # Test individual resource fields
        config_with_individual = {
            "base_model": "test/model",
            "gpu": 4,
            "cpu": "32",
            "memory": "500Gi"
        }
        
        resources = config_manager.extract_resource_requirements(config_with_individual)
        assert resources is not None
        assert resources["limits"]["nvidia.com/gpu"] == "4"
        assert resources["limits"]["cpu"] == "32"
        assert resources["limits"]["memory"] == "500Gi"
        
        # Test explicit resources block
        config_with_resources = {
            "base_model": "test/model",
            "resources": {
                "limits": {"nvidia.com/gpu": "8"},
                "requests": {"nvidia.com/gpu": "8"}
            }
        }
        
        resources = config_manager.extract_resource_requirements(config_with_resources)
        assert resources["limits"]["nvidia.com/gpu"] == "8"
        assert resources["requests"]["nvidia.com/gpu"] == "8"