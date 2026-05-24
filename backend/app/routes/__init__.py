from fastapi import APIRouter, Depends, HTTPException

from backend.app.db.session import database_configured

from .accounts import router as accounts_router


def require_database_configured() -> None:
    if not database_configured():
        raise HTTPException(status_code=503, detail="Database not configured")


api_router = APIRouter(dependencies=[Depends(require_database_configured)])
api_router.include_router(accounts_router)
