# -*- coding: utf-8 -*-
"""本地草稿箱：JSON 存储。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List

from narrativeloom.config.settings import DRAFT_DIR


def _ensure() -> None:
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)


def list_drafts() -> List[Dict[str, Any]]:
    _ensure()
    out: List[Dict[str, Any]] = []
    for path in sorted(DRAFT_DIR.glob("*.json"), key=lambda p: p.name, reverse=True):
        try:
            with path.open("r", encoding="utf-8") as f:
                d = json.load(f)
            d["_file"] = path.name
            d["_id"] = path.stem
            out.append(d)
        except (json.JSONDecodeError, OSError):
            continue
    return out


def save_draft(payload: Dict[str, Any]) -> str:
    _ensure()
    did = payload.get("id") or uuid.uuid4().hex[:12]
    path = DRAFT_DIR / f"{did}.json"
    payload = {**payload, "id": did, "updated_at": datetime.now().isoformat(timespec="seconds")}
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return did


def load_draft(draft_id: str) -> Dict[str, Any]:
    path = DRAFT_DIR / f"{draft_id}.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def delete_draft(draft_id: str) -> None:
    path = DRAFT_DIR / f"{draft_id}.json"
    if path.is_file():
        path.unlink()
