from creator_agent.collectors.youtube_browser import (
    BrowserCollectionUnavailable,
    collect_page_html,
    extract_yt_initial_data,
    parse_channel_recent_videos,
    parse_video_metadata,
)


def test_extract_yt_initial_data_reads_embedded_json():
    html = """
    <html>
      <script>
        var ytInitialData = {"contents":{"twoColumnWatchNextResults":{"results":{}}}};
      </script>
    </html>
    """

    data = extract_yt_initial_data(html)

    assert "contents" in data


def test_parse_video_metadata_reads_watch_page_initial_data():
    initial_data = {
        "contents": {
            "twoColumnWatchNextResults": {
                "results": {
                    "results": {
                        "contents": [
                            {
                                "videoPrimaryInfoRenderer": {
                                    "title": {"runs": [{"text": "How creators build durable growth"}]},
                                    "viewCount": {
                                        "videoViewCountRenderer": {
                                            "viewCount": {"simpleText": "12,345 views"}
                                        }
                                    },
                                    "dateText": {"simpleText": "Jun 6, 2026"},
                                }
                            },
                            {
                                "videoSecondaryInfoRenderer": {
                                    "owner": {
                                        "videoOwnerRenderer": {
                                            "title": {
                                                "runs": [
                                                    {
                                                        "text": "Growth Lab",
                                                        "navigationEndpoint": {
                                                            "browseEndpoint": {
                                                                "browseId": "UC123",
                                                                "canonicalBaseUrl": "/@growthlab",
                                                            }
                                                        },
                                                    }
                                                ]
                                            }
                                        }
                                    }
                                }
                            },
                        ]
                    }
                }
            }
        }
    }

    metadata = parse_video_metadata(
        initial_data=initial_data,
        video_url="https://www.youtube.com/watch?v=abc123",
        fallback_video_id="abc123",
    )

    assert metadata["youtube_video_id"] == "abc123"
    assert metadata["title"] == "How creators build durable growth"
    assert metadata["view_count"] == 12345
    assert metadata["published_text"] == "Jun 6, 2026"
    assert metadata["channel"] == {
        "id": "UC123",
        "title": "Growth Lab",
        "url": "https://www.youtube.com/@growthlab",
    }


def test_parse_channel_recent_videos_reads_grid_items():
    initial_data = {
        "contents": {
            "richGridRenderer": {
                "contents": [
                    {
                        "richItemRenderer": {
                            "content": {
                                "videoRenderer": {
                                    "videoId": "abc123",
                                    "title": {"runs": [{"text": "First video"}]},
                                    "publishedTimeText": {"simpleText": "1 day ago"},
                                    "viewCountText": {"simpleText": "1.2K views"},
                                }
                            }
                        }
                    },
                    {
                        "richItemRenderer": {
                            "content": {
                                "videoRenderer": {
                                    "videoId": "def456",
                                    "title": {"simpleText": "Second video"},
                                    "viewCountText": {"simpleText": "987 views"},
                                }
                            }
                        }
                    },
                ]
            }
        }
    }

    videos = parse_channel_recent_videos(initial_data, limit=1)

    assert videos == [
        {
            "youtube_video_id": "abc123",
            "title": "First video",
            "url": "https://www.youtube.com/watch?v=abc123",
            "published_text": "1 day ago",
            "view_count": 1200,
        }
    ]


def test_parse_channel_recent_videos_handles_large_and_localized_view_counts():
    initial_data = {
        "contents": {
            "richGridRenderer": {
                "contents": [
                    {
                        "richItemRenderer": {
                            "content": {
                                "videoRenderer": {
                                    "videoId": "abc123",
                                    "title": {"runs": [{"text": "Billion view video"}]},
                                    "viewCountText": {"simpleText": "1.5B views"},
                                }
                            }
                        }
                    },
                    {
                        "richItemRenderer": {
                            "content": {
                                "videoRenderer": {
                                    "videoId": "def456",
                                    "title": {"simpleText": "Chinese count video"},
                                    "viewCountText": {"simpleText": "2.4万 次观看"},
                                }
                            }
                        }
                    },
                    {
                        "richItemRenderer": {
                            "content": {
                                "videoRenderer": {
                                    "videoId": "ghi789",
                                    "title": {"simpleText": "Fresh upload"},
                                    "viewCountText": {"simpleText": "No views"},
                                }
                            }
                        }
                    },
                ]
            }
        }
    }

    videos = parse_channel_recent_videos(initial_data, limit=3)

    assert [video["view_count"] for video in videos] == [1_500_000_000, 24_000, 0]


