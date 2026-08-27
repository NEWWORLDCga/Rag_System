from fastapi import APIRouter
from .collection import router as collection_router
from .config import router as config_router

admin_router = APIRouter(prefix="/admin")
admin_router.include_router(collection_router)
admin_router.include_router(config_router)
