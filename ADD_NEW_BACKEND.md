# Adding a New Training Backend to CW-CLI

This guide explains how to add a new training framework (like TRL, Transformers, or any other ML training backend) to the CW-CLI system.

## Overview

The CW-CLI architecture makes it straightforward to add new backends by implementing a few key components:
1. **Framework Implementation** - Core logic for your backend
2. **Kubernetes YAML Files** - Deployment configurations
3. **Registration** - Plugging into the CLI system
4. **CLI Integration** - Adding commands (optional)

## Step-by-Step Guide

### Step 1: Implement Your Framework Class

Create a new framework class that inherits from `BaseTrainingFramework`:

```python
# cw_cli/core/framework.py (add to existing file)

class TRLFramework(BaseTrainingFramework):
    """TRL (Transformer Reinforcement Learning) framework implementation."""
    
    def __init__(self, kubeconfig_dir: Path):
        super().__init__("trl", kubeconfig_dir)
    
    def validate_config(self, config_data: Dict[str, Any], training_type: TrainingType) -> bool:
        """Validate TRL-specific configuration."""
        if training_type == TrainingType.SFT:
            # TRL SFT requires a model and dataset
            return "model_name" in config_data and "dataset_name" in config_data
        elif training_type == TrainingType.GRPO:
            # TRL RLHF requires reward model
            return "reward_model" in config_data
        return True
    
    def prepare_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove TRL-specific cluster fields."""
        clean_config = config_data.copy()
        # Remove fields that are used for cluster deployment but not TRL training
        cluster_fields = ['image', 'gpu', 'cpu', 'memory', 'resources']
        for field in cluster_fields:
            clean_config.pop(field, None)
        return clean_config
    
    def get_configmap_name(self, training_type: TrainingType) -> str:
        """Get ConfigMap name for TRL."""
        if training_type == TrainingType.SFT:
            return "cw-trl-train-sft-config"
        elif training_type == TrainingType.GRPO:
            return "cw-trl-train-rlhf-config"
        else:
            raise ValueError(f"Unsupported training type: {training_type}")
    
    def get_job_name(self, training_type: TrainingType) -> str:
        """Get Job name for TRL."""
        if training_type == TrainingType.SFT:
            return "cw-trl-train-sft"
        elif training_type == TrainingType.GRPO:
            return "cw-trl-train-rlhf"
        else:
            raise ValueError(f"Unsupported training type: {training_type}")
    
    def get_yaml_templates(self, training_type: TrainingType) -> List[Path]:
        """Get YAML templates for TRL."""
        if training_type == TrainingType.SFT:
            return [self.kubeconfig_dir / "trl" / "sft_job.yaml"]
        elif training_type == TrainingType.GRPO:
            trl_dir = self.kubeconfig_dir / "trl" / "rlhf"
            return [
                trl_dir / "reward-model-deployment.yaml",
                trl_dir / "rlhf-training-job.yaml"
            ]
        else:
            raise ValueError(f"Unsupported training type: {training_type}")
    
    def get_default_image(self) -> str:
        """Get default image for TRL."""
        return 'huggingface/transformers-pytorch-gpu:latest'
```

### Step 2: Create Kubernetes YAML Files

Create framework-specific YAML files in the kubeconfigs directory:

```bash
mkdir -p cw_cli/kubeconfigs/trl/rlhf
```

#### SFT Job Example (`cw_cli/kubeconfigs/trl/sft_job.yaml`):

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: cw-trl-train-sft
  labels:
    app: trl-train
    task: training
