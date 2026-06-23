# Workflow Execution Service

A minimal, production-ready, asynchronous Workflow Execution Service built with **FastAPI**, **SQLAlchemy** (asyncio), and **MySQL** (using Pydantic v2).

## 1. Project Overview

The Workflow Execution Service allows users to define a sequence of execution steps (a workflow), run that sequence asynchronously, track its execution state, and query its execution history.

## 2. Architecture Overview

The system uses clean architecture principles. It separates routes, services, step execution logic, database models, and repository access layers.

### Flow Architecture

```text
Client
  |
  v
FastAPI (Controller / Routes)
  |
  v
Workflow Service (Business Orchestrator)
  |
  v
Execution Engine (State & Execution Runner)
  |
  v
MySQL (Database Layer via Async SQLAlchemy)
```

- **FastAPI Layer**: Exposes routes and parses camelCase JSON payloads to snake_case models.
- **Workflow Service**: Core orchestrator checking prerequisites and scheduling executions.
- **Execution Engine**: Manages step-by-step executions, loads registered handlers, processes inputs, and passes execution context from previous steps.
- **Repository Layer**: Encapsulates DB operations and query optimization using Async SQLAlchemy `selectinload` to prevent N+1 queries.

---

## 3. Database Schema

The database consists of 4 main tables:

### Workflow Table (`workflows`)
*Stores the static workflow configuration metadata.*
- `id` (INT, Primary Key, Autoincrement)
- `workflow_id` (VARCHAR(255), Unique, Indexed)
- `created_at` (DATETIME, Default: UTC Now)

### WorkflowStep Table (`workflow_steps`)
*Stores steps belonging to a workflow. Ordered by step_order.*
- `id` (INT, Primary Key, Autoincrement)
- `workflow_id` (INT, Foreign Key referencing `workflows.id`)
- `step_order` (INT)
- `name` (VARCHAR(255))
- `input_json` (JSON, Nullable)

### Execution Table (`executions`)
*Tracks global execution state of a workflow run.*
- `id` (INT, Primary Key, Autoincrement)
- `execution_id` (VARCHAR(36), UUID, Unique, Indexed)
- `workflow_id` (INT, Foreign Key referencing `workflows.id`)
- `status` (VARCHAR(50), pending -> running -> completed/failed)
- `current_step` (INT, step index counter, e.g., 0 initially, then 1, 2...)
- `started_at` (DATETIME, Default: UTC Now)
- `completed_at` (DATETIME, Nullable)

### ExecutionStep Table (`execution_steps`)
*Tracks progress and outputs of each step within an execution.*
- `id` (INT, Primary Key, Autoincrement)
- `execution_id` (INT, Foreign Key referencing `executions.id`)
- `step_name` (VARCHAR(255))
- `status` (VARCHAR(50), running -> completed/failed)
- `output_json` (JSON, Nullable)
- `started_at` (DATETIME, Default: UTC Now)
- `completed_at` (DATETIME, Nullable)

---

## 4. API Documentation

### Create Workflow
- **Endpoint**: `POST /api/v1/workflows`
- **Request Body**:
  ```json
  {
    "workflowId": "contract-review",
    "steps": [
      {
        "name": "validate",
        "input": {
          "contractId": "123"
        }
      },
      {
        "name": "approve"
      },
      {
        "name": "execute"
      }
    ]
  }
  ```
- **Response**: `201 Created`

### Execute Workflow
- **Endpoint**: `POST /api/v1/workflows/{workflowId}/execute`
- **Response**:
  ```json
  {
    "executionId": "b1a13437-05be-443b-ab5f-d23bc6ee7b7d"
  }
  ```

### Get Execution Status
- **Endpoint**: `GET /api/v1/executions/{executionId}`
- **Response**:
  ```json
  {
    "executionId": "b1a13437-05be-443b-ab5f-d23bc6ee7b7d",
    "status": "running",
    "currentStep": 2
  }
  ```

### Get Execution History
- **Endpoint**: `GET /api/v1/executions/{executionId}/history`
- **Response**:
  ```json
  {
    "executionId": "b1a13437-05be-443b-ab5f-d23bc6ee7b7d",
    "status": "completed",
    "steps": [
      {
        "name": "validate",
        "status": "completed",
        "output": {
          "valid": true
        }
      },
      {
        "name": "approve",
        "status": "completed",
        "output": {
          "approvedBy": "system"
        }
      },
      {
        "name": "execute",
        "status": "completed",
        "output": {
          "result": "success"
        }
      }
    ]
  }
  ```

