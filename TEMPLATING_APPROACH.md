# CW-CLI Templating Strategy

## Why Framework-Specific Templates Make Sense

You're absolutely correct that each framework is very specific. Here's the refined approach:

## Current Approach: Framework-Specific YAML Files

### **Axolotl Framework**
- `kubeconfigs/axolotl/sft_job.yaml` - Axolotl-specific SFT job
- `kubeconfigs/axolotl/grpo/training-job.yaml` - Axolotl-specific GRPO training
- `kubeconfigs/axolotl/grpo/vllm-deployment.yaml` - Axolotl-specific VLLM service
- `kubeconfigs/axolotl/grpo/rewards-deployment.yaml` - Axolotl-specific rewards service

### **Verifiers Framework**  
- `kubeconfigs/verifiers/training-job.yaml` - Verifiers-specific GRPO training
- `kubeconfigs/verifiers/vllm-deployment.yaml` - Verifiers-specific VLLM service
- `kubeconfigs/verifiers/rewards-deployment.yaml` - Verifiers-specific rewards service

## Template Engine: Limited Scope

The template engine should be used **only** for:

### 1. **Resource Injection** ✅
```yaml
# Original YAML
resources:
  limits:
    nvidia.com/gpu: "8"
    cpu: "32"
    memory: "1600Gi"

# After resource injection from config
resources:
  limits:
    nvidia.com/gpu: "4"      # From --gpu 4 override
    cpu: "64"                # From config
    memory: "2000Gi"         # From config
```

### 2. **Image Updates** ✅
```yaml
# Original YAML
image: ghcr.io/tcapelle/triton_eval:1506

# After image injection from config
image: ghcr.io/tcapelle/triton_eval:1906  # From config
```

### 3. **Environment Variables** ✅
```yaml
# Add PULL_LATEST if --pull flag is used
env:
- name: PULL_LATEST
  value: "true"
```

## What NOT to Template

### ❌ **Framework-Specific Logic**
Each framework has unique:
- Container commands and arguments
- Working directories (`/app/axolotl_dev` vs `/app/verifiers`)
- Environment variables (e.g., `TRITON_SERVER_URL` for GRPO)
- Init containers and dependencies
- Volume mount paths
- Service discovery patterns

### ❌ **Training Type Differences**
- SFT jobs vs GRPO multi-service deployments
- Different service orchestration patterns
- Framework-specific validation logic

## Better Approach: Smart Resource Injection

Instead of generic templates, we use **smart resource injection** that:

1. **Reads framework-specific YAML files** (no templates needed)
2. **Injects resources dynamically** based on config and overrides
3. **Updates images** when specified in config
4. **Adds environment variables** when needed (like PULL_LATEST)

## Implementation

```python
# core/templating.py - Resource injection, not templating
def render_template(template_path: Path, context: Dict[str, Any]) -> str:
    """Process existing YAML with resource injection."""
    
    # Read the framework-specific YAML file
    with open(template_path, 'r') as f:
        yaml_content = f.read()
    
    # Parse and update with resources from context
    yaml_docs = list(yaml.safe_load_all(yaml_content))
    
    for doc in yaml_docs:
        if doc and doc.get('kind') in ['Job', 'Deployment']:
            # Inject resources
            if 'resources' in context:
                containers = get_containers(doc)
                for container in containers:
                    container['resources'] = context['resources']
            
            # Inject image
            if 'image' in context:
                containers = get_containers(doc)
                for container in containers:
                    container['image'] = context['image']
    
    return yaml_to_string(yaml_docs)
```

## Benefits of This Approach

### ✅ **Framework Specificity**
- Each framework keeps its specific YAML files
- No loss of framework-specific optimizations
- Easy to maintain and debug

### ✅ **Resource Flexibility**
- Dynamic resource allocation
- Command-line overrides work
- Different resource profiles per training type

### ✅ **Backward Compatibility**
- All existing YAML files work unchanged
- No breaking changes
- Gradual adoption possible

### ✅ **Future Extensibility**
- New frameworks add their own YAML files
- Resource injection works for any framework
- Optional true templating for specific use cases

## When to Use True Templating

True Jinja2 templating might be useful for:

1. **User-specific customizations** (e.g., different persistent volume claims)
2. **Environment-specific deployments** (dev vs prod configurations)
3. **Advanced users** who want to customize beyond resource allocation

But the **default should be framework-specific YAML files** with smart resource injection.

## Conclusion

Your observation is correct: **frameworks are very specific** and shouldn't be force-fit into generic templates. The architecture provides the **capability** for templating where needed, but the **default approach** uses framework-specific YAML files with intelligent resource injection.

This gives us the best of both worlds:
- **Simplicity** for the common case (framework-specific files)
- **Flexibility** for advanced customization (optional templating)
- **Maintainability** by keeping framework logic separate