spec:
  ttlSecondsAfterFinished: 0
  backoffLimit: 0   
  template:
    metadata:
      labels:
        app: trl-train
        task: training
    spec:
      containers:
      - name: trl-train-container
        image: huggingface/transformers-pytorch-gpu:latest
        workingDir: /workspace
        command: ["python"]
        args:
          - "-c"
          - |
            import yaml
            import os
            from trl import SFTTrainer
            from transformers import AutoTokenizer, AutoModelForCausalLM
            
            # Load config
            with open('/mnt/trl-config/config.yaml', 'r') as f:
                config = yaml.safe_load(f)
            
            # Initialize model and tokenizer
            model = AutoModelForCausalLM.from_pretrained(config['model_name'])
            tokenizer = AutoTokenizer.from_pretrained(config['model_name'])
            
            # Create trainer
            trainer = SFTTrainer(
                model=model,
                tokenizer=tokenizer,
                dataset_text_field="text",
                **config.get('trainer_args', {})
            )
            
            # Train
            trainer.train()
            
            # Save model
            output_dir = config.get('output_dir', '/model-checkpoints/trl-sft')
            trainer.save_model(output_dir)
            
        env:
        - name: WANDB_API_KEY
          valueFrom:
            secretKeyRef:
              name: wandb-api-key-secret
              key: WANDB_API_KEY
        - name: HF_TOKEN
          valueFrom:
            secretKeyRef:
              name: hf-token-secret
              key: HF_TOKEN
        volumeMounts:
          - name: config-volume
            mountPath: /mnt/trl-config
          - name: model-checkpoints
            mountPath: /model-checkpoints
          - name: dshm
            mountPath: /dev/shm
        resources:
          limits:
            nvidia.com/gpu: "8"
            cpu: "32"
            memory: "1600Gi"
          requests:
            nvidia.com/gpu: "8"
            cpu: "32"
            memory: "1600Gi"
      volumes:
        - name: model-checkpoints
          persistentVolumeClaim:
            claimName: model-checkpoints
        - name: dshm
          emptyDir:
            medium: Memory
            sizeLimit: 500Gi
        - name: config-volume
          configMap:
            name: cw-trl-train-sft-config
      restartPolicy: OnFailure
  backoffLimit: 0
```

#### RLHF Multi-Service Example (`cw_cli/kubeconfigs/trl/rlhf/rlhf-training-job.yaml`):

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: cw-trl-train-rlhf
  labels:
    app: trl-train
    task: training
spec:
  ttlSecondsAfterFinished: 0
  backoffLimit: 0   
  template:
    metadata:
      labels:
        app: trl-train
        task: training
    spec:
      initContainers:
      - name: wait-for-reward-model
        image: busybox:1.28
        command: ['sh', '-c', 'until nc -zv cw-trl-reward-model-service 8000; do echo "Waiting for reward model..."; sleep 5; done']
      containers:
      - name: trl-rlhf-container
        image: huggingface/transformers-pytorch-gpu:latest
        workingDir: /workspace
        command: ["python"]
        args:
          - "-c"
          - |
            import yaml
            import requests
            from trl import PPOTrainer, PPOConfig
            from transformers import AutoTokenizer, AutoModelForCausalLM
            
            # Load config
            with open('/mnt/trl-config/config.yaml', 'r') as f:
                config = yaml.safe_load(f)
            
            # Initialize model and tokenizer
            model = AutoModelForCausalLM.from_pretrained(config['model_name'])
            tokenizer = AutoTokenizer.from_pretrained(config['model_name'])
            
            # Create PPO config
            ppo_config = PPOConfig(**config.get('ppo_config', {}))
            
            # Create trainer with remote reward model
            trainer = PPOTrainer(
                config=ppo_config,
                model=model,
                tokenizer=tokenizer,
                reward_model_url=os.environ['REWARD_MODEL_URL']
            )
            
            # Train
            trainer.train()
            
            # Save model
            output_dir = config.get('output_dir', '/model-checkpoints/trl-rlhf')
            trainer.save_model(output_dir)
            
        env:
        - name: WANDB_API_KEY
          valueFrom:
            secretKeyRef:
              name: wandb-api-key-secret
              key: WANDB_API_KEY
        - name: HF_TOKEN
          valueFrom:
            secretKeyRef:
              name: hf-token-secret
              key: HF_TOKEN
        - name: REWARD_MODEL_URL
          value: "http://cw-trl-reward-model-service:8000"
        volumeMounts:
          - name: config-volume
            mountPath: /mnt/trl-config
          - name: model-checkpoints
            mountPath: /model-checkpoints
          - name: dshm
            mountPath: /dev/shm
        resources:
          limits:
            nvidia.com/gpu: "8"
            cpu: "64"
            memory: "2000Gi"
          requests:
            nvidia.com/gpu: "8"
            cpu: "64"
            memory: "1800Gi"
      volumes:
        - name: model-checkpoints
          persistentVolumeClaim:
            claimName: model-checkpoints
        - name: dshm
          emptyDir:
            medium: Memory
            sizeLimit: 200Gi
        - name: config-volume
          configMap:
            name: cw-trl-train-rlhf-config
      restartPolicy: OnFailure
  backoffLimit: 0
```

