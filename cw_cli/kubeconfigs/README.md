# Kubeconfigs Directory Structure

This directory contains Kubernetes configuration files organized by training framework.

## Current Structure

```
kubeconfigs/
├── axolotl/           # Axolotl framework configs
│   ├── sft_job.yaml   # SFT (Supervised Fine-Tuning) job
│   └── grpo/          # GRPO (Generalized Reward Policy Optimization) configs
│       ├── vllm-deployment.yaml      # VLLM inference server
│       ├── rewards-deployment.yaml   # Rewards server
│       └── training-job.yaml         # GRPO training job
└── README.md          # This file
```

## Future Framework Support

Additional frameworks can be added as subdirectories:

```
kubeconfigs/
├── axolotl/           # Axolotl framework (current)
├── transformers/      # HuggingFace Transformers (planned)
├── torchtune/         # PyTorch Tune (planned)
└── other-frameworks/  # Other ML training frameworks
```

## Usage

The CLI automatically references these configurations based on the training command used:

- `cw axolotl sft config.yaml` → uses `axolotl/sft_job.yaml`
- `cw axolotl grpo config.yaml` → uses `axolotl/grpo/*.yaml`
- Future: `cw transformers train config.yaml` → would use `transformers/*.yaml`

## Configuration Files

Each framework directory should contain:
- Job/Deployment YAML files for training
- Service YAML files for multi-service deployments (like GRPO)
- Any framework-specific configurations

All files should use the `cw-` prefix for resource names to enable proper cleanup and management.