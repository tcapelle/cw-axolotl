#!/usr/bin/env python3
"""Main CLI entry point for CW CLI."""

import sys
from simple_parsing import ArgumentParser

from .config import (
    TrainConfig, GrpoConfig, GrpoRestartConfig, VerifiersConfig, EvalConfig, LogsConfig, StatusConfig, DeleteConfig, 
    ListConfig, JobsConfig, PodsConfig, InfoConfig, ResourcesConfig, GpuConfig, DevPodConfig
)
from .commands import (
    train_command, grpo_command, grpo_restart_command, verifiers_grpo_command, verifiers_eval_command, logs_command, status_command, delete_command,
    list_command, jobs_command, pods_command, info_command, resources_command, gpu_command, devpod_command
)


def main():
    """CW CLI - Kubernetes job management for ML training"""
    
    import argparse
    
    parser = ArgumentParser(
        description="CW CLI - Kubernetes job management for ML training",
        epilog="""Examples:
  # Training
  cw axolotl sft axolotl/sft_config.yaml              Train a model with SFT
  cw axolotl sft config.yaml --gpu 6                  Override GPU count
  cw axolotl sft config.yaml --gpu 4 --batch_size 8   Override multiple params
  cw axolotl grpo train axolotl/grpo_config.yaml      Train with GRPO (3-service deployment)
  cw axolotl grpo train config.yaml --services        Deploy only GRPO services (VLLM + Rewards)
  cw verifiers grpo verifiers/conf.yaml               Train with Verifiers GRPO
  cw verifiers grpo config.yaml --services            Deploy only Verifiers services (VLLM + Rewards)
  
  # GRPO service management
  cw axolotl grpo restart vllm                Restart VLLM service
  cw axolotl grpo restart rewards             Restart rewards service
  
  # Resource monitoring  
  cw jobs -A                                  List all jobs (all namespaces)
  cw pods -w -r                               Watch pods with resources
  cw nodes -n                                 Show detailed node info
  cw resources                                Show available cluster resources
  cw gpu                                      Watch nvidia-smi on training node
  cw gpu my-job -i 5                          Watch specific job's GPU every 5s
  
  # Job management
  cw describe                                 Select job to check status
  cw describe my-job -w                       Watch specific job status
  cw logs                                     Select job to view logs
  cw logs -j my-job                           Follow specific job logs
  cw delete                                   Select job to delete
  cw delete my-job                            Delete specific job
  
  # Development pods
  cw devpod start                             Create/start a devpod (interactive)
  cw devpod start mydev --gpu 4 --cpu 32     Create devpod with custom resources
  cw devpod ssh                               SSH to devpod (interactive selection)
  cw devpod ssh mydev                         SSH to specific devpod
  cw devpod list                              List all devpods
  cw devpod stop mydev                        Stop a devpod
  cw devpod delete mydev                      Delete a devpod
  
  # Quick workflows
  cw jobs | grep Running                      Find running jobs
  cw pods -A | grep gpu                       Find GPU pods""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Add subparsers for different commands
    subparsers_dict = parser.add_subparsers(
        title="Commands",
        description="Available commands (use 'cw <command> --help' for more info)"
    )
    
    # Training commands
    axolotl_parser = subparsers_dict.add_parser("axolotl", help="Train models")
    axolotl_subparsers = axolotl_parser.add_subparsers()
    
    sft_parser = axolotl_subparsers.add_parser("sft", help="Train a model with SFT")
    sft_parser.add_arguments(TrainConfig, dest="train_config")
    sft_parser.set_defaults(func=lambda args: train_command(args.train_config))
    
    axolotl_grpo_parser = axolotl_subparsers.add_parser("grpo", help="GRPO training and management")
    axolotl_grpo_subparsers = axolotl_grpo_parser.add_subparsers()
    
    # GRPO training subcommand
    grpo_train_parser = axolotl_grpo_subparsers.add_parser("train", help="Train a model with GRPO")
    grpo_train_parser.add_arguments(GrpoConfig, dest="grpo_config")
    grpo_train_parser.set_defaults(func=lambda args: grpo_command(args.grpo_config))
    
    # GRPO restart subcommand
    grpo_restart_parser = axolotl_grpo_subparsers.add_parser("restart", help="Restart GRPO services")
    grpo_restart_parser.add_arguments(GrpoRestartConfig, dest="grpo_restart_config")
    grpo_restart_parser.set_defaults(func=lambda args: grpo_restart_command(args.grpo_restart_config.service))
    
    # Verifiers training commands
    verifiers_parser = subparsers_dict.add_parser("verifiers", help="Verifiers training framework")
    verifiers_subparsers = verifiers_parser.add_subparsers()
    
    verifiers_grpo_parser = verifiers_subparsers.add_parser("grpo", help="Train with Verifiers GRPO")
    verifiers_grpo_parser.add_arguments(VerifiersConfig, dest="verifiers_config")
    verifiers_grpo_parser.set_defaults(func=lambda args: verifiers_grpo_command(args.verifiers_config))
    
    verifiers_eval_parser = verifiers_subparsers.add_parser("eval", help="Evaluate with Verifiers")
    verifiers_eval_parser.add_arguments(EvalConfig, dest="eval_config")
    verifiers_eval_parser.set_defaults(func=lambda args: verifiers_eval_command(args.eval_config))
    
    # Resource listing
    jobs_parser = subparsers_dict.add_parser("jobs", help="List jobs")
    jobs_parser.add_arguments(JobsConfig, dest="jobs_config")
    jobs_parser.set_defaults(func=lambda args: jobs_command(args.jobs_config.namespace, args.jobs_config.all_namespaces))
    
    pods_parser = subparsers_dict.add_parser("pods", help="List pods")
    pods_parser.add_arguments(PodsConfig, dest="pods_config")
    pods_parser.set_defaults(func=lambda args: pods_command(args.pods_config.namespace, args.pods_config.all_namespaces, args.pods_config.show_resources, args.pods_config.watch))
    
    nodes_parser = subparsers_dict.add_parser("nodes", help="List nodes")
    nodes_parser.add_arguments(InfoConfig, dest="info_config")
    nodes_parser.set_defaults(func=lambda args: info_command(args.info_config.nodes))
    
    resources_parser = subparsers_dict.add_parser("resources", help="Show available cluster resources")
    resources_parser.add_arguments(ResourcesConfig, dest="resources_config")
    resources_parser.set_defaults(func=lambda args: resources_command())
    
    gpu_parser = subparsers_dict.add_parser("gpu", help="Watch GPU usage on training nodes")
    gpu_parser.add_arguments(GpuConfig, dest="gpu_config")
    gpu_parser.set_defaults(func=lambda args: gpu_command(args.gpu_config.job, args.gpu_config.interval))
    
    # Job management
    logs_parser = subparsers_dict.add_parser("logs", help="View logs")
    logs_parser.add_arguments(LogsConfig, dest="logs_config")
    logs_parser.set_defaults(func=lambda args: logs_command(args.logs_config))
    
    describe_parser = subparsers_dict.add_parser("describe", help="Describe job")
    describe_parser.add_arguments(StatusConfig, dest="status_config")
    describe_parser.set_defaults(func=lambda args: status_command(args.status_config.job, args.status_config.watch, args.status_config.output))
    
    delete_parser = subparsers_dict.add_parser("delete", help="Delete job")
    delete_parser.add_arguments(DeleteConfig, dest="delete_config")
    delete_parser.set_defaults(func=lambda args: delete_command(args.delete_config.job))
    
    # Development pods
    devpod_parser = subparsers_dict.add_parser("devpod", help="Manage development pods")
    devpod_parser.add_arguments(DevPodConfig, dest="devpod_config")
    devpod_parser.set_defaults(func=lambda args: devpod_command(args.devpod_config))
    
    # Legacy
    list_parser = subparsers_dict.add_parser("list", help="List axolotl jobs")
    list_parser.add_arguments(ListConfig, dest="list_config") 
    list_parser.set_defaults(func=lambda args: list_command())
    
    # Parse arguments and execute the appropriate function
    args, unknown = parser.parse_known_args()
    
    if hasattr(args, 'func'):
        return args.func(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())