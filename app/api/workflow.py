from fastapi import APIRouter, Depends, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db, async_session_maker
from app.services.executor_service import ExecutorService
from app.services.workflow_service import WorkflowService
from app.schemas.workflow import WorkflowCreate, WorkflowResponse
from app.schemas.execution import ExecutionCreateResponse, ExecutionStatusResponse, ExecutionHistoryResponse

router = APIRouter()

def get_executor() -> ExecutorService:
    """Dependency to retrieve the executor service instance."""
    return ExecutorService(async_session_maker)

def get_workflow_service(
    db: AsyncSession = Depends(get_db),
    executor: ExecutorService = Depends(get_executor)
) -> WorkflowService:
    """Dependency to retrieve the workflow service instance."""
    return WorkflowService(db, executor)

@router.post(
    "/workflows",
    status_code=status.HTTP_201_CREATED,
    response_model=WorkflowResponse,
    summary="Create a new workflow",
    description="Registers a new workflow with sequential steps. Validates that step names map to valid step handlers."
)
async def create_workflow(
    workflow_data: WorkflowCreate,
    service: WorkflowService = Depends(get_workflow_service)
):
    return await service.create_workflow(workflow_data)

@router.post(
    "/workflows/{workflow_id}/execute",
    status_code=status.HTTP_201_CREATED,
    response_model=ExecutionCreateResponse,
    summary="Execute a workflow",
    description="Dispatches a workflow execution task in the background and returns a tracking execution ID."
)
async def execute_workflow(
    workflow_id: str,
    background_tasks: BackgroundTasks,
    service: WorkflowService = Depends(get_workflow_service)
):
    return await service.execute_workflow(workflow_id, background_tasks)

@router.get(
    "/executions/{execution_id}",
    response_model=ExecutionStatusResponse,
    summary="Get execution status",
    description="Retrieves the current execution status and the current step order number."
)
async def get_execution_status(
    execution_id: str,
    service: WorkflowService = Depends(get_workflow_service)
):
    return await service.get_execution_status(execution_id)

@router.get(
    "/executions/{execution_id}/history",
    response_model=ExecutionHistoryResponse,
    summary="Get execution history",
    description="Retrieves execution details along with status and output logs of each completed step."
)
async def get_execution_history(
    execution_id: str,
    service: WorkflowService = Depends(get_workflow_service)
):
    return await service.get_execution_history(execution_id)
