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

#### `cw axolotl train <config> [--pull]`
Launch a Supervised Fine-Tuning job.

```bash
# Basic usage
cw axolotl train my_config.yaml

# With resource overrides
cw axolotl train my_config.yaml --gpu 4 --cpu 32 --memory 500Gi

# With training parameter overrides
cw axolotl train my_config.yaml --learning_rate 2e-5 --batch_size 8

# Pull latest axolotl_dev code before training
cw axolotl train my_config.yaml --pull
```

#### `cw axolotl grpo <config> [--pull]`
Launch a GRPO training job with VLLM server, rewards server, and training components.

```bash
# Basic GRPO training
cw axolotl grpo grpo_config.yaml

# With custom resources
cw axolotl grpo grpo_config.yaml --gpu 8 --memory 1000Gi

# Pull latest code for all services (training, vllm, rewards)
cw axolotl grpo grpo_config.yaml --pull
```

**Note**: The `--pull` flag executes `git pull origin main` in `/app/axolotl_dev` before starting any services, ensuring you're using the latest code.

### Monitoring Commands

#### `cw jobs [-n <ns>] [-A|--all-namespaces]`
List all jobs in the cluster.

```bash
# All jobs in default namespace
cw jobs

# Jobs in specific namespace
cw jobs -n my-namespace

# Jobs across all namespaces
cw jobs -A
```

#### `cw pods [-w|--watch] [-n <ns>] [-A|--all-namespaces] [-r|--show-resources]`
List all pods with resource information.

```bash
# List pods once
cw pods

# Watch pods in real-time (refreshes every 2 seconds)
cw pods -w

# Show resource requests/limits
cw pods -r

# Pods in specific namespace
cw pods -n my-namespace

# Pods across all namespaces
cw pods -A

# Watch pods with resources across all namespaces
cw pods -w -r -A
```

#### `cw resources`
Show available cluster resources (GPU, CPU, Memory) with detailed breakdown.

```bash
# Show cluster resources with detailed GPU breakdown
cw resources
```

Example output:
```
🖥️ Cluster Resource Summary
┌─────────┬──────────┬───────────┬────────────┬──────────┬─────────────────────────┐
│ Node    │ Status   │ GPUs      │ CPU        │ Memory   │ Availability            │
├─────────┼──────────┼───────────┼────────────┼──────────┼─────────────────────────┤
│ g122466 │ Ready    │ 5/8 free  │ 128.0 cores│ 2062Gi   │ ⚠️  Partial (5 GPUs)   │
│ gd8ff0c │ Ready    │ 6/8 free  │ 128.0 cores│ 2062Gi   │ ⚠️  Partial (6 GPUs)   │
│ gd96896 │ Ready    │ 6/8 free  │ 128.0 cores│ 2062Gi   │ ⚠️  Partial (6 GPUs)   │
│ gf43324 │ Ready    │ 8/8 free  │ 128.0 cores│ 2062Gi   │ ✅ Full node (8+ GPUs) │
└─────────┴──────────┴───────────┴────────────┴──────────┴─────────────────────────┘

📊 Summary:
• Available full nodes (8+ GPUs): 1
• Total free GPUs: 25
• GPU nodes: 15
```

#### `cw nodes [-n|--nodes]`
Show cluster information and node details.

```bash
# Basic cluster overview
cw nodes

# Detailed node information
cw nodes -n
```

### Management Commands

#### `cw describe [job] [-w|--watch] [-o <format>]`
Check detailed job status.

```bash
# Interactive job selection
cw describe

# Specific job
cw describe my-training-job

# Watch job status in real-time
cw describe my-training-job -w

# Output in different formats
cw describe my-training-job -o yaml
cw describe my-training-job -o json
```

#### `cw logs [-j <job>] [-n|--no-follow]`
View job logs.

```bash
# Interactive job selection (follows by default)
cw logs

# Specific job (follows by default)
cw logs -j my-training-job

# Show logs once without following
cw logs -j my-training-job -n
```

#### `cw delete [job] [--force]`
Delete jobs and associated resources.

```bash
# Interactive job selection
cw delete

# Specific job
cw delete my-training-job

# Force delete any CW resources (jobs, deployments, services)
cw delete --force
```

**Note**: The `--force` flag allows you to select and delete any CW-prefixed resources, including stuck deployments or services that weren't properly cleaned up.

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
cw logs  # Interactive selection, follows by default

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
cw logs -j grpo-training-job
cw logs -j grpo-vllm-server
cw logs -j grpo-rewards-server

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
cw logs -j exp1
cw logs -j exp2
cw logs -j exp3
```

## Troubleshooting

### Common Issues

1. **Job fails to start**: Check that required secrets exist and cluster has available resources
2. **Out of memory**: Reduce `micro_batch_size` or increase `gradient_accumulation_steps`
3. **GPU allocation fails**: Verify GPU availability with `cw nodes`
4. **Logs not showing**: Wait for pod to be ready, or check pod status with `cw pods`

### Debug Commands

```bash
# Check available cluster resources
cw resources

# Check detailed resource breakdown
cw resources -d

# Check cluster nodes
cw nodes

# Check all pods status
cw pods

# Check specific job details
cw describe my-job

# Check job logs
cw logs -j my-job

# Force cleanup stuck resources
cw delete --force
```

### Resource Planning

Before launching training jobs, use `cw resources` to check availability:

```bash
# Check cluster resources and availability
cw resources
```

This helps you:
- See which nodes have enough free GPUs for your job
- Check available memory and CPU capacity
- Identify nodes that might be unavailable due to scheduling issues
- Plan resource allocation for multiple concurrent jobs

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
