"""Pure per-message API insight contract: label schema, revision, scope and shape.

This module must stay dependency-free (standard library only) and must not import
services, adapters, storage, the runtime, or the portrait contract module.

The API display contract is intentionally small: one short emotion and one short intent
per message. JSON/ID handling remains for transport, while semantic vocabulary is left to
the provider. The revision is separate so old, richer API rows are never reused by this
simple mode.
"""
from __future__ import annotations

FINE_LABEL_SCHEMA = "generic-v9"

API_INSIGHT_REVISION = "reading-v1"
API_INSIGHT_STYLE_REVISION = "reading-v2"
API_INSIGHT_STYLES = frozenset({"dating", "general"})

API_INSIGHT_STATUSES = frozenset({"ok", "routine", "uncertain", "insufficient"})
API_AFFECT_FIELDS = ("tone", "feeling", "interaction")
API_INTENT_LIMIT = 1
API_LABEL_MIN = 1
API_LABEL_MAX = 4


def api_insight_scope(source_id, style=None):
    """Legacy rows stay at reading-v1. Styled rows use reading-v2 and never overwrite them."""
    if style is None:
        return source_id + ":" + API_INSIGHT_REVISION
    if style not in API_INSIGHT_STYLES:
        raise ValueError("invalid insight style")
    return source_id + ":" + API_INSIGHT_STYLE_REVISION + ":" + style


def api_insight_read_scopes(source_id, style=None):
    """General display also reads the pre-style reading-v1 rows. Dating does not."""
    if style is None:
        return [api_insight_scope(source_id)]
    scopes = [api_insight_scope(source_id, style)]
    if style == "general":
        scopes.append(api_insight_scope(source_id))
    return scopes


def api_insight_write_scope(source_id, style=None):
    if style is None:
        return api_insight_scope(source_id)
    return api_insight_scope(source_id, style)


def _is_han(character):
    code = ord(character)
    return (0x3400 <= code <= 0x4DBF or 0x4E00 <= code <= 0x9FFF or
            0xF900 <= code <= 0xFAFF or 0x20000 <= code <= 0x2FA1F)


def valid_api_insight_label(value):
    """A displayed short label: 1-4 Han characters and nothing else."""
    return (isinstance(value, str) and API_LABEL_MIN <= len(value) <= API_LABEL_MAX and
            all(_is_han(character) for character in value))


def _normalize_readings(value):
    """Two to four distinct readings whose integer percents sum to 100."""
    if not isinstance(value, list) or not 2 <= len(value) <= 4:
        raise ValueError("invalid-insights")
    clean = []
    seen = set()
    total = 0
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("invalid-insights")
        text = item.get("text")
        percent = item.get("percent")
        if not isinstance(text, str):
            raise ValueError("invalid-insights")
        text = text.strip()
        han = sum(1 for character in text if _is_han(character))
        if (not 6 <= len(text) <= 32 or han < 4 or text in seen or
                any(ord(character) < 32 or ord(character) == 127 for character in text)):
            raise ValueError("invalid-insights")
        if isinstance(percent, bool) or not isinstance(percent, int) or not 1 <= percent <= 99:
            raise ValueError("invalid-insights")
        seen.add(text)
        total += percent
        clean.append({"text": text, "percent": percent})
    if total != 100:
        raise ValueError("invalid-insights")
    return clean


def normalize_api_insight(item):
    """Validate one insight item and return the canonical stored shape.

    New shape: ``{id,status}`` plus, for ``ok``, at most one short affect label and one
    short intent. The older affect/intents shape remains readable so saved historical
    rows can be displayed, but this revision stores the simple pair.

    Legacy scalar ``{emotion,intent}`` ok items are accepted for compatibility and
    normalized into the new shape (``emotion`` -> ``affect.feeling``, ``intent`` ->
    ``intents[0]``); the application always stores the new shape. Raises ``ValueError``
    on any violation and never invents a label.
    """
    if not isinstance(item, dict):
        raise ValueError("invalid-insights")
    identifier = item.get("id")
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("invalid-insights")
    status = item.get("status")
    if status not in API_INSIGHT_STATUSES:
        raise ValueError("invalid-insights")
    if status == "ok" and "readings" in item:
        readings = _normalize_readings(item.get("readings"))
        result = {"id": identifier, "status": "ok", "intents": [], "readings": readings}
        emotion = item.get("emotion")
        affect = item.get("affect")
        feeling = None
        if isinstance(emotion, str) and valid_api_insight_label(emotion) and emotion not in {"无", "暂无", "没有"}:
            feeling = emotion
        elif isinstance(affect, dict):
            raw = affect.get("feeling")
            if isinstance(raw, str) and valid_api_insight_label(raw) and raw not in {"无", "暂无", "没有"}:
                feeling = raw
        if feeling:
            result["affect"] = {"feeling": feeling}
        return result
    if status != "ok":
        affect = item.get("affect")
        intents = item.get("intents")
        if affect is not None and (not isinstance(affect, dict) or affect):
            raise ValueError("invalid-insights")
        if intents is not None and (not isinstance(intents, list) or intents):
            raise ValueError("invalid-insights")
        return {"id": identifier, "status": status}
    if "affect" in item or "intents" in item:
        affect = item.get("affect")
        if affect is None:
            affect = {}
        if not isinstance(affect, dict) or any(key not in API_AFFECT_FIELDS for key in affect):
            raise ValueError("invalid-insights")
        clean_affect = {}
        for field in API_AFFECT_FIELDS:
            label = affect.get(field)
            if label is None:
                continue
            if not valid_api_insight_label(label):
                raise ValueError("invalid-insights")
            clean_affect[field] = label
        values = list(clean_affect.values())
        if len(set(values)) != len(values):
            raise ValueError("invalid-insights")
        intents = item.get("intents")
        if intents is None:
            intents = []
        if not isinstance(intents, list) or len(intents) > API_INTENT_LIMIT:
            raise ValueError("invalid-insights")
        clean_intents = []
        for label in intents:
            if not valid_api_insight_label(label):
                raise ValueError("invalid-insights")
            if label in clean_intents:
                raise ValueError("invalid-insights")
            clean_intents.append(label)
        if set(clean_intents) & set(clean_affect.values()):
            raise ValueError("invalid-insights")
        result = {"id": identifier, "status": "ok"}
        if clean_affect:
            result["affect"] = clean_affect
        result["intents"] = clean_intents
        return result
    # Legacy scalar ok item; normalized into the new shape, never invented.
    emotion = item.get("emotion")
    intent = item.get("intent")
    if not valid_api_insight_label(emotion) or not valid_api_insight_label(intent):
        raise ValueError("invalid-insights")
    return {"id": identifier, "status": "ok", "affect": {"feeling": emotion},
            "intents": [intent]}
