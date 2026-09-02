from dataclasses import dataclass

import asyncpg
from aiogram import Bot
from redis.asyncio import Redis

from app.config.settings import Settings
from app.repositories.admins import AdminRepository
from app.repositories.channels import ChannelRepository
from app.repositories.movies import MovieRepository
from app.repositories.settings import SettingsRepository
from app.repositories.users import UserRepository
from app.services.admins import AdminService
from app.services.age_gate import AgeGateService
from app.services.broadcast import BroadcastService
from app.services.cache import MovieCache
from app.services.discovery import DiscoveryService
from app.services.movies import MovieService
from app.services.subscriptions import SubscriptionService
from app.services.settings import BotSettingsService


@dataclass(slots=True)
class Services:
    users: UserRepository
    movies: MovieService
    channels: ChannelRepository
    subscriptions: SubscriptionService
    admins: AdminService
    broadcasts: BroadcastService
    configuration: BotSettingsService
    age_gate: AgeGateService
    discovery: DiscoveryService


def build_services(settings: Settings, pool: asyncpg.Pool, redis: Redis, bot: Bot) -> Services:
    users = UserRepository(pool)
    channels = ChannelRepository(pool)
    movie_repository = MovieRepository(pool)
    return Services(
        users=users,
        movies=MovieService(movie_repository, MovieCache(redis)),
        channels=channels,
        subscriptions=SubscriptionService(bot, redis, channels, settings.subscription_cache_ttl),
        admins=AdminService(redis, AdminRepository(pool), settings.admin_ids),
        broadcasts=BroadcastService(pool, redis, users, bot, settings.broadcast_concurrency, settings.broadcast_rate_per_second),
        configuration=BotSettingsService(redis, SettingsRepository(pool)),
        age_gate=AgeGateService(redis, users),
        discovery=DiscoveryService(redis, movie_repository),
    )
