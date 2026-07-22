import pytest

from geekbaku.domain.catalog.value_objects import (
    AnimeType,
    ImageUrl,
    StreamQuality,
    Thumbnail,
)
from geekbaku.domain.providers.value_objects import (
    CacheConfig,
    Catalog,
    ExternalReference,
    ProviderConfiguration,
    ProviderId,
    ProviderMetadata,
    ProviderStatus,
    RateLimitConfig,
    RetryConfig,
    SearchResult,
    Source,
)
from geekbaku.domain.shared.errors import ValidationError


class TestProviderId:
    def test_accepts_kebab_case(self) -> None:
        assert str(ProviderId("provider-a")) == "provider-a"

    @pytest.mark.parametrize("raw", ["Provider-A", "provider_a", ""])
    def test_rejects_invalid_format(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            ProviderId(raw)


class TestExternalReference:
    def test_rejects_empty_external_id(self) -> None:
        with pytest.raises(ValidationError):
            ExternalReference(provider_id=ProviderId("provider-a"), external_id=" ")

    def test_accepts_valid_reference(self) -> None:
        reference = ExternalReference(provider_id=ProviderId("provider-a"), external_id="123")
        assert reference.external_id == "123"


class TestProviderMetadata:
    def test_rejects_empty_display_name(self) -> None:
        with pytest.raises(ValidationError):
            ProviderMetadata(display_name=" ")

    def test_defaults_all_capabilities_to_true(self) -> None:
        metadata = ProviderMetadata(display_name="Provider A")
        assert metadata.supports_search is True
        assert metadata.supports_latest is True
        assert metadata.supports_popular is True
        assert metadata.supports_genres is True
        assert metadata.supports_types is True


class TestSource:
    def test_rejects_empty_url(self) -> None:
        reference = ExternalReference(provider_id=ProviderId("provider-a"), external_id="1")
        with pytest.raises(ValidationError):
            Source(reference=reference, url=" ", quality=StreamQuality.HD)


class TestSearchResult:
    def test_rejects_empty_title(self) -> None:
        reference = ExternalReference(provider_id=ProviderId("provider-a"), external_id="1")
        with pytest.raises(ValidationError):
            SearchResult(reference=reference, title=" ")

    def test_accepts_optional_fields(self) -> None:
        reference = ExternalReference(provider_id=ProviderId("provider-a"), external_id="1")
        result = SearchResult(
            reference=reference,
            title="Attack on Titan",
            thumbnail=Thumbnail(ImageUrl("https://cdn.example.com/t.jpg")),
            anime_type=AnimeType.TV,
            year=2013,
        )
        assert result.year == 2013


class TestCatalog:
    def test_holds_genres_and_types(self) -> None:
        catalog = Catalog(
            provider_id=ProviderId("provider-a"),
            genres=("Action", "Isekai"),
            types=("TV", "Movie"),
        )
        assert catalog.genres == ("Action", "Isekai")
        assert catalog.types == ("TV", "Movie")


class TestProviderStatus:
    def test_has_four_states(self) -> None:
        assert {s.value for s in ProviderStatus} == {"unknown", "healthy", "degraded", "down"}


class TestRateLimitConfig:
    def test_rejects_non_positive_max_requests(self) -> None:
        with pytest.raises(ValidationError):
            RateLimitConfig(max_requests=0, period_seconds=60)

    def test_rejects_non_positive_period(self) -> None:
        with pytest.raises(ValidationError):
            RateLimitConfig(max_requests=10, period_seconds=0)

    def test_accepts_valid_config(self) -> None:
        config = RateLimitConfig(max_requests=10, period_seconds=60)
        assert config.max_requests == 10


class TestRetryConfig:
    def test_defaults(self) -> None:
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.backoff_multiplier == 2.0

    def test_rejects_zero_attempts(self) -> None:
        with pytest.raises(ValidationError):
            RetryConfig(max_attempts=0)

    def test_rejects_negative_backoff_base(self) -> None:
        with pytest.raises(ValidationError):
            RetryConfig(backoff_base_seconds=-1)

    def test_rejects_multiplier_below_one(self) -> None:
        with pytest.raises(ValidationError):
            RetryConfig(backoff_multiplier=0.5)


class TestCacheConfig:
    def test_defaults_enabled(self) -> None:
        config = CacheConfig()
        assert config.enabled is True
        assert config.ttl_seconds == 300.0

    def test_rejects_negative_ttl(self) -> None:
        with pytest.raises(ValidationError):
            CacheConfig(ttl_seconds=-1)


class TestProviderConfiguration:
    def test_accepts_minimal_configuration(self) -> None:
        config = ProviderConfiguration(
            provider_id=ProviderId("provider-a"), base_url="https://example.com"
        )
        assert config.timeout_seconds == 10.0
        assert config.rate_limit is None
        assert isinstance(config.retry, RetryConfig)
        assert isinstance(config.cache, CacheConfig)

    def test_rejects_empty_base_url(self) -> None:
        with pytest.raises(ValidationError):
            ProviderConfiguration(provider_id=ProviderId("provider-a"), base_url=" ")

    def test_rejects_non_positive_timeout(self) -> None:
        with pytest.raises(ValidationError):
            ProviderConfiguration(
                provider_id=ProviderId("provider-a"),
                base_url="https://example.com",
                timeout_seconds=0,
            )
