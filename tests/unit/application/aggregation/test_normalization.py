from geekbaku.application.aggregation.normalization import normalize_image_url, normalize_video_url


class TestNormalizeImageUrl:
    def test_returns_none_for_none(self) -> None:
        assert normalize_image_url(None) is None

    def test_accepts_valid_http_url(self) -> None:
        assert normalize_image_url("https://cdn.example.com/a.jpg") == (
            "https://cdn.example.com/a.jpg"
        )

    def test_rejects_malformed_url(self) -> None:
        assert normalize_image_url("not-a-url") is None

    def test_rejects_non_http_scheme(self) -> None:
        assert normalize_image_url("ftp://example.com/a.jpg") is None


class TestNormalizeVideoUrl:
    def test_returns_none_for_none(self) -> None:
        assert normalize_video_url(None) is None

    def test_accepts_valid_http_url(self) -> None:
        assert normalize_video_url("https://cdn.example.com/a.mp4") == (
            "https://cdn.example.com/a.mp4"
        )

    def test_rejects_malformed_url(self) -> None:
        assert normalize_video_url("not-a-url") is None
