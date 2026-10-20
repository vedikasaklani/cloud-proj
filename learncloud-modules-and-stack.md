# LearnCloud: Minimal Modules, Stack, and Deployment Checklist

Serverless course learning portal on AWS. Students browse courses, open lesson files, and mark lessons complete. Built to be deployed from the AWS console in one day by three people.

## 1. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | One `index.html` with vanilla JavaScript (`fetch`) | No build step, nothing to install |
| Backend | Python on AWS Lambda, using `boto3` (already in the runtime) | Smallest code for DynamoDB calls, no packaging |
| API | API Gateway **HTTP API** with Lambda proxy integration | Simpler and quicker to set up than a REST API |
| Database | DynamoDB, on-demand capacity | No capacity to size, console can add items by hand |
| Hosting | S3 (private) + CloudFront | Matches the report, HTTPS with no extra setup |
| Monitoring | CloudWatch (default Lambda logs and metrics) | Nothing to build |
| Access control | IAM, one role per Lambda | Least-privilege story for the report |
| Deployment | AWS console, no IaC | Fastest for one day; CloudFormation stays in Future Enhancements |

Not used on purpose: Cognito, custom domain, WAF, CloudFormation, frontend frameworks.

## 2. Minimal modules

Six modules need real work. Three more are configuration or a few lines of code.

| # | Module | Needs code? |
|---|---|---|
| 1 | Web frontend | Yes (one HTML file) |
| 2 | Content delivery | No (console config) |
| 3 | API Gateway | No (console config) |
| 4 | Course catalog | Yes (one Lambda) |
| 5 | Progress tracking | Yes (one Lambda) |
| 6 | Data storage | No (two tables, a few items) |
| 7 | Error handling | A few lines inside modules 4 and 5 |
| 8 | Monitoring | No (verify, optional alarm) |
| 9 | Security | No (IAM policies, bucket settings) |

## 3. Responsibilities and what to deploy

### Module 1. Web frontend

**Responsibility:** show the course list, the lessons of a course, lesson links, and a "mark complete" button; remember the student ID.

**Build**
- One `index.html`. A `const API_URL = "..."` at the top.
- Student ID typed once and kept in `localStorage`.
- Lesson links point to `/materials/<material_key>` on the same CloudFront domain.
- Show the `error` text from any failed API call.

**Deploy:** upload `index.html` to the S3 bucket (see Module 2).

**Done when:** the page loads from the CloudFront URL and lists the sample courses.

### Module 2. Content delivery (S3 + CloudFront)

**Responsibility:** serve the page and lesson files over HTTPS from a private bucket.

**Deploy**
- **S3:** one bucket, Block Public Access on. Upload `index.html` at the root and lesson files under `materials/`. Keys must match the `material_key` values in DynamoDB.
- **CloudFront:** one distribution with the bucket as origin, origin access control (let the console create it and update the bucket policy), default root object `index.html`, viewer protocol "Redirect HTTP to HTTPS".

**Done when:** the CloudFront URL opens the page, a direct S3 URL returns access denied.

### Module 3. API Gateway

**Responsibility:** expose four routes and pass them to the right Lambda.

**Deploy (HTTP API)**

| Route | Integration |
|---|---|
| `GET /courses` | `learncloud-catalog` |
| `GET /courses/{course_id}` | `learncloud-catalog` |
| `POST /progress` | `learncloud-progress` |
| `GET /progress/{student_id}` | `learncloud-progress` |

- CORS: allow all origins at first, then switch to the CloudFront domain. Allow methods `GET`, `POST`, `OPTIONS` and header `content-type`.
- Stage throttling set low (demo level).
- Auto-deploy on the default stage. Save the invoke URL.

**Done when:** `<invoke URL>/courses` returns JSON in the browser.

### Module 4. Course catalog (`learncloud-catalog`)

**Responsibility:** return the course list and one course with its lessons. Read-only.

**Build**
- One handler. Branch on `event["routeKey"]`.
- List: `Scan` the courses table, return `course_id`, `title`, `description`.
- One course: `GetItem` by `event["pathParameters"]["course_id"]`; 404 if missing.

**Deploy**
- Lambda, Python runtime, timeout 10 s.
- Env var `COURSES_TABLE=learncloud-courses`.
- Role: basic execution role plus an inline policy allowing only `dynamodb:GetItem` and `dynamodb:Scan` on the courses table ARN.

