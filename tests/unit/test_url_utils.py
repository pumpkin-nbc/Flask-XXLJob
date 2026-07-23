"""URL joining tests (0.1.1)."""

from __future__ import annotations

from flask_xxljob.utils.url_utils import join_url


def test_simple_join():
    assert join_url("http://a:8080", "api/registry") == "http://a:8080/api/registry"


def test_trailing_slash_on_base():
    assert join_url("http://a:8080/", "/api/registry") == "http://a:8080/api/registry"


def test_duplicate_slashes():
    assert join_url("http://a:8080///", "///api/registry") == "http://a:8080/api/registry"


def test_base_with_path():
    assert (
        join_url("http://a:8080/xxl-job-admin", "/api/callback")
        == "http://a:8080/xxl-job-admin/api/callback"
    )


def test_empty_path_returns_trimmed_base():
    assert join_url("http://a:8080/", "") == "http://a:8080"
