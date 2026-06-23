from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True
    )

class WorkflowStepCreate(CamelModel):
    name: str
    # Use "input" for the schema matching the payload, but it will map to input_json in DB
    input: Optional[Dict[str, Any]] = None

class WorkflowStepResponse(CamelModel):
    id: int
    step_order: int
    name: str
    input: Optional[Dict[str, Any]] = Field(default=None, validation_alias="input_json")

class WorkflowCreate(CamelModel):
    workflow_id: str
    steps: List[WorkflowStepCreate]

class WorkflowResponse(CamelModel):
    id: int
    workflow_id: str
    created_at: datetime
    steps: List[WorkflowStepResponse]
