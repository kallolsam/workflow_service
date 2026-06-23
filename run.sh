#!/bin/bash

# Port to run FastAPI server on
PORT=8085
BASE_URL="http://127.0.0.1:$PORT"

echo "=== Starting Workflow Service local server on port $PORT ==="
./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port $PORT > /dev/null 2>&1 &
SERVER_PID=$!

# Function to clean up server on exit
cleanup() {
    echo "=== Stopping Workflow Service server (PID: $SERVER_PID) ==="
    kill $SERVER_PID
    wait $SERVER_PID 2>/dev/null
}
trap cleanup EXIT

# Wait for server to start
echo "Waiting for server to become healthy..."
HEALTHY=false
for i in {1..15}; do
    response_code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health")
    if [ "$response_code" -eq 200 ]; then
        echo "Server is up and running!"
        HEALTHY=true
        break
    fi
    sleep 0.5
done

if [ "$HEALTHY" = false ]; then
    echo "Error: Server failed to start on port $PORT within 7 seconds."
    exit 1
fi

echo "=== Running Smoke Test ==="
./venv/bin/python smoke_test.py
SMOKE_RC=$?

if [ $SMOKE_RC -eq 0 ]; then
    echo "=== Smoke Test Completed Successfully! ==="
else
    echo "=== Smoke Test Failed! ==="
fi

exit $SMOKE_RC
