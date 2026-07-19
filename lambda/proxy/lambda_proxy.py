import json, os, time, urllib.request, urllib.error
import boto3

dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")

TABLE_NAME = os.environ["TABLE_NAME"]
METERING_FN = os.environ["METERING_FUNCTION_NAME"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
WARN_THRESHOLD = 0.8

table = dynamodb.Table(TABLE_NAME)

PRICES = {
    # dollars per 1,000 tokens --- illustrative; update with current OpenAI pricing
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
}


def response(status, body):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}


def estimate_cost(model, usage):
    price = PRICES.get(model, PRICES["gpt-4o-mini"])
    pt = usage.get("prompt_tokens", 0)
    ct = usage.get("completion_tokens", 0)
    return round((pt / 1000) * price["input"] + (ct / 1000) * price["output"], 6)


def handler(event, context):
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    api_key = headers.get("x-api-key")
    session_id = headers.get("x-session-id", "default")

    if not api_key:
        return response(401, {"error": "missing_api_key"})

    key_item = table.get_item(Key={"PK": f"APIKEY#{api_key}", "SK": "MAP"}).get("Item")
    if not key_item:
        return response(401, {"error": "invalid_api_key"})

    agent_id = key_item["agent_id"]
    team_id = key_item["team_id"]

    agent = table.get_item(Key={"PK": f"AGENT#{agent_id}", "SK": "PERIOD#current"}).get("Item")
    team = table.get_item(Key={"PK": f"TEAM#{team_id}", "SK": "PERIOD#current"}).get("Item")

    if not agent or not team:
        return response(500, {"error": "agent_or_team_not_registered"})

    if agent.get("status") == "PAUSED":
        return response(403, {"error": "agent_paused_human_review_required"})

    agent_limit = float(agent["limit_month"])
    team_limit = float(team["limit_month"])
    agent_spend = float(agent.get("spend_month", 0))
    team_spend = float(team.get("spend_month", 0))
    session_spend = float(agent.get("spend_session", 0))
    session_limit = float(agent.get("limit_session", 2))

    if session_spend >= session_limit:
        return response(402, {"error": "session_budget_exhausted"})

    if agent_spend / agent_limit >= 1.0 or team_spend / team_limit >= 1.0:
        return response(429, {"error": "budget_exhausted"})

    warning = (agent_spend / agent_limit >= WARN_THRESHOLD) or (team_spend / team_limit >= WARN_THRESHOLD)

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return response(400, {"error": "invalid_json_body"})

    requested_model = body.get("model", "gpt-4o-mini")
    model_spend = agent.get("model_spend", {})
    model_limits = agent.get("model_limits", {})
    substitution_map = agent.get("substitution_map", {})

    final_model = requested_model
    substituted = False
    if requested_model in model_limits:
        used = float(model_spend.get(requested_model, 0))
        limit = float(model_limits[requested_model])
        if used >= limit and requested_model in substitution_map:
            final_model = substitution_map[requested_model]
            substituted = True

    body["model"] = final_model

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return response(e.code, {"error": "openai_error", "detail": e.read().decode("utf-8")})
    except urllib.error.URLError as e:
        return response(504, {"error": "openai_timeout_or_network_error", "detail": str(e)})

    usage = result.get("usage", {})
    cost = estimate_cost(final_model, usage)

    lambda_client.invoke(
        FunctionName=METERING_FN,
        InvocationType="Event",  # fire-and-forget async, agent isn't kept waiting
        Payload=json.dumps({
            "agent_id": agent_id, "team_id": team_id, "session_id": session_id,
            "model": final_model, "cost": cost,
        }).encode("utf-8"),
    )

    result["_governance"] = {
        "warning": warning, "model_substituted": substituted,
        "model_used": final_model, "estimated_cost": cost,
    }
    return response(200, result)
