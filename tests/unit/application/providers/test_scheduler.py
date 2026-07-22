import pytest

from geekbaku.application.providers.scheduler import InMemorySyncJobRegistry, SyncJobDefinition
from geekbaku.domain.providers.value_objects import ProviderId
from geekbaku.domain.shared.errors import ValidationError

PROVIDER_A = ProviderId("provider-a")


class TestSyncJobDefinition:
    def test_accepts_valid_syncable_operation(self) -> None:
        job = SyncJobDefinition(provider_id=PROVIDER_A, operation="latest", interval_seconds=3600)
        assert job.operation == "latest"

    def test_rejects_non_syncable_operation(self) -> None:
        with pytest.raises(ValidationError):
            SyncJobDefinition(
                provider_id=PROVIDER_A, operation="get_anime_detail", interval_seconds=3600
            )

    def test_rejects_non_positive_interval(self) -> None:
        with pytest.raises(ValidationError):
            SyncJobDefinition(provider_id=PROVIDER_A, operation="latest", interval_seconds=0)


class TestInMemorySyncJobRegistry:
    def test_add_and_list(self) -> None:
        registry = InMemorySyncJobRegistry()
        job = SyncJobDefinition(provider_id=PROVIDER_A, operation="latest", interval_seconds=3600)

        registry.add(job)

        assert registry.list_all() == (job,)
        assert registry.get(PROVIDER_A, "latest") == job

    def test_add_replaces_existing_job_for_same_operation(self) -> None:
        registry = InMemorySyncJobRegistry()
        registry.add(
            SyncJobDefinition(provider_id=PROVIDER_A, operation="latest", interval_seconds=3600)
        )
        updated = SyncJobDefinition(
            provider_id=PROVIDER_A, operation="latest", interval_seconds=7200
        )

        registry.add(updated)

        assert registry.list_all() == (updated,)

    def test_remove(self) -> None:
        registry = InMemorySyncJobRegistry()
        registry.add(
            SyncJobDefinition(provider_id=PROVIDER_A, operation="latest", interval_seconds=3600)
        )

        registry.remove(PROVIDER_A, "latest")

        assert registry.list_all() == ()

    def test_remove_unknown_is_noop(self) -> None:
        registry = InMemorySyncJobRegistry()
        registry.remove(PROVIDER_A, "latest")
        assert registry.list_all() == ()

    def test_list_enabled_excludes_disabled_jobs(self) -> None:
        registry = InMemorySyncJobRegistry()
        registry.add(
            SyncJobDefinition(provider_id=PROVIDER_A, operation="latest", interval_seconds=3600)
        )
        registry.add(
            SyncJobDefinition(
                provider_id=PROVIDER_A, operation="popular", interval_seconds=3600, enabled=False
            )
        )

        enabled = registry.list_enabled()

        assert len(enabled) == 1
        assert enabled[0].operation == "latest"
