from aiogram import Router

from .analytics import router as analytics_router
from .admin_cleanup import router as admin_cleanup_router
from .catalog import router as catalog_router
from .client import router as client_router
from .general import router as general_router
from .menu_settings import router as menu_settings_router
from .settings import router as settings_router

router = Router()
router.include_router(general_router)
router.include_router(admin_cleanup_router)
router.include_router(client_router)
router.include_router(settings_router)
router.include_router(menu_settings_router)
router.include_router(catalog_router)
router.include_router(analytics_router)
