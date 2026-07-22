import pytest

from geekbaku.application.providers.retry import RetryPolicy
from geekbaku.domain.providers.value_objects import RetryConfig


class RecordingSleeper:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


class TestRetryPolicy:
    async def test_returns_result_on_first_success(self) -> None:
        sleeper = RecordingSleeper()
        policy = RetryPolicy(sleep=sleeper)
        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            return "ok"

        result = await policy.run(RetryConfig(max_attempts=3), operation)

        assert result == "ok"
        assert calls == 1
        assert sleeper.delays == []

    async def test_retries_and_eventually_succeeds(self) -> None:
        sleeper = RecordingSleeper()
        policy = RetryPolicy(sleep=sleeper)
        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RuntimeError("boom")
            return "ok"

        result = await policy.run(
            RetryConfig(max_attempts=5, backoff_base_seconds=1, backoff_multiplier=2), operation
        )

        assert result == "ok"
        assert calls == 3
        assert sleeper.delays == [1, 2]

    async def test_raises_after_exhausting_attempts(self) -> None:
        policy = RetryPolicy(sleep=RecordingSleeper())
        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            raise RuntimeError(f"boom {calls}")

        with pytest.raises(RuntimeError, match="boom 3"):
            await policy.run(RetryConfig(max_attempts=3, backoff_base_seconds=0), operation)

        assert calls == 3

    async def test_invokes_on_retry_callback_with_attempt_number(self) -> None:
        policy = RetryPolicy(sleep=RecordingSleeper())
        seen: list[tuple[int, str]] = []

        async def operation() -> str:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await policy.run(
                RetryConfig(max_attempts=3, backoff_base_seconds=0),
                operation,
                on_retry=lambda attempt, exc: seen.append((attempt, str(exc))),
            )

        assert seen == [(1, "boom"), (2, "boom")]

    async def test_does_not_sleep_after_last_attempt(self) -> None:
        sleeper = RecordingSleeper()
        policy = RetryPolicy(sleep=sleeper)

        async def operation() -> str:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await policy.run(RetryConfig(max_attempts=2, backoff_base_seconds=1), operation)

        assert sleeper.delays == [1]