### Module 5. Progress tracking (`learncloud-progress`)

**Responsibility:** save a completed lesson and return a student's completed lessons.

**Build**
- One handler. Branch on `event["routeKey"]`.
- `POST`: parse the JSON body, check `student_id`, `course_id`, `lesson_id` exist and are short strings (for example, under 64 characters), `PutItem` with `lesson_key = course_id#lesson_id` and `completed_at` as an ISO timestamp. Same lesson twice overwrites the same item.
- `GET`: `Query` by `student_id`, return the list of `lesson_key` values.

**Deploy**
- Lambda, Python runtime, timeout 10 s.
- Env var `PROGRESS_TABLE=learncloud-progress`.
- Role: basic execution role plus an inline policy allowing only `dynamodb:PutItem` and `dynamodb:Query` on the progress table ARN.

### Module 6. Data storage (DynamoDB)

**Responsibility:** hold courses and progress.

**Deploy**

| Table | Partition key | Sort key | Capacity |
|---|---|---|---|
| `learncloud-courses` | `course_id` (String) | none | On-demand |
| `learncloud-progress` | `student_id` (String) | `lesson_key` (String) | On-demand |

Add 2 courses with 2 to 3 lessons each by hand (Create item). Each item has `course_id`, `title`, `description`, and `lessons`, a list of maps with `lesson_id`, `title`, `material_key`.

Tip: keep every attribute a string. A DynamoDB number comes back as a `Decimal` that `json.dumps` cannot serialize without extra code.

### Module 7. Error handling

**Responsibility:** clear, consistent errors.

- Every response is `{"statusCode": ..., "headers": {"Content-Type": "application/json"}, "body": "<json string>"}`.
- Errors use the body `{"error": "message"}`: 400 invalid input, 404 unknown course, 500 anything unexpected (wrap the handler in `try/except`).
- The frontend displays `error`.

### Module 8. Monitoring

**Responsibility:** logs and metrics for the report.

- Nothing to build: Lambda log groups and Lambda and API Gateway metrics exist once the functions run.
- Print one log line per request: route, status code, duration. Do not log request bodies.
- Optional: one alarm on the `Errors` metric of each Lambda.

### Module 9. Security

**Responsibility:** least privilege and no public data.

- The two inline IAM policies above, each limited to one table ARN.
- S3 Block Public Access on, access only through CloudFront.
- HTTPS everywhere, API throttling on, CORS narrowed to the CloudFront domain at the end.
- Known limit for the report: no sign-in, so `student_id` is a label.

## 4. Interface contract (agree on this first)

| Endpoint | Request | Success | Errors |
|---|---|---|---|
| `GET /courses` | none | `200` `[{course_id, title, description}]` | 500 |
| `GET /courses/{course_id}` | path | `200` `{course_id, title, description, lessons:[{lesson_id, title, material_key}]}` | 404 |
| `POST /progress` | JSON `{student_id, course_id, lesson_id}` | `201` `{student_id, lesson_key, completed_at}` | 400 |
| `GET /progress/{student_id}` | path | `200` `{"completed": ["cloud-101#l1", ...]}` | 400 |

## 5. Deployment order and team split

Order matters because each step needs the one before it: DynamoDB, then Lambda, then API Gateway, then S3 and CloudFront, then connect the page, then test.

| Person | Owns | Modules |
|---|---|---|
| A | Tables, sample data, both Lambdas, IAM policies | 4, 5, 6, 7, 9 |
| B | API Gateway, CloudWatch checks, tests and latency numbers | 3, 8 |
| C | `index.html`, S3, CloudFront, lesson files, screenshots for the report | 1, 2 |

Rough plan for one day (adjust to your pace):

1. **First hour:** everyone agrees on the contract in section 4. A creates the tables. C writes the page against a hard-coded sample response.
2. **Next 2 to 3 hours:** A finishes both Lambdas and tests them in the Lambda console. C creates S3 and CloudFront (the distribution takes a while to finish deploying, so start it early). B creates the HTTP API once the functions exist.
3. **After that:** C sets the real `API_URL` and re-uploads the page; B narrows CORS and runs the tests from the report; everyone takes screenshots as they go.
4. **Last:** fill in the report's evidence sections, then delete the resources.

## 6. Cut line if time runs short

Keep modules 1 to 6. Drop in this order: alarms, throttling tuning, the CORS tightening step, the latency table. Do not drop the IAM policies or the screenshots, since the report depends on both.
