import asyncio

from geekbaku.infrastructure.identity.brute_force_guard import InMemoryBruteForceGuard


class TestInMemoryBruteForceGuard:
    async def test_not_blocked_initially(self) -> None:
        guard = InMemoryBruteForceGuard(max_failures=3, window_seconds=60)
        assert await guard.is_blocked("key") is False

    async def test_blocks_after_max_failures(self) -> None:
        guard = InMemoryBruteForceGuard(max_failures=3, window_seconds=60)
        for _ in range(3):
            await guard.register_failure("key")

        assert await guard.is_blocked("key") is True

    async def test_success_clears_failures(self) -> None:
        guard = InMemoryBruteForceGuard(max_failures=3, window_seconds=60)
        for _ in range(3):
            await guard.register_failure("key")

        await guard.register_success("key")

        assert await guard.is_blocked("key") is False

    async def test_window_expiry_clears_block(self) -> None:
        guard = InMemoryBruteForceGuard(max_failures=1, window_seconds=1)
        await guard.register_failure("key")
        assert await guard.is_blocked("key") is True

        await asyncio.sleep(1.2)

        assert await guard.is_blocked("key") is False

    async def test_keys_are_independent(self) -> None:
        guard = InMemoryBruteForceGuard(max_failures=1, window_seconds=60)
        await guard.register_failure("key-a")

        assert await guard.is_blocked("key-a") is True
        assert await guard.is_blocked("key-b") is False
