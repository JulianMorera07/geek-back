import pytest

from geekbaku.domain.catalog.value_objects import (
    Banner,
    Country,
    Duration,
    EpisodeNumber,
    ExternalId,
    ExternalIdSource,
    ImageUrl,
    Language,
    Media,
    MediaKind,
    Rating,
    SeasonNumber,
    Slug,
    Synopsis,
    Thumbnail,
    Title,
    Trailer,
    VideoUrl,
)
from geekbaku.domain.shared.errors import ValidationError


class TestSlug:
    def test_accepts_valid_kebab_case(self) -> None:
        assert str(Slug("attack-on-titan")) == "attack-on-titan"

    @pytest.mark.parametrize(
        "raw",
        ["Attack-On-Titan", "attack_on_titan", "attack on titan", "", "-attack", "attack-"],
    )
    def test_rejects_invalid_slugs(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            Slug(raw)


class TestTitle:
    def test_rejects_empty_title(self) -> None:
        with pytest.raises(ValidationError):
            Title("   ")

    def test_rejects_title_too_long(self) -> None:
        with pytest.raises(ValidationError):
            Title("a" * 256)


class TestSynopsis:
    def test_rejects_synopsis_too_long(self) -> None:
        with pytest.raises(ValidationError):
            Synopsis("a" * 5001)


class TestCountry:
    def test_accepts_valid_iso_code(self) -> None:
        country = Country(code="JP", name="Japan")
        assert str(country) == "JP"

    @pytest.mark.parametrize("code", ["jp", "JPN", "J", ""])
    def test_rejects_invalid_iso_code(self, code: str) -> None:
        with pytest.raises(ValidationError):
            Country(code=code, name="Japan")


class TestLanguage:
    def test_accepts_valid_iso_code(self) -> None:
        language = Language(code="ja", name="Japanese")
        assert str(language) == "ja"

    @pytest.mark.parametrize("code", ["JA", "jpn", "j", ""])
    def test_rejects_invalid_iso_code(self, code: str) -> None:
        with pytest.raises(ValidationError):
            Language(code=code, name="Japanese")


class TestDuration:
    def test_rejects_non_positive_minutes(self) -> None:
        with pytest.raises(ValidationError):
            Duration(0)

    def test_rejects_minutes_above_limit(self) -> None:
        with pytest.raises(ValidationError):
            Duration(601)

    def test_accepts_valid_duration(self) -> None:
        assert Duration(24).minutes == 24


class TestMedia:
    def test_accepts_http_url(self) -> None:
        media = Media(kind=MediaKind.COVER, url="https://cdn.example.com/cover.jpg")
        assert media.url.startswith("https://")

    def test_rejects_non_http_url(self) -> None:
        with pytest.raises(ValidationError):
            Media(kind=MediaKind.COVER, url="ftp://example.com/cover.jpg")


class TestExternalId:
    def test_rejects_empty_value(self) -> None:
        with pytest.raises(ValidationError):
            ExternalId(source=ExternalIdSource.MAL, value="  ")


class TestSeasonNumber:
    def test_rejects_non_positive(self) -> None:
        with pytest.raises(ValidationError):
            SeasonNumber(0)

    def test_accepts_positive(self) -> None:
        assert SeasonNumber(1).value == 1


class TestEpisodeNumber:
    def test_rejects_non_positive(self) -> None:
        with pytest.raises(ValidationError):
            EpisodeNumber(0)

    def test_accepts_positive(self) -> None:
        assert EpisodeNumber(1).value == 1


class TestImageUrl:
    def test_accepts_http_url(self) -> None:
        assert ImageUrl("https://cdn.example.com/a.jpg").value.startswith("https://")

    def test_rejects_non_http_url(self) -> None:
        with pytest.raises(ValidationError):
            ImageUrl("ftp://example.com/a.jpg")


class TestVideoUrl:
    def test_accepts_http_url(self) -> None:
        assert VideoUrl("https://cdn.example.com/a.mp4").value.startswith("https://")

    def test_rejects_non_http_url(self) -> None:
        with pytest.raises(ValidationError):
            VideoUrl("ftp://example.com/a.mp4")


class TestThumbnailBannerTrailer:
    def test_thumbnail_wraps_image_url(self) -> None:
        thumbnail = Thumbnail(ImageUrl("https://cdn.example.com/t.jpg"))
        assert thumbnail.url.value.endswith("t.jpg")

    def test_banner_wraps_image_url(self) -> None:
        banner = Banner(ImageUrl("https://cdn.example.com/b.jpg"))
        assert banner.url.value.endswith("b.jpg")

    def test_trailer_wraps_video_url(self) -> None:
        trailer = Trailer(VideoUrl("https://cdn.example.com/tr.mp4"))
        assert trailer.url.value.endswith("tr.mp4")


class TestRating:
    def test_accepts_valid_score(self) -> None:
        rating = Rating(score=8.5, votes=100, source="mal")
        assert rating.score == 8.5

    def test_defaults_source_to_internal(self) -> None:
        assert Rating(score=5.0).source == "internal"

    @pytest.mark.parametrize("score", [-0.1, 10.1])
    def test_rejects_score_out_of_range(self, score: float) -> None:
        with pytest.raises(ValidationError):
            Rating(score=score)

    def test_rejects_negative_votes(self) -> None:
        with pytest.raises(ValidationError):
            Rating(score=5.0, votes=-1)
