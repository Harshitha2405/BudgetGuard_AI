import boto3, uuid
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("BudgetControllerTable")


def _dec(x):
    # boto3's DynamoDB Table resource rejects native float; tiny test limits (e.g. 0.05) need this.
    return Decimal(str(x))


def register_team(team_id, limit_month, notify_email):
    table.put_item(Item={
        "PK": f"TEAM#{team_id}", "SK": "PERIOD#current",
        "spend_month": 0, "limit_month": _dec(limit_month), "notify_channel": notify_email,
    })


def register_agent(agent_id, team_id, project_id, limit_month, limit_session,
                    model_limits=None, substitution_map=None):
    table.put_item(Item={
        "PK": f"AGENT#{agent_id}", "SK": "PERIOD#current",
        "team_id": team_id, "project_id": project_id,
        "spend_month": 0, "spend_session": 0, "spend_hour": 0,
        "limit_month": _dec(limit_month), "limit_session": _dec(limit_session),
        "status": "ACTIVE",
        "model_spend": {}, "model_limits": {k: _dec(v) for k, v in (model_limits or {}).items()},
        "substitution_map": substitution_map or {},
    })


def issue_api_key(agent_id, team_id, project_id):
    api_key = f"sk-budget-{uuid.uuid4().hex}"
    table.put_item(Item={
        "PK": f"APIKEY#{api_key}", "SK": "MAP",
        "agent_id": agent_id, "team_id": team_id, "project_id": project_id,
    })
    return api_key


if __name__ == "__main__":
    register_team("demo-team", limit_month=50, notify_email="harshithav00024@gmail.com")

    register_agent(
        "agent-1", team_id="demo-team", project_id="demo-project",
        limit_month=10, limit_session=2,
        model_limits={"gpt-4o-mini": 10},
        substitution_map={},
    )

    key = issue_api_key("agent-1", "demo-team", "demo-project")
    print("Your API key (save this securely):", key)
