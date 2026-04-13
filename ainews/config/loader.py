"""配置文件读写：YAML 加载/保存."""

from __future__ import annotations

from pathlib import Path

import yaml

from ainews.config.settings import AppConfig

_cached_config: AppConfig | None = None

DEFAULT_CONFIG_DIR = Path.home() / ".ainews"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.yaml"


def load_config(path: Path | None = None) -> AppConfig:
    """从 YAML 文件加载配置，文件不存在时返回默认配置."""
    config_path = path or DEFAULT_CONFIG_PATH
    if config_path.exists():
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return AppConfig(**data)
    return AppConfig()


def save_config(config: AppConfig, path: Path | None = None) -> None:
    """将配置写入 YAML 文件，自动创建目录."""
    config_path = path or DEFAULT_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump()
    content = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    config_path.write_text(content, encoding="utf-8")


def get_config(path: Path | None = None) -> AppConfig:
    """获取配置（带缓存），优先返回缓存实例."""
    global _cached_config
    if _cached_config is None:
        _cached_config = load_config(path)
    return _cached_config


def clear_config_cache() -> None:
    """清除配置缓存."""
    global _cached_config
    _cached_config = None


def set_config_value(config: AppConfig, dotted_key: str, value: str) -> AppConfig:
    """通过点分路径修改配置项，返回新配置对象."""
    data = config.model_dump()
    keys = dotted_key.split(".")
    target = data
    for key in keys[:-1]:
        if key not in target:
            msg = f"配置路径不存在: {dotted_key}"
            raise KeyError(msg)
        target = target[key]
    last_key = keys[-1]
    if last_key not in target:
        msg = f"配置路径不存在: {dotted_key}"
        raise KeyError(msg)

    # 尝试类型推断转换
    old_value = target[last_key]
    if isinstance(old_value, bool):
        target[last_key] = value.lower() in ("true", "1", "yes")
    elif isinstance(old_value, int):
        target[last_key] = int(value)
    elif isinstance(old_value, float):
        target[last_key] = float(value)
    elif isinstance(old_value, list):
        target[last_key] = [item.strip() for item in value.split(",")]
    else:
        target[last_key] = value

    return AppConfig(**data)
