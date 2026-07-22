import pytest

from geekbaku.domain.catalog.entities import (
    Anime,
    Episode,
    Genre,
    Producer,
    Season,
    StreamingSource,
    Studio,
    Tag,
)
from geekbaku.domain.catalog.exceptions import (
    DuplicateEpisodeNumberError,
    DuplicateExternalIdError,
    DuplicateRelationError,
    DuplicateSeasonNumberError,
    DuplicateStreamingSourceError,
    EpisodeNotFoundError,
    InvalidStatusTransitionError,
    SeasonNotFoundError,
    SelfRelationError,
    StreamingSourceNotFoundError,
)
from geekbaku.domain.catalog.value_objects import (
    AnimeId,
    AnimeStatus,
    AnimeType,
    EpisodeId,
    EpisodeNumber,
    ExternalId,
    ExternalIdSource,
    GenreId,
    ImageUrl,
    Language,
    Media,
    MediaKind,
    ProducerId,
    Rating,
    Relation,
    RelationType,
    SeasonId,
    SeasonNumber,
    Slug,
    StreamingSourceId,
    StreamQuality,
    StudioId,
    TagId,
    Title,
    VideoUrl,
)
from geekbaku.domain.shared.errors import ValidationError

JAPANESE = Language(code="ja", name="Japanese")


def make_anime(
    status: AnimeStatus = AnimeStatus.ANNOUNCED, anime_type: AnimeType = AnimeType.TV
) -> Anime:
    return Anime(
        id=AnimeId.new(),
        title=Title("Attack on Titan"),
        slug=Slug("attack-on-titan"),
        anime_type=anime_type,
        status=status,
    )


def make_episode(number: int = 1) -> Episode:
    return Episode(
        id=EpisodeId.new(), number=EpisodeNumber(number), title=Title(f"Episode {number}")
    )


def make_streaming_source(provider: str = "provider_a", ref: str = "ep-1") -> StreamingSource:
    return StreamingSource(
        id=StreamingSourceId.new(),
        provider_name=provider,
        external_ref=ref,
        quality=StreamQuality.HD,
        audio_language=JAPANESE,
    )


class TestGenreStudioProducerTag:
    def test_genre_rejects_empty_name(self) -> None:
        with pytest.raises(ValidationError):
            Genre(id=GenreId.new(), name=" ", slug=Slug("shonen"))

    def test_studio_accepts_optional_country(self) -> None:
        studio = Studio(id=StudioId.new(), name="MAPPA", slug=Slug("mappa"), country=None)
        assert studio.country is None

    def test_producer_rejects_empty_name(self) -> None:
        with pytest.raises(ValidationError):
            Producer(id=ProducerId.new(), name=" ", slug=Slug("aniplex"))

    def test_producer_equality_by_id(self) -> None:
        producer_id = ProducerId.new()
        producer_a = Producer(id=producer_id, name="Aniplex", slug=Slug("aniplex"))
        producer_b = Producer(id=producer_id, name="Different name", slug=Slug("aniplex"))
        assert producer_a == producer_b
        assert hash(producer_a) == hash(producer_b)

    def test_tag_equality_by_id(self) -> None:
        tag_id = TagId.new()
        tag_a = Tag(id=tag_id, name="Isekai", slug=Slug("isekai"))
        tag_b = Tag(id=tag_id, name="Different name", slug=Slug("isekai"))
        assert tag_a == tag_b
        assert hash(tag_a) == hash(tag_b)


class TestStreamingSource:
    def test_rejects_empty_provider_name(self) -> None:
        with pytest.raises(ValidationError):
            StreamingSource(
                id=StreamingSourceId.new(),
                provider_name="  ",
                external_ref="ep-1",
                quality=StreamQuality.HD,
                audio_language=JAPANESE,
            )

    def test_activate_and_deactivate(self) -> None:
        source = make_streaming_source()
        source.deactivate()
        assert source.is_active is False
        source.activate()
        assert source.is_active is True

    def test_accepts_optional_video_url(self) -> None:
        source = StreamingSource(
            id=StreamingSourceId.new(),
            provider_name="provider_a",
            external_ref="ep-1",
            quality=StreamQuality.HD,
            audio_language=JAPANESE,
            url=VideoUrl("https://cdn.example.com/ep-1.m3u8"),
        )
        assert source.url is not None
        assert source.url.value == "https://cdn.example.com/ep-1.m3u8"


class TestEpisode:
    def test_add_streaming_source(self) -> None:
        episode = make_episode()
        source = make_streaming_source()
        episode.add_streaming_source(source)
        assert episode.streaming_sources == (source,)

    def test_add_duplicate_streaming_source_raises(self) -> None:
        episode = make_episode()
        episode.add_streaming_source(make_streaming_source())
        with pytest.raises(DuplicateStreamingSourceError):
            episode.add_streaming_source(make_streaming_source())

    def test_remove_streaming_source(self) -> None:
        episode = make_episode()
        source = make_streaming_source()
        episode.add_streaming_source(source)
        episode.remove_streaming_source(source.id)
        assert episode.streaming_sources == ()

    def test_remove_unknown_streaming_source_raises(self) -> None:
        episode = make_episode()
        with pytest.raises(StreamingSourceNotFoundError):
            episode.remove_streaming_source(StreamingSourceId.new())

    def test_add_external_id_rejects_duplicate_source(self) -> None:
        episode = make_episode()
        episode.add_external_id(ExternalId(source=ExternalIdSource.MAL, value="123"))
        with pytest.raises(DuplicateExternalIdError):
            episode.add_external_id(ExternalId(source=ExternalIdSource.MAL, value="456"))

    def test_thumbnail_derived_from_media(self) -> None:
        episode = make_episode()
        assert episode.thumbnail is None
        episode.add_media(Media(kind=MediaKind.THUMBNAIL, url="https://cdn.example.com/t.jpg"))
        assert episode.thumbnail is not None
        assert episode.thumbnail.url == ImageUrl("https://cdn.example.com/t.jpg")


