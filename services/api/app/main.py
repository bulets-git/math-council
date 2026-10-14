import logging
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.db.session import get_db
from app.routes.problems import router as problems_router
from app.routes.runs import router as runs_router
from app.routes.models import router as models_router

logger = logging.getLogger("app")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handlers
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def custom_validation_exception_handler(request: Request, exc: RequestValidationError):
    from fastapi.encoders import jsonable_encoder

    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Internal server error encountered while processing %s", request.url)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error. Please try again later."},
    )


# Health check endpoint
@app.get("/health", status_code=status.HTTP_200_OK, tags=["health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        logger.exception("Database connection check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection error",
        )


# API v1 routes
api_v1_router = APIRouter(prefix=settings.API_V1_STR)
api_v1_router.include_router(problems_router)
api_v1_router.include_router(runs_router)
api_v1_router.include_router(models_router)

app.include_router(api_v1_router)


@app.get("/")
async def root():
    return {"message": "Math Council API is running", "docs": "/docs", "health": "/health"}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=status.HTTP_204_NO_CONTENT)