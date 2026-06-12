# -*- coding: utf-8 -*-
"""轻量 RAG：从前文节拍块中按查询词重叠检索相关片段，供生成与审查使用。"""

from __future__ import annotations

import re
from typing import List, Tuple


def _bigrams(s: str) -> set[str]:
    s = re.sub(r"\s+", "", s or "")
    if len(s) < 2:
        return set()
    return {s[i : i + 2] for i in range(len(s) - 1)}


def _score(query: str, chunk: str) -> float:
    qb = _bigrams(query)
    cb = _bigrams(chunk)
    if not qb:
        return 0.0
    return len(qb & cb) / len(qb)


def build_chunks_from_beats(beat_texts: List[str], max_chunk_chars: int = 900) -> List[str]:
    """将已确认节拍拆成检索块（过长则按段切）。"""
    chunks: List[str] = []
    for t in beat_texts:
        if not (t or "").strip():
            continue
        t = t.strip()
        if len(t) <= max_chunk_chars:
            chunks.append(t)
            continue
        for i in range(0, len(t), max_chunk_chars):
            chunks.append(t[i : i + max_chunk_chars])
    return chunks


def canon_sheet_from_beats(
    beats: List,
    *,
    background_prefix: str = "",
    global_cast_block: str = "",
    lang: str = "zh",
) -> str:
    """从已选节拍汇总「设定清单」：人物与地点线索，强制模型沿用。可选前置背景纲要。"""
    en = (lang or "zh") == "en"
    lines: List[str] = []
    bp = (background_prefix or "").strip()
    if bp:
        lines.append("【Creative background (must follow)】" if en else "【创作背景（须遵守）】")
        lines.append(bp[:4000])
        lines.append("")
    gcb = (global_cast_block or "").strip()
    if gcb:
        lines.append(gcb)
        lines.append("")
    names: List[str] = []
    locs: List[str] = []
    for b in beats:
        if not b or not isinstance(b, dict):
            continue
        if b.get("mode") == "typified":
            ch = (b.get("characters") or "").strip()
            st = (b.get("setting") or "").strip()
            if ch:
                names.append(ch)
            if st:
                locs.append(st)
        else:
            m = (b.get("merged") or "").strip()
            if m:
                names.append(m[:200])
    if names:
        lines.append(
            "【Locked character info (reuse exact names and forms; no renames or duplicate aliases)】"
            if en
            else "【已定稿人物信息（后续必须沿用相同姓名与称谓，禁止改名或新增同角色别名）】"
        )
        lines.extend(names)
    if locs:
        lines.append(
            "\n【Locked setting / spatiotemporal cues】"
            if en
            else "\n【已定稿地点/时空线索】"
        )
        lines.extend(locs[:8])
    return "\n".join(lines)[:6000]


def retrieve_context(
    *,
    query: str,
    chunks: List[str],
    top_k: int = 4,
) -> str:
    """词重叠检索：返回若干最相关前文摘录。"""
    if not chunks:
        return ""
    scored: List[Tuple[float, str]] = [(_score(query, c), c) for c in chunks]
    scored.sort(key=lambda x: -x[0])
    picked: List[str] = []
    for sc, ch in scored[:top_k]:
        if sc <= 0 and picked:
            break
        picked.append(ch)
    return "\n---\n".join(picked)[:4500]
