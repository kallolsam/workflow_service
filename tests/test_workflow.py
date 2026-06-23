import subprocess
import time
import uuid
import httpx
import pytest

PORT = 8086
BASE_URL = f"http://127.0.0.1:{PORT}"

@pytest.fixture(scope="module", autouse=True)
def run_server():
    # Start the server in a background subprocess
    process = subprocess.Popen(
        ["./venv/bin/uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    # Wait for the server to start and become healthy
    time.sleep(2)
    for _ in range(15):
        try:
            response = httpx.get(f"{BASE_URL}/health")
            if response.status_code == 200:
                break
        except httpx.RequestError:
            pass
        time.sleep(0.5)
    else:
        process.terminate()
        raise RuntimeError("FastAPI server failed to start on port 8086")

    yield BASE_URL

    # Terminate the server after tests are done
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()

def test_health_check():
    response = httpx.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_workflow_happy_path():
    workflow_id = f"test-wf-{uuid.uuid4().hex[:8]}"
    
    # 1. Create Workflow
    payload = {
        "workflowId": workflow_id,
        "steps": [
            {"name": "validate", "input": {"contractId": "123"}},
            {"name": "transform", "input": {"set": {"approved": True, "reviewer": "test-user"}}},
            {"name": "delay", "input": {"seconds": 2}},
            {"name": "approve"},
            {"name": "execute"}
        ]
    }
    response = httpx.post(f"{BASE_URL}/api/v1/workflows", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["workflowId"] == workflow_id
    assert len(data["steps"]) == 5

    # 2. Execute Workflow
    response = httpx.post(f"{BASE_URL}/api/v1/workflows/{workflow_id}/execute")
    assert response.status_code == 201
    exec_data = response.json()
    assert "executionId" in exec_data
    execution_id = exec_data["executionId"]

    # 3. Poll Mid-Flight (during the 2-second delay)
    time.sleep(0.8)
    response = httpx.get(f"{BASE_URL}/api/v1/executions/{execution_id}")
    assert response.status_code == 200
    status_data = response.json()
    # It should be running and currently executing one of the early steps
    assert status_data["status"] == "running"
    assert status_data["currentStep"] > 0

    # 4. Wait for completion and fetch history
    time.sleep(2.5)
    response = httpx.get(f"{BASE_URL}/api/v1/executions/{execution_id}/history")
    assert response.status_code == 200
    history = response.json()
    assert history["status"] == "completed"
    assert len(history["steps"]) == 5
    
    # Check outputs
    steps = {s["name"]: s for s in history["steps"]}
    assert steps["validate"]["status"] == "completed"
    assert steps["validate"]["output"] == {"valid": True}
    assert steps["transform"]["status"] == "completed"
    assert steps["transform"]["output"] == {"transformed": {"approved": True, "reviewer": "test-user"}}
    assert steps["delay"]["status"] == "completed"
    assert steps["delay"]["output"] == {"waited_seconds": 2}
    assert steps["approve"]["status"] == "completed"
    assert steps["execute"]["status"] == "completed"

    # Check final context
    assert history["finalContext"] is not None
    assert history["finalContext"]["approved"] is True
    assert history["finalContext"]["reviewer"] == "test-user"

def test_workflow_failure_and_skipping():
    workflow_id = f"test-fail-wf-{uuid.uuid4().hex[:8]}"
    
    # 1. Create Workflow containing "fail" step
    payload = {
        "workflowId": workflow_id,
        "steps": [
            {"name": "validate", "input": {"contractId": "456"}},
            {"name": "transform", "input": {"set": {"pre_fail": "yes"}}},
            {"name": "fail"},
            {"name": "approve"},
            {"name": "execute"}
        ]
    }
    response = httpx.post(f"{BASE_URL}/api/v1/workflows", json=payload)
    assert response.status_code == 201

    # 2. Execute Workflow
    response = httpx.post(f"{BASE_URL}/api/v1/workflows/{workflow_id}/execute")
    assert response.status_code == 201
    execution_id = response.json()["executionId"]

    # 3. Wait for execution to finish
    time.sleep(1.5)

    # 4. Get History
    response = httpx.get(f"{BASE_URL}/api/v1/executions/{execution_id}/history")
    assert response.status_code == 200
    history = response.json()
    assert history["status"] == "failed"
    assert len(history["steps"]) == 5

    # Check steps statuses
    steps = {s["name"]: s for s in history["steps"]}
    assert steps["validate"]["status"] == "completed"
    assert steps["transform"]["status"] == "completed"
    assert steps["fail"]["status"] == "failed"
    assert "error" in steps["fail"]["output"]
    assert steps["approve"]["status"] == "skipped"
    assert steps["execute"]["status"] == "skipped"

    # Verify that intermediate context was persisted
    assert history["finalContext"] is not None
    assert history["finalContext"]["pre_fail"] == "yes"

def test_create_workflow_invalid_step():
    payload = {
        "workflowId": "invalid-step-wf",
        "steps": [
            {"name": "non-existent-step"}
        ]
    }
    response = httpx.post(f"{BASE_URL}/api/v1/workflows", json=payload)
    assert response.status_code == 400
    assert "Invalid step name" in response.json()["detail"]
