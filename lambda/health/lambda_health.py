import json, os
import boto3

dynamodb = boto3.client("dynamodb")
TABLE_NAME = os.environ["TABLE_NAME"]


def handler(event, context):
    try:
        dynamodb.describe_table(TableName=TABLE_NAME)
        db_ok = True
    except Exception:
        db_ok = False

    status = "healthy" if db_ok else "unhealthy"
    code = 200 if db_ok else 503

    return {
        "statusCode": code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"status": status, "dynamodb": db_ok}),
    }
