from __future__ import annotations

import os

import pytest

from azure_functions_knowledge.auth import resolve_connection
from azure_functions_knowledge.errors import ConfigurationError


class TestResolveConnection:
    def test_no_placeholders(self) -> None:
        assert resolve_connection("plain-string") == "plain-string"

    def test_single_placeholder(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_TOKEN", "secret-123")
        assert resolve_connection("%MY_TOKEN%") == "secret-123"

    def test_multiple_placeholders(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "8080")
        result = resolve_connection("http://%HOST%:%PORT%/api")
        assert result == "http://localhost:8080/api"

    def test_partial_substitution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TOKEN", "abc")
        result = resolve_connection("Bearer %TOKEN%")
        assert result == "Bearer abc"

    def test_missing_env_var_raises(self) -> None:
        if "NONEXISTENT_VAR" in os.environ:
            del os.environ["NONEXISTENT_VAR"]
        with pytest.raises(ConfigurationError, match="NONEXISTENT_VAR"):
            resolve_connection("%NONEXISTENT_VAR%")

    def test_empty_string(self) -> None:
        assert resolve_connection("") == ""

    def test_percent_signs_without_match(self) -> None:
        assert resolve_connection("100%") == "100%"
        assert resolve_connection("50% off") == "50% off"
