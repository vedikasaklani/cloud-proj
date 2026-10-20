import json
import logging
import os
import time

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("COURSES_TABLE", "learncloud-courses")
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


def handler(event, context):
    started = time.monotonic()
    route = event.get("routeKey", "")
    status_code = 500
    try:
        if route == "GET /courses":
            items = table.scan().get("Items", [])
            body = [
                {
                    "course_id": item["course_id"],
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                }
                for item in items
            ]
            status_code = 200
        elif route == "GET /courses/{course_id}":
            course_id = event.get("pathParameters", {}).get("course_id")
            item = table.get_item(Key={"course_id": course_id}).get("Item")
            if item is None:
                status_code = 404
                body = {"error": "Course not found"}
            else:
                body = {
                    "course_id": item["course_id"],
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "lessons": item.get("lessons", []),
                }
                status_code = 200
        else:
            status_code = 404
            body = {"error": "Route not found"}
    except Exception:
        logger.exception("Catalog request failed")
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
