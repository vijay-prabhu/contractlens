from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.database import init_db, close_db
from app.core.exceptions import (
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler,
)
from app.api.documents import router as documents_router
from app.api.search import router as search_router
from app.api.comparison import router as comparison_router
from app.workers import start_processor, stop_processor

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle events."""
    # Startup
    print("Starting up ContractLens API...")
    # Note: Tables are managed via SQL migrations, not auto-created
    await start_processor()
    print("Background processor started.")
    print("Ready to accept connections.")
    yield
    # Shutdown
    print("Shutting down...")
    await stop_processor()
    print("Background processor stopped.")
    await close_db()
    print("Database connections closed.")


app = FastAPI(
    title=settings.app_name,
    description="AI-powered contract review and risk analysis API",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# Exception handlers
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(documents_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(comparison_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Welcome to ContractLens API", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "environment": settings.environment}
