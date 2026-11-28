"""Persistent runtime settings edited from the dashboard.

The sensor and the admin API share this store: updates apply to the live
Settings/SOAR objects and to a JSON file so they survive a restart.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import structlog
from pydantic import SecretStr

from .config import Settings, secret_to_str

logger = structlog.get_logger("cloudsentinel.runtime_config")

SECTIONS = ("deception", "hassh", "soar", "llm")
DECEPTION_LEVELS = {"full", "restricted", "listener"}
HASSH_ACTIONS = {"monitor", "drop"}
SOAR_TRIGGERS = {"risk", "mitre", "auth_spike", "any_input"}
SOAR_EXECUTIONS = {"eventgrid", "host"}
LLM_PROVIDERS = {"gemini", "litellm", "openai", "groq", "anthropic"}
LLM_PROVIDER_ALIASES = {
    "google gemini": "gemini",
    "groq cloud": "groq",
    "anthropic claude": "anthropic",
    "litellm unified gateway": "litellm",
}
DECEPTION_MODES = {"dynamic", "deterministic"}


def _default_path() -> Path:
    return Path(os.getenv("CLOUDSENTINEL_RUNTIME_CONFIG_PATH", "var/runtime_config.json"))


class RuntimeConfigStore:
    def __init__(
        self,
        settings: Settings,
        path: str | Path | None = None,
        soar: Any = None,
    ) -> None:
        self.settings = settings
        self.soar = soar
        self.path = Path(path) if path is not None else _default_path()
        self._stored: dict[str, dict[str, Any]] = {}
        self._load()
        self.apply()

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(raw, dict):
            return
        for section in SECTIONS:
            values = raw.get(section)
            if not isinstance(values, dict):
                continue
            try:
                self._stored[section] = self._validate(section, values)
            except ValueError as exc:
                logger.warning(
                    "runtime_config_invalid_section",
                    section=section,
                    error=str(exc),
                )

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._stored, indent=2, sort_keys=True), encoding="utf-8")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def snapshot(self) -> dict[str, dict[str, Any]]:
        llm = self.settings.llm
        soar = self.soar if self.soar is not None else self.settings.soar
        return {
            "deception": {
                "level": self.settings.deception.level,
                "seed_canary_keys": self.settings.deception.seed_canary_keys,
            },
            "hassh": {
                "action": self.settings.deception.hassh_action,
                "threshold": self.settings.deception.hassh_threshold,
            },
            "soar": {
                "trigger": getattr(soar, "trigger", self.settings.soar.trigger),
                "risk_threshold": int(getattr(soar, "risk_threshold", self.settings.soar.risk_threshold)),
                "execution": "eventgrid" if getattr(soar, "eventgrid_enabled", False) else "host",
            },
            "llm": {
                "provider": llm.provider,
                "model": llm.model,
                "fallback_models": list(llm.fallback_models),
                "hourly_limit": llm.global_hourly_limit,
                "prompt_sanitization": llm.prompt_sanitization,
                "deception_mode": llm.deception_mode,
                "has_api_key": bool(secret_to_str(llm.api_key)),
            },
        }

    def update(self, payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        if not isinstance(payload, dict):
            raise ValueError("config payload must be an object")
        unknown = set(payload) - set(SECTIONS)
        if unknown:
            raise ValueError(f"unknown config section: {', '.join(sorted(unknown))}")

        staged: dict[str, dict[str, Any]] = {}
        for section, values in payload.items():
            if not isinstance(values, dict):
                raise ValueError(f"{section} must be an object")
            staged[section] = self._validate(section, values)

        api_key = str(staged.get("llm", {}).get("api_key") or "")
        if not api_key:
            staged.get("llm", {}).pop("api_key", None)
        for section, values in staged.items():
            merged = {**self._stored.get(section, {}), **values}
            if merged:
                self._stored[section] = merged
        if api_key:
            self.settings.llm.api_key = SecretStr(api_key)
            os.environ["LLM_API_KEY"] = api_key

        self.apply()
        self._save()
        return self.snapshot()

    def apply(self) -> None:
        deception = self._stored.get("deception", {})
        hassh = self._stored.get("hassh", {})
        soar_cfg = self._stored.get("soar", {})
        llm_cfg = self._stored.get("llm", {})

        if "level" in deception:
            self.settings.deception.level = str(deception["level"])
        if "seed_canary_keys" in deception:
            self.settings.deception.seed_canary_keys = bool(deception["seed_canary_keys"])
        if "action" in hassh:
            self.settings.deception.hassh_action = str(hassh["action"])
        if "threshold" in hassh:
            self.settings.deception.hassh_threshold = int(hassh["threshold"])

        if "trigger" in soar_cfg:
            self.settings.soar.trigger = str(soar_cfg["trigger"])
        if "risk_threshold" in soar_cfg:
            self.settings.soar.risk_threshold = int(soar_cfg["risk_threshold"])
        if "execution" in soar_cfg:
            self.settings.soar.eventgrid_enabled = soar_cfg["execution"] == "eventgrid"

        if self.soar is not None:
            if "trigger" in soar_cfg:
                self.soar.trigger = self.settings.soar.trigger
            if "risk_threshold" in soar_cfg:
                self.soar.risk_threshold = self.settings.soar.risk_threshold
            if "execution" in soar_cfg:
                self.soar.eventgrid_enabled = self.settings.soar.eventgrid_enabled

        llm = self.settings.llm
        if "provider" in llm_cfg:
            llm.provider = str(llm_cfg["provider"])
        if "model" in llm_cfg:
            llm.model = str(llm_cfg["model"])
            os.environ["LLM_MODEL"] = llm.model
        if "fallback_models" in llm_cfg:
            llm.fallback_models = [str(model) for model in llm_cfg["fallback_models"]]
            os.environ["LLM_FALLBACK_MODELS"] = ",".join(llm.fallback_models)
        if "hourly_limit" in llm_cfg:
            llm.global_hourly_limit = int(llm_cfg["hourly_limit"])
        if "prompt_sanitization" in llm_cfg:
            llm.prompt_sanitization = bool(llm_cfg["prompt_sanitization"])
        if "deception_mode" in llm_cfg:
            llm.deception_mode = str(llm_cfg["deception_mode"])
        if llm_cfg.get("api_key"):
            llm.api_key = SecretStr(str(llm_cfg["api_key"]))
            os.environ["LLM_API_KEY"] = str(llm_cfg["api_key"])

        api_key = secret_to_str(llm.api_key)
        if api_key:
            provider = (llm.provider or llm.model).lower()
            if "gemini" in provider:
                os.environ["GEMINI_API_KEY"] = api_key
            elif "openai" in provider:
                os.environ["OPENAI_API_KEY"] = api_key
            elif "groq" in provider:
                os.environ["GROQ_API_KEY"] = api_key
            elif "anthropic" in provider:
                os.environ["ANTHROPIC_API_KEY"] = api_key

    def _validate(self, section: str, values: dict[str, Any]) -> dict[str, Any]:
        validators = {
            "deception": self._validate_deception,
            "hassh": self._validate_hassh,
            "soar": self._validate_soar,
            "llm": self._validate_llm,
        }
        return validators[section](values)

    @staticmethod
    def _choice(section: str, key: str, value: Any, allowed: set[str]) -> str:
        text = str(value)
        if text not in allowed:
            raise ValueError(f"invalid {section}.{key}: {value}")
        return text

    @staticmethod
    def _boolean(section: str, key: str, value: Any) -> bool:
        if not isinstance(value, bool):
            raise ValueError(f"{section}.{key} must be a boolean")
        return value

    @staticmethod
    def _integer(section: str, key: str, value: Any, low: int, high: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{section}.{key} must be an integer")
        if value < low or value > high:
            raise ValueError(f"{section}.{key} must be between {low} and {high}")
        return value

    def _validate_deception(self, values: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if "level" in values:
            result["level"] = self._choice("deception", "level", values["level"], DECEPTION_LEVELS)
        if "seed_canary_keys" in values:
            result["seed_canary_keys"] = self._boolean(
                "deception", "seed_canary_keys", values["seed_canary_keys"]
            )
        self._reject_unknown("deception", values, result)
        return result

    def _validate_hassh(self, values: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if "action" in values:
            result["action"] = self._choice("hassh", "action", values["action"], HASSH_ACTIONS)
        if "threshold" in values:
            result["threshold"] = self._integer("hassh", "threshold", values["threshold"], 0, 100)
        self._reject_unknown("hassh", values, result)
        return result

    def _validate_soar(self, values: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if "trigger" in values:
            result["trigger"] = self._choice("soar", "trigger", values["trigger"], SOAR_TRIGGERS)
        if "risk_threshold" in values:
            result["risk_threshold"] = self._integer(
                "soar", "risk_threshold", values["risk_threshold"], 1, 100
            )
        if "execution" in values:
            result["execution"] = self._choice(
                "soar", "execution", values["execution"], SOAR_EXECUTIONS
            )
        self._reject_unknown("soar", values, result)
        return result

    def _validate_llm(self, values: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if "provider" in values:
            provider = str(values["provider"]).strip()
            canonical = LLM_PROVIDER_ALIASES.get(provider.lower(), provider.lower())
            if canonical not in LLM_PROVIDERS:
                raise ValueError(f"invalid llm.provider: {values['provider']}")
            result["provider"] = provider
        if "model" in values:
            model = str(values["model"]).strip()
            if not model:
                raise ValueError("llm.model must not be empty")
            result["model"] = model
        if "fallback_models" in values:
            raw = values["fallback_models"]
            if not isinstance(raw, list):
                raise ValueError("llm.fallback_models must be a list")
            result["fallback_models"] = [str(item).strip() for item in raw if str(item).strip()]
        if "hourly_limit" in values:
            result["hourly_limit"] = self._integer(
                "llm", "hourly_limit", values["hourly_limit"], 0, 10000
            )
        if "prompt_sanitization" in values:
            result["prompt_sanitization"] = self._boolean(
                "llm", "prompt_sanitization", values["prompt_sanitization"]
            )
        if "deception_mode" in values:
            result["deception_mode"] = self._choice(
                "llm", "deception_mode", values["deception_mode"], DECEPTION_MODES
            )
        if "api_key" in values:
            result["api_key"] = str(values["api_key"]).strip()
        self._reject_unknown("llm", values, result)
        return result

    @staticmethod
    def _reject_unknown(section: str, values: dict[str, Any], result: dict[str, Any]) -> None:
        unknown = set(values) - set(result)
        if unknown:
            raise ValueError(f"unknown {section} key: {', '.join(sorted(unknown))}")


def build_runtime_config_store(settings: Settings, soar: Any = None) -> RuntimeConfigStore:
    return RuntimeConfigStore(settings, soar=soar)
