#!/usr/bin/env python3
"""Unit tests for framework abstractions."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from cw_cli.core.framework import (
    BaseTrainingFramework, 
    AxolotlFramework, 
    VerifiersFramework,
    TrainingType,
    TrainingJob,
    DeploymentResult
)


class TestTrainingType:
    """Test TrainingType enum."""

    def test_enum_values(self):
        """Test enum values are correct."""
        assert TrainingType.SFT.value == "sft"
        assert TrainingType.GRPO.value == "grpo"

    def test_enum_membership(self):
        """Test enum membership."""
        assert TrainingType.SFT in TrainingType
        assert TrainingType.GRPO in TrainingType


class TestTrainingJob:
    """Test TrainingJob dataclass."""

    def test_training_job_creation(self):
        """Test creating a TrainingJob."""
        config_path = Path("/tmp/config.yaml")
        config_data = {"base_model": "test/model"}
        
        job = TrainingJob(
            name="test-job",
            config_path=config_path,
            training_type=TrainingType.SFT,
            config_data=config_data,
            pull_latest=True,
            services_only=False
        )
        
        assert job.name == "test-job"
        assert job.config_path == config_path
        assert job.training_type == TrainingType.SFT
        assert job.config_data == config_data
        assert job.pull_latest is True
        assert job.services_only is False

    def test_training_job_defaults(self):
        """Test TrainingJob default values."""
        job = TrainingJob(
            name="test-job",
            config_path=Path("/tmp/config.yaml"),
            training_type=TrainingType.SFT,
            config_data={}
        )
        
        assert job.pull_latest is False
        assert job.services_only is False


class TestDeploymentResult:
    """Test DeploymentResult dataclass."""

    def test_successful_result(self):
        """Test successful deployment result."""
        result = DeploymentResult(
            success=True,
            job_name="test-job",
            services=["service1", "service2"]
        )
        
        assert result.success is True
        assert result.job_name == "test-job"
        assert result.services == ["service1", "service2"]
        assert result.error_message is None

    def test_failed_result(self):
        """Test failed deployment result."""
        result = DeploymentResult(
            success=False,
            error_message="Deployment failed"
        )
        
        assert result.success is False
        assert result.job_name is None
        assert result.services is None
        assert result.error_message == "Deployment failed"


class TestAxolotlFramework:
    """Test AxolotlFramework implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.kubeconfig_dir = Path("/tmp/kubeconfigs")
        self.framework = AxolotlFramework(self.kubeconfig_dir)

    def test_initialization(self):
        """Test framework initialization."""
        assert self.framework.name == "axolotl"
        assert self.framework.kubeconfig_dir == self.kubeconfig_dir

    def test_validate_config_sft(self):
        """Test SFT config validation."""
        config = {"base_model": "test/model"}
        assert self.framework.validate_config(config, TrainingType.SFT) is True

    def test_validate_config_grpo_valid(self):
        """Test valid GRPO config validation."""
        config = {"base_model": "test/model", "rl": "grpo"}
        assert self.framework.validate_config(config, TrainingType.GRPO) is True

    def test_validate_config_grpo_invalid(self):
        """Test invalid GRPO config validation."""
        config = {"base_model": "test/model"}  # Missing rl: grpo
        assert self.framework.validate_config(config, TrainingType.GRPO) is False

    def test_prepare_config(self):
        """Test config preparation removes cluster fields."""
        config = {
            "base_model": "test/model",
            "learning_rate": 0.001,
            "gpu": 8,
            "cpu": "32",
            "memory": "1000Gi",
            "image": "test:latest",
            "resources": {"limits": {}}
        }
        
        clean_config = self.framework.prepare_config(config)
        
        # Training fields should remain
        assert clean_config["base_model"] == "test/model"
        assert clean_config["learning_rate"] == 0.001
        
        # Cluster fields should be removed
        assert "gpu" not in clean_config
        assert "cpu" not in clean_config
        assert "memory" not in clean_config
        assert "image" not in clean_config
        assert "resources" not in clean_config

    def test_get_configmap_name_sft(self):
        """Test SFT ConfigMap name."""
        name = self.framework.get_configmap_name(TrainingType.SFT)
        assert name == "cw-axolotl-train-sft-config"

    def test_get_configmap_name_grpo(self):
        """Test GRPO ConfigMap name."""
        name = self.framework.get_configmap_name(TrainingType.GRPO)
        assert name == "cw-axolotl-train-grpo-config"

    def test_get_configmap_name_invalid(self):
        """Test invalid training type raises error."""
        with pytest.raises(ValueError, match="Unsupported training type"):
            self.framework.get_configmap_name("invalid")

    def test_get_job_name_sft(self):
        """Test SFT job name."""
        name = self.framework.get_job_name(TrainingType.SFT)
        assert name == "cw-axolotl-train-sft"

    def test_get_job_name_grpo(self):
        """Test GRPO job name."""
        name = self.framework.get_job_name(TrainingType.GRPO)
        assert name == "cw-axolotl-train-grpo"

    def test_get_yaml_templates_sft(self):
        """Test SFT YAML templates."""
        templates = self.framework.get_yaml_templates(TrainingType.SFT)
        assert len(templates) == 1
        assert templates[0] == self.kubeconfig_dir / "axolotl" / "sft_job.yaml"

    def test_get_yaml_templates_grpo(self):
        """Test GRPO YAML templates."""
        templates = self.framework.get_yaml_templates(TrainingType.GRPO)
        assert len(templates) == 3
        
        expected_paths = [
            self.kubeconfig_dir / "axolotl" / "grpo" / "vllm-deployment.yaml",
            self.kubeconfig_dir / "axolotl" / "grpo" / "rewards-deployment.yaml",
            self.kubeconfig_dir / "axolotl" / "grpo" / "training-job.yaml"
        ]
        
        assert templates == expected_paths

    def test_get_default_image(self):
        """Test default image."""
        image = self.framework.get_default_image()
        assert image == 'ghcr.io/tcapelle/triton_eval:1906'

    def test_get_template_context(self):
        """Test template context generation."""
        job = TrainingJob(
            name="test-job",
            config_path=Path("/tmp/config.yaml"),
            training_type=TrainingType.SFT,
            config_data={"base_model": "test/model", "image": "custom:latest"},
            pull_latest=True,
            services_only=False
        )
        
        context = self.framework.get_template_context(job)
        
        assert context["framework"] == "axolotl"
        assert context["training_type"] == "sft"
        assert context["job_name"] == "cw-axolotl-train-sft"
        assert context["configmap_name"] == "cw-axolotl-train-sft-config"
        assert context["config_data"] == job.config_data
        assert context["pull_latest"] is True
        assert context["services_only"] is False
        assert context["image"] == "custom:latest"


