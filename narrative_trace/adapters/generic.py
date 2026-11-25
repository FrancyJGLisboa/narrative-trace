"""Generic adapter: the payload already is a neutral event (or a list of them).

Use it from custom loops, OpenTelemetry exporters, or any harness without native hooks.
"""
from ..schema import KINDS, make_event

H = "generic"
EVENTS = ()


def _one(obj, session):
    if not isinstance(obj, dict) or obj.get("kind") not in KINDS:
        return None
    ev = make_event(obj["kind"], obj.get("harness") or H, session, tool=obj.get("tool"),
                    target=obj.get("target"), status=obj.get("status"),
                    error_text=obj.get("error"), text=obj.get("text"))
    if obj.get("summary"):
        from ..schema import redact, truncate
        ev["summary"] = truncate(redact(obj["summary"]), 300)
    return ev


def to_events(event_name, payload, session, state):
    try:
        items = payload if isinstance(payload, list) else [payload]
        if isinstance(payload, dict) and isinstance(payload.get("events"), list):
            items = payload["events"]
        return [e for e in (_one(i, session) for i in items) if e]
    except Exception:
        return []
