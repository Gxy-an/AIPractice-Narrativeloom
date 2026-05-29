# -*- coding: utf-8 -*-
"""实验数据写入本地 CSV。"""

from __future__ import annotations

import csv
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

LOG_PATH = os.path.join(os.path.dirname(__file__), "data", "experiment_log.csv")

COLUMNS = [
    "timestamp",
    "persona_pool",
    "feedback_mode",
    "writing_experience",
    "beat_index",
    "beat_seconds",
    "beat_edit_events",
    "selected_personas",
    "final_char_count",
    "coherence_conflict_count",
    "likert_understanding",
    "likert_inspiration",
    "likert_cognitive_load",
    "likert_satisfaction",
    "notes",
]


def _ensure_file() -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()


def append_row(row: Dict[str, Any]) -> str:
    _ensure_file()
    row = {k: row.get(k, "") for k in COLUMNS}
    if not row.get("timestamp"):
        row["timestamp"] = datetime.now().isoformat(timespec="seconds")
    with open(LOG_PATH, "a", newline="", encoding="utf-8-sig") as f:
        csv.DictWriter(f, fieldnames=COLUMNS).writerow(row)
    return LOG_PATH


def log_session_summary(
    *,
    persona_pool: str,
    feedback_mode: str,
    writing_experience: str,
    beat_rows: List[Dict[str, Any]],
    final_char_count: int,
    coherence_conflict_count: int,
    likert: Dict[str, int],
    notes: str = "",
) -> str:
    """每个节拍一行，主观量表写入最后一行（beat_index=-1 表示汇总可选；此处每节拍一行+最终一行）。"""
    _ensure_file()
    paths = []
    for br in beat_rows:
        paths.append(
            append_row(
                {
                    "persona_pool": persona_pool,
                    "feedback_mode": feedback_mode,
                    "writing_experience": writing_experience,
                    "beat_index": br.get("beat_index", ""),
                    "beat_seconds": br.get("beat_seconds", ""),
                    "beat_edit_events": br.get("beat_edit_events", ""),
                    "selected_personas": br.get("selected_personas", ""),
                    "final_char_count": "",
                    "coherence_conflict_count": "",
                    "likert_understanding": "",
                    "likert_inspiration": "",
                    "likert_cognitive_load": "",
                    "likert_satisfaction": "",
                    "notes": br.get("notes", ""),
                }
            )
        )
    paths.append(
        append_row(
            {
                "persona_pool": persona_pool,
                "feedback_mode": feedback_mode,
                "writing_experience": writing_experience,
                "beat_index": "summary",
                "beat_seconds": "",
                "beat_edit_events": sum(int(x.get("beat_edit_events") or 0) for x in beat_rows),
                "selected_personas": "",
                "final_char_count": final_char_count,
                "coherence_conflict_count": coherence_conflict_count,
                "likert_understanding": likert.get("understanding", ""),
                "likert_inspiration": likert.get("inspiration", ""),
                "likert_cognitive_load": likert.get("cognitive_load", ""),
                "likert_satisfaction": likert.get("satisfaction", ""),
                "notes": notes,
            }
        )
    )
    return LOG_PATH
