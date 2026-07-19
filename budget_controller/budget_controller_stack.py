from aws_cdk import (
    Stack, Duration, RemovalPolicy, CfnOutput,
    aws_dynamodb as dynamodb,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_events as events,
    aws_events_targets as targets,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
)
from constructs import Construct


class BudgetControllerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # ---- Single DynamoDB table stores agent / team / api-key cards ----
        table = dynamodb.Table(
            self, "BudgetControllerTable",
            table_name="BudgetControllerTable",
            partition_key=dynamodb.Attribute(name="PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,  # fine for a learning project
        )

        # ---- Event bus + SNS email alerts ----
        bus = events.EventBus(self, "BudgetGovernanceBus", event_bus_name="budget-governance")

        topic = sns.Topic(self, "BudgetAlertsTopic")
        topic.add_subscription(subs.EmailSubscription("harshithav00024@gmail.com"))

        rule = events.Rule(
            self, "BudgetEventsRule",
            event_bus=bus,
            event_pattern=events.EventPattern(
                source=["budget.controller"],
                detail_type=["budget.warning", "budget.exhausted", "budget.runaway"],
            ),
        )
        rule.add_target(targets.SnsTopic(topic))

        # ---- Metering Lambda (updates spend counters) ----
        metering_fn = _lambda.Function(
            self, "MeteringFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambda_metering.handler",
            code=_lambda.Code.from_asset("lambda/metering"),
            timeout=Duration.seconds(10),
            environment={
                "TABLE_NAME": table.table_name,
                "EVENT_BUS_NAME": bus.event_bus_name,
            },
        )
        table.grant_read_write_data(metering_fn)
        bus.grant_put_events_to(metering_fn)

        # ---- Proxy Lambda (checks budget, calls OpenAI, triggers metering) ----
        proxy_fn = _lambda.Function(
            self, "ProxyFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambda_proxy.handler",
            code=_lambda.Code.from_asset("lambda/proxy"),
            timeout=Duration.seconds(29),
            environment={
                "TABLE_NAME": table.table_name,
                "METERING_FUNCTION_NAME": metering_fn.function_name,
                "OPENAI_API_KEY": self.node.try_get_context("openai_api_key") or "REPLACE_ME",
            },
        )
        table.grant_read_data(proxy_fn)
        metering_fn.grant_invoke(proxy_fn)

        # ---- Health check Lambda ----
        health_fn = _lambda.Function(
            self, "HealthFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambda_health.handler",
            code=_lambda.Code.from_asset("lambda/health"),
            timeout=Duration.seconds(5),
            environment={"TABLE_NAME": table.table_name},
        )
        table.grant_read_data(health_fn)

        # ---- API Gateway ----
        api = apigateway.RestApi(
            self, "BudgetControllerApi",
            rest_api_name="budget-controller-api",
            deploy_options=apigateway.StageOptions(stage_name="v1"),
        )

        chat = api.root.add_resource("chat").add_resource("completions")
        chat.add_method("POST", apigateway.LambdaIntegration(proxy_fn))

        health = api.root.add_resource("health")
        health.add_method("GET", apigateway.LambdaIntegration(health_fn))

        # ---- Dashboard Lambda: serves the live HTML page and its JSON data ----
        dashboard_fn = _lambda.Function(
            self, "DashboardFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambda_dashboard.handler",
            code=_lambda.Code.from_asset("lambda/dashboard"),
            timeout=Duration.seconds(10),
            environment={"TABLE_NAME": table.table_name},
        )
        table.grant_read_data(dashboard_fn)

        dashboard = api.root.add_resource("dashboard")
        dashboard.add_method("GET", apigateway.LambdaIntegration(dashboard_fn))
        dashboard_data = dashboard.add_resource("data")
        dashboard_data.add_method("GET", apigateway.LambdaIntegration(dashboard_fn))

        CfnOutput(self, "DashboardUrl", value=api.url + "dashboard")

        # Print the API URL after every deploy
        CfnOutput(self, "ApiUrl", value=api.url)
