import json
import os
import sys
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from unittest.mock import MagicMock, patch


ROOT = os.path.dirname(os.path.dirname(__file__))


def load_module(name):
    path = os.path.join(ROOT, "backend", f"{name}.py")
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class LambdaTests(unittest.TestCase):
    @patch("boto3.resource")
    def test_catalog_list(self, resource):
        table = resource.return_value.Table.return_value
        table.scan.return_value = {"Items": [{"course_id": "c1", "title": "T", "description": "D"}]}
        catalog = load_module("catalog")
        result = catalog.handler({"routeKey": "GET /courses"}, None)
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(json.loads(result["body"])[0]["course_id"], "c1")

    @patch("boto3.resource")
    def test_catalog_missing_course(self, resource):
        table = resource.return_value.Table.return_value
        table.get_item.return_value = {}
        catalog = load_module("catalog")
        result = catalog.handler({"routeKey": "GET /courses/{course_id}", "pathParameters": {"course_id": "missing"}}, None)
        self.assertEqual(result["statusCode"], 404)

    @patch("boto3.resource")
    def test_progress_rejects_invalid_body(self, resource):
        progress = load_module("progress")
        result = progress.handler({"routeKey": "POST /progress", "body": "{}"}, None)
        self.assertEqual(result["statusCode"], 400)

    @patch("boto3.resource")
    def test_progress_writes_completion(self, resource):
        table = resource.return_value.Table.return_value
        progress = load_module("progress")
        result = progress.handler({"routeKey": "POST /progress", "body": json.dumps({"student_id": "s1", "course_id": "c1", "lesson_id": "l1"})}, None)
        self.assertEqual(result["statusCode"], 201)
        self.assertEqual(table.put_item.call_args.kwargs["Item"]["lesson_key"], "c1#l1")


if __name__ == "__main__":
    unittest.main()
