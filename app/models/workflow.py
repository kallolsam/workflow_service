from datetime import datetime, timezone
from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List
from app.core.database import Base

class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False
    )

    # Relationships
    steps: Mapped[List["WorkflowStep"]] = relationship(
        "WorkflowStep", 
        back_populates="workflow", 
        cascade="all, delete-orphan",
        order_by="WorkflowStep.step_order"
    )
    executions: Mapped[List["Execution"]] = relationship(
        "Execution", 
        back_populates="workflow", 
        cascade="all, delete-orphan"
    )
