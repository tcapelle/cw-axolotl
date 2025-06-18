# CW-Axolotl-CLI - Unified Axolotl Training CLI

> Note: This is my own research CLI tool that leverages tcapelle/triton_eval repo. It is axolotl based but is using my own docker images and rewards functions. It would be easy to adapt to use generic axolotl training anyway.

A Kubernetes-based command-line interface for managing machine learning training jobs, specifically designed for [Axolotl](https://github.com/OpenAccess-AI-Collective/axolotl) fine-tuning workflows on GPU clusters.

## Features

- 🚀 **Simple Training Deployment**: Launch SFT and GRPO training jobs with a single command
- 🎯 **Resource-Aware**: Automatic GPU, CPU, and memory management with availability checking
- 📊 **Real-time Monitoring**: Live cluster status, job progress, and resource utilization
- 🔧 **Interactive Management**: Easy job selection, log viewing, and cleanup
- 🛡️ **Safe Operations**: Only manages CW-prefixed resources to prevent accidents
- ⚡ **Development-Friendly**: Command-line parameter overrides and latest code pulling
- 📈 **Resource Planning**: Check available cluster capacity before launching jobs
- 🧹 **Smart Cleanup**: Automatic log saving and force cleanup for stuck resources

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
cw axolotl sft axolotl/sft_config.yaml

# GRPO training with multi-service deployment
cw axolotl grpo axolotl/grpo_config.yaml

# Override parameters from command line
cw axolotl sft config.yaml --learning_rate 1e-5 --gpu 8 --memory 1000Gi
```

### 2. Monitor Your Jobs

```bash
# List all jobs
cw jobs

# Monitor pods in real-time
cw pods -w

# Check available cluster resources
cw resources

# Check cluster nodes
cw nodes

# View job logs (interactive selection)
cw logs

# Follow logs in real-time (default behavior)
cw logs -j my-training-job
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
- `cw axolotl sft <config> [--pull]` - Launch SFT training
- `cw axolotl grpo <config> [--pull]` - Launch GRPO training (3 services)

### Monitoring Commands  
- `cw resources` - Show cluster resources and GPU availability
- `cw jobs [-A]` - List jobs (use `-A` for all namespaces)
- `cw pods [-w] [-r] [-A]` - List pods (use `-w` to watch, `-r` for resources)
- `cw nodes [-n]` - Show cluster nodes (use `-n` for details)

### Management Commands
- `cw logs [-j <job>] [-n]` - View logs (interactive selection or specific job)
- `cw describe [job] [-w] [-o <format>]` - Check job status
- `cw delete [job] [--force]` - Delete jobs (use `--force` for stuck resources)

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
cw axolotl sft config.yaml \
  --learning_rate 1e-5 \
  --num_epochs 5 \
  --micro_batch_size 2

# Override resource requirements
cw axolotl sft config.yaml \
  --gpu 8 \
  --cpu 64 \
  --memory 1000Gi

# Mix training and resource overrides
cw axolotl sft config.yaml \
  --learning_rate 3e-5 \
  --gpu 2 \
  --gradient_accumulation_steps 16
```

## Usage Examples

```bash
# Basic SFT training
cw axolotl sft axolotl/sft_config.yaml

# GRPO training with 3 services
cw axolotl grpo axolotl/grpo_config.yaml

# Override resources
cw axolotl sft config.yaml --gpu 8 --memory 1200Gi

# Pull latest code before training
cw axolotl sft config.yaml --pull

# Monitor cluster resources
cw resources

# Follow specific job logs
cw logs -j my-training-job

# Clean up resources
cw delete --force
```

## License

This project is licensed under the MIT License.
