# CW-CLI Architecture Overview

This document describes the refactored architecture of CW-CLI, designed for improved maintainability and extensibility.

## Core Architecture

The new architecture is organized around several key abstractions:

### 1. Framework Abstraction (`cw_cli.core.framework`)

**Purpose**: Provides a unified interface for different training frameworks (Axolotl, Verifiers, etc.)

**Key Components**:
- `BaseTrainingFramework`: Abstract base class for all frameworks
- `AxolotlFramework`: Implementation for Axolotl framework
- `VerifiersFramework`: Implementation for Verifiers framework
- `TrainingJob`: Data class representing a training job
- `TrainingType`: Enum for training types (SFT, GRPO)

**Benefits**:
- Easy to add new frameworks
- Consistent interface across frameworks
- Framework-specific logic is encapsulated

### 2. Registry System (`cw_cli.core.registry`)

**Purpose**: Manages discovery and instantiation of training frameworks

**Key Components**:
- `FrameworkRegistry`: Central registry for frameworks
- `get_framework()`: Global function to get framework instances

**Benefits**:
- Centralized framework management
- Easy framework discovery
- Plugin-ready architecture

### 3. Deployment Strategy (`cw_cli.core.deployment`)

**Purpose**: Abstracts deployment logic for different training types

**Key Components**:
- `BaseDeploymentStrategy`: Abstract base for deployment strategies
- `SFTDeploymentStrategy`: Strategy for SFT training
- `GRPODeploymentStrategy`: Strategy for GRPO multi-service deployment

**Benefits**:
- Separates deployment logic from framework logic
- Easy to customize deployment behavior
- Supports complex multi-service deployments

### 4. Configuration Management (`cw_cli.core.configuration`)

**Purpose**: Centralized configuration loading, validation, and processing

**Key Components**:
- `ConfigurationManager`: Main configuration management class
- `TrainingConfig`: Pydantic model for configuration validation
- `ResourceRequirements`: Model for resource specification

**Benefits**:
- Schema-based validation with Pydantic
- Consistent configuration processing
- Better error messages for invalid configs

### 5. Resource Management (`cw_cli.core.resources`)

**Purpose**: Handles resource allocation and requirements

**Key Components**:
- `ResourceManager`: Manages resource allocation logic
- Resource merging and validation functions

**Benefits**:
- Centralized resource logic
- Consistent resource handling
- Easy to extend for new resource types

### 6. Resource Injection System (`cw_cli.core.templating`)

**Purpose**: Smart resource injection into framework-specific YAML files

**Key Components**:
- `render_template()`: Processes existing YAML files with resource injection
- Resource merging and image updating
- Environment variable injection for special cases

**Benefits**:
- Framework-specific YAML files maintained
- Dynamic resource allocation from config and overrides
- Backward compatibility with existing templates
- Optional Jinja2 templating for advanced use cases

### 7. Exception Hierarchy (`cw_cli.core.exceptions`)

**Purpose**: Structured exception handling with user-friendly error messages

**Key Components**:
- `CWCLIError`: Base exception class
- Specific exceptions for different error types
- Error formatting and suggestion functions

**Benefits**:
- Better error categorization
- User-friendly error messages
- Actionable error suggestions

### 8. Plugin System (`cw_cli.core.plugins`)

**Purpose**: Extensibility through plugins

**Key Components**:
- `Plugin`: Base class for all plugins
- `FrameworkPlugin`: For adding new frameworks
- `DeploymentStrategyPlugin`: For custom deployment strategies
- `CommandPlugin`: For adding new CLI commands
- `PluginManager`: Manages plugin lifecycle

**Benefits**:
- Easy extensibility without modifying core code
- Supports framework, command, and strategy plugins
- Clean plugin lifecycle management

## Migration Guide

### For Users

The CLI interface remains the same. All existing commands work as before:

```bash
# These commands work exactly as before
cw axolotl sft config.yaml
cw axolotl grpo train config.yaml
cw verifiers grpo config.yaml
```

### For Developers

#### Adding New Frameworks

Before (old way):
```python
# Had to modify multiple files and duplicate lots of code
```

After (new way):
```python
from cw_cli.core.framework import BaseTrainingFramework

class MyFramework(BaseTrainingFramework):
    def __init__(self, kubeconfig_dir):
        super().__init__("myframework", kubeconfig_dir)
    
    def validate_config(self, config_data, training_type):
        # Framework-specific validation
        return True
    
    def prepare_config(self, config_data):
        # Clean config for deployment
        return config_data
    
    # Implement other required methods...

# Register the framework
from cw_cli.core.registry import get_registry
registry = get_registry()
registry.register("myframework", MyFramework(registry.kubeconfig_dir))
```

#### Adding New Deployment Strategies

```python
from cw_cli.core.deployment import BaseDeploymentStrategy

class MyDeploymentStrategy(BaseDeploymentStrategy):
    def deploy(self, framework, job):
        # Custom deployment logic
        pass

# Register the strategy
from cw_cli.core.deployment import register_deployment_strategy
register_deployment_strategy(TrainingType.CUSTOM, MyDeploymentStrategy())
```

#### Creating Plugins

```python
from cw_cli.core.plugins import FrameworkPlugin

class MyFrameworkPlugin(FrameworkPlugin):
    @property
    def name(self):
        return "my-framework-plugin"
    
    def get_framework_class(self):
        return MyFramework
    
    # Implement other required methods...

# Plugin will be auto-discovered if placed in ~/.cw-cli/plugins/
```

## Benefits of the New Architecture

1. **Maintainability**: 
   - Clear separation of concerns
   - Reduced code duplication
   - Smaller, focused functions

2. **Extensibility**:
   - Easy to add new frameworks
   - Plugin architecture for custom extensions
   - Template-based YAML generation

3. **Testability**:
   - Smaller components with clear interfaces
   - Dependency injection through registries
   - Mockable abstractions

4. **User Experience**:
   - Better error messages with suggestions
   - Consistent behavior across frameworks
   - Maintained backward compatibility

5. **Performance**:
   - Lazy loading of frameworks
   - Efficient template caching
   - Parallel resource operations

## File Structure

```
cw_cli/
├── core/                     # New core abstractions
│   ├── __init__.py          # Public API exports
│   ├── framework.py         # Framework abstractions
│   ├── registry.py          # Framework registry
│   ├── deployment.py        # Deployment strategies
│   ├── configuration.py     # Config management
│   ├── resources.py         # Resource management
│   ├── templating.py        # Template engine
│   ├── exceptions.py        # Exception hierarchy
│   └── plugins.py           # Plugin system
├── cli.py                   # CLI entry point (updated)
├── new_commands.py          # New command implementations
├── commands.py              # Legacy commands (unchanged)
├── config.py                # Configuration classes (unchanged)
└── kubeconfigs/             # Framework-specific Kubernetes YAML files
    ├── axolotl/             # Axolotl-specific deployments
    └── verifiers/           # Verifiers-specific deployments
```

This architecture maintains full backward compatibility while providing a solid foundation for future enhancements.