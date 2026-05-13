"""
Storage Stack: VPC, S3 buckets, ECR repositories.
"""
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_s3 as s3,
    aws_ecr as ecr,
    RemovalPolicy,
    Duration,
)
from constructs import Construct

SERVICE_NAMES = ["ml", "agent", "gateway", "frontend"]


class StorageStack(Stack):
    def __init__(self, scope: Construct, id: str, stage: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.stage = stage

        # ── VPC ──────────────────────────────────────────────────────────────
        self.vpc = ec2.Vpc(
            self, "VPC",
            max_azs=2,
            nat_gateways=1 if stage == "prod" else 0,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="Private", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=24),
            ],
        )

        # ── S3 — model artefacts ──────────────────────────────────────────────
        self.models_bucket = s3.Bucket(
            self, "ModelsBucket",
            bucket_name=f"trialmind-models-{stage}-{self.account}",
            versioned=True,
            removal_policy=RemovalPolicy.RETAIN if stage == "prod" else RemovalPolicy.DESTROY,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="archive-old-models",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INTELLIGENT_TIERING,
                            transition_after=Duration.days(30),
                        )
                    ],
                )
            ],
        )

        # ── ECR repositories ─────────────────────────────────────────────────
        self.ecr_repos = {}
        for name in SERVICE_NAMES:
            self.ecr_repos[name] = ecr.Repository(
                self, f"Ecr{name.capitalize()}",
                repository_name=f"trialmind-{name}-{stage}",
                removal_policy=RemovalPolicy.DESTROY,
                lifecycle_rules=[ecr.LifecycleRule(max_image_count=5)],
            )
