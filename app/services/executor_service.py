import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from app.repositories.execution_repository import ExecutionRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.handlers.step_handlers import STEP_REGISTRY

logger = logging.getLogger(__name__)

class ExecutorService:
    """
    Execution engine for sequential step workflows.
    Runs asynchronously and updates execution states and context.
    """
    def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
        self.session_maker = session_maker

    async def run_execution(self, execution_id: str) -> None:
        """
        Runs the workflow execution step-by-step.
        Obtains its own database connection to run safely in background task.
        """
        async with self.session_maker() as db:
            exec_repo = ExecutionRepository(db)
            wf_repo = WorkflowRepository(db)

            # 1. Fetch execution details
            execution = await exec_repo.get_by_execution_id(execution_id)
            if not execution:
                logger.error(f"Execution with ID {execution_id} not found.")
                return

            # 2. Fetch workflow and its steps
            # The execution belongs to a workflow. The relationship is setup.
            workflow = await wf_repo.get_by_workflow_id(execution.workflow.workflow_id)
            if not workflow:
                logger.error(f"Workflow associated with execution {execution_id} not found.")
                execution.status = "failed"
                execution.completed_at = datetime.now(timezone.utc)
                await exec_repo.update(execution)
                return

            # Update overall status to running
            execution.status = "running"
            execution.current_step = 0
            execution = await exec_repo.update(execution)

            context = {}
            steps = workflow.steps  # Order is guaranteed by order_by="WorkflowStep.step_order"

            for idx, step in enumerate(steps):
                step_num = idx + 1
                
                # Update current running step index
                execution.current_step = step_num
                execution = await exec_repo.update(execution)

                step_start_time = datetime.now(timezone.utc)
                
                # Create a database record for this step (status = "running")
                db_step = await exec_repo.create_step(
                    execution_id=execution.id,
                    step_name=step.name,
                    status="running",
                    started_at=step_start_time
                )

                # Check if step handler exists in registry
                handler = STEP_REGISTRY.get(step.name)
                if not handler:
                    error_msg = f"Invalid step name: Handler for '{step.name}' is not registered."
                    logger.error(error_msg)
                    
                    # Update step status to failed
                    db_step.status = "failed"
                    db_step.output_json = {"error": error_msg}
                    db_step.completed_at = datetime.now(timezone.utc)
                    await db.commit()

                    # Mark trailing steps as skipped
                    for remaining_step in steps[idx + 1:]:
                        await exec_repo.create_step(
                            execution_id=execution.id,
                            step_name=remaining_step.name,
                            status="skipped",
                            started_at=datetime.now(timezone.utc),
                            completed_at=datetime.now(timezone.utc)
                        )

                    # Mark workflow execution as failed
                    execution.status = "failed"
                    execution.final_context = context
                    execution.completed_at = datetime.now(timezone.utc)
                    await exec_repo.update(execution)
                    return

                try:
                    # Run the registered async handler
                    input_data = step.input_json or {}
                    output = await handler(input_data, context)

                    # Update step status to completed
                    db_step.status = "completed"
                    db_step.output_json = output
                    db_step.completed_at = datetime.now(timezone.utc)
                    await db.commit()

                    # Save to execution context for subsequent steps
                    context[step.name] = output

                except Exception as e:
                    error_msg = f"Step '{step.name}' failed with exception: {str(e)}"
                    logger.exception(error_msg)

                    # Update step status to failed
                    db_step.status = "failed"
                    db_step.output_json = {"error": str(e)}
                    db_step.completed_at = datetime.now(timezone.utc)
                    await db.commit()

                    # Mark trailing steps as skipped
                    for remaining_step in steps[idx + 1:]:
                        await exec_repo.create_step(
                            execution_id=execution.id,
                            step_name=remaining_step.name,
                            status="skipped",
                            started_at=datetime.now(timezone.utc),
                            completed_at=datetime.now(timezone.utc)
                        )

                    # Mark workflow execution as failed
                    execution.status = "failed"
                    execution.final_context = context
                    execution.completed_at = datetime.now(timezone.utc)
                    await exec_repo.update(execution)
                    return

            # Mark execution as completed when all steps finish successfully
            execution.status = "completed"
            execution.final_context = context
            execution.completed_at = datetime.now(timezone.utc)
            await exec_repo.update(execution)
