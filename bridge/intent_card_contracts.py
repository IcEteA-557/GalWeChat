"""Stored shape for intent cards. Standard library only.

The Node analyzer is the source of the card. This module rejects anything that
does not match that contract before it is written or shown.
"""
from __future__ import annotations

import hashlib
import re

INTENT_CARD_REVISION = "intent-card-v1"
INTENT_CARD_STYLES = frozenset({"dating", "general"})
INTENT_CARD_BATCH = 8
INTENT_CARD_CONTEXT = 20
INTENT_CARD_ID_LIMIT = 500
INTENT_CARD_WIRE_LIMIT = 40
TITLE_MAX = 24
OPTION_LABEL_MAX = 16
METER_TITLE_MAX = 12
ADVICE_MAX = 40
FORBIDDEN_MOVE = re.compile("装死|服从测试|煤气灯|贬低|威胁")
FORBIDDEN_ADVICE = re.compile("装死|服从测试|煤气灯")
CONTROL = re.compile(r"[\u0000-\u001f\u007f]")


def intent_card_scope(source_id):
    return source_id + ":" + INTENT_CARD_REVISION


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("invalid-intent-cards")
    return value


def _bounded(value, maximum):
    if not isinstance(value, str):
        raise ValueError("invalid-intent-cards")
    text = value.strip()
    if not text or len(text) > maximum or CONTROL.search(text):
        raise ValueError("invalid-intent-cards")
    return text


def _choice(section):
    title = _bounded(section.get("title"), TITLE_MAX)
    options = section.get("options")
    if not isinstance(options, list) or not 2 <= len(options) <= 4:
        raise ValueError("invalid-intent-cards")
    clean = []
    for option in options:
        _exact(option, ("label", "percent"))
        label = _bounded(option.get("label"), OPTION_LABEL_MAX)
        percent = option.get("percent")
        if type(percent) is not int or isinstance(percent, bool) or not 0 <= percent <= 100:
            raise ValueError("invalid-intent-cards")
        clean.append({"label": label, "percent": percent})
    if sum(item["percent"] for item in clean) != 100:
        raise ValueError("invalid-intent-cards")
    if "动作" in title and any(item["percent"] >= 50 and FORBIDDEN_MOVE.search(item["label"])
                              for item in clean):
        raise ValueError("invalid-intent-cards")
    return {"kind": "choice", "title": title, "options": clean}


def _meter(section):
    title = _bounded(section.get("title"), METER_TITLE_MAX)
    value = section.get("value")
    if (type(value) is not int or isinstance(value, bool) or not 0 <= value <= 10 or
            section.get("max") != 10):
        raise ValueError("invalid-intent-cards")
    return {"kind": "meter", "title": title, "value": value, "max": 10}


def _advice(section):
    text = _bounded(section.get("text"), ADVICE_MAX)
    if FORBIDDEN_ADVICE.search(text):
        raise ValueError("invalid-intent-cards")
    return {"kind": "advice", "text": text}


def normalize_intent_card(item, style):
    """Return the canonical card. Raises ValueError on any violation."""
    if style not in INTENT_CARD_STYLES:
        raise ValueError("invalid-intent-cards")
    _exact(item, ("id", "sections"))
    identifier = item.get("id")
    if not isinstance(identifier, str) or not identifier or len(identifier) > 200 or CONTROL.search(identifier):
        raise ValueError("invalid-intent-cards")
    raw_sections = item.get("sections")
    if not isinstance(raw_sections, list) or not 1 <= len(raw_sections) <= 4:
        raise ValueError("invalid-intent-cards")
    sections = []
    meters = 0
    advice = 0
    for section in raw_sections:
        if not isinstance(section, dict):
            raise ValueError("invalid-intent-cards")
        kind = section.get("kind")
        if kind == "choice":
            _exact(section, ("kind", "title", "options"))
            sections.append(_choice(section))
        elif kind == "meter":
            if style != "dating":
                raise ValueError("invalid-intent-cards")
            _exact(section, ("kind", "title", "value", "max"))
            meters += 1
            sections.append(_meter(section))
        elif kind == "advice":
            _exact(section, ("kind", "text"))
            advice += 1
            sections.append(_advice(section))
        else:
            raise ValueError("invalid-intent-cards")
    if meters > 1 or advice > 1:
        raise ValueError("invalid-intent-cards")
    return {"id": identifier, "sections": sections}


def intent_card_targets(text_window, start_id):
    """Other texts from start_id through the end of the already filtered window."""
    if not isinstance(start_id, str) or not 1 <= len(start_id) <= 200 or CONTROL.search(start_id):
        raise ValueError("invalid intent card start")
    start = next((index for index, item in enumerate(text_window)
                  if item.get("id") == start_id and item.get("side") == "other"), None)
    if start is None:
        raise ValueError("intent-card-start-outside-window")
    selected = [item for item in text_window[start:] if item.get("side") == "other"]
    if not selected or len(selected) > INTENT_CARD_ID_LIMIT:
        raise ValueError("intent-card-start-outside-window")
    return selected


def intent_card_batches(text_window, targets):
    """Split targets into model calls.

    Each call carries at most 8 targets, preceded by up to 20 texts that sit
    immediately before that batch's first target. The chat tail is not reused
    as context for an earlier batch.
    """
    if not targets:
        return []
    positions = {item.get("id"): index for index, item in enumerate(text_window)}
    batches = []
    for offset in range(0, len(targets), INTENT_CARD_BATCH):
        batch = targets[offset:offset + INTENT_CARD_BATCH]
        first = positions.get(batch[0].get("id"))
        if first is None:
            raise ValueError("intent-card-start-outside-window")
        preceding = text_window[max(0, first - INTENT_CARD_CONTEXT):first]
        items = [*preceding, *batch]
        if len(items) > INTENT_CARD_WIRE_LIMIT:
            items = items[-INTENT_CARD_WIRE_LIMIT:]
        wire = [{"id": item["id"], "sender": "SELF" if item.get("side") == "self" else "OTHER",
                 "text": item["text"]} for item in items]
        batches.append((batch, wire))
    return batches
