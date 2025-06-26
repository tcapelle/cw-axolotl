#!/usr/bin/env python3
"""Template engine for Kubernetes YAML generation."""

import yaml
from typing import Dict, Any
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template

from .resources import ResourceManager


class TemplateEngine:
    """Template engine for rendering Kubernetes YAML files."""
    
    def __init__(self, template_dirs: list[Path] = None):
        """Initialize template engine with template directories."""
        if template_dirs is None:
            template_dirs = []
        
        # Convert Path objects to strings for Jinja2
        template_dir_strings = [str(d) for d in template_dirs]
        
        self.env = Environment(
            loader=FileSystemLoader(template_dir_strings) if template_dir_strings else None,
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self.env.filters['to_yaml'] = self._to_yaml_filter
        self.env.filters['merge_resources'] = self._merge_resources_filter
    
    def _to_yaml_filter(self, value: Any) -> str:
        """Convert value to YAML string."""
        return yaml.dump(value, default_flow_style=False).strip()
    
    def _merge_resources_filter(self, base_resources: Dict[str, Any], 
                               config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Merge resource requirements from config into base resources."""
        resource_manager = ResourceManager()
        return resource_manager.merge_resources(base_resources, config_data)
    
    def render_from_string(self, template_str: str, context: Dict[str, Any]) -> str:
        """Render template from string."""
        template = Template(template_str, environment=self.env)
        return template.render(**context)
    
    def render_from_file(self, template_path: Path, context: Dict[str, Any]) -> str:
        """Render template from file."""
        with open(template_path, 'r') as f:
            template_content = f.read()
        return self.render_from_string(template_content, context)


# Global template engine instance
_template_engine: TemplateEngine = None


def get_template_engine() -> TemplateEngine:
    """Get the global template engine instance."""
    global _template_engine
    if _template_engine is None:
        # Initialize with default kubeconfigs directory
        kubeconfigs_dir = Path(__file__).parent.parent / "kubeconfigs"
        template_dirs = [kubeconfigs_dir]
        _template_engine = TemplateEngine(template_dirs)
    return _template_engine


def render_template(template_path: Path, context: Dict[str, Any]) -> str:
    """Render a template file with given context."""
    # For now, we'll use the existing YAML files directly with resource injection
    # This maintains backward compatibility while we determine if templating is needed
    
    # Read the original YAML file
    with open(template_path, 'r') as f:
        yaml_content = f.read()
    
    # Parse and update with resources from context
    yaml_docs = list(yaml.safe_load_all(yaml_content))
    updated_docs = []
    
    for doc in yaml_docs:
        if doc and doc.get('kind') in ['Job', 'Deployment']:
            # Update resources if provided in context
            if 'resources' in context and context['resources']:
                containers = doc.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
                for container in containers:
                    container['resources'] = context['resources']
            
            # Update image if provided
            if 'image' in context:
                containers = doc.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
                for container in containers:
                    container['image'] = context['image']
            
            # Add pull latest env var if requested
            if context.get('pull_latest'):
                containers = doc.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
                for container in containers:
                    if 'env' not in container:
                        container['env'] = []
                    container['env'].append({
                        'name': 'PULL_LATEST',
                        'value': 'true'
                    })
        
        updated_docs.append(doc)
    
    # Convert back to YAML
    return '---\n'.join(yaml.dump(doc, default_flow_style=False) for doc in updated_docs if doc)


def _inject_resources_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Inject resource-related context for templates."""
    config_data = context.get('config_data', {})
    
    # Extract resource requirements
    resources = {}
    if 'resources' in config_data:
        resources = config_data['resources']
    elif any(key in config_data for key in ['gpu', 'cpu', 'memory']):
        # Build resources from individual fields
        if 'gpu' in config_data:
            resources.setdefault('limits', {})['nvidia.com/gpu'] = str(config_data['gpu'])
            resources.setdefault('requests', {})['nvidia.com/gpu'] = str(config_data['gpu'])
        if 'cpu' in config_data:
            resources.setdefault('limits', {})['cpu'] = str(config_data['cpu'])
            resources.setdefault('requests', {})['cpu'] = str(config_data['cpu'])
        if 'memory' in config_data:
            resources.setdefault('limits', {})['memory'] = str(config_data['memory'])
            resources.setdefault('requests', {})['memory'] = str(config_data['memory'])
    
    # Add resources to context
    enhanced_context = context.copy()
    enhanced_context['resources'] = resources
    
    return enhanced_context