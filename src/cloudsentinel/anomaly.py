"""
CloudSentinel Anomaly Detection — ML-based command pattern analysis.
Uses IsolationForest for unsupervised anomaly detection on attacker commands.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger("cloudsentinel.anomaly")

# Feature extraction for shell commands


def extract_features(command: str) -> dict[str, float]:
    """Extract numerical features from a shell command for ML scoring."""
    cmd = command.strip().lower()
    return {
        "length": min(len(cmd) / 500.0, 1.0),
        "pipe_count": min(cmd.count("|") / 5.0, 1.0),
        "redirect_count": min((cmd.count(">") + cmd.count("<")) / 3.0, 1.0),
        "semicolon_count": min(cmd.count(";") / 3.0, 1.0),
        "backtick_count": min(cmd.count("`") / 2.0, 1.0),
        "has_wget": 1.0 if "wget" in cmd else 0.0,
        "has_curl": 1.0 if "curl" in cmd else 0.0,
        "has_chmod": 1.0 if "chmod" in cmd else 0.0,
        "has_bash_c": 1.0 if ("bash -c" in cmd or "sh -c" in cmd) else 0.0,
        "has_python_c": 1.0 if "python" in cmd and "-c" in cmd else 0.0,
        "has_dev_shm": 1.0 if "/dev/shm" in cmd or "/tmp/" in cmd else 0.0,
        "has_base64": 1.0 if "base64" in cmd else 0.0,
        "has_nc": 1.0 if "nc " in cmd or "netcat" in cmd else 0.0,
        "has_ssh_lateral": 1.0 if cmd.startswith("ssh ") else 0.0,
        "has_crypto_miner": 1.0 if any(x in cmd for x in ("xmrig", "miner", "stratum")) else 0.0,
        "has_reverse_shell": 1.0 if any(x in cmd for x in ("/dev/tcp/", "socket", "connect(")) else 0.0,
    }


class CommandAnomalyDetector:
    """Unsupervised anomaly detection for attacker commands.

    Uses a hybrid approach:
    1. IsolationForest (if scikit-learn available) for statistical anomaly detection
    2. Rule-based heuristics as fallback
    3. Sliding window of recent commands for context-aware scoring
    """

    def __init__(self, contamination: float = 0.1, window_size: int = 100) -> None:
        self.contamination = contamination
        self.window_size = window_size
        self._recent_commands: deque[str] = deque(maxlen=window_size)
        self._model: Any = None
        self._feature_names: list[str] = list(extract_features("test").keys())
        self._model_ready = False
        self._total_commands = 0

        # Try to initialize ML model
        try:
            from sklearn.ensemble import IsolationForest
            self._model = IsolationForest(
                contamination=contamination,
                random_state=42,
                n_estimators=100,
            )
            logger.info("IsolationForest anomaly detector initialized")
        except ImportError:
            logger.info("scikit-learn not available — using heuristic anomaly detection")

    def score(self, command: str) -> dict[str, Any]:
        """Score a command for anomalousness. Returns risk dict."""
        self._total_commands += 1
        self._recent_commands.append(command)

        features = extract_features(command)
        feature_vector = [features.get(k, 0.0) for k in self._feature_names]

        # Heuristic score (always available)
        heuristic_score = sum(features.values()) / len(features) * 100

        # ML score (if model available and trained)
        ml_score = 0.0
        ml_anomaly = False
        if self._model is not None and self._model_ready:
            try:
                import numpy as np
                pred = self._model.predict(np.array([feature_vector]))[0]
                ml_anomaly = pred == -1  # -1 = anomaly in IsolationForest
                ml_score = 100.0 if ml_anomaly else heuristic_score * 0.5
            except Exception:
                pass

        # Combined score
        final_score = max(heuristic_score, ml_score) if ml_anomaly else heuristic_score

        return {
            "anomaly_score": round(final_score, 1),
            "heuristic_score": round(heuristic_score, 1),
            "ml_score": round(ml_score, 1) if ml_anomaly else 0.0,
            "ml_anomaly": ml_anomaly,
            "model_ready": self._model_ready,
            "features": {k: round(v, 2) for k, v in features.items() if v > 0},
        }

    def train(self) -> None:
        """Train the ML model on collected command data."""
        if self._model is None:
            return

        try:
            import numpy as np
            samples = []
            for cmd in self._recent_commands:
                f = extract_features(cmd)
                samples.append([f.get(k, 0.0) for k in self._feature_names])

            if len(samples) < 10:
                logger.debug("Not enough samples to train anomaly model (%d)", len(samples))
                return

            X = np.array(samples)
            self._model.fit(X)
            self._model_ready = True
            logger.info("Anomaly model trained on %d commands", len(samples))
        except Exception as exc:
            logger.warning("Anomaly model training failed: %s", exc)

    def save(self, path: str = "var/lib/cloudsentinel/anomaly_model.json") -> None:
        """Persist anomaly detection state."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "total_commands": self._total_commands,
            "feature_names": self._feature_names,
            "model_ready": self._model_ready,
        }
        out.write_text(json.dumps(data, indent=2))

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_commands_analyzed": self._total_commands,
            "model_ready": self._model_ready,
            "window_size": self.window_size,
            "recent_count": len(self._recent_commands),
        }
