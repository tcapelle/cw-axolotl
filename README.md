# CW-Axolotl-CLI - Unified Axolotl Training CLI

A Kubernetes-based command-line interface for managing machine learning training jobs, specifically designed for [Axolotl](https://github.com/OpenAccess-AI-Collective/axolotl) fine-tuning workflows on GPU clusters.

## Features

- 🚀 **Simple Training Deployment**: Launch SFT and GRPO training jobs with a single command
- 🎯 **Resource-Aware**: Automatic GPU, CPU, and memory management
- 📊 **Real-time Monitoring**: Live cluster status, job progress, and resource utilization
- 🔧 **Interactive Management**: Easy job selection, log viewing, and cleanup
- 🛡️ **Safe Operations**: Only manages CW-prefixed resources to prevent accidents
- ⚡ **Development-Friendly**: Command-line parameter overrides for quick experimentation

## Installation

```bash
pip install -e .
```

## Prerequisites

- `kubectl` installed and configured
- Access to a Kubernetes cluster with GPU nodes
- Required Kubernetes secrets:
  - `wandb-api-key-secret` (for Weights & Biases logging)
  - `hf-token-secret` (for Hugging Face model access)

## Quick Start

### 1. Launch a Training Job

```bash
# Basic SFT training
cw axolotl train axolotl/sft_config.yaml

# GRPO training with multi-service deployment
cw axolotl grpo axolotl/grpo_config.yaml

# Override parameters from command line
cw axolotl train config.yaml --learning_rate 1e-5 --gpu 8 --memory 1000Gi
```

### 2. Monitor Your Jobs

```bash
# List all jobs
cw jobs

# Monitor pods in real-time
cw pods -w

# Check cluster resources
cw nodes

# View job logs
cw logs my-training-job

# Follow logs in real-time
cw logs my-training-job -f
```

### 3. Manage Jobs

```bash
# Describe job status
cw describe my-training-job

# Delete a job and cleanup resources
cw delete my-training-job

# List only CW-managed jobs
cw list
```

## Commands Reference

### Training Commands

#### `cw axolotl train <config>`
Launch a Supervised Fine-Tuning job.

```bash
# Basic usage
cw axolotl train my_config.yaml

# With resource overrides
cw axolotl train my_config.yaml --gpu 4 --cpu 32 --memory 500Gi

# With training parameter overrides
cw axolotl train my_config.yaml --learning_rate 2e-5 --batch_size 8
```

#### `cw axolotl grpo <config>`
Launch a GRPO training job with VLLM server, rewards server, and training components.

```bash
# Basic GRPO training
cw axolotl grpo grpo_config.yaml

# With custom resources
cw axolotl grpo grpo_config.yaml --gpu 8 --memory 1000Gi
```

### Monitoring Commands

#### `cw jobs [--namespace <ns>]`
List all jobs in the cluster.

```bash
# All jobs
cw jobs

# Jobs in specific namespace
cw jobs --namespace my-namespace
```

#### `cw pods [-w|--watch] [--namespace <ns>]`
List all pods with resource information.

```bash
# List pods once
cw pods

# Watch pods in real-time (refreshes every 2 seconds)
cw pods -w

# Pods in specific namespace
cw pods --namespace my-namespace
```

#### `cw nodes`
Show cluster information and node details.

```bash
cw nodes
```

Example output:
```
Cluster Overview:
┌─────────────┬───────┐
│ GPU Type    │ Count │
├─────────────┼───────┤
│ H100        │ 32    │
│ A100        │ 16    │
└─────────────┴───────┘

Node Details:
┌──────────────┬────────┬──────────┬────────────┬────────┐
│ Node         │ GPUs   │ CPU      │ Memory     │ Status │
├──────────────┼────────┼──────────┼────────────┼────────┤
│ gpu-node-1   │ 8xH100 │ 128 CPUs │ 2048Gi     │ Ready  │
│ gpu-node-2   │ 8xA100 │ 96 CPUs  │ 1536Gi     │ Ready  │
└──────────────┴────────┴──────────┴────────────┴────────┘
```

### Management Commands

#### `cw describe [job]`
Check detailed job status.

```bash
# Interactive job selection
cw describe

# Specific job
cw describe my-training-job
```

#### `cw logs [job] [-f|--follow]`
View job logs.

```bash
# Interactive job selection
cw logs

# Specific job
cw logs my-training-job

# Follow logs in real-time
cw logs my-training-job -f
```

#### `cw delete [job]`
Delete jobs and associated resources.

```bash
# Interactive job selection
cw delete

# Specific job
cw delete my-training-job
```

#### `cw list`
List only CW-managed jobs (legacy command).

```bash
cw list
```

## Configuration

### Training Config Structure

Your Axolotl config files can include standard parameters plus optional resource specifications:

```yaml
# Standard Axolotl configuration
base_model: Qwen/Qwen2.5-7B-Instruct
model_type: AutoModelForCausalLM
tokenizer_type: AutoTokenizer

datasets:
  - path: my_dataset
    type: chat_template

# Training parameters
learning_rate: 2e-5
lr_scheduler: cosine
num_epochs: 3
micro_batch_size: 1
gradient_accumulation_steps: 8

# Optional: Resource requirements (overrides job defaults)
gpu: 4
cpu: "32"
memory: "500Gi"

# Or use full resources block
resources:
  limits:
    nvidia.com/gpu: "4"
    cpu: "32"
    memory: "500Gi"
  requests:
    nvidia.com/gpu: "4"
    cpu: "32"
    memory: "500Gi"
```

### Command-Line Overrides

Any parameter in your config can be overridden from the command line:

```bash
# Override training parameters
cw axolotl train config.yaml \
  --learning_rate 1e-5 \
  --num_epochs 5 \
  --micro_batch_size 2

# Override resource requirements
cw axolotl train config.yaml \
  --gpu 8 \
  --cpu 64 \
  --memory 1000Gi

# Mix training and resource overrides
cw axolotl train config.yaml \
  --learning_rate 3e-5 \
  --gpu 2 \
  --gradient_accumulation_steps 16
```

## Examples

### Example 1: Basic SFT Training

```bash
# Launch training job
cw axolotl train axolotl/sft_config.yaml

# Monitor progress
cw pods -w

# View logs
cw logs  # Will prompt to select the job

# Check detailed status
cw describe
```

### Example 2: Resource-Intensive Training

```bash
# Launch with specific resources
cw axolotl train large_model_config.yaml \
  --gpu 8 \
  --cpu 128 \
  --memory 2000Gi \
  --learning_rate 1e-5

# Monitor cluster utilization
cw nodes
cw jobs
```

### Example 3: GRPO Training Workflow

```bash
# Launch GRPO training (creates 3 services)
cw axolotl grpo axolotl/grpo_config.yaml

# Monitor all components
cw pods -w

# Check logs for each component
cw jobs  # See all 3 services
cw logs grpo-training-job
cw logs grpo-vllm-server
cw logs grpo-rewards-server

# Cleanup when done
cw delete grpo-training-job  # Cleans up all related resources
```

### Example 4: Development Workflow

```bash
# Quick experimentation with parameter sweeps
cw axolotl train base_config.yaml --learning_rate 1e-5 --run_name exp1
cw axolotl train base_config.yaml --learning_rate 2e-5 --run_name exp2
cw axolotl train base_config.yaml --learning_rate 5e-5 --run_name exp3

# Monitor all experiments
cw jobs
cw pods

# Compare logs
cw logs exp1
cw logs exp2
cw logs exp3
```

## Troubleshooting

### Common Issues

1. **Job fails to start**: Check that required secrets exist and cluster has available resources
2. **Out of memory**: Reduce `micro_batch_size` or increase `gradient_accumulation_steps`
3. **GPU allocation fails**: Verify GPU availability with `cw nodes`
4. **Logs not showing**: Wait for pod to be ready, or check pod status with `cw pods`

### Debug Commands

```bash
# Check cluster resources
cw nodes

# Check all pods status
cw pods

# Check specific job details
cw describe my-job

# Check job logs
cw logs my-job
```

## Development

### Project Structure

```
cw_cli/
├── cli.py          # Main CLI interface
├── commands.py     # Command implementations
├── cluster.py      # Cluster information and node management
├── pods.py         # Pod listing and monitoring
├── config.py       # Configuration management
├── utils.py        # Utility functions
├── display.py      # Output formatting and display
└── kubeconfigs/    # Kubernetes deployment templates
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with your Kubernetes cluster
5. Submit a pull request

## License

This project is licensed under the MIT License.
