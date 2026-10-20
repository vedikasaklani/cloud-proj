# LearnCloud

LearnCloud is a small serverless course portal for an AWS-console deployment in one day. Students browse courses, open lesson materials, and record completed lessons.

## What is built

- **Frontend:** responsive vanilla HTML/CSS/JavaScript in [`frontend/index.html`](frontend/index.html).
- **Catalog Lambda:** `GET /courses` and `GET /courses/{course_id}` in [`backend/catalog.py`](backend/catalog.py).
- **Progress Lambda:** `POST /progress` and `GET /progress/{student_id}` in [`backend/progress.py`](backend/progress.py).
- **Data:** DynamoDB-ready sample records in [`sample-data/courses.json`](sample-data/courses.json).
- **Security:** least-privilege policy templates in [`iam/`](iam/).
- **Tests:** local handler tests in [`tests/test_lambdas.py`](tests/test_lambdas.py).

## Run the checks

From the repository root:

```powershell
python -m unittest discover -s tests -v
```

The tests mock DynamoDB and do not require AWS credentials.

## Fast deployment path

1. Create on-demand DynamoDB tables `learncloud-courses` (partition key `course_id`, String) and `learncloud-progress` (partition key `student_id`, String; sort key `lesson_key`, String).
2. Add the records from `sample-data/courses.json` to the courses table. In the DynamoDB console, convert each JSON object to DynamoDB JSON or add the attributes manually.
3. Create Python Lambda functions named `learncloud-catalog` and `learncloud-progress`. Copy the matching backend file into the inline editor, set the environment variable shown below, and set a 10-second timeout.
   - Catalog: `COURSES_TABLE=learncloud-courses`
   - Progress: `PROGRESS_TABLE=learncloud-progress`
4. Attach each Lambda's basic execution role plus its matching policy from [`iam/`](iam/), replacing `<REGION>` and `<ACCOUNT_ID>`.
5. Create an API Gateway **HTTP API** with these Lambda proxy routes:
   - `GET /courses`
   - `GET /courses/{course_id}`
   - `POST /progress`
   - `GET /progress/{student_id}`
   
   Enable CORS for `GET`, `POST`, `OPTIONS`, `content-type`, and `*` during the first deploy. Restrict the origin to the CloudFront domain before handoff.
6. Test the API invoke URL in a browser or with `curl`. Save the URL.
7. Replace `REPLACE_WITH_API_URL` near the top of [`frontend/index.html`](frontend/index.html) with the invoke URL.
8. Create a private S3 bucket with Block Public Access enabled. Upload `frontend/index.html` at the root and lesson PDFs under the exact `materials/...` keys in the sample data.
9. Create a CloudFront distribution using Origin Access Control, set the default root object to `index.html`, and redirect HTTP to HTTPS. Upload the updated page after the API URL is set.

## API contract

| Method | Path | Success |
|---|---|---|
| GET | `/courses` | `200` course summaries |
| GET | `/courses/{course_id}` | `200` course and lessons, or `404` |
| POST | `/progress` | `201` completion record, or `400` |
| GET | `/progress/{student_id}` | `200` `{ "completed": [...] }`, or `400` |

Every response is JSON. Unexpected service failures return `500` without exposing internals. Each Lambda logs route, status, and duration but never request bodies.

## Next steps

Prioritize these after the demo path works:

1. **Add real lesson files and smoke-test CloudFront** with a direct S3 access-denied check.
2. **Narrow CORS and add throttling** once the final CloudFront hostname is known.
3. **Add CloudWatch alarms** for Lambda `Errors` and API 5xx responses.
4. **Add integration tests** against a deployed staging API, including duplicate completion and unknown-course cases.
5. **Add sign-in** (Cognito or an existing identity provider) so `student_id` cannot be impersonated.
6. **Automate deployment** with CloudFormation or CDK after the one-day console deployment is stable.
7. **Add pagination** to course scans and progress queries when the dataset grows.

## Known demo limits

There is intentionally no authentication, uploads, admin UI, custom domain, WAF, or infrastructure-as-code yet. `student_id` is a user-entered label until sign-in is added.
