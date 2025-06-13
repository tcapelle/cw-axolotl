# CW-CLI - Unified Axolotl Training CLI

A unified command-line interface for running Axolotl SFT jobs on Kubernetes with dynamic configuration injection.

## Installation

```bash
pip install -e .
```

## Usage

### Basic Training Command

Run an SFT training job with a single command:

```bash
cw axolotl train axolotl/sft_config.yaml
```

#### Command-line Overrides

Override any configuration parameter on the fly:

```bash
# Override GPU count
cw axolotl train axolotl/sft_config.yaml --gpu 6

# Override multiple parameters
cw axolotl train axolotl/sft_config.yaml --gpu 4 --learning_rate 0.001 --batch_size 8

# Override any YAML key
cw axolotl train axolotl/sft_config.yaml --base_model "microsoft/DialoGPT-medium"
```

### Resource Commands

List and monitor cluster resources:

```bash
# List jobs
cw jobs
cw jobs -n my-namespace
cw jobs -A  # All namespaces

# List pods  
cw pods
cw pods -n my-namespace  
cw pods -A  # All namespaces
cw pods -r  # Show resource requests/limits
cw pods -w  # Watch for changes

# List nodes
cw nodes
cw nodes -n  # Show detailed node info
```

### Job Management Commands

Monitor and manage your training jobs:

```bash
# Interactive job selection (shows available jobs)
cw describe                      # Select job to check status
cw logs                          # Select job to view logs  
cw delete                        # Select job to delete

# Direct job specification
cw describe my-job -w            # Watch specific job status
cw describe my-job -o yaml       # YAML output for specific job
cw logs -j my-job                # Follow specific job logs
cw logs -j my-job -n             # Don't follow logs
cw delete my-job                 # Delete specific job

# Legacy commands (still supported)
cw list                          # List axolotl jobs only
```

**Interactive Features:**
- When no job is specified, commands show available jobs and let you choose
- Single job: "Do you want to view logs for `my-job`? (y/N)"
- Multiple jobs: Shows numbered list for selection
- Supports selection by number, full name, or partial name matching

### Direct Python Usage

You can also use the Python module directly:

```bash
python main.py axolotl train axolotl/sft_config.yaml
python main.py logs
python main.py status
python main.py delete
```

## How It Works

The CLI tool simplifies Kubernetes job deployment by:

1. **Dynamic ConfigMap Creation**: Automatically creates a ConfigMap from your SFT config file
2. **Resource Injection**: Reads resource requirements from your config and applies them to the job
3. **Single Command Deployment**: Handles both ConfigMap and Job creation with proper cleanup on failure

### Configuration

Your SFT config file (`axolotl/sft_config.yaml`) can include resource specifications:

```yaml
# Standard Axolotl config
base_model: Qwen/Qwen3-4B
datasets:
  - path: tcapelle/train_ds_triton_sft_think
    type: chat_template
# ... other config options

# Optional: Resource requirements (will override job defaults)
gpu: 8
cpu: "32"
memory: "1600Gi"

# Or use the full resources block:
resources:
  limits:
    nvidia.com/gpu: "8"
    cpu: "32"
    memory: "1600Gi"
  requests:
    nvidia.com/gpu: "8"
    cpu: "32"
    memory: "1600Gi"
```

### What Happens Behind the Scenes

1. The tool reads your SFT config file
2. Creates a ConfigMap named `axolotl-sft-config` with your configuration
3. Updates the Kubernetes job template with any resource requirements from your config
4. Applies the ConfigMap to your cluster
5. Applies the Job to your cluster
6. If the job fails to create, automatically cleans up the ConfigMap

### Prerequisites

- `kubectl` installed and configured
- Access to a Kubernetes cluster with GPU nodes
- Required secrets configured:
  - `wandb-api-key-secret` (for W&B logging)
  - `hf-token-secret` (for Hugging Face access)

### Job Configuration

The tool uses the predefined job template in `kubeconfigs/sft_job.yaml` which includes:

- Pod anti-affinity rules to avoid scheduling conflicts
- Volume mounts for model checkpoints and shared memory
- Environment variables for W&B and HF tokens
- Default resource allocations (overridable via config)

## Advantages Over Manual kubectl

- **Single Configuration File**: Define everything in your SFT config
- **Automatic Resource Management**: No need to manually create ConfigMaps
- **Error Handling**: Automatic cleanup on failures
- **Simplified Workflow**: One command instead of multiple kubectl operations
- **Resource Flexibility**: Override job resources directly in your training config

## Dependencies

- Python e3.12
- pyyaml e6.0
- simple-parsing e0.1.7
- kubectl (system dependency)