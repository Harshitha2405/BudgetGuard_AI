import json, os, time
from decimal import Decimal
import boto3

dynamodb = boto3.resource("dynamodb")
events = boto3.client("events")

TABLE_NAME = os.environ["TABLE_NAME"]
EVENT_BUS_NAME = os.environ["EVENT_BUS_NAME"]
RUNAWAY_HOURLY_FRACTION = 0.2

table = dynamodb.Table(TABLE_NAME)


def publish_event(detail_type, agent_id, team_id, detail):
    events.put_events(Entries=[{
        "Source": "budget.controller",
        "DetailType": detail_type,
        "Detail": json.dumps({"agent_id": agent_id, "team_id": team_id, **detail}),
        "EventBusName": EVENT_BUS_NAME,
    }])


def handler(event, context):
    agent_id = event["agent_id"]
    team_id = event["team_id"]
    cost = Decimal(str(event["cost"]))  # boto3's DynamoDB Table resource rejects native float
    model = event.get("model", "unknown")

    hour_bucket = time.strftime("%Y-%m-%d-%H")
    existing = table.get_item(Key={"PK": f"AGENT#{agent_id}", "SK": "PERIOD#current"}).get("Item", {})
    same_hour = existing.get("hour_bucket") == hour_bucket
    hour_expr = "spend_hour = if_not_exists(spend_hour, :zero) + :c" if same_hour else "spend_hour = :c"

    expr_values = {":c": cost, ":hb": hour_bucket, ":ts": int(time.time())}
    if same_hour:
        expr_values[":zero"] = 0  # only referenced by the if_not_exists branch above

    agent = table.update_item(
        Key={"PK": f"AGENT#{agent_id}", "SK": "PERIOD#current"},
        UpdateExpression=(
            f"ADD spend_month :c, spend_session :c, model_spend.#m :c "
            f"SET {hour_expr}, hour_bucket = :hb, last_active_ts = :ts"
        ),
        ExpressionAttributeNames={"#m": model},
        ExpressionAttributeValues=expr_values,
        ReturnValues="ALL_NEW",
    )["Attributes"]

    team = table.update_item(
        Key={"PK": f"TEAM#{team_id}", "SK": "PERIOD#current"},
        UpdateExpression="ADD spend_month :c",
        ExpressionAttributeValues={":c": cost},
        ReturnValues="ALL_NEW",
    )["Attributes"]

    # Per-session record, for dashboard-level insight (does not affect budget enforcement,
    # which still checks the agent's cumulative spend_session field above).
    session_id = event.get("session_id", "default")
    now_ts = int(time.time())
    table.update_item(
        Key={"PK": f"AGENT#{agent_id}", "SK": f"SESSION#{session_id}"},
        UpdateExpression=(
            "ADD spend_total :c, call_count :one "
            "SET last_active_ts = :ts, first_seen_ts = if_not_exists(first_seen_ts, :ts), "
            "team_id = :team_id, #m2 = :model"
        ),
        ExpressionAttributeNames={"#m2": "last_model"},
        ExpressionAttributeValues={":c": cost, ":one": 1, ":ts": now_ts, ":team_id": team_id, ":model": model},
    )

    # Append-only hourly spend log, for dashboard trend charts. Distinct from the
    # spend_hour/hour_bucket fields above (which are overwritten every new hour for the
    # runaway check) -- this one keeps history so the dashboard can chart it over time.
    table.update_item(
        Key={"PK": f"AGENT#{agent_id}", "SK": f"HOUR#{hour_bucket}"},
        UpdateExpression="ADD spend :c SET team_id = :team_id",
        ExpressionAttributeValues={":c": cost, ":team_id": team_id},
    )

    agent_pct = float(agent["spend_month"]) / float(agent["limit_month"])
    team_pct = float(team["spend_month"]) / float(team["limit_month"])

    if agent_pct >= 1.0 or team_pct >= 1.0:
        publish_event("budget.exhausted", agent_id, team_id, {"agent_pct": agent_pct, "team_pct": team_pct})
    elif agent_pct >= 0.8 or team_pct >= 0.8:
        publish_event("budget.warning", agent_id, team_id, {"agent_pct": agent_pct, "team_pct": team_pct})

    hourly_spend = float(agent.get("spend_hour", 0))
    if hourly_spend >= RUNAWAY_HOURLY_FRACTION * float(agent["limit_month"]):
        table.update_item(
            Key={"PK": f"AGENT#{agent_id}", "SK": "PERIOD#current"},
            UpdateExpression="SET #s = :paused",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":paused": "PAUSED"},
        )
        publish_event("budget.runaway", agent_id, team_id, {"hourly_spend": hourly_spend})

    return {"ok": True}
