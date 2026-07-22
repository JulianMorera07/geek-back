"""`CatalogUnitOfWork` in-memory: implementación real por defecto (no un
doble de test), mismo criterio que
`InMemoryIdentityUnitOfWork`/`InMemoryPlaybackSessionRepository`
(Sprints 7/9): sin un adapter SQLAlchemy todavía (pendiente desde el
Sprint 2), correr contra un store en memoria del proceso es un default de
desarrollo razonable — permite levantar `uvicorn --reload` localmente sin
Postgres. Los datos no sobreviven un restart del proceso; cuando exista
el adapter SQLAlchemy, reemplaza este provider en
`infrastructure/http/deps.py` sin tocar ningún caso de uso.

A diferencia de `tests/unit/application/catalog/fakes.py::FakeCatalogUnitOfWork`
(que mantiene `episodes` desacoplado de `animes` a propósito, para que los
tests registren solo lo que necesitan), acá `EpisodeRepository` busca
directamente dentro del árbol `Anime -> Season -> Episode` ya persistido
en `AnimeRepository`: un default "real" debe poder resolver cualquier
episodio de cualquier anime agregado, no solo los registrados a mano.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from geekbaku.application.catalog.ports import (
    AnimeRepository,
    EpisodeRepository,
    GenreRepository,
    ProducerRepository,
    StudioRepository,
    TagRepository,
)
from geekbaku.application.common.pagination import Pagination
from geekbaku.domain.catalog.entities import Anime, Episode, Genre, Producer, Studio, Tag
from geekbaku.domain.catalog.value_objects import (
    AnimeFilter,
    AnimeId,
    EpisodeId,
    GenreId,
    ProducerId,
    Slug,
    StudioId,
    TagId,
)


class InMemoryAnimeRepository:
    def __init__(self) -> None:
        self._animes: dict[AnimeId, Anime] = {}

    async def get_by_id(self, anime_id: AnimeId) -> Anime | None:
        return self._animes.get(anime_id)

    async def get_by_slug(self, slug: Slug) -> Anime | None:
        for anime in self._animes.values():
            if anime.slug == slug:
                return anime
        return None

    async def exists_by_slug(self, slug: Slug) -> bool:
        return any(anime.slug == slug for anime in self._animes.values())

    def all_animes(self) -> list[Anime]:
        """Nombrado distinto de `list` (el método del Protocol) a
        propósito: un método de instancia llamado `list` sombrea el
        `list` builtin para el resto del cuerpo de la clase, incluidas
        las anotaciones de tipo de métodos definidos después — este
        helper debe declararse ANTES de `list` para poder anotar su
        propio retorno como `list[Anime]` sin ese conflicto.
        """
        return list(self._animes.values())

    async def list(
        self, filters: AnimeFilter, pagination: Pagination
    ) -> tuple[list[Anime], int]:
        results = list(self._animes.values())

        if filters.status is not None:
            results = [a for a in results if a.status == filters.status]
        if filters.type is not None:
            results = [a for a in results if a.type == filters.type]
        if filters.country_code is not None:
            results = [
                a for a in results if a.country and a.country.code == filters.country_code
            ]
        if filters.genre_id is not None:
            results = [a for a in results if filters.genre_id in a.genre_ids]
        if filters.studio_id is not None:
            results = [a for a in results if filters.studio_id in a.studio_ids]
        if filters.producer_id is not None:
            results = [a for a in results if filters.producer_id in a.producer_ids]
        if filters.tag_id is not None:
            results = [a for a in results if filters.tag_id in a.tag_ids]
        if filters.search_text is not None:
            needle = filters.search_text.lower()
            results = [a for a in results if needle in str(a.title).lower()]

        total = len(results)
        start = pagination.offset
        end = start + pagination.limit
        return results[start:end], total

    async def add(self, anime: Anime) -> None:
        self._animes[anime.id] = anime

    async def update(self, anime: Anime) -> None:
        self._animes[anime.id] = anime


class InMemoryEpisodeRepository:
    """Comparte estado con `InMemoryAnimeRepository` (recibido en el
    constructor): busca el episodio recorriendo `Anime.seasons` de todos
    los animes ya agregados, en vez de mantener un índice propio
    desincronizado.
    """

    def __init__(self, anime_repository: InMemoryAnimeRepository) -> None:
        self._anime_repository = anime_repository

    async def get_by_id(self, episode_id: EpisodeId) -> Episode | None:
        for anime in self._anime_repository.all_animes():
            for season in anime.seasons:
                for episode in season.episodes:
                    if episode.id == episode_id:
                        return episode
        return None


class InMemoryGenreRepository:
    def __init__(self) -> None:
        self._genres: dict[GenreId, Genre] = {}

    async def get_by_id(self, genre_id: GenreId) -> Genre | None:
        return self._genres.get(genre_id)

    async def get_by_slug(self, slug: Slug) -> Genre | None:
        return next((g for g in self._genres.values() if g.slug == slug), None)

    async def get_many_by_ids(self, genre_ids: set[GenreId]) -> list[Genre]:
        return [g for g in self._genres.values() if g.id in genre_ids]

    async def exists_by_slug(self, slug: Slug) -> bool:
        return any(g.slug == slug for g in self._genres.values())

    async def list_all(self) -> list[Genre]:
        return list(self._genres.values())

    async def add(self, genre: Genre) -> None:
        self._genres[genre.id] = genre


class InMemoryStudioRepository:
    def __init__(self) -> None:
        self._studios: dict[StudioId, Studio] = {}

    async def get_by_id(self, studio_id: StudioId) -> Studio | None:
        return self._studios.get(studio_id)

    async def get_by_slug(self, slug: Slug) -> Studio | None:
        return next((s for s in self._studios.values() if s.slug == slug), None)

    async def get_many_by_ids(self, studio_ids: set[StudioId]) -> list[Studio]:
        return [s for s in self._studios.values() if s.id in studio_ids]

    async def exists_by_slug(self, slug: Slug) -> bool:
        return any(s.slug == slug for s in self._studios.values())

    async def list_all(self) -> list[Studio]:
        return list(self._studios.values())

    async def add(self, studio: Studio) -> None:
        self._studios[studio.id] = studio


class InMemoryProducerRepository:
    def __init__(self) -> None:
        self._producers: dict[ProducerId, Producer] = {}

    async def get_by_id(self, producer_id: ProducerId) -> Producer | None:
        return self._producers.get(producer_id)

    async def get_by_slug(self, slug: Slug) -> Producer | None:
        return next((p for p in self._producers.values() if p.slug == slug), None)

    async def get_many_by_ids(self, producer_ids: set[ProducerId]) -> list[Producer]:
        return [p for p in self._producers.values() if p.id in producer_ids]

    async def exists_by_slug(self, slug: Slug) -> bool:
        return any(p.slug == slug for p in self._producers.values())

    async def list_all(self) -> list[Producer]:
        return list(self._producers.values())

    async def add(self, producer: Producer) -> None:
        self._producers[producer.id] = producer


class InMemoryTagRepository:
    def __init__(self) -> None:
        self._tags: dict[TagId, Tag] = {}

    async def get_by_id(self, tag_id: TagId) -> Tag | None:
        return self._tags.get(tag_id)

    async def get_by_slug(self, slug: Slug) -> Tag | None:
        return next((t for t in self._tags.values() if t.slug == slug), None)

    async def get_many_by_ids(self, tag_ids: set[TagId]) -> list[Tag]:
        return [t for t in self._tags.values() if t.id in tag_ids]

    async def exists_by_slug(self, slug: Slug) -> bool:
        return any(t.slug == slug for t in self._tags.values())

    async def list_all(self) -> list[Tag]:
        return list(self._tags.values())

    async def add(self, tag: Tag) -> None:
        self._tags[tag.id] = tag


class InMemoryCatalogUnitOfWork:
    """Sin transacciones reales (todo es memoria del proceso): `commit`/
    `rollback` son no-ops que solo registran haber sido llamados, para
    que un caso de uso que dependa de `UnitOfWork.commit()` funcione sin
    condicionales especiales para este adapter.
    """

    def __init__(self) -> None:
        anime_repository = InMemoryAnimeRepository()

        self.animes: AnimeRepository = anime_repository
        self.episodes: EpisodeRepository = InMemoryEpisodeRepository(anime_repository)
        self.genres: GenreRepository = InMemoryGenreRepository()
        self.studios: StudioRepository = InMemoryStudioRepository()
        self.producers: ProducerRepository = InMemoryProducerRepository()
        self.tags: TagRepository = InMemoryTagRepository()
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


__all__ = ["InMemoryCatalogUnitOfWork"]
