from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import BackgroundTasks, HTTPException, status
from app.repositories.workflow_repository import WorkflowRepository
from app.repositories.execution_repository import ExecutionRepository
from app.services.executor_service import ExecutorService
from app.models.workflow import Workflow
from app.schemas.workflow import WorkflowCreate
from app.schemas.execution import ExecutionCreateResponse, ExecutionStatusResponse, ExecutionHistoryResponse
from sqlalchemy.exc import IntegrityError

class WorkflowService:
    """
    Main Service orchestrating Workflows and Executions.
    """
    def __init__(self, db: AsyncSession, executor: ExecutorService):
        self.db = db
        self.executor = executor
        self.workflow_repo = WorkflowRepository(db)
        self.execution_repo = ExecutionRepository(db)

    async def create_workflow(self, workflow_data: WorkflowCreate) -> Workflow:
        """
        Creates a new workflow with its steps.
        Checks for duplicate workflow IDs.
        """
        existing = await self.workflow_repo.get_by_workflow_id(workflow_data.workflow_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Workflow with ID '{workflow_data.workflow_id}' already exists."
            )

        # Convert Pydantic schemas to dictionary format for repository
        steps_list = []
        for step in workflow_data.steps:
            # Validate step name is in registry
            from app.handlers.step_handlers import STEP_REGISTRY
            if step.name not in STEP_REGISTRY:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid step name: '{step.name}'. Must be one of {list(STEP_REGISTRY.keys())}"
                )
            
            steps_list.append({
                "name": step.name,
                "input": step.input
            })

        try:
            return await self.workflow_repo.create(workflow_data.workflow_id, steps_list)
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Workflow with ID '{workflow_data.workflow_id}' already exists."
            )

    async def execute_workflow(self, workflow_id: str, background_tasks: BackgroundTasks) -> ExecutionCreateResponse:
        """
        Initiates workflow execution. Creates a pending execution record and
        kicks off execution asynchronously in a background thread/task.
        """
        workflow = await self.workflow_repo.get_by_workflow_id(workflow_id)
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow with ID '{workflow_id}' not found."
            )

        # Create base execution in the database (marked pending)
        execution = await self.execution_repo.create(workflow.id)

        # Dispatch execution engine to run in background
        background_tasks.add_task(self.executor.run_execution, execution.execution_id)

        return ExecutionCreateResponse(execution_id=execution.execution_id)

    async def get_execution_status(self, execution_id: str) -> ExecutionStatusResponse:
        """
        Retrieves current execution status and step index.
        """
        execution = await self.execution_repo.get_by_execution_id(execution_id)
        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution with ID '{execution_id}' not found."
            )
        return ExecutionStatusResponse.model_validate(execution)

    async def get_execution_history(self, execution_id: str) -> ExecutionHistoryResponse:
        """
        Retrieves history of steps executed along with status and output.
        """
        execution = await self.execution_repo.get_by_execution_id(execution_id)
        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution with ID '{execution_id}' not found."
            )
        return ExecutionHistoryResponse.model_validate(execution)
