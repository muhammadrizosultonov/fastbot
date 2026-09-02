import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.db.postgres import create_pool
from app.db.redis import create_redis
from app.services.container import build_services


async def main() -> None:
    settings = get_settings()
    pool = await create_pool(settings.database_url, settings.db_pool_min_size, settings.db_pool_max_size)
    redis = create_redis(settings.redis_url)
    bot = Bot(settings.bot_token.get_secret_value(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        await build_services(settings, pool, redis, bot).broadcasts.run_forever()
    finally:
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
    asyncio.run(main())


if __name__ == "__main__":
    run()
