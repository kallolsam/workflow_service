import asyncio
from typing import Dict, Any, Callable, Awaitable

# Define the type signature for step handlers.
# Each handler accepts:
#   1. input_data: The input defined in the workflow step.
#   2. context: A dictionary containing outcomes of previous steps (e.g. {"validate": {"valid": True}}).
StepHandler = Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]]

async def validate_handler(input_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Validate step handler. Returns a static validation response."""
    return {"valid": True}

async def approve_handler(input_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Approve step handler. Returns approval information."""
    return {"approvedBy": "system"}

async def execute_handler(input_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute step handler. Returns success results."""
    return {"result": "success"}

async def transform_handler(input_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Transform step handler. Merges specified key-value pairs from input_data['set'] into context."""
    to_set = input_data.get("set", {})
    context.update(to_set)
    return {"transformed": to_set}

async def delay_handler(input_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Delay step handler. Sleeps for a specified number of seconds."""
    seconds = input_data.get("seconds", 1)
    await asyncio.sleep(seconds)
    return {"waited_seconds": seconds}

async def fail_handler(input_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Fail step handler. Intentionally raises an exception for testing."""
    raise ValueError("Intentionally failed step handler")

# Step registry mapping step names to their handler functions
STEP_REGISTRY: Dict[str, StepHandler] = {
    "validate": validate_handler,
    "approve": approve_handler,
    "execute": execute_handler,
    "transform": transform_handler,
    "delay": delay_handler,
    "fail": fail_handler
}
