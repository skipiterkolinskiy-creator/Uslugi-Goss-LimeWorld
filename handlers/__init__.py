from handlers.start import router as start_router
from handlers.registration import router as registration_router
from handlers.profile import router as profile_router
from handlers.medical import router as medical_router
from handlers.licenses import router as licenses_router
from handlers.payments import router as payments_router
from handlers.admin_panel import router as admin_panel_router
from handlers.admin_search import router as admin_search_router
from handlers.admin_edit import router as admin_edit_router
from handlers.moderation import router as moderation_router
from handlers.fallback import router as fallback_router

routers = [
    start_router,
    registration_router,
    profile_router,
    medical_router,
    licenses_router,
    payments_router,
    admin_panel_router,
    admin_search_router,
    admin_edit_router,
    moderation_router,
    fallback_router,
]
