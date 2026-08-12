from fastapi import APIRouter, Depends

from src.core.deps import require_supplier_ctx
from src.api.v1.supplier import (
    catalog,
    companies,
    contracts,
    finance,
    notifications,
    payments,
    proposals,
    rfqs,
    subscription,
)

router = APIRouter(prefix="/supplier", dependencies=[Depends(require_supplier_ctx)])

router.include_router(companies.router)
router.include_router(catalog.router)
router.include_router(subscription.router)
router.include_router(finance.router)
router.include_router(rfqs.router)
router.include_router(proposals.router)
router.include_router(contracts.router)
router.include_router(payments.router)
router.include_router(notifications.router)
