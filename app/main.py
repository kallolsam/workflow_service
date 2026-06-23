from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from app.core.config import settings
from app.core.database import engine, Base
from app.api.workflow import router as workflow_router
# Import models to ensure they are registered with Base.metadata
import app.models  # noqa

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown lifecycle events.
    Creates database tables on startup.
    """
    # Create tables in MySQL if they do not exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    # Clean up and close connection pools
    await engine.dispose()

app = FastAPI(
    title=settings.APP_NAME,
    description="Minimal production-quality Workflow Execution Service using FastAPI and Async SQLAlchemy.",
    version="1.0.0",
    lifespan=lifespan,
    debug=settings.DEBUG
)

# Root/Health check endpoint
@app.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Simple health endpoint returning the status of the service."
)
async def health_check():
    return {"status": "healthy"}

# Register workflow API router under prefix /api/v1
app.include_router(workflow_router, prefix="/api/v1")
