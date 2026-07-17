"""Tests for the ATLAS config service (~/.atlas/config.yaml)."""
from __future__ import annotations

import pytest
import yaml

from atlas_runtime import config_service as cfgsvc
from atlas_runtime.config_service import AtlasConfig


def test_load_missing_returns_defaults(tmp_path):
    cfg = cfgsvc.load_config(tmp_path / "nope.yaml")
    assert isinstance(cfg, AtlasConfig)
    assert cfg.provider.name == "openrouter"
    assert cfg.runtime.default_agent == "native"
    assert cfg.modules["wiki"] is True
    assert cfg.functions.actor_model == ""


def test_save_then_load_roundtrips(tmp_path):
    path = tmp_path / "config.yaml"
    cfg = AtlasConfig()
    cfg = cfgsvc.set_value(cfg, "provider.model", "anthropic/claude-opus-4")
    cfg = cfgsvc.set_value(cfg, "runtime.iteration_budget", 50)
    cfgsvc.save_config(cfg, path)
    loaded = cfgsvc.load_config(path)
    assert loaded.provider.model == "anthropic/claude-opus-4"
    assert loaded.runtime.iteration_budget == 50


def test_save_is_atomic_and_yaml(tmp_path):
    path = tmp_path / "config.yaml"
    cfgsvc.save_config(AtlasConfig(), path)
    # Valid YAML, no leftover temp files in the dir.
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["provider"]["name"] == "openrouter"
    assert [p for p in path.parent.iterdir() if p.suffix == ".tmp"] == []


def test_inline_secret_rejected():
    with pytest.raises(ValueError):
        AtlasConfig.model_validate({"provider": {"api_key": "sk-livesecret123"}})


def test_env_ref_api_key_accepted():
    cfg = AtlasConfig.model_validate({"provider": {"api_key": "env:OPENROUTER_API_KEY"}})
    assert cfg.provider.api_key == "env:OPENROUTER_API_KEY"


def test_set_value_revalidates_secret_rule():
    cfg = AtlasConfig()
    # Setting an env ref is fine.
    cfg2 = cfgsvc.set_value(cfg, "provider.api_key", "env:FOO")
    assert cfg2.provider.api_key == "env:FOO"
    # Setting an inline secret is rejected through set_value's revalidation.
    with pytest.raises(ValueError):
        cfgsvc.set_value(cfg, "provider.api_key", "sk-inline-leak")


def test_get_value_dotted():
    cfg = AtlasConfig()
    assert cfgsvc.get_value(cfg, "gateway.rust_port") == 8484
    with pytest.raises(KeyError):
        cfgsvc.get_value(cfg, "gateway.nonexistent")


def test_masked_dict_has_no_inline_secrets(tmp_path):
    cfg = cfgsvc.set_value(AtlasConfig(), "provider.api_key", "env:OPENROUTER_API_KEY")
    masked = cfgsvc.masked_dict(cfg)
    # The only credential field is an env ref, never a raw value.
    assert masked["provider"]["api_key"] == "env:OPENROUTER_API_KEY"
    assert "sk-" not in yaml.safe_dump(masked)


def test_atlas_home_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path / "custom"))
    assert cfgsvc.default_config_path() == tmp_path / "custom" / "config.yaml"


def test_masked_dict_mock_mode_true_when_api_key_blank():
    # Default provider.api_key is "" — no env ref at all, so mock_mode is True.
    masked = cfgsvc.masked_dict(AtlasConfig())
    assert masked["mock_mode"] is True


def test_masked_dict_mock_mode_true_when_env_var_unset(monkeypatch):
    monkeypatch.delenv("ATLAS_TEST_UNSET_KEY", raising=False)
    cfg = cfgsvc.set_value(AtlasConfig(), "provider.api_key", "env:ATLAS_TEST_UNSET_KEY")
    masked = cfgsvc.masked_dict(cfg)
    assert masked["mock_mode"] is True
    # No secret value leaks — only the env: reference is present.
    assert masked["provider"]["api_key"] == "env:ATLAS_TEST_UNSET_KEY"


def test_masked_dict_mock_mode_false_when_env_var_set(monkeypatch):
    monkeypatch.setenv("ATLAS_TEST_SET_KEY", "sk-resolved-secret-value")
    cfg = cfgsvc.set_value(AtlasConfig(), "provider.api_key", "env:ATLAS_TEST_SET_KEY")
    masked = cfgsvc.masked_dict(cfg)
    assert masked["mock_mode"] is False
    # The resolved secret value never appears in the masked dict — only the ref.
    assert masked["provider"]["api_key"] == "env:ATLAS_TEST_SET_KEY"
    assert "sk-resolved-secret-value" not in yaml.safe_dump(masked)
