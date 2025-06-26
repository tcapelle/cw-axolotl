#!/usr/bin/env python3
"""Unit tests for framework registry."""

import pytest
from pathlib import Path
from unittest.mock import Mock

from cw_cli.core.registry import FrameworkRegistry, get_registry, get_framework
from cw_cli.core.framework import BaseTrainingFramework


class TestFrameworkRegistry:
    """Test FrameworkRegistry functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.kubeconfig_dir = Path("/tmp/kubeconfigs")
        self.registry = FrameworkRegistry(self.kubeconfig_dir)

    def test_initialization(self):
        """Test registry initialization."""
        assert self.registry.kubeconfig_dir == self.kubeconfig_dir
        
        # Should have built-in frameworks registered
        frameworks = self.registry.list_frameworks()
        assert "axolotl" in frameworks
        assert "verifiers" in frameworks

    def test_register_framework(self):
        """Test registering a new framework."""
        # Create a mock framework
        mock_framework = Mock(spec=BaseTrainingFramework)
        mock_framework.name = "test-framework"
        
        self.registry.register("test", mock_framework)
        
        # Should be able to retrieve it
        retrieved = self.registry.get_framework("test")
        assert retrieved == mock_framework
        
        # Should appear in list
        frameworks = self.registry.list_frameworks()
        assert "test" in frameworks

    def test_get_framework_existing(self):
        """Test getting an existing framework."""
        framework = self.registry.get_framework("axolotl")
        assert framework is not None
        assert framework.name == "axolotl"

    def test_get_framework_nonexistent(self):
        """Test getting a non-existent framework."""
        framework = self.registry.get_framework("nonexistent")
        assert framework is None

    def test_list_frameworks(self):
        """Test listing all frameworks."""
        frameworks = self.registry.list_frameworks()
        assert isinstance(frameworks, list)
        assert len(frameworks) >= 2  # At least axolotl and verifiers
        assert "axolotl" in frameworks
        assert "verifiers" in frameworks

    def test_is_framework_supported(self):
        """Test checking if framework is supported."""
        assert self.registry.is_framework_supported("axolotl") is True
        assert self.registry.is_framework_supported("verifiers") is True
        assert self.registry.is_framework_supported("nonexistent") is False

    def test_register_duplicate_framework(self):
        """Test that registering duplicate framework overwrites."""
        # Create mock frameworks
        mock_framework1 = Mock(spec=BaseTrainingFramework)
        mock_framework1.name = "test1"
        
        mock_framework2 = Mock(spec=BaseTrainingFramework)
        mock_framework2.name = "test2"
        
        # Register first framework
        self.registry.register("test", mock_framework1)
        retrieved1 = self.registry.get_framework("test")
        assert retrieved1 == mock_framework1
        
        # Register second framework with same name (should overwrite)
        self.registry.register("test", mock_framework2)
        retrieved2 = self.registry.get_framework("test")
        assert retrieved2 == mock_framework2
        assert retrieved2 != mock_framework1


class TestGlobalRegistry:
    """Test global registry functions."""

    def test_get_registry_singleton(self):
        """Test that get_registry returns the same instance."""
        registry1 = get_registry()
        registry2 = get_registry()
        assert registry1 is registry2

    def test_get_framework_global(self):
        """Test global get_framework function."""
        framework = get_framework("axolotl")
        assert framework is not None
        assert framework.name == "axolotl"

    def test_get_framework_global_nonexistent(self):
        """Test global get_framework with non-existent framework."""
        framework = get_framework("nonexistent")
        assert framework is None

    def test_global_registry_has_builtin_frameworks(self):
        """Test that global registry has built-in frameworks."""
        registry = get_registry()
        frameworks = registry.list_frameworks()
        
        assert "axolotl" in frameworks
        assert "verifiers" in frameworks
        
        # Test that we can actually get them
        axolotl = get_framework("axolotl")
        verifiers = get_framework("verifiers")
        
        assert axolotl is not None
        assert verifiers is not None
        assert axolotl.name == "axolotl"
        assert verifiers.name == "verifiers"


class TestFrameworkRegistryEdgeCases:
    """Test edge cases for framework registry."""

    def test_empty_framework_name(self):
        """Test registering framework with empty name."""
        registry = FrameworkRegistry(Path("/tmp"))
        mock_framework = Mock(spec=BaseTrainingFramework)
        
        # Empty string should work (though not recommended)
        registry.register("", mock_framework)
        retrieved = registry.get_framework("")
        assert retrieved == mock_framework

    def test_framework_name_with_special_chars(self):
        """Test framework names with special characters."""
        registry = FrameworkRegistry(Path("/tmp"))
        mock_framework = Mock(spec=BaseTrainingFramework)
        
        special_names = ["test-framework", "test_framework", "test.framework", "test123"]
        
        for name in special_names:
            registry.register(name, mock_framework)
            retrieved = registry.get_framework(name)
            assert retrieved == mock_framework

    def test_case_sensitive_framework_names(self):
        """Test that framework names are case-sensitive."""
        registry = FrameworkRegistry(Path("/tmp"))
        
        mock_framework1 = Mock(spec=BaseTrainingFramework)
        mock_framework2 = Mock(spec=BaseTrainingFramework)
        
        registry.register("Test", mock_framework1)
        registry.register("test", mock_framework2)
        
        # Should be separate entries
        assert registry.get_framework("Test") == mock_framework1
        assert registry.get_framework("test") == mock_framework2
        assert registry.get_framework("TEST") is None

    def test_none_framework_registration(self):
        """Test registering None as framework."""
        registry = FrameworkRegistry(Path("/tmp"))
        
        # This should work but probably indicates a bug
        registry.register("none-test", None)
        retrieved = registry.get_framework("none-test")
        assert retrieved is None

    def test_list_frameworks_immutability(self):
        """Test that modifying returned framework list doesn't affect registry."""
        registry = FrameworkRegistry(Path("/tmp"))
        
        frameworks_list = registry.list_frameworks()
        original_length = len(frameworks_list)
        
        # Try to modify the returned list
        frameworks_list.append("fake-framework")
        
        # Should not affect the registry
        new_list = registry.list_frameworks()
        assert len(new_list) == original_length
        assert "fake-framework" not in new_list