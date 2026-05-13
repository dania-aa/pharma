#!/usr/bin/env python3
"""
TrialMind AWS CDK Application.
Deploys all infrastructure to AWS.

Usage:
    cd infra
    pip install -r requirements.txt
    cdk bootstrap
    cdk deploy --all
"""
import aws_cdk as cdk
from stacks.database_stack import DatabaseStack
from stacks.compute_stack import ComputeStack
from stacks.storage_stack import StorageStack
from stacks.monitoring_stack import MonitoringStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account") or None,
    region=app.node.try_get_context("region") or "us-east-1",
)

stage = app.node.try_get_context("stage") or "dev"

storage = StorageStack(app, f"TrialMind-Storage-{stage}", env=env, stage=stage)
database = DatabaseStack(app, f"TrialMind-Database-{stage}", env=env, stage=stage,
                         vpc=storage.vpc)
compute = ComputeStack(app, f"TrialMind-Compute-{stage}", env=env, stage=stage,
                       vpc=storage.vpc,
                       db_secret=database.db_secret,
                       models_bucket=storage.models_bucket,
                       ecr_repos=storage.ecr_repos)
MonitoringStack(app, f"TrialMind-Monitoring-{stage}", env=env, stage=stage,
                services=compute.services)

app.synth()
