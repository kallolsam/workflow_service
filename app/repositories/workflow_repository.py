from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import Optional, List, Dict, Any
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep

class WorkflowRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_workflow_id(self, workflow_id: str) -> Optional[Workflow]:
        """Fetch a workflow by its unique string workflow_id including its steps."""
        result = await self.db.execute(
            select(Workflow)
            .where(Workflow.workflow_id == workflow_id)
            .options(selectinload(Workflow.steps))
        )
        return result.scalar_one_or_none()

    async def create(self, workflow_id: str, steps_data: List[Dict[str, Any]]) -> Workflow:
        """Create a workflow and its associated workflow steps in order."""
        workflow = Workflow(workflow_id=workflow_id)
        self.db.add(workflow)
        await self.db.flush()  # Populate workflow.id to link steps
        
        for idx, step in enumerate(steps_data):
            workflow_step = WorkflowStep(
                workflow_id=workflow.id,
                step_order=idx + 1,
                name=step["name"],
                input_json=step.get("input")
            )
            self.db.add(workflow_step)
            
        await self.db.commit()
        # Fetch again or refresh to ensure all relationships are loaded
        result = await self.db.execute(
            select(Workflow)
            .where(Workflow.id == workflow.id)
            .options(selectinload(Workflow.steps))
        )
        return result.scalar_one()
