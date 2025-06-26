#!/usr/bin/env python3
"""Framework registry for training framework discovery and instantiation."""

from typing import Dict, Type, Optional
from pathlib import Path

from .framework import BaseTrainingFramework, AxolotlFramework, VerifiersFramework


class FrameworkRegistry:
    """Registry for training frameworks."""
    
    def __init__(self, kubeconfig_dir: Path):
        self.kubeconfig_dir = kubeconfig_dir
        self._frameworks: Dict[str, BaseTrainingFramework] = {}
        self._register_builtin_frameworks()
    
    def _register_builtin_frameworks(self):
        """Register built-in frameworks."""
        self.register("axolotl", AxolotlFramework(self.kubeconfig_dir))
        self.register("verifiers", VerifiersFramework(self.kubeconfig_dir))
    
    def register(self, name: str, framework: BaseTrainingFramework):
        """Register a framework."""
        self._frameworks[name] = framework
    
    def get_framework(self, name: str) -> Optional[BaseTrainingFramework]:
        """Get a framework by name."""
        return self._frameworks.get(name)
    
    def list_frameworks(self) -> list[str]:
        """List all registered framework names."""
        return list(self._frameworks.keys())
    
    def is_framework_supported(self, name: str) -> bool:
        """Check if a framework is supported."""
        return name in self._frameworks


# Global registry instance - initialized when first imported
_registry: Optional[FrameworkRegistry] = None


def get_registry() -> FrameworkRegistry:
    """Get the global framework registry."""
    global _registry
    if _registry is None:
        # Default kubeconfig directory
        kubeconfig_dir = Path(__file__).parent.parent / "kubeconfigs"
        _registry = FrameworkRegistry(kubeconfig_dir)
    return _registry


def get_framework(name: str) -> Optional[BaseTrainingFramework]:
    """Get a framework from the global registry."""
    return get_registry().get_framework(name)