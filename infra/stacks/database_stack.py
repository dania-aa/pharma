"""
Database Stack: RDS PostgreSQL + DynamoDB tables.
"""
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_dynamodb as dynamodb,
    aws_secretsmanager as secretsmanager,
    RemovalPolicy,
    Duration,
)
from constructs import Construct


class DatabaseStack(Stack):
    def __init__(self, scope: Construct, id: str, stage: str, vpc: ec2.Vpc, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.stage = stage

        # ── RDS PostgreSQL ────────────────────────────────────────────────────
        self.db_secret = rds.DatabaseSecret(
            self, "DbSecret",
            username="trialmind",
            secret_name=f"trialmind/{stage}/db-credentials",
        )

        db_sg = ec2.SecurityGroup(self, "DbSG", vpc=vpc, description="TrialMind RDS SG")
        db_sg.add_ingress_rule(ec2.Peer.ipv4(vpc.vpc_cidr_block), ec2.Port.tcp(5432))

        self.db_instance = rds.DatabaseInstance(
            self, "Postgres",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16_3
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3,
                ec2.InstanceSize.MEDIUM if stage == "prod" else ec2.InstanceSize.SMALL,
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[db_sg],
            credentials=rds.Credentials.from_secret(self.db_secret),
            database_name="trialmind",
            multi_az=stage == "prod",
            allocated_storage=100 if stage == "prod" else 20,
            backup_retention=Duration.days(7) if stage == "prod" else Duration.days(1),
            deletion_protection=stage == "prod",
            removal_policy=RemovalPolicy.RETAIN if stage == "prod" else RemovalPolicy.DESTROY,
        )

        # ── DynamoDB — conversation history ───────────────────────────────────
        self.conversations_table = dynamodb.Table(
            self, "ConversationsTable",
            table_name=f"trialmind-conversations-{stage}",
            partition_key=dynamodb.Attribute(name="id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl",
        )

        # ── DynamoDB — event log ──────────────────────────────────────────────
        self.events_table = dynamodb.Table(
            self, "EventsTable",
            table_name=f"trialmind-events-{stage}",
            partition_key=dynamodb.Attribute(name="id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="timestamp", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
