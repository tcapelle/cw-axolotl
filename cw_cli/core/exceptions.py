#!/usr/bin/env python3
"""Structured exception hierarchy for CW CLI."""

from typing import Optional, Dict, Any


class CWCLIError(Exception):
    """Base exception for all CW CLI errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)
    
    def __str__(self) -> str:
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({detail_str})"
        return self.message


class ConfigurationError(CWCLIError):
    """Raised when configuration is invalid or missing."""
    pass


class FrameworkError(CWCLIError):
    """Raised when framework-specific operations fail."""
    
    def __init__(self, framework: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.framework = framework
        enhanced_details = {"framework": framework}
        if details:
            enhanced_details.update(details)
        super().__init__(message, enhanced_details)


class DeploymentError(CWCLIError):
    """Raised when deployment operations fail."""
    
    def __init__(self, operation: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.operation = operation
        enhanced_details = {"operation": operation}
        if details:
            enhanced_details.update(details)
        super().__init__(message, enhanced_details)


class TemplateError(CWCLIError):
    """Raised when template rendering fails."""
    
    def __init__(self, template_path: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.template_path = template_path
        enhanced_details = {"template_path": template_path}
        if details:
            enhanced_details.update(details)
        super().__init__(message, enhanced_details)


class ResourceError(CWCLIError):
    """Raised when resource allocation or validation fails."""
    pass


class KubernetesError(CWCLIError):
    """Raised when Kubernetes operations fail."""
    
    def __init__(self, operation: str, resource_type: str, message: str, 
                 details: Optional[Dict[str, Any]] = None):
        self.operation = operation
        self.resource_type = resource_type
        enhanced_details = {"operation": operation, "resource_type": resource_type}
        if details:
            enhanced_details.update(details)
        super().__init__(message, enhanced_details)


class ValidationError(CWCLIError):
    """Raised when validation fails."""
    
    def __init__(self, field: str, value: Any, message: str, 
                 details: Optional[Dict[str, Any]] = None):
        self.field = field
        self.value = value
        enhanced_details = {"field": field, "value": str(value)}
        if details:
            enhanced_details.update(details)
        super().__init__(message, enhanced_details)


def format_error_for_user(error: Exception) -> str:
    """Format error message for user display."""
    if isinstance(error, CWCLIError):
        return f"❌ {error.message}"
    else:
        return f"❌ Unexpected error: {str(error)}"


def get_error_suggestions(error: Exception) -> Optional[str]:
    """Get suggestions for fixing common errors."""
    if isinstance(error, ConfigurationError):
        return "💡 Check your YAML configuration file for syntax errors or missing required fields"
    elif isinstance(error, FrameworkError):
        return f"💡 Verify that the {error.framework} framework is properly configured"
    elif isinstance(error, DeploymentError):
        return "💡 Check cluster resources and ensure kubectl is properly configured"
    elif isinstance(error, TemplateError):
        return "💡 Verify that all required template variables are provided"
    elif isinstance(error, ResourceError):
        return "💡 Check resource requirements and cluster capacity"
    elif isinstance(error, KubernetesError):
        return "💡 Verify kubectl access and cluster connectivity"
    return None