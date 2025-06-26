#!/usr/bin/env python3
"""Resource management for Kubernetes deployments."""

from typing import Dict, Any, Optional


class ResourceManager:
    """Manages resource allocation and requirements for deployments."""
    
    def __init__(self):
        """Initialize resource manager."""
        self.default_resources = {
            'sft': {
                'limits': {
                    'nvidia.com/gpu': '8',
                    'cpu': '32',
                    'memory': '1600Gi'
                },
                'requests': {
                    'nvidia.com/gpu': '8',
                    'cpu': '32',
                    'memory': '1600Gi'
                }
            },
            'grpo': {
                'limits': {
                    'nvidia.com/gpu': '8',
                    'cpu': '64',
                    'memory': '2000Gi'
                },
                'requests': {
                    'nvidia.com/gpu': '8',
                    'cpu': '64',
                    'memory': '1800Gi'
                }
            }
        }
    
    def get_default_resources(self, training_type: str) -> Dict[str, Any]:
        """Get default resource requirements for a training type."""
        return self.default_resources.get(training_type, self.default_resources['sft'])
    
    def merge_resources(self, base_resources: Dict[str, Any], 
                       config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Merge resource requirements from config into base resources."""
        if not config_data:
            return base_resources
        
        # Start with base resources or empty dict
        merged = base_resources.copy() if base_resources else {}
        
        # Handle explicit resources block
        if 'resources' in config_data:
            config_resources = config_data['resources']
            if isinstance(config_resources, dict):
                merged = self._deep_merge(merged, config_resources)
            return merged
        
        # Handle individual resource fields
        resource_updates = {}
        
        if 'gpu' in config_data:
            gpu_value = str(config_data['gpu'])
            resource_updates.setdefault('limits', {})['nvidia.com/gpu'] = gpu_value
            resource_updates.setdefault('requests', {})['nvidia.com/gpu'] = gpu_value
        
        if 'cpu' in config_data:
            cpu_value = str(config_data['cpu'])
            resource_updates.setdefault('limits', {})['cpu'] = cpu_value
            resource_updates.setdefault('requests', {})['cpu'] = cpu_value
        
        if 'memory' in config_data:
            memory_value = str(config_data['memory'])
            resource_updates.setdefault('limits', {})['memory'] = memory_value
            resource_updates.setdefault('requests', {})['memory'] = memory_value
        
        if resource_updates:
            merged = self._deep_merge(merged, resource_updates)
        
        return merged
    
    def _deep_merge(self, base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in updates.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def validate_resources(self, resources: Dict[str, Any]) -> bool:
        """Validate resource requirements."""
        if not isinstance(resources, dict):
            return False
        
        # Check for required structure
        if 'limits' not in resources and 'requests' not in resources:
            return False
        
        # Validate GPU requirements
        limits = resources.get('limits', {})
        requests = resources.get('requests', {})
        
        gpu_limits = limits.get('nvidia.com/gpu')
        gpu_requests = requests.get('nvidia.com/gpu')
        
        if gpu_limits and gpu_requests:
            try:
                if int(gpu_limits) != int(gpu_requests):
                    return False
            except ValueError:
                return False
        
        return True
    
    def calculate_node_requirements(self, resources: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate node requirements based on resource requests."""
        requirements = {
            'gpu_required': False,
            'min_gpu_count': 0,
            'min_cpu_cores': 0,
            'min_memory_gb': 0
        }
        
        requests = resources.get('requests', {})
        
        # GPU requirements
        gpu_request = requests.get('nvidia.com/gpu', '0')
        try:
            gpu_count = int(gpu_request)
            if gpu_count > 0:
                requirements['gpu_required'] = True
                requirements['min_gpu_count'] = gpu_count
        except ValueError:
            pass
        
        # CPU requirements
        cpu_request = requests.get('cpu', '0')
        try:
            if cpu_request.endswith('m'):
                cpu_cores = int(cpu_request[:-1]) / 1000
            else:
                cpu_cores = int(cpu_request)
            requirements['min_cpu_cores'] = cpu_cores
        except ValueError:
            pass
        
        # Memory requirements
        memory_request = requests.get('memory', '0')
        try:
            if memory_request.endswith('Gi'):
                memory_gb = int(memory_request[:-2])
            elif memory_request.endswith('Mi'):
                memory_gb = int(memory_request[:-2]) / 1024
            elif memory_request.endswith('Ki'):
                memory_gb = int(memory_request[:-2]) / (1024 * 1024)
            else:
                memory_gb = int(memory_request) / (1024 * 1024 * 1024)
            requirements['min_memory_gb'] = memory_gb
        except ValueError:
            pass
        
        return requirements