### Step 3: Register Your Framework

Add your framework to the registry:

```python
# cw_cli/core/registry.py (modify existing _register_builtin_frameworks method)

def _register_builtin_frameworks(self):
    """Register built-in frameworks."""
    self.register("axolotl", AxolotlFramework(self.kubeconfig_dir))
    self.register("verifiers", VerifiersFramework(self.kubeconfig_dir))
    self.register("trl", TRLFramework(self.kubeconfig_dir))  # Add this line
```

### Step 4: Add CLI Commands (Optional)

Add CLI commands for your framework by modifying the CLI:

```python
# cw_cli/cli.py (add after verifiers commands)

# TRL training commands
trl_parser = subparsers_dict.add_parser("trl", help="TRL training framework")
trl_subparsers = trl_parser.add_subparsers()

trl_sft_parser = trl_subparsers.add_parser("sft", help="Train with TRL SFT")
trl_sft_parser.add_arguments(TrainConfig, dest="train_config")
trl_sft_parser.set_defaults(func=lambda args: trl_sft_command(args.train_config))

trl_rlhf_parser = trl_subparsers.add_parser("rlhf", help="Train with TRL RLHF")
trl_rlhf_parser.add_arguments(GrpoConfig, dest="grpo_config")  # Reuse GrpoConfig for multi-service
trl_rlhf_parser.set_defaults(func=lambda args: trl_rlhf_command(args.grpo_config))
```

Add the command implementations:

```python
# cw_cli/commands.py (add new functions)

def trl_sft_command(train_config) -> int:
    """Train a model with TRL SFT using new architecture."""
    from .core.commands import train_sft_command
    from .core.exceptions import format_error_for_user, get_error_suggestions
    
    try:
        return train_sft_command(
            framework_name="trl",
            config_path=train_config.config,
            pull_latest=train_config.pull
        )
    except Exception as e:
        console.print(format_error_for_user(e), style="red")
        suggestion = get_error_suggestions(e)
        if suggestion:
            console.print(suggestion, style="yellow")
        return 1

def trl_rlhf_command(grpo_config) -> int:
    """Train a model with TRL RLHF using new architecture."""
    from .core.commands import train_grpo_command
    from .core.exceptions import format_error_for_user, get_error_suggestions
    
    try:
        return train_grpo_command(
            framework_name="trl",
            config_path=grpo_config.config,
            pull_latest=grpo_config.pull,
            services_only=grpo_config.services
        )
    except Exception as e:
        console.print(format_error_for_user(e), style="red")
        suggestion = get_error_suggestions(e)
        if suggestion:
            console.print(suggestion, style="yellow")
        return 1
```

### Step 5: Create Configuration Schema

Define your framework's configuration format:

