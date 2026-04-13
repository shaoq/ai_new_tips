"""测试配置管理：加载/保存/验证/脱敏."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ainews.config.loader import load_config, save_config, set_config_value, clear_config_cache
from ainews.config.settings import AppConfig, LLMConfig, _mask


class TestConfigModels:
    """配置模型测试."""

    def test_default_config(self) -> None:
        config = AppConfig()
        assert config.llm.model == "gpt-4o"
        assert config.llm.max_tokens == 1024
        assert config.obsidian.port == 27124
        assert config.logging.level == "INFO"

    def test_config_from_dict(self) -> None:
        data = {"llm": {"base_url": "https://api.example.com/v1", "api_key": "sk-123", "model": "claude-3"}}
        config = AppConfig(**data)
        assert config.llm.base_url == "https://api.example.com/v1"
        assert config.llm.model == "claude-3"
        assert config.llm.max_tokens == 1024  # default

    def test_config_paths(self) -> None:
        config = AppConfig()
        assert config.config_path == Path.home() / ".ainews" / "config.yaml"
        assert config.db_path == Path.home() / ".ainews" / "data.db"

    def test_base_url_validation_trailing_slash(self) -> None:
        config = AppConfig(llm=LLMConfig(base_url="https://api.example.com/v1/"))
        assert config.llm.base_url == "https://api.example.com/v1"

    def test_base_url_validation_invalid(self) -> None:
        with pytest.raises(Exception):
            LLMConfig(base_url="ftp://invalid")

    def test_port_validation(self) -> None:
        from ainews.config.settings import ObsidianConfig
        with pytest.raises(Exception):
            ObsidianConfig(port=0)
        with pytest.raises(Exception):
            ObsidianConfig(port=70000)

    def test_log_level_validation(self) -> None:
        from ainews.config.settings import LoggingConfig
        with pytest.raises(Exception):
            LoggingConfig(level="VERBOSE")


class TestMaskSecrets:
    """脱敏测试."""

    def test_mask_short(self) -> None:
        assert _mask("") == ""
        assert _mask("abc") == "***"

    def test_mask_long(self) -> None:
        assert _mask("sk-1234567890abcdef") == "***cdef"

    def test_mask_exactly_4(self) -> None:
        assert _mask("abcd") == "***abcd"

    def test_config_mask_secrets(self) -> None:
        config = AppConfig(llm=LLMConfig(api_key="sk-secret-key-1234"))
        masked = config.mask_secrets()
        assert masked.llm.api_key == "***1234"
        assert config.llm.api_key == "sk-secret-key-1234"  # 原始不变


class TestConfigLoadSave:
    """配置文件读写测试."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        config = AppConfig(llm=LLMConfig(api_key="test-key", model="gpt-4o-mini"))
        save_config(config, config_path)

        loaded = load_config(config_path)
        assert loaded.llm.api_key == "test-key"
        assert loaded.llm.model == "gpt-4o-mini"

    def test_load_missing_file(self, tmp_path: Path) -> None:
        config = load_config(tmp_path / "nonexistent.yaml")
        assert config.llm.model == "gpt-4o"  # defaults

    def test_load_empty_file(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text("")
        config = load_config(config_path)
        assert config.llm.model == "gpt-4o"


class TestSetConfigValue:
    """点分路径修改测试."""

    def test_set_string(self) -> None:
        config = AppConfig()
        new_config = set_config_value(config, "llm.model", "claude-3")
        assert new_config.llm.model == "claude-3"

    def test_set_int(self) -> None:
        config = AppConfig()
        new_config = set_config_value(config, "obsidian.port", "8080")
        assert new_config.obsidian.port == 8080

    def test_set_invalid_path(self) -> None:
        config = AppConfig()
        with pytest.raises(KeyError):
            set_config_value(config, "nonexistent.key", "value")
