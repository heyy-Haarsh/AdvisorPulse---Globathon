"""
Gemini API client for Meeting Intelligence.

Secrets: GEMINI_API_KEY (backend only). Never expose to the frontend.
Optional: GEMINI_MODEL (default gemini-2.0-flash)
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env")

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


class GeminiNotConfigured(RuntimeError):
    pass


class GeminiError(RuntimeError):
    pass


def api_key() -> str | None:
    key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    return key or None


def is_configured() -> bool:
    return bool(api_key())


def looks_like_ai_studio_key(key: str | None = None) -> bool:
    """Google AI Studio keys typically start with AIza…"""
    k = (key if key is not None else api_key()) or ""
    return k.startswith("AIza")


def is_usable() -> bool:
    """
    True when we should attempt live Gemini calls.
    A present-but-invalid key (common demo failure) is treated as unusable so
    Meeting Intelligence falls back to the packaged demo path without 401 noise.
    Set GEMINI_FORCE=1 to attempt calls even when the key format looks wrong.
    """
    if not is_configured():
        return False
    if os.getenv("GEMINI_FORCE", "").strip() in {"1", "true", "yes"}:
        return True
    return looks_like_ai_studio_key()


def friendly_error(exc: BaseException) -> str:
    """Collapse Google HttpError / discovery noise into a short advisor-facing message."""
    msg = str(exc)
    low = msg.lower()
    if "api key not valid" in low or "api_key_invalid" in low or "access_token_type_unsupported" in low:
        hint = ""
        if not looks_like_ai_studio_key():
            hint = (
                " Current GEMINI_API_KEY does not look like a Google AI Studio key "
                "(those usually start with AIza). Create one at https://aistudio.google.com/apikey "
                "and put it in .env, then restart the API."
            )
        return (
            "Gemini API key is invalid or rejected. "
            "For the judge demo use “Load demo transcript” instead of Transcribe."
            + hint
        )
    if "api key" in low and ("invalid" in low or "permission" in low or "denied" in low):
        return "Gemini API key rejected. Use “Load demo transcript” for the demo, or set a valid GEMINI_API_KEY."
    # Strip huge discovery URL payloads
    if "HttpError" in msg and "generativelanguage.googleapis.com" in msg:
        return "Gemini request failed (API key or quota). Use “Load demo transcript” for the demo."
    if len(msg) > 280:
        return msg[:277] + "…"
    return msg


def status() -> dict[str, Any]:
    key = api_key()
    usable = is_usable()
    return {
        "provider": "google_gemini",
        "configured": is_configured(),
        "usable": usable,
        "model": DEFAULT_MODEL,
        "key_format_ok": looks_like_ai_studio_key(key) if key else False,
        "env_vars": ["GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_FORCE"],
        "note": (
            "Set a valid Google AI Studio GEMINI_API_KEY (usually starts with AIza) for live "
            "transcription/minutes. Prep briefs and the Priya demo (Meet + transcript + MoM) "
            "work without a usable key."
        ),
    }


def _client():
    key = api_key()
    if not key:
        raise GeminiNotConfigured(
            "GEMINI_API_KEY is not set. Add it to .env to enable Gemini transcription and minutes."
        )
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError as e:
        raise GeminiError("google-generativeai package is not installed") from e
    genai.configure(api_key=key)
    return genai


def _extract_json(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        raise GeminiError("Empty Gemini response")
    # Strip markdown fences
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try first { ... } or [ ... ]
        m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if not m:
            raise GeminiError("Gemini response was not valid JSON")
        return json.loads(m.group(1))


def generate_json(prompt: str, *, system: str | None = None, temperature: float = 0.2) -> Any:
    genai = _client()
    model = genai.GenerativeModel(
        DEFAULT_MODEL,
        system_instruction=system
        or (
            "You are an advisor meeting-intelligence assistant for Indian wealth management. "
            "Return ONLY valid JSON matching the requested schema. "
            "Never invent portfolio numbers, meetings, or client facts not present in the input. "
            "If evidence is weak, mark evidence_status as Limited or Insufficient. "
            "Do not treat silence as client agreement."
        ),
    )
    resp = model.generate_content(
        prompt,
        generation_config={
            "temperature": temperature,
            "response_mime_type": "application/json",
        },
    )
    text = getattr(resp, "text", None) or ""
    if not text and getattr(resp, "candidates", None):
        parts = resp.candidates[0].content.parts
        text = "".join(getattr(p, "text", "") or "" for p in parts)
    return _extract_json(text)


def transcribe_audio_file(path: Path, *, mime_type: str | None = None) -> dict[str, Any]:
    """
    Transcribe an audio file with Gemini multimodal.
    Returns { full_text, segments: [{start_time, end_time, speaker_id, text}] }
    """
    try:
        genai = _client()
        if not path.exists():
            raise GeminiError(f"Audio file not found: {path}")

        mime = mime_type or _guess_mime(path)
        uploaded = genai.upload_file(path=str(path), mime_type=mime)
        model = genai.GenerativeModel(DEFAULT_MODEL)
        prompt = (
            "Transcribe this advisor–client meeting audio accurately. "
            "Return JSON with keys: full_text (string), segments (array of objects with "
            "start_time (mm:ss or HH:mm:ss string), end_time, speaker_id (Speaker 1/2…), text). "
            "Do not invent content that is not audible. If unintelligible, use [inaudible]. "
            "Do not assume Speaker 1 is the advisor."
        )
        resp = model.generate_content(
            [prompt, uploaded],
            generation_config={"temperature": 0.1, "response_mime_type": "application/json"},
        )
        text = getattr(resp, "text", None) or ""
        data = _extract_json(text)
        if isinstance(data, str):
            data = {
                "full_text": data,
                "segments": [
                    {
                        "start_time": "00:00",
                        "end_time": "",
                        "speaker_id": "Speaker 1",
                        "text": data,
                    }
                ],
            }
        if "full_text" not in data and "segments" in data:
            data["full_text"] = " ".join(s.get("text", "") for s in data["segments"])
        data["provider"] = "google_gemini"
        data["model"] = DEFAULT_MODEL
        return data
    except GeminiNotConfigured:
        raise
    except GeminiError:
        raise
    except Exception as e:
        raise GeminiError(friendly_error(e)) from e


def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".webm": "audio/webm",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
    }.get(ext, "audio/webm")