### Health Check (Bonus)
- **Endpoint**: `GET /health`
- **Response**:
  ```json
  {
    "status": "healthy"
  }
  ```

---

## 5. Required Questions

### Q1: How does the system handle state transitions and guarantee sequential execution?
State transitions are managed sequentially inside the asynchronous background runner (`ExecutorService.run_execution`). When a workflow execution is triggered, the executor loads the static workflow steps sorted by `step_order`. It iterates through the steps one by one:
1. The execution's `current_step` attribute is updated to the step's sequence number and saved.
2. A new `ExecutionStep` record is created in the database with status `running`.
3. The step handler corresponding to the step name is loaded from the registry and executed with the accumulated context and step input.
4. Upon successful completion, the `ExecutionStep` is marked `completed` and the output is stored.
5. If a step handler fails or is not found, the `ExecutionStep` is marked `failed`, all subsequent steps in the workflow are explicitly created with status `skipped`, and the overall `Execution` is marked `failed`.
6. Once all steps successfully complete, the overall `Execution` is marked `completed`.
By running the steps inside a single loop in order of `step_order`, sequential execution is guaranteed.

### Q2: What are the key trade-offs in using an in-process background task runner vs. a message queue?
- **In-process Task Runner (FastAPI BackgroundTasks):**
  - *Pros:* Extremely simple to implement, zero external operational dependencies (no Redis, RabbitMQ, or Celery worker fleet required), low overhead, and fast setup.
  - *Cons:* If the FastAPI server crashes or restarts, all currently executing workflows are lost from memory and will remain in a "running" status in the database indefinitely. There is no automatic retry capability or rate limiting, and background tasks share the CPU/memory resources of the web server, which can lead to resource starvation under heavy load.
- **Distributed Message Queue (e.g., Celery, Temporal, AWS SQS):**
  - *Pros:* High reliability and resilience. Tasks are stored in a broker (Redis/RabbitMQ/Temporal DB) and can survive server restarts. It supports automatic retries, rate limiting, and horizontal scaling of worker nodes.
  - *Cons:* Significantly higher operational complexity, additional infrastructure to maintain (broker and workers), and message serialization overhead.

### Q3: How does the database schema support tracking execution step output and overall execution state?
The database schema tracks progress and state through two primary tables:
- **`executions`**: Tracks the global status of a workflow execution (`pending`, `running`, `completed`, `failed`), the `current_step` index, and timestamps for tracking execution duration. Crucially, it also features a `final_context` JSON column which persists the accumulated variables and outputs from all steps upon completion or failure.
- **`execution_steps`**: Has a foreign key referencing `executions.id`. It tracks the individual status of each step (`running`, `completed`, `failed`, `skipped`), its `step_name`, start/completion timestamps, and contains an `output_json` field where the specific output returned by that step handler is stored as a JSON object.

### Q4: How does the application manage database connections and concurrency in asynchronous background execution?
The application uses SQLAlchemy's asynchronous extension (`sqlalchemy.ext.asyncio`) with the `aiomysql` driver to handle database operations non-blockingly:
- **Connection Lifecycle:** The background runner (`ExecutorService.run_execution`) is instantiated with a session maker (`async_sessionmaker[AsyncSession]`). When the background task begins, it opens its own independent database session using `async with self.session_maker() as db:`. This ensures that the background task has a dedicated database connection, avoiding connection sharing or race conditions with active API requests.
- **Concurrency:** FastAPI executes background tasks within the running asyncio event loop. Since the database queries and step handlers (like the `delay` handler using `await asyncio.sleep()`) are fully asynchronous, they yield control back to the event loop, allowing the server to handle concurrent API requests and execute multiple workflows concurrently without blocking.

---

## 6. Assumptions

- **Sequential Execution**: Steps execute sequentially in ascending order of `step_order`.
- **Immutability**: Workflow definitions and steps are immutable once registered.
- **Security**: No authentication or authorization is required for the API (as per minimalist assignment guidelines).
- **Deployment**: Deployment is optimized for a single-node setup using Python asyncio for background concurrency.

## 7. Tradeoffs

