import asyncio
import contextlib

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.db.postgres import create_pool
from app.db.redis import create_redis
from app.handlers import build_router
from app.middlewares.rate_limit import RateLimitMiddleware
from app.middlewares.subscription import SubscriptionMiddleware
from app.middlewares.user import UserMiddleware
from app.services.container import build_services


async def health(_: web.Request) -> web.Response:
    return web.Response(text="ok")


async def build_dispatcher():  # type: ignore[no-untyped-def]
    settings = get_settings()
    pool = await create_pool(settings.database_url, settings.db_pool_min_size, settings.db_pool_max_size)
    redis = create_redis(settings.redis_url)
    await redis.ping()
    bot = Bot(settings.bot_token.get_secret_value(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    services = build_services(settings, pool, redis, bot)
    # Redis FSM is essential when webhook requests can reach different worker processes.
    dispatcher = Dispatcher(storage=RedisStorage(redis=redis))
    dispatcher.update.outer_middleware(RateLimitMiddleware(redis, settings.rate_limit_per_second))
    dispatcher.update.outer_middleware(UserMiddleware(services))
    dispatcher.update.outer_middleware(SubscriptionMiddleware(services))
    dispatcher.include_router(build_router())
    return settings, bot, dispatcher, pool, redis, services


async def run_polling() -> None:
    settings, bot, dispatcher, pool, redis, services = await build_dispatcher()
    worker = asyncio.create_task(services.broadcasts.run_forever()) if settings.run_broadcast_worker else None
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        if worker:
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker
        await bot.session.close()
        await redis.aclose()
        await pool.close()


async def run_webhook() -> None:
    settings, bot, dispatcher, pool, redis, services = await build_dispatcher()
    app = web.Application()
    app.router.add_get("/healthz", health)
    SimpleRequestHandler(dispatcher=dispatcher, bot=bot, secret_token=settings.webhook_secret.get_secret_value() if settings.webhook_secret else None).register(app, path=settings.webhook_path)
    setup_application(app, dispatcher, bot=bot)
    await bot.set_webhook(f"{settings.webhook_url.rstrip('/')}{settings.webhook_path}", secret_token=settings.webhook_secret.get_secret_value() if settings.webhook_secret else None, allowed_updates=dispatcher.resolve_used_update_types())
    worker = asyncio.create_task(services.broadcasts.run_forever()) if settings.run_broadcast_worker else None
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.host, settings.port)
    await site.start()
    try:
        await asyncio.Event().wait()
    finally:
        if worker:
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker
        await runner.cleanup()
        await bot.session.close()
        await redis.aclose()
        await pool.close()


def run() -> None:
    configure_logging()
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass
    settings = get_settings()
    if settings.webhook_url:
        asyncio.run(run_webhook())
    else:
        asyncio.run(run_polling())