def test_parse_channel_recent_videos_reads_lockup_view_models():
    initial_data = {
        "contents": {
            "richGridRenderer": {
                "contents": [
                    {
                        "richItemRenderer": {
                            "content": {
                                "lockupViewModel": {
                                    "contentId": "abc123",
                                    "metadata": {
                                        "lockupMetadataViewModel": {
                                            "title": {"content": "New channel page video"},
                                            "metadata": {
                                                "contentMetadataViewModel": {
                                                    "metadataRows": [
                                                        {
                                                            "metadataParts": [
                                                                {"text": {"content": "81K views"}},
                                                                {"text": {"content": "1 day ago"}},
                                                            ]
                                                        }
                                                    ]
                                                }
                                            },
                                        }
                                    },
                                }
                            }
                        }
                    }
                ]
            }
        }
    }

    videos = parse_channel_recent_videos(initial_data)

    assert videos == [
        {
            "youtube_video_id": "abc123",
            "title": "New channel page video",
            "url": "https://www.youtube.com/watch?v=abc123",
            "published_text": "1 day ago",
            "view_count": 81000,
        }
    ]


def test_browser_collector_unavailable_is_public_error_type():
    assert issubclass(BrowserCollectionUnavailable, RuntimeError)


def test_collect_page_html_dispatches_to_playwright(monkeypatch):
    calls = []

    def fake_playwright(url: str) -> str:
        calls.append(url)
        return "<html>playwright</html>"

    monkeypatch.setattr("creator_agent.collectors.youtube_browser.collect_page_html_with_playwright", fake_playwright)

    html = collect_page_html("https://www.youtube.com/watch?v=abc123", engine="playwright")

    assert html == "<html>playwright</html>"
    assert calls == ["https://www.youtube.com/watch?v=abc123"]


def test_collect_page_html_dispatches_to_drission(monkeypatch):
    calls = []

    def fake_drission(url: str) -> str:
        calls.append(url)
        return "<html>drission</html>"

    monkeypatch.setattr("creator_agent.collectors.youtube_browser.collect_page_html_with_drission", fake_drission)

    html = collect_page_html("https://www.youtube.com/watch?v=abc123", engine="drission")

    assert html == "<html>drission</html>"
    assert calls == ["https://www.youtube.com/watch?v=abc123"]


def test_collect_page_html_dispatches_to_cdp(monkeypatch):
    calls = []

    def fake_cdp(url: str) -> str:
        calls.append(url)
        return "<html>cdp</html>"

    monkeypatch.setattr("creator_agent.collectors.youtube_browser.collect_page_html_with_cdp", fake_cdp)

    html = collect_page_html("https://www.youtube.com/watch?v=abc123", engine="cdp")

    assert html == "<html>cdp</html>"
    assert calls == ["https://www.youtube.com/watch?v=abc123"]


def test_video_metadata_marks_selected_collection_engine(monkeypatch):
    html = """
    <script>
      var ytInitialData = {
        "contents": {
          "twoColumnWatchNextResults": {
            "results": {
              "results": {
                "contents": [
                  {
                    "videoPrimaryInfoRenderer": {
                      "title": {"runs": [{"text": "Collected with Drission"}]},
                      "viewCount": {
                        "videoViewCountRenderer": {
                          "viewCount": {"simpleText": "99 views"}
                        }
                      }
                    }
                  }
                ]
              }
            }
          }
        }
      };
    </script>
    """

    monkeypatch.setenv("YCA_BROWSER_ENGINE", "drission")
    monkeypatch.setattr("creator_agent.collectors.youtube_browser.collect_page_html_with_drission", lambda url: html)

    from creator_agent.collectors.youtube_browser import collect_video_metadata

    metadata = collect_video_metadata(video_url="https://www.youtube.com/watch?v=abc123")

    assert metadata["collection_source"] == "browser:drission"


def test_channel_collection_marks_empty_parse_as_warning(monkeypatch):
    html = """
    <script>
      var ytInitialData = {"contents":{"richGridRenderer":{"contents":[]}}};
    </script>
    """
    monkeypatch.setenv("YCA_BROWSER_ENGINE", "playwright")
    monkeypatch.setattr("creator_agent.collectors.youtube_browser.collect_page_html_with_playwright", lambda url: html)

    from creator_agent.collectors.youtube_browser import collect_channel_recent_videos

    result = collect_channel_recent_videos("https://www.youtube.com/@empty")

    assert result["collection_status"] == "empty"
    assert result["videos"] == []
    assert "No videos were parsed" in result["collection_error"]


def test_collect_page_html_rejects_unknown_engine():
    try:
        collect_page_html("https://www.youtube.com/watch?v=abc123", engine="unknown")
    except BrowserCollectionUnavailable as exc:
        assert "Unsupported browser engine" in str(exc)
    else:
        raise AssertionError("Expected BrowserCollectionUnavailable")
