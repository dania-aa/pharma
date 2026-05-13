"""
Monitoring Stack: CloudWatch dashboards and alarms.
"""
from aws_cdk import (
    Stack,
    aws_cloudwatch as cw,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    Duration,
)
from constructs import Construct


class MonitoringStack(Stack):
    def __init__(self, scope: Construct, id: str, stage: str, services: dict, **kwargs):
        super().__init__(scope, id, **kwargs)

        alarm_topic = sns.Topic(self, "AlarmTopic", topic_name=f"trialmind-alarms-{stage}")

        widgets = []

        for name, svc in services.items():
            # 5xx error rate alarm
            error_alarm = cw.Alarm(
                self, f"{name.capitalize()}5xxAlarm",
                alarm_name=f"trialmind-{name}-5xx-{stage}",
                metric=svc.load_balancer.metric_http_code_elb(
                    code=cw.HttpCodeElb.ELB_5_XX_COUNT,
                    period=Duration.minutes(1),
                ),
                threshold=10,
                evaluation_periods=2,
                comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
                treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
            )
            error_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))

            # Dashboard widgets
            widgets.append(
                cw.GraphWidget(
                    title=f"{name} — Request Count",
                    left=[svc.load_balancer.metric_request_count()],
                    width=12,
                )
            )
            widgets.append(
                cw.GraphWidget(
                    title=f"{name} — Latency",
                    left=[svc.load_balancer.metric_target_response_time()],
                    width=12,
                )
            )

        cw.Dashboard(
            self, "Dashboard",
            dashboard_name=f"TrialMind-{stage}",
            widgets=[widgets],
        )