```yaml
# Example TRL SFT config (trl_sft_config.yaml)
model_name: "microsoft/DialoGPT-medium"
dataset_name: "imdb"
output_dir: "/model-checkpoints/trl-sft-dialo"

# TRL-specific training arguments
trainer_args:
  learning_rate: 2e-5
  num_train_epochs: 3
  per_device_train_batch_size: 4
  gradient_accumulation_steps: 8
  warmup_steps: 100
  logging_steps: 10
  save_steps: 500
  max_seq_length: 512

# Resource overrides (optional)
gpu: 4
cpu: "32"
memory: "500Gi"
image: "huggingface/transformers-pytorch-gpu:4.21.0"
```

```yaml
# Example TRL RLHF config (trl_rlhf_config.yaml)
model_name: "microsoft/DialoGPT-medium"
reward_model: "sentiment-analysis-model"
output_dir: "/model-checkpoints/trl-rlhf-dialo"

# PPO-specific configuration
ppo_config:
  learning_rate: 1e-5
  batch_size: 16
  mini_batch_size: 4
  gradient_accumulation_steps: 1
  ppo_epochs: 4
  max_grad_norm: 1.0
  adap_kl_ctrl: true
  init_kl_coef: 0.2

# Resource requirements
gpu: 8
cpu: "64"
memory: "1000Gi"
```

## Usage Examples

Once implemented, users can use your new backend:

```bash
# TRL SFT training
cw trl sft trl_sft_config.yaml

# TRL RLHF training
cw trl rlhf trl_rlhf_config.yaml

# With overrides
cw trl sft config.yaml --gpu 4 --learning_rate 1e-5

# Services only (for RLHF)
cw trl rlhf config.yaml --services
```

## Advanced: Plugin-Based Approach

For external frameworks, you can create a plugin:

```python
# ~/.cw-cli/plugins/my_trl_plugin/__init__.py

from cw_cli.core.plugins import FrameworkPlugin
from cw_cli.core.framework import TrainingType
from .trl_framework import TRLFramework

class TRLPlugin(FrameworkPlugin):
    @property
    def name(self):
        return "trl-plugin"
    
    @property
    def version(self):
        return "1.0.0"
    
    @property
    def description(self):
        return "TRL framework integration for CW-CLI"
    
    def get_framework_class(self):
        return TRLFramework
    
    def get_supported_training_types(self):
        return [TrainingType.SFT, TrainingType.GRPO]
    
    def initialize(self, context):
        pass
    
    def cleanup(self):
        pass

# Plugin entry point
def get_plugin():
    return TRLPlugin()
```

## Testing Your Backend

1. **Create test configs** with your framework's format
2. **Test resource injection** with `--gpu`, `--memory` overrides
3. **Verify YAML generation** works correctly
4. **Test deployment** in your Kubernetes cluster
5. **Run the architecture test** to ensure integration works:

```bash
python test_architecture.py
```

## Best Practices

### 1. **Framework-Specific Design**
- Don't try to make your backend generic
- Use framework-specific commands, environment variables, and paths
- Leverage your framework's native configuration format

### 2. **Resource Management**
- Support resource overrides (`--gpu`, `--cpu`, `--memory`)
- Provide sensible defaults for your framework
- Consider different resource profiles for different training types

### 3. **Error Handling**
- Implement thorough config validation in `validate_config()`
- Provide helpful error messages for common mistakes
- Test edge cases and invalid configurations

### 4. **Container Images**
- Use official or well-maintained images when possible
- Pin to specific versions for reproducibility
- Include all necessary dependencies for your framework

### 5. **Documentation**
- Document your configuration format
- Provide example configs for common use cases
- Include troubleshooting guides

## Conclusion

The CW-CLI architecture makes it straightforward to add new training backends while maintaining:

- **Framework specificity** - Each backend can be optimized for its use case
- **Consistent interface** - All backends work with the same CLI patterns
- **Resource flexibility** - Dynamic resource allocation works across frameworks
- **Extensibility** - Easy to add new training types and deployment patterns

The key is to implement the `BaseTrainingFramework` interface, create framework-specific YAML files, and register your framework with the system. The rest of the architecture (configuration management, resource injection, deployment strategies) works automatically with your new backend.