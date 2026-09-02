from aiogram import Router

from app.handlers import admin, common, join_requests, movies, user_features


def build_router() -> Router:
    router = Router()
    router.include_router(join_requests.router)
    router.include_router(common.router)
    router.include_router(admin.router)
    router.include_router(user_features.router)
    router.include_router(movies.router)
    return router
