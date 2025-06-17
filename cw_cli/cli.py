#!/usr/bin/env python3
"""Main CLI entry point for CW CLI."""

import sys
from simple_parsing import ArgumentParser

from .config import (
    TrainConfig, GrpoConfig, LogsConfig, StatusConfig, DeleteConfig, 
    ListConfig, JobsConfig, PodsConfig, InfoConfig, ResourcesConfig
)
from .commands import (
    train_command, grpo_command, logs_command, status_command, delete_command,
    list_command, jobs_command, pods_command, info_command, resources_command
)


def main():
    """CW CLI - Kubernetes job management for ML training"""
    
    import argparse
    
    parser = ArgumentParser(
        description="CW CLI - Kubernetes job management for ML training",
        epilog="""Examples:
  # Training
  cw axolotl train axolotl/sft_config.yaml             Train a model
  cw axolotl train config.yaml --gpu 6                 Override GPU count
  cw axolotl train config.yaml --gpu 4 --batch_size 8  Override multiple params
  cw axolotl grpo axolotl/grpo_config.yaml             Train with GRPO (3-service deployment)
  
  # Resource monitoring  
  cw jobs -A                                  List all jobs (all namespaces)
  cw pods -w -r                               Watch pods with resources
  cw nodes -n                                 Show detailed node info
  cw resources                                Show available cluster resources
  cw resources -d                             Show detailed GPU breakdown
  cw resources -a                             Show only available nodes
  
  # Job management
  cw describe                                 Select job to check status
  cw describe my-job -w                       Watch specific job status
  cw logs                                     Select job to view logs
  cw logs -j my-job                           Follow specific job logs
  cw delete                                   Select job to delete
  cw delete my-job                            Delete specific job
  
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
    
    train_parser = axolotl_subparsers.add_parser("train", help="Train a model")
    train_parser.add_arguments(TrainConfig, dest="train_config")
    train_parser.set_defaults(func=lambda args: train_command(args.train_config))
    
    grpo_parser = axolotl_subparsers.add_parser("grpo", help="Train a model with GRPO")
    grpo_parser.add_arguments(GrpoConfig, dest="grpo_config")
    grpo_parser.set_defaults(func=lambda args: grpo_command(args.grpo_config))
    
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
    resources_parser.set_defaults(func=lambda args: resources_command(args.resources_config.detailed, args.resources_config.only_available))
    
    # Job management
    logs_parser = subparsers_dict.add_parser("logs", help="View logs")
    logs_parser.add_arguments(LogsConfig, dest="logs_config")
    logs_parser.set_defaults(func=lambda args: logs_command(args.logs_config.job, args.logs_config.no_follow))
    
    describe_parser = subparsers_dict.add_parser("describe", help="Describe job")
    describe_parser.add_arguments(StatusConfig, dest="status_config")
    describe_parser.set_defaults(func=lambda args: status_command(args.status_config.job, args.status_config.watch, args.status_config.output))
    
    delete_parser = subparsers_dict.add_parser("delete", help="Delete job")
    delete_parser.add_arguments(DeleteConfig, dest="delete_config")
    delete_parser.set_defaults(func=lambda args: delete_command(args.delete_config.job, args.delete_config.force))
    
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