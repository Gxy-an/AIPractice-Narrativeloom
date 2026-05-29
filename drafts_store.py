# -*- coding: utf-8 -*-
"""本地草稿箱：JSON 存储。"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List

DRAFT_DIR = os.path.join(os.path.dirname(__file__), "data", "drafts")


def _ensure() -> None:
    os.makedirs(DRAFT_DIR, exist_ok=True)


def list_drafts() -> List[Dict[str, Any]]:
    _ensure()
    out: List[Dict[str, Any]] = []
    for name in sorted(os.listdir(DRAFT_DIR), reverse=True):
        if not name.endswith(".json"):
            continue
        path = os.path.join(DRAFT_DIR, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            d["_file"] = name
            d["_id"] = name.replace(".json", "")
            out.append(d)
        except (json.JSONDecodeError, OSError):
            continue
    return out


def save_draft(payload: Dict[str, Any]) -> str:
    _ensure()
    did = payload.get("id") or uuid.uuid4().hex[:12]
    path = os.path.join(DRAFT_DIR, f"{did}.json")
    payload = {**payload, "id": did, "updated_at": datetime.now().isoformat(timespec="seconds")}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return did


def load_draft(draft_id: str) -> Dict[str, Any]:
    path = os.path.join(DRAFT_DIR, f"{draft_id}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def delete_draft(draft_id: str) -> None:
    path = os.path.join(DRAFT_DIR, f"{draft_id}.json")
    if os.path.isfile(path):
        os.remove(path)
