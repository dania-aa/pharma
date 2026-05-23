"""
Compute Stack: ECS Fargate cluster + services for all microservices.
"""
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_iam as iam,
    aws_ecr as ecr,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
    aws_elasticloadbalancingv2 as elbv2,
    Duration,
)
from constructs import Construct


class ComputeStack(Stack):
    def __init__(
        self, scope: Construct, id: str, stage: str, vpc: ec2.Vpc,
        db_secret: secretsmanager.ISecret,
        models_bucket: s3.Bucket,
        ecr_repos: dict,
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)

        self.stage = stage
        self.services = {}

        # ── ECS Cluster ───────────────────────────────────────────────────────
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc, cluster_name=f"trialmind-{stage}")

        # ── Task execution role ───────────────────────────────────────────────
        execution_role = iam.Role(
            self, "ExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy"),
            ],
        )
        db_secret.grant_read(execution_role)

        # ── Task role (app permissions) ───────────────────────────────────────
        task_role = iam.Role(
            self, "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        models_bucket.grant_read_write(task_role)
        task_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            resources=["*"],
        ))
        task_role.add_to_policy(iam.PolicyStatement(
            actions=["dynamodb:*"],
            resources=["*"],
        ))

        # ── Helper: build Fargate service ─────────────────────────────────────
        def make_service(name: str, port: int, cpu: int = 512, memory: int = 1024, env_vars: dict = None):
            task_def = ecs.FargateTaskDefinition(
                self, f"{name.capitalize()}Task",
                cpu=cpu, memory_limit_mib=memory,
                execution_role=execution_role,
                task_role=task_role,
            )
            container = task_def.add_container(
                f"{name}-container",
                image=ecs.ContainerImage.from_ecr_repository(ecr_repos[name]),
                logging=ecs.LogDrivers.aws_logs(stream_prefix=f"trialmind-{name}"),
                environment={
                    "STAGE": stage,
                    **(env_vars or {}),
                },
                secrets={
                    "DATABASE_URL": ecs.Secret.from_secrets_manager(db_secret, "connectionString"),
                },
                health_check=ecs.HealthCheck(
                    command=["CMD-SHELL", f"curl -f http://localhost:{port}/health || exit 1"],
                    interval=Duration.seconds(30),
                    timeout=Duration.seconds(5),
                    retries=3,
                ),
            )
            container.add_port_mappings(ecs.PortMapping(container_port=port))
            service = ecs_patterns.ApplicationLoadBalancedFargateService(
                self, f"{name.capitalize()}Service",
                cluster=cluster,
                task_definition=task_def,
                desired_count=1 if stage != "prod" else 2,
                public_load_balancer=name == "gateway",
                listener_port=80,
            )
            service.target_group.configure_health_check(path="/health")
            return service

        # ── Deploy services ───────────────────────────────────────────────────
        self.services["ml"] = make_service("ml", 8001, cpu=1024, memory=2048)
        self.services["agent"] = make_service(
            "agent", 8002, cpu=1024, memory=2048,
            env_vars={
                "ML_SERVICE_URL": f"http://{self.services['ml'].load_balancer.load_balancer_dns_name}",
            },
        )
        self.services["gateway"] = make_service(
            "gateway", 3000,
            env_vars={
                "ML_SERVICE_URL": f"http://{self.services['ml'].load_balancer.load_balancer_dns_name}",
                "AGENT_SERVICE_URL": f"http://{self.services['agent'].load_balancer.load_balancer_dns_name}",
            },
        )
        self.services["frontend"] = make_service("frontend", 80)
