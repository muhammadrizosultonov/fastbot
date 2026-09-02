from app.repositories.models import Movie
from app.repositories.movies import MovieRepository
from app.services.cache import MovieCache


class MovieService:
    def __init__(self, repository: MovieRepository, cache: MovieCache) -> None:
        self.repository = repository
        self.cache = cache

    async def find(self, code: str) -> Movie | None:
        # Only a compact Redis payload crosses the network on the hot path.
        cached, movie = await self.cache.get(code)
        if cached:
            return movie
        movie = await self.repository.get_by_code(code)
        if movie:
            await self.cache.set(movie)
        else:
            await self.cache.set_not_found(code)
        return movie

    async def save(self, movie: Movie) -> None:
        await self.repository.upsert(movie)
        await self.cache.set(movie)

    async def delete(self, code: str) -> bool:
        deleted = await self.repository.delete(code)
        if deleted:
            await self.cache.set_not_found(code)
        return deleted
