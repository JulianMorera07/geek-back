from geekbaku.application.providers.cache import InMemoryProviderCache, build_cache_key


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


class TestInMemoryProviderCache:
    async def test_returns_none_when_missing(self) -> None:
        cache = InMemoryProviderCache()
        assert await cache.get("missing") is None

    async def test_set_and_get(self) -> None:
        cache = InMemoryProviderCache()
        await cache.set("key", ["a", "b"], ttl_seconds=60)

        assert await cache.get("key") == ["a", "b"]

    async def test_expires_after_ttl(self) -> None:
        clock = FakeClock()
        cache = InMemoryProviderCache(clock=clock)
        await cache.set("key", "value", ttl_seconds=10)

        clock.now += 9
        assert await cache.get("key") == "value"

        clock.now += 2
        assert await cache.get("key") is None

    async def test_clear_removes_all_entries(self) -> None:
        cache = InMemoryProviderCache()
        await cache.set("a", 1, ttl_seconds=60)
        await cache.set("b", 2, ttl_seconds=60)

        cache.clear()

        assert await cache.get("a") is None
        assert await cache.get("b") is None

    async def test_invalidate_removes_single_key(self) -> None:
        cache = InMemoryProviderCache()
        await cache.set("a", 1, ttl_seconds=60)
        await cache.set("b", 2, ttl_seconds=60)

        await cache.invalidate("a")

        assert await cache.get("a") is None
        assert await cache.get("b") == 2

    async def test_invalidate_unknown_key_is_noop(self) -> None:
        cache = InMemoryProviderCache()
        await cache.invalidate("missing")  # no debe lanzar

    async def test_invalidate_matching_removes_all_matches(self) -> None:
        cache = InMemoryProviderCache()
        await cache.set("get_genres:provider-a", 1, ttl_seconds=60)
        await cache.set("get_types:provider-a", 2, ttl_seconds=60)
        await cache.set("get_genres:provider-b", 3, ttl_seconds=60)

        await cache.invalidate_matching(lambda key: ":provider-a" in key)

        assert await cache.get("get_genres:provider-a") is None
        assert await cache.get("get_types:provider-a") is None
        assert await cache.get("get_genres:provider-b") == 3


class TestBuildCacheKey:
    def test_joins_operation_and_parts(self) -> None:
        assert build_cache_key("search", "provider-a", "naruto", "1") == (
            "search:provider-a:naruto:1"
        )

    def test_different_parts_produce_different_keys(self) -> None:
        key_one = build_cache_key("search", "provider-a", "naruto")
        key_two = build_cache_key("search", "provider-a", "one piece")
        assert key_one != key_two
