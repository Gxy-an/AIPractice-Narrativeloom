# -*- coding: utf-8 -*-
"""轻量连贯性校验：关键词与矛盾词对匹配，标注潜在冲突。"""

from __future__ import annotations

import re
from typing import Iterable, List, Tuple

# 简易矛盾词对（同一段落/全文共现时提示）
CONFLICT_PAIRS: List[Tuple[str, str]] = [
    ("死亡", "站起"),
    ("身亡", "微笑"),
    ("去世", "说道"),
    ("殒命", "离开房间"),
    ("白天", "深夜"),
    ("清晨", "午夜"),
    ("在地球", "在火星"),
    ("室内", "暴雨中狂奔于荒野"),
]

# 人物占位：从结构化文本中提取「人物」行常见标签后的片段
_NAME_LINE = re.compile(
    r"(人物|角色|Characters?)[:：]\s*([^\n]+)", re.MULTILINE | re.IGNORECASE
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def extract_character_tokens(story_text: str) -> List[str]:
    """从已选节拍文本中抽取简短人物名/称谓（启发式）。"""
    found: List[str] = []
    for m in _NAME_LINE.finditer(story_text or ""):
        chunk = m.group(2).strip()
        for part in re.split(r"[、,，/]", chunk):
            p = part.strip()
            if 1 < len(p) <= 12:
                found.append(p)
    # 去重保序
    seen = set()
    out = []
    for x in found:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out[:20]


def check_keyword_conflicts(full_text: str) -> List[str]:
    """扫描全文，若同一矛盾对两端均出现则记录提示（粗粒度）。"""
    t = full_text or ""
    notes: List[str] = []
    for a, b in CONFLICT_PAIRS:
        if a in t and b in t:
            notes.append(f"同时出现「{a}」与「{b}」，请核对是否矛盾")
    return notes


def check_repeated_lines(beats_text: List[str]) -> List[str]:
    """若多节拍间出现相同或高度相似的非空行，提示可能重复。"""
    counts: dict[str, int] = {}
    sample: dict[str, str] = {}
    for b in beats_text:
        for ln in (b or "").splitlines():
            s = ln.strip()
            if len(s) < 12:
                continue
            norm = re.sub(r"\s+", "", s)
            if not norm:
                continue
            counts[norm] = counts.get(norm, 0) + 1
            sample.setdefault(norm, s)
    alerts: List[str] = []
    for norm, cnt in counts.items():
        if cnt >= 2:
            preview = sample[norm]
            if len(preview) > 48:
                preview = preview[:47] + "…"
            alerts.append(f"多节出现相似语句（{cnt} 次）：「{preview}」")
    return alerts[:8]


def check_cross_beat_names(
    prior_text: str, new_beat_text: str, names: Iterable[str]
) -> List[str]:
    """若前文出现某人物「死亡」类词，后文仍让其行动，则提示。"""
    prior = _normalize(prior_text)
    new = new_beat_text or ""
    alerts: List[str] = []
    death_kw = ("死亡", "身亡", "去世", "殒命", "牺牲")
    alive_kw = ("说道", "微笑", "点头", "离开", "站起", "握住")
    for n in names:
        if not n:
            continue
        if any(k in prior for k in death_kw) and n in prior:
            if n in new and any(k in new for k in alive_kw):
                alerts.append(f"人物「{n}」在前文有死亡相关描述，本节拍仍有行动描写，请核对")
    return alerts


def analyze_story(beats_text: List[str]) -> Tuple[int, List[str]]:
    """
    返回 (冲突条数, 冲突说明列表)。
    """
    merged = "\n\n".join(beats_text)
    issues: List[str] = []
    issues.extend(check_keyword_conflicts(merged))
    issues.extend(check_repeated_lines(beats_text))
    acc = ""
    names = extract_character_tokens(acc)
    for i, b in enumerate(beats_text):
        if i > 0:
            issues.extend(check_cross_beat_names(acc, b, names))
        acc += "\n" + (b or "")
        names = extract_character_tokens(acc)
    # 去重
    uniq = []
    seen = set()
    for x in issues:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return len(uniq), uniq
