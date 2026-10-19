"""
File-backed runtime persistence for advisor decisions, feedback, settings, audit.

Demo-level auth: single DEMO advisor. Sensitive ops are audited without PII payloads.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "data" / "runtime"
RUNTIME.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()

DEFAULT_SETTINGS = {
    "weights": {
        "goal_deviation": 0.35,
        "active_underperformance": 0.20,
        "urgency_time_to_goal": 0.15,
        "overdue_followups": 0.15,
        "stale_review": 0.10,
        "data_quality": 0.05,
    },
    "goal_deviation_critical_pct": -18.0,
    "goal_deviation_high_pct": -8.0,
    "active_return_high_pp": -4.0,
    "stale_data_days": 45,
    "stale_review_days": 120,
    "note_retention_days": 365,
    "privacy": {
        "demo_auth": True,
        "demo_auth_note": (
            "Demo uses a single DEMO-ADV-USER-01 context. "
            "Production must enforce real advisor-client ACL."
        ),
        "transcription_mode": "mocked_local",
        "log_pii": False,
    },
    "advisor_id": "DEMO-ADV-USER-01",
    "accessible_clients": None,  # None = all demo clients
}


def _path(name: str) -> Path:
    return RUNTIME / name


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(name: str, default: Any) -> Any:
    path = _path(name)
    if not path.exists():
        return default
    with _lock:
        return json.loads(path.read_text(encoding="utf-8"))


def _write(name: str, data: Any) -> None:
    path = _path(name)
    with _lock:
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def load_settings() -> dict[str, Any]:
    stored = _read("settings.json", {})
    out = dict(DEFAULT_SETTINGS)
    out.update({k: v for k, v in stored.items() if k != "weights"})
    if "weights" in stored:
        w = dict(DEFAULT_SETTINGS["weights"])
        w.update(stored["weights"])
        out["weights"] = w
    return out


def save_settings(patch: dict[str, Any]) -> dict[str, Any]:
    current = load_settings()
    if "weights" in patch and isinstance(patch["weights"], dict):
        current["weights"].update(patch["weights"])
        patch = {k: v for k, v in patch.items() if k != "weights"}
    current.update(patch)
    _write("settings.json", current)
    audit("settings_update", {"keys": list(patch.keys())})
    return current


def load_decisions() -> dict[str, Any]:
    """Attention decisions keyed by alert_key or investor_id."""
    return _read("attention_decisions.json", {})


def save_decision(key: str, decision: dict[str, Any]) -> dict[str, Any]:
    data = load_decisions()
    record = {
        **decision,
        "key": key,
        "updated_at": _now(),
        "id": decision.get("id") or str(uuid4()),
    }
    data[key] = record
    _write("attention_decisions.json", data)
    audit("attention_decision", {"key": key, "action": decision.get("action")})
    return record


def load_drift_state() -> dict[str, Any]:
    return _read("drift_state.json", {})


def save_drift_state(alert_id: str, state: dict[str, Any]) -> dict[str, Any]:
    data = load_drift_state()
    data[alert_id] = {**state, "updated_at": _now()}
    _write("drift_state.json", data)
    audit("drift_state", {"alert_id": alert_id, "status": state.get("status")})
    return data[alert_id]


def load_feedback() -> list[dict[str, Any]]:
    return _read("feedback.json", [])


def add_feedback(entry: dict[str, Any]) -> dict[str, Any]:
    items = load_feedback()
    record = {
        "id": str(uuid4()),
        "created_at": _now(),
        **entry,
    }
    items.append(record)
    _write("feedback.json", items)
    audit("feedback", {"investor_id": entry.get("investor_id"), "action": entry.get("action")})
    return record


def load_advice_versions() -> dict[str, Any]:
    return _read("advice_versions.json", {})


def version_advice(advice_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = load_advice_versions()
    versions = data.get(advice_id, [])
    versions.append(
        {
            "version": len(versions) + 1,
            "recorded_at": _now(),
            "immutable": True,
            **payload,
        }
    )
    data[advice_id] = versions
    _write("advice_versions.json", data)
    return versions[-1]


def load_commitments() -> list[dict[str, Any]]:
    return _read("commitments.json", [])


def save_commitments(items: list[dict[str, Any]]) -> None:
    _write("commitments.json", items)


def upsert_commitment(commitment: dict[str, Any]) -> dict[str, Any]:
    items = load_commitments()
    cid = commitment.get("id") or str(uuid4())
    commitment["id"] = cid
    commitment["updated_at"] = _now()
    found = False
    for i, c in enumerate(items):
        if c.get("id") == cid:
            items[i] = {**c, **commitment}
            found = True
            break
    if not found:
        commitment.setdefault("created_at", _now())
        items.append(commitment)
    save_commitments(items)
    audit("commitment", {"id": cid, "status": commitment.get("status")})
    return commitment


def load_notes_runtime() -> list[dict[str, Any]]:
    # Prefer runtime folder; fall back to legacy path
    legacy = ROOT / "data" / "runtime_notes.json"
    primary = _path("notes.json")
    if primary.exists():
        return _read("notes.json", [])
    if legacy.exists():
        notes = json.loads(legacy.read_text(encoding="utf-8"))
        _write("notes.json", notes)
        return notes
    return []


def save_notes_runtime(notes: list[dict[str, Any]]) -> None:
    _write("notes.json", notes)


def load_extractions() -> list[dict[str, Any]]:
    return _read("extractions.json", [])


def save_extractions(items: list[dict[str, Any]]) -> None:
    _write("extractions.json", items)


def audit(action: str, meta: dict[str, Any] | None = None) -> None:
    """Append audit row without PII (no note text, no names)."""
    log = _read("audit.json", [])
    safe_meta = {k: v for k, v in (meta or {}).items() if k not in {"note_text", "transcript", "display_name"}}
    log.append({"ts": _now(), "action": action, "meta": safe_meta})
    # keep last 500
    _write("audit.json", log[-500:])


def load_audit(limit: int = 50) -> list[dict[str, Any]]:
    return _read("audit.json", [])[-limit:]
