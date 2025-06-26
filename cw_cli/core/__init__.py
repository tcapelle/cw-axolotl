"""Core abstractions for the CW CLI framework."""

from .framework import BaseTrainingFramework, TrainingJob, TrainingType, DeploymentResult
from .registry import FrameworkRegistry, get_registry, get_framework
from .deployment import BaseDeploymentStrategy, get_deployment_strategy
from .configuration import ConfigurationManager, get_config_manager
from .resources import ResourceManager
from .templating import TemplateEngine, get_template_engine, render_template
from .exceptions import CWCLIError, ConfigurationError, FrameworkError, DeploymentError
from .plugins import PluginManager, Plugin, get_plugin_manager

__all__ = [
    # Framework abstractions
    'BaseTrainingFramework', 'TrainingJob', 'TrainingType', 'DeploymentResult',
    
    # Registry system
    'FrameworkRegistry', 'get_registry', 'get_framework',
    
    # Deployment system
    'BaseDeploymentStrategy', 'get_deployment_strategy',
    
    # Configuration management
    'ConfigurationManager', 'get_config_manager',
    
    # Resource management
    'ResourceManager',
    
    # Templating system
    'TemplateEngine', 'get_template_engine', 'render_template',
    
    # Exception hierarchy
    'CWCLIError', 'ConfigurationError', 'FrameworkError', 'DeploymentError',
    
    # Plugin system
    'PluginManager', 'Plugin', 'get_plugin_manager'
]