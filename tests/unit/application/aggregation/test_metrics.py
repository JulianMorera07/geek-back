from geekbaku.application.aggregation.metrics import AggregationMetrics


class TestAggregationMetrics:
    def test_starts_at_zero(self) -> None:
        metrics = AggregationMetrics()
        assert metrics.total_aggregations == 0
        assert metrics.average_raw_results_per_aggregation == 0.0
        assert metrics.deduplication_rate == 0.0
        assert metrics.cache_hit_rate == 0.0

    def test_records_aggregation_counts(self) -> None:
        metrics = AggregationMetrics()

        metrics.record_aggregation(raw_count=5, merged_count=3)

        assert metrics.total_aggregations == 1
        assert metrics.total_raw_results == 5
        assert metrics.total_merged_results == 3
        assert metrics.total_duplicates_merged == 2

    def test_deduplication_rate(self) -> None:
        metrics = AggregationMetrics()
        metrics.record_aggregation(raw_count=10, merged_count=4)

        assert metrics.deduplication_rate == 0.6

    def test_average_raw_results_per_aggregation(self) -> None:
        metrics = AggregationMetrics()
        metrics.record_aggregation(raw_count=4, merged_count=4)
        metrics.record_aggregation(raw_count=6, merged_count=6)

        assert metrics.average_raw_results_per_aggregation == 5.0

    def test_cache_hit_rate(self) -> None:
        metrics = AggregationMetrics()
        metrics.record_cache_hit()
        metrics.record_cache_hit()
        metrics.record_cache_miss()

        assert metrics.cache_hit_rate == 2 / 3

    def test_no_duplicates_when_merged_equals_raw(self) -> None:
        metrics = AggregationMetrics()
        metrics.record_aggregation(raw_count=3, merged_count=3)
        assert metrics.total_duplicates_merged == 0
