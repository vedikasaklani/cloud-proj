import json
import logging
import os
import time

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("COURSES_TABLE", "learncloud-courses")
table = boto3.resource("dynamodb").Table(TABLE_NAME)
logger.info("catalog_module_loaded table=%s", TABLE_NAME)


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
    route = event.get("routeKey", "") if isinstance(event, dict) else ""
    status_code = 500
    logger.info(
        "catalog_handler_invoked route=%s path_parameters=%s",
        route,
        event.get("pathParameters") if isinstance(event, dict) else None,
    )
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
            path_parameters = event.get("pathParameters") or {}
            course_id = path_parameters.get("course_id")
            logger.info(
                "catalog_detail_lookup table=%s course_id=%s path_parameter_keys=%s",
                TABLE_NAME,
                course_id,
                sorted(path_parameters.keys()),
            )
            if not isinstance(course_id, str) or not course_id:
                status_code = 400
                body = {"error": "course_id is required"}
            else:
                item = table.get_item(Key={"course_id": course_id}).get("Item")
                logger.info(
                    "catalog_detail_lookup_result course_id=%s found=%s",
                    course_id,
                    item is not None,
                )
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
    except Exception as error:
        logger.exception(
            "Catalog request failed route=%s table=%s error_type=%s error=%s",
            route,
            TABLE_NAME,
            type(error).__name__,
            str(error),
        )
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
