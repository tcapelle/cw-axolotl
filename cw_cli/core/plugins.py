#!/usr/bin/env python3
"""Plugin architecture foundation for CW CLI extensibility."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type
import importlib
import pkgutil
from pathlib import Path

from .framework import BaseTrainingFramework, TrainingType
from .deployment import BaseDeploymentStrategy
from .exceptions import CWCLIError


class PluginError(CWCLIError):
    """Raised when plugin operations fail."""
    pass


class Plugin(ABC):
    """Base class for all plugins."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name."""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Plugin description."""
        pass
    
    @abstractmethod
    def initialize(self, context: Dict[str, Any]):
        """Initialize the plugin with context."""
        pass
    
    @abstractmethod
    def cleanup(self):
        """Cleanup plugin resources."""
        pass


class FrameworkPlugin(Plugin):
    """Plugin for adding new training frameworks."""
    
    @abstractmethod
    def get_framework_class(self) -> Type[BaseTrainingFramework]:
        """Get the framework class provided by this plugin."""
        pass
    
    @abstractmethod
    def get_supported_training_types(self) -> List[TrainingType]:
        """Get training types supported by this framework."""
        pass


class DeploymentStrategyPlugin(Plugin):
    """Plugin for adding new deployment strategies."""
    
    @abstractmethod
    def get_strategy_class(self) -> Type[BaseDeploymentStrategy]:
        """Get the deployment strategy class provided by this plugin."""
        pass
    
    @abstractmethod
    def get_training_type(self) -> TrainingType:
        """Get the training type this strategy handles."""
        pass


class CommandPlugin(Plugin):
    """Plugin for adding new CLI commands."""
    
    @abstractmethod
    def get_command_name(self) -> str:
        """Get the command name."""
        pass
    
    @abstractmethod
    def get_command_help(self) -> str:
        """Get command help text."""
        pass
    
    @abstractmethod
    def setup_parser(self, parser):
        """Setup argument parser for this command."""
        pass
    
    @abstractmethod
    def execute(self, args) -> int:
        """Execute the command."""
        pass


class PluginManager:
    """Manages plugin discovery, loading, and lifecycle."""
    
    def __init__(self):
        self.loaded_plugins: Dict[str, Plugin] = {}
        self.framework_plugins: Dict[str, FrameworkPlugin] = {}
        self.strategy_plugins: Dict[TrainingType, DeploymentStrategyPlugin] = {}
        self.command_plugins: Dict[str, CommandPlugin] = {}
    
    def discover_plugins(self, plugin_dirs: List[Path] = None):
        """Discover plugins in specified directories."""
        if plugin_dirs is None:
            plugin_dirs = [Path.home() / ".cw-cli" / "plugins"]
        
        for plugin_dir in plugin_dirs:
            if not plugin_dir.exists():
                continue
            
            self._discover_plugins_in_directory(plugin_dir)
    
    def _discover_plugins_in_directory(self, plugin_dir: Path):
        """Discover plugins in a specific directory."""
        # Add plugin directory to Python path temporarily
        import sys
        original_path = sys.path.copy()
        sys.path.insert(0, str(plugin_dir))
        
        try:
            # Look for Python packages in the directory
            for finder, name, ispkg in pkgutil.iter_modules([str(plugin_dir)]):
                if ispkg:
                    self._load_plugin_package(name)
        finally:
            # Restore original Python path
            sys.path = original_path
    
    def _load_plugin_package(self, package_name: str):
        """Load a plugin package."""
        try:
            module = importlib.import_module(package_name)
            
            # Look for plugin entry point
            if hasattr(module, 'get_plugin'):
                plugin = module.get_plugin()
                self.register_plugin(plugin)
            elif hasattr(module, 'PLUGIN_CLASS'):
                plugin_class = module.PLUGIN_CLASS
                plugin = plugin_class()
                self.register_plugin(plugin)
        except Exception as e:
            raise PluginError(f"Failed to load plugin package '{package_name}': {e}")
    
    def register_plugin(self, plugin: Plugin):
        """Register a plugin."""
        if plugin.name in self.loaded_plugins:
            raise PluginError(f"Plugin '{plugin.name}' is already registered")
        
        # Initialize plugin
        context = self._get_plugin_context()
        plugin.initialize(context)
        
        # Store plugin
        self.loaded_plugins[plugin.name] = plugin
        
        # Register in specific registries based on type
        if isinstance(plugin, FrameworkPlugin):
            self.framework_plugins[plugin.name] = plugin
            # Register framework in main registry
            from .registry import get_registry
            registry = get_registry()
            framework_class = plugin.get_framework_class()
            framework = framework_class(registry.kubeconfig_dir)
            registry.register(plugin.name, framework)
        
        elif isinstance(plugin, DeploymentStrategyPlugin):
            training_type = plugin.get_training_type()
            self.strategy_plugins[training_type] = plugin
            # Register strategy
            from .deployment import register_deployment_strategy
            strategy_class = plugin.get_strategy_class()
            strategy = strategy_class()
            register_deployment_strategy(training_type, strategy)
        
        elif isinstance(plugin, CommandPlugin):
            command_name = plugin.get_command_name()
            self.command_plugins[command_name] = plugin
    
    def _get_plugin_context(self) -> Dict[str, Any]:
        """Get context to pass to plugins during initialization."""
        return {
            'cli_version': '0.1.0',  # TODO: Get from package
            'kubeconfig_dir': Path(__file__).parent.parent / "kubeconfigs"
        }
    
    def unregister_plugin(self, plugin_name: str):
        """Unregister a plugin."""
        if plugin_name not in self.loaded_plugins:
            raise PluginError(f"Plugin '{plugin_name}' is not registered")
        
        plugin = self.loaded_plugins[plugin_name]
        
        # Cleanup plugin
        try:
            plugin.cleanup()
        except Exception as e:
            # Log warning but continue with unregistration
            print(f"Warning: Error during plugin cleanup: {e}")
        
        # Remove from registries
        if isinstance(plugin, FrameworkPlugin):
            self.framework_plugins.pop(plugin_name, None)
        elif isinstance(plugin, DeploymentStrategyPlugin):
            # Find and remove from strategy plugins
            for training_type, strategy_plugin in list(self.strategy_plugins.items()):
                if strategy_plugin.name == plugin_name:
                    self.strategy_plugins.pop(training_type, None)
                    break
        elif isinstance(plugin, CommandPlugin):
            command_name = plugin.get_command_name()
            self.command_plugins.pop(command_name, None)
        
        # Remove from main registry
        self.loaded_plugins.pop(plugin_name)
    
    def list_plugins(self) -> List[Dict[str, str]]:
        """List all loaded plugins."""
        return [
            {
                'name': plugin.name,
                'version': plugin.version,
                'description': plugin.description,
                'type': type(plugin).__name__
            }
            for plugin in self.loaded_plugins.values()
        ]
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a plugin by name."""
        return self.loaded_plugins.get(name)
    
    def shutdown(self):
        """Shutdown plugin manager and cleanup all plugins."""
        for plugin in self.loaded_plugins.values():
            try:
                plugin.cleanup()
            except Exception as e:
                print(f"Warning: Error during plugin cleanup: {e}")
        
        self.loaded_plugins.clear()
        self.framework_plugins.clear()
        self.strategy_plugins.clear()
        self.command_plugins.clear()


# Global plugin manager instance
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager