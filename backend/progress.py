import json
import logging
import os
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("PROGRESS_TABLE", "learncloud-progress")
table = boto3.resource("dynamodb").Table(TABLE_NAME)


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def valid_value(value):
    return isinstance(value, str) and 0 < len(value) <= 64


def handler(event, context):
    started = time.monotonic()
    route = event.get("routeKey", "")
    status_code = 500
    try:
        if route == "POST /progress":
            try:
                payload = json.loads(event.get("body") or "{}")
            except (TypeError, json.JSONDecodeError):
                payload = {}
            required = ("student_id", "course_id", "lesson_id")
            if not all(valid_value(payload.get(key)) for key in required):
                status_code = 400
                body = {"error": "student_id, course_id, and lesson_id are required"}
            else:
                completed_at = datetime.now(timezone.utc).isoformat()
                lesson_key = f"{payload['course_id']}#{payload['lesson_id']}"
                table.put_item(
                    Item={
                        "student_id": payload["student_id"],
                        "lesson_key": lesson_key,
                        "completed_at": completed_at,
                    }
                )
                status_code = 201
                body = {
                    "student_id": payload["student_id"],
                    "lesson_key": lesson_key,
                    "completed_at": completed_at,
                }
        elif route == "GET /progress/{student_id}":
            student_id = event.get("pathParameters", {}).get("student_id")
            if not valid_value(student_id):
                status_code = 400
                body = {"error": "student_id is required"}
            else:
                result = table.query(
                    KeyConditionExpression=boto3.dynamodb.conditions.Key(
                        "student_id"
                    ).eq(student_id)
                )
                status_code = 200
                body = {
                    "completed": [
                        item["lesson_key"]
                        for item in result.get("Items", [])
                        if "lesson_key" in item
                    ]
                }
        else:
            status_code = 404
            body = {"error": "Route not found"}
    except ClientError:
        logger.exception("Progress database request failed")
        status_code = 500
        body = {"error": "Internal server error"}
    except Exception:
        logger.exception("Progress request failed")
        status_code = 500
        body = {"error": "Internal server error"}
    finally:
        logger.info(
            "route=%s status_code=%s duration_ms=%.2f",
            route,
            status_code,
            (time.monotonic() - started) * 1000,
        )
    return response(status_code, body)
