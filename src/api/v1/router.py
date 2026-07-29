from fastapi import APIRouter

from src.api.v1.admin.router import router as admin_router
from src.api.v1.auth.router import router as auth_router
from src.api.v1.buyer.router import router as buyer_router
from src.api.v1.public.router import router as public_router
from src.api.v1.supplier.router import router as supplier_router
from src.api.v1.ws import router as ws_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(public_router)
api_router.include_router(buyer_router)
api_router.include_router(supplier_router)
api_router.include_router(admin_router)
api_router.include_router(ws_router, prefix="/ws", tags=["websocket"])
