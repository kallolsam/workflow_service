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

# Step registry mapping step names to their handler functions
STEP_REGISTRY: Dict[str, StepHandler] = {
    "validate": validate_handler,
    "approve": approve_handler,
    "execute": execute_handler
}
