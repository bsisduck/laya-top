from laya_top.benchmarking import summary


def test_benchmark_summary_uses_nearest_rank_p95():
    samples = [value / 1000 for value in range(1, 21)]

    assert summary(samples) == {
        "minimum_ms": 1.0,
        "median_ms": 10.5,
        "p95_ms": 19.0,
        "maximum_ms": 20.0,
    }
