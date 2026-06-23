import time
import subprocess
import urllib.request
import urllib.error
import json
import sys

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
    print(f"Starting FastAPI server in background on port {port}...")
    
    server_process = subprocess.Popen(
        ["./venv/bin/uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for server to start
    time.sleep(3)
    
    # Try connecting to health check
    for i in range(10):
        code, res = make_request(f"{base_url}/health")
        if code == 200:
            print("Server is up and healthy!")
            break
        print("Waiting for server to respond...")
        time.sleep(1)
    else:
        print("Server failed to start. Logs:")
        try:
            stdout, stderr = server_process.communicate(timeout=1)
            print("STDOUT:", stdout)
            print("STDERR:", stderr)
        except Exception as ex:
            print("Could not get logs:", ex)
        sys.exit(1)
        
    try:
        workflow_id = f"contract-review-{int(time.time())}"
        # 1. Create Workflow
        print(f"\n--- 1. Creating Workflow '{workflow_id}' ---")
        workflow_payload = {
            "workflowId": workflow_id,
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
        code, res = make_request(f"{base_url}/api/v1/workflows", "POST", workflow_payload)
        print(f"Status Code: {code}")
        print("Response:", json.dumps(res, indent=2))
        if code != 201:
            print("Create workflow failed.")
            sys.exit(1)
        
        # 1b. Test Duplicate Workflow ID
        print("\n--- 1b. Testing Duplicate Workflow ID ---")
        code, res = make_request(f"{base_url}/api/v1/workflows", "POST", workflow_payload)
        print(f"Status Code: {code}")
        print("Response:", json.dumps(res, indent=2))
        
        # 2. Execute Workflow
        print("\n--- 2. Executing Workflow ---")
        code, res = make_request(f"{base_url}/api/v1/workflows/{workflow_id}/execute", "POST")
        print(f"Status Code: {code}")
        print("Response:", json.dumps(res, indent=2))
        if code != 201:
            print("Execute workflow failed.")
            sys.exit(1)
        execution_id = res["executionId"]
        
        # 3. Poll Execution Status
        print("\n--- 3. Polling Execution Status ---")
        for i in range(10):
            code, status_data = make_request(f"{base_url}/api/v1/executions/{execution_id}")
            print(f"Poll {i+1}: Status Code: {code}, Response: {status_data}")
            if status_data.get("status") in ["completed", "failed"]:
                break
            time.sleep(1)
            
        # 4. Get Execution History
        print("\n--- 4. Getting Execution History ---")
        code, history_data = make_request(f"{base_url}/api/v1/executions/{execution_id}/history")
        print(f"Status Code: {code}")
        print("Response:", json.dumps(history_data, indent=2))
        
    finally:
        print("\nStopping server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except Exception:
            server_process.kill()
        print("Server stopped.")

if __name__ == "__main__":
    main()
