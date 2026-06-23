from typing import List, Dict, Any, Optional
from pydantic import Field
from app.schemas.workflow import CamelModel

class ExecutionCreateResponse(CamelModel):
    execution_id: str

class ExecutionStatusResponse(CamelModel):
    execution_id: str
    status: str
    current_step: int

class ExecutionStepHistoryResponse(CamelModel):
    # Map step_name (database field) to name (schema field)
    name: str = Field(..., validation_alias="step_name")
    status: str
    # Map output_json (database field) to output (schema field)
    output: Optional[Dict[str, Any]] = Field(default=None, validation_alias="output_json")

class ExecutionHistoryResponse(CamelModel):
    execution_id: str
    status: str
    steps: List[ExecutionStepHistoryResponse]
