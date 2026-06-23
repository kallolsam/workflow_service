from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from app.models.execution import Execution
from app.models.execution_step import ExecutionStep

class ExecutionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_execution_id(self, execution_id: str) -> Optional[Execution]:
        """Fetch an execution by its UUID execution_id, including its steps."""
        result = await self.db.execute(
            select(Execution)
            .where(Execution.execution_id == execution_id)
            .options(
                selectinload(Execution.steps),
                selectinload(Execution.workflow)
            )
        )
        return result.scalar_one_or_none()

    async def create(self, workflow_id: int) -> Execution:
        """Create a new execution record."""
        execution = Execution(
            workflow_id=workflow_id,
            status="pending",
            current_step=0,
            started_at=datetime.now(timezone.utc)
        )
        self.db.add(execution)
        await self.db.commit()
        # Fetch with loaded steps (which will be empty initially)
        return await self.get_by_execution_id(execution.execution_id)

    async def update(self, execution: Execution) -> Execution:
        """Update an existing execution record."""
        self.db.add(execution)
        await self.db.commit()
        # Return refreshed execution with steps
        return await self.get_by_execution_id(execution.execution_id)

    async def create_step(
        self,
        execution_id: int,
        step_name: str,
        status: str,
        output_json: Optional[Dict[str, Any]] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ) -> ExecutionStep:
        """Create a new execution step record."""
        step = ExecutionStep(
            execution_id=execution_id,
            step_name=step_name,
            status=status,
            output_json=output_json,
            started_at=started_at or datetime.now(timezone.utc),
            completed_at=completed_at
        )
        self.db.add(step)
        await self.db.commit()
        await self.db.refresh(step)
        return step
