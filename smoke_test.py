import time
import urllib.request
import urllib.error
import json
import sys
import uuid

def make_request(url, method="GET", data=None):
    headers = {"Content-Type": "application/json"}
    req_data = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
        except Exception:
            err_body = e.reason
        return e.code, err_body
    except Exception as e:
        return 0, str(e)

def main():
    port = 8085
    base_url = f"http://127.0.0.1:{port}"
    print(f"Starting server connection on {base_url}...")
    
    # Check health check
    code, res = make_request(f"{base_url}/health")
    if code != 200:
        print(f"Error: Server is not running on port {port}. Please make sure the server is started.")
        sys.exit(1)
    print("Server is healthy! Running smoke test...")

    workflow_id = f"smoke-test-workflow-{uuid.uuid4().hex[:8]}"
    
    # 1. Create Workflow
    print(f"\n--- 1. Creating Workflow '{workflow_id}' ---")
    payload = {
        "workflowId": workflow_id,
        "steps": [
            {
                "name": "validate",
                "input": {
                    "contractId": "smoke-999"
                }
            },
            {
                "name": "transform",
                "input": {
                    "set": {
                        "approved": True,
                        "test_run": "smoke",
                        "reviewer": "QA-Person"
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
    }
    code, res = make_request(f"{base_url}/api/v1/workflows", "POST", payload)
    print(f"Status Code: {code}")
    print("Response:", json.dumps(res, indent=2))
    assert code == 201, "Workflow creation failed"

    # 2. Execute Workflow
    print("\n--- 2. Executing Workflow ---")
    code, res = make_request(f"{base_url}/api/v1/workflows/{workflow_id}/execute", "POST")
    print(f"Status Code: {code}")
    print("Response:", json.dumps(res, indent=2))
    assert code == 201, "Workflow execution trigger failed"
    execution_id = res["executionId"]

    # 3. Poll Execution Status Mid-flight
    print("\n--- 3. Polling Execution Status Mid-flight (Demonstrating Concurrency & Progress) ---")
    for i in range(5):
        time.sleep(0.8)
        code, status_data = make_request(f"{base_url}/api/v1/executions/{execution_id}")
        print(f"Poll {i+1} after {0.8 * (i+1):.1f}s: Status Code: {code}, Response: {status_data}")

    # 4. Wait for completion and query history
    print("\n--- 4. Waiting for completion & Fetching History ---")
    time.sleep(2.0)
    code, history_data = make_request(f"{base_url}/api/v1/executions/{execution_id}/history")
    print(f"Status Code: {code}")
    print("History Response:", json.dumps(history_data, indent=2))
    
    # Assertions
    assert code == 200, "Failed to get history"
    assert history_data["status"] == "completed", f"Expected completed, got {history_data['status']}"
    assert len(history_data["steps"]) == 5, "Expected 5 steps"
    
    # Assert final context values propagated
    final_context = history_data.get("finalContext")
    assert final_context is not None, "finalContext was not persisted!"
    assert final_context.get("approved") is True, "approved should be True in finalContext"
    assert final_context.get("test_run") == "smoke", "test_run should be smoke in finalContext"
    assert final_context.get("reviewer") == "QA-Person", "reviewer should be QA-Person"

    print("\n==========================================")
    print("SMOKE TEST PASSED SUCCESSFULY!")
    print("==========================================")

if __name__ == "__main__":
    main()