class TestSeason:
    def test_add_episode_rejects_duplicate_number(self) -> None:
        season = Season(id=SeasonId.new(), number=SeasonNumber(1))
        season.add_episode(make_episode(number=1))
        with pytest.raises(DuplicateEpisodeNumberError):
            season.add_episode(make_episode(number=1))

    def test_get_episode_not_found_raises(self) -> None:
        season = Season(id=SeasonId.new(), number=SeasonNumber(1))
        with pytest.raises(EpisodeNotFoundError):
            season.get_episode(EpisodeId.new())


class TestAnime:
    def test_defaults_to_announced_status(self) -> None:
        anime = make_anime()
        assert anime.status == AnimeStatus.ANNOUNCED

    def test_add_genre_is_idempotent(self) -> None:
        anime = make_anime()
        genre_id = GenreId.new()
        anime.add_genre(genre_id)
        anime.add_genre(genre_id)
        assert anime.genre_ids == frozenset({genre_id})

    def test_add_producer_is_idempotent(self) -> None:
        anime = make_anime()
        producer_id = ProducerId.new()
        anime.add_producer(producer_id)
        anime.add_producer(producer_id)
        assert anime.producer_ids == frozenset({producer_id})

    def test_add_season_rejects_duplicate_number(self) -> None:
        anime = make_anime()
        anime.add_season(Season(id=SeasonId.new(), number=SeasonNumber(1)))
        with pytest.raises(DuplicateSeasonNumberError):
            anime.add_season(Season(id=SeasonId.new(), number=SeasonNumber(1)))

    def test_get_season_not_found_raises(self) -> None:
        anime = make_anime()
        with pytest.raises(SeasonNotFoundError):
            anime.get_season(SeasonId.new())

    def test_find_episode_across_seasons(self) -> None:
        anime = make_anime()
        season = Season(id=SeasonId.new(), number=SeasonNumber(1))
        episode = make_episode(number=1)
        season.add_episode(episode)
        anime.add_season(season)

        found = anime.find_episode(episode.id)

        assert found is episode

    def test_find_episode_not_found_raises(self) -> None:
        anime = make_anime()
        with pytest.raises(EpisodeNotFoundError):
            anime.find_episode(EpisodeId.new())

    def test_add_external_id_rejects_duplicate_source(self) -> None:
        anime = make_anime()
        anime.add_external_id(ExternalId(source=ExternalIdSource.ANILIST, value="1"))
        with pytest.raises(DuplicateExternalIdError):
            anime.add_external_id(ExternalId(source=ExternalIdSource.ANILIST, value="2"))

    def test_add_relation_rejects_self_relation(self) -> None:
        anime = make_anime()
        with pytest.raises(SelfRelationError):
            anime.add_relation(
                Relation(related_anime_id=anime.id, relation_type=RelationType.SEQUEL)
            )

    def test_add_relation_rejects_duplicate(self) -> None:
        anime = make_anime()
        related_id = AnimeId.new()
        anime.add_relation(Relation(related_anime_id=related_id, relation_type=RelationType.SEQUEL))
        with pytest.raises(DuplicateRelationError):
            anime.add_relation(
                Relation(related_anime_id=related_id, relation_type=RelationType.SEQUEL)
            )

    def test_change_status_valid_transition(self) -> None:
        anime = make_anime(status=AnimeStatus.ANNOUNCED)
        anime.change_status(AnimeStatus.ONGOING)
        assert anime.status == AnimeStatus.ONGOING

    def test_change_status_same_status_is_noop(self) -> None:
        anime = make_anime(status=AnimeStatus.ONGOING)
        updated_at_before = anime.updated_at
        anime.change_status(AnimeStatus.ONGOING)
        assert anime.updated_at == updated_at_before

    def test_change_status_invalid_transition_raises(self) -> None:
        anime = make_anime(status=AnimeStatus.COMPLETED)
        with pytest.raises(InvalidStatusTransitionError):
            anime.change_status(AnimeStatus.ONGOING)

    def test_set_rating(self) -> None:
        anime = make_anime()
        assert anime.rating is None
        anime.set_rating(Rating(score=8.5, votes=1000, source="mal"))
        assert anime.rating == Rating(score=8.5, votes=1000, source="mal")

    def test_thumbnail_banner_trailer_derived_from_media(self) -> None:
        anime = make_anime()
        assert anime.thumbnail is None
        assert anime.banner is None
        assert anime.trailer is None

        anime.add_media(Media(kind=MediaKind.THUMBNAIL, url="https://cdn.example.com/t.jpg"))
        anime.add_media(Media(kind=MediaKind.BANNER, url="https://cdn.example.com/b.jpg"))
        anime.add_media(Media(kind=MediaKind.TRAILER, url="https://cdn.example.com/tr.mp4"))

        assert anime.thumbnail is not None and anime.thumbnail.url.value.endswith("t.jpg")
        assert anime.banner is not None and anime.banner.url.value.endswith("b.jpg")
        assert anime.trailer is not None and anime.trailer.url.value.endswith("tr.mp4")

    def test_equality_by_id(self) -> None:
        anime_id = AnimeId.new()
        anime_a = Anime(
            id=anime_id, title=Title("A"), slug=Slug("a"), anime_type=AnimeType.TV
        )
        anime_b = Anime(
            id=anime_id, title=Title("B"), slug=Slug("b"), anime_type=AnimeType.MOVIE
        )
        assert anime_a == anime_b
        assert hash(anime_a) == hash(anime_b)