- **MySQL over Distributed DB**: Used MySQL to satisfy constraints and keep setup simple, although a distributed DB (like DynamoDB or CockroachDB) would be preferred for high availability and partition tolerance.
- **In-process Concurrency**: Used FastAPI `BackgroundTasks` instead of a distributed message broker (like Redis/Celery). If the web server crashes or restarts, running workflows could remain in a "running" status indefinitely.
- **No Retries**: If a step handler fails, it immediately terminates the workflow without a retry policy.
- **Sequential Executions Only**: No Support for Directed Acyclic Graphs (DAGs) or parallel execution pathways.

## 8. Future Improvements

- **Retry Policies**: Support automatic step retries with exponential backoffs.
- **Workflow Versioning**: Allow upgrading workflow step layouts while maintaining old executions on old schemas.
- **DAG Execution**: Introduce parallel branch executions using a Directed Acyclic Graph resolver.
- **Redis Queue / Celery Workers**: Migrate background executions from local memory to distributed task queues.
- **Event-Driven Architecture**: Use Apache Kafka or RabbitMQ to stream state transitions for downstream analytics or auditing.

---

## 9. One-Command Startup (Docker Compose)

The easiest way to start the service along with its database is using Docker Compose:
```bash
docker compose up --build
```
This spins up:
1. A **MySQL** container (`db`) pre-configured with the database `workflow_db`.
2. A **FastAPI** container (`app`) that waits for the database to be healthy, creates the database tables automatically on startup, and exposes the service on port `8000`.

---

## 10. Local Setup Instructions

### Prerequisites
- Python 3.12+
- MySQL Server (running on port 3306)

### 1. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Requirements
```bash
pip install -r requirements.txt
```

### 3. Setup Database
Ensure MySQL is running and login to create a database:
```sql
CREATE DATABASE IF NOT EXISTS workflow_db;
```
Alternatively, you can import the pre-existing schema structure from the provided `schema.sql` dump file in the root folder:
```bash
mysql -u root -p workflow_db < schema.sql
```

### 4. Configure .env
Copy `.env.example` to `.env` and fill in credentials:
```bash
cp .env.example .env
```
Ensure your `DATABASE_URL` is pointing to your MySQL server. Remember to URL-encode special characters in your password (e.g. `@` as `%40`).

### 5. Run Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 11. Testing

### Run Automated Test Suite
The automated test suite uses `pytest` and `httpx`. To run the tests, execute:
```bash
PYTHONPATH=. ./venv/bin/pytest tests/test_workflow.py
```
This runs 4 tests verifying:
- `/health` check.
- **Happy Path Workflow**: step-by-step execution including `transform`, `delay` (verifying status is `running` mid-flight), and verifying `finalContext`.
- **Failing Step & Skipping Trailing Steps**: verifying that when a step fails, remaining steps are set to `skipped` and the accumulated context is successfully saved.
- **Invalid step creation validation**.

### Run Smoke Test Script
To run the end-to-end smoke test which starts the server locally, runs the progress scenario (with a 3-second delay), polls mid-flight, and checks history/finalContext:
```bash
./run.sh
```

---

## 12. Example Curl Commands

### Create a Workflow
```bash
curl -X POST http://127.0.0.1:8000/api/v1/workflows \
     -H "Content-Type: application/json" \
     -d '{
       "workflowId": "contract-review",
       "steps": [
         {
           "name": "validate",
           "input": {
             "contractId": "123"
           }
         },
         {
           "name": "transform",
           "input": {
             "set": {
               "approved": true,
               "reviewer": "Alice"
             }
           }
         },
         {
           "name": "delay",
           "input": {
             "seconds": 3
           }
         },
         {
           "name": "approve"
         },
         {
           "name": "execute"
         }
       ]
     }'
```

### Execute the Workflow
```bash
curl -X POST http://127.0.0.1:8000/api/v1/workflows/contract-review/execute
```

### Query Execution Status
*(Replace `YOUR_EXECUTION_ID` with the UUID returned from the execute endpoint)*
```bash
curl -X GET http://127.0.0.1:8000/api/v1/executions/YOUR_EXECUTION_ID
```

### Query Execution History
*(Replace `YOUR_EXECUTION_ID` with the UUID returned from the execute endpoint)*
```bash
curl -X GET http://127.0.0.1:8000/api/v1/executions/YOUR_EXECUTION_ID/history
```

### Health Check
```bash
curl -X GET http://127.0.0.1:8000/health
```