class TestVerifiersFramework:
    """Test VerifiersFramework implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.kubeconfig_dir = Path("/tmp/kubeconfigs")
        self.framework = VerifiersFramework(self.kubeconfig_dir)

    def test_initialization(self):
        """Test framework initialization."""
        assert self.framework.name == "verifiers"
        assert self.framework.kubeconfig_dir == self.kubeconfig_dir

    def test_validate_config(self):
        """Test config validation (should always return True for verifiers)."""
        config = {"base_model": "test/model"}
        assert self.framework.validate_config(config, TrainingType.GRPO) is True

    def test_get_configmap_name_grpo(self):
        """Test GRPO ConfigMap name."""
        name = self.framework.get_configmap_name(TrainingType.GRPO)
        assert name == "cw-verifiers-train-grpo-config"

    def test_get_configmap_name_invalid(self):
        """Test invalid training type raises error."""
        with pytest.raises(ValueError, match="Unsupported training type"):
            self.framework.get_configmap_name(TrainingType.SFT)

    def test_get_job_name_grpo(self):
        """Test GRPO job name."""
        name = self.framework.get_job_name(TrainingType.GRPO)
        assert name == "cw-verifiers-train-grpo"

    def test_get_yaml_templates_grpo(self):
        """Test GRPO YAML templates."""
        templates = self.framework.get_yaml_templates(TrainingType.GRPO)
        assert len(templates) == 3
        
        expected_paths = [
            self.kubeconfig_dir / "verifiers" / "vllm-deployment.yaml",
            self.kubeconfig_dir / "verifiers" / "rewards-deployment.yaml",
            self.kubeconfig_dir / "verifiers" / "training-job.yaml"
        ]
        
        assert templates == expected_paths

    def test_get_default_image(self):
        """Test default image."""
        image = self.framework.get_default_image()
        assert image == 'ghcr.io/tcapelle/triton_eval:1906'


class TestBaseTrainingFramework:
    """Test BaseTrainingFramework abstract methods."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that BaseTrainingFramework cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseTrainingFramework("test", Path("/tmp"))

    @patch('cw_cli.core.deployment.get_deployment_strategy')
    def test_deploy_method(self, mock_get_strategy):
        """Test that deploy method calls deployment strategy."""
        # Create a concrete implementation for testing
        class TestFramework(BaseTrainingFramework):
            def validate_config(self, config_data, training_type):
                return True
            def prepare_config(self, config_data):
                return config_data
            def get_configmap_name(self, training_type):
                return "test-config"
            def get_job_name(self, training_type):
                return "test-job"
            def get_yaml_templates(self, training_type):
                return []
            def get_default_image(self):
                return "test:latest"
        
        framework = TestFramework("test", Path("/tmp"))
        job = TrainingJob(
            name="test-job",
            config_path=Path("/tmp/config.yaml"),
            training_type=TrainingType.SFT,
            config_data={}
        )
        
        # Mock the deployment strategy
        mock_strategy = Mock()
        mock_result = DeploymentResult(success=True)
        mock_strategy.deploy.return_value = mock_result
        mock_get_strategy.return_value = mock_strategy
        
        # Call deploy
        result = framework.deploy(job)
        
        # Verify strategy was called
        mock_get_strategy.assert_called_once_with(TrainingType.SFT)
        mock_strategy.deploy.assert_called_once_with(framework, job)
        assert result == mock_result