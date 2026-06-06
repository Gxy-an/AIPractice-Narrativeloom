# -*- coding: utf-8 -*-
"""核心事件等展示为 Markdown 分条。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

_MUT_OPEN = "⟦mut⟧"
_MUT_CLOSE = "⟦/mut⟧"

# 过短或仅占位的「核心事件」视为无效，触发补全或界面提示
_KEY_EVENTS_TRIVIAL = frozenset(
    {
        "",
        "-",
        "—",
        "–",
        "·",
        "…",
        "...",
        "……",
        "无",
        "暂无",
        "待补充",
        "tbd",
        "TBD",
        "n/a",
        "N/A",
        "null",
        "None",
    }
)


def muffle_markdown_heading_lines(text: str) -> str:
    """将行首 # 转为全角 ＃，避免在 st.markdown 中被解析成巨型标题。"""
    if not text:
        return ""
    out: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^(\s*)(#+)(\s*)(.*)$", line)
        if m:
            indent, hashes, sp, rest = m.groups()
            out.append(f"{indent}{'＃' * len(hashes)}{sp}{rest}")
        else:
            out.append(line)
    return "\n".join(out)


def coerce_display_text(val: Any) -> str:
    """将模型可能返回的 list/dict 等转为可展示的纯文本（用于设定/人物/核心事件）。"""
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, list):
        rows: list[str] = []
        for item in val:
            if isinstance(item, str) and item.strip():
                rows.append(item.strip())
            elif isinstance(item, dict):
                piece = item.get("event") or item.get("text") or item.get("line") or item.get("beat")
                if isinstance(piece, str) and piece.strip():
                    rows.append(piece.strip())
                elif item:
                    rows.append(str(item).strip())
            elif item is not None:
                s = str(item).strip()
                if s:
                    rows.append(s)
        return "\n".join(rows)
    if isinstance(val, dict):
        inner = val.get("events") or val.get("lines") or val.get("key_events")
        if isinstance(inner, (list, str)):
            return coerce_display_text(inner)
        return str(val).strip()
    return str(val).strip()


def key_events_meaningful(val: Any) -> bool:
    """核心事件字段是否有实质内容（非空、非单字符占位）。"""
    raw = coerce_display_text(val).strip()
    if not raw or raw in _KEY_EVENTS_TRIVIAL:
        return False
    if len(raw) < 8:
        return False
    if re.fullmatch(r"[-–—·\s•]+", raw):
        return False
    return True


def typified_characters_meaningful(val: Any) -> bool:
    """类型化小节人物字段是否含至少两名具名角色。"""
    raw = coerce_display_text(val).strip()
    if not raw or raw in _KEY_EVENTS_TRIVIAL:
        return False
    if "待补全" in raw:
        return False
    entries = [
        e
        for e in _split_character_entries(raw)
        if e and e not in _KEY_EVENTS_TRIVIAL and len(e) > 2
    ]
    named = 0
    for e in entries:
        line = e.lstrip("-·• ").strip()
        if "：" in line or ":" in line:
            name = line.replace(":", "：").split("：", 1)[0].strip()
            if name and len(name) >= 2:
                named += 1
        elif len(line) >= 2:
            named += 1
    return named >= 2


_PLACEHOLDER_CHARACTER_DESC = (
    "承接前文既定人物",
    "本节须保留",
    "本节必须存在",
    "关键剧情人物",
    "动机与性格须在本小节行动中体现",
    "须在本节行动中有动机",
    "本节出场人物",
    "本节新出场或补充角色",
    "与本节冲突相关",
)


def _is_placeholder_character_desc(desc: str) -> bool:
    d = (desc or "").strip()
    if not d or len(d) < 2:
        return True
    return any(p in d for p in _PLACEHOLDER_CHARACTER_DESC)


def _plain_setting_hint(setting: str) -> str:
    parts: List[str] = []
    for ln in (setting or "").splitlines():
        t = re.sub(r"^[-*•·]\s*", "", ln.strip())
        t = re.sub(r"^(地点|时间)[：:]\s*", "", t)
        if t:
            parts.append(t.rstrip("，,；; "))
    if parts:
        return "，".join(parts)[:36]
    return (setting or "").strip()[:36]


def _resolve_character_description(
    name: str,
    desc: str = "",
    *,
    seed: str = "",
    setting: str = "",
    key_events: str = "",
    prior_profiles: Optional[Dict[str, str]] = None,
    raw_map: Optional[Dict[str, str]] = None,
) -> str:
    """为人物生成具体设定句，禁止占位/承接类无效描述。"""
    prior = lookup_character_profile(name, prior_profiles)
    if prior:
        return prior
    d = (desc or "").strip()
    if d and not _is_placeholder_character_desc(d):
        return d
    if raw_map:
        for k, v in raw_map.items():
            if k == name or name.startswith(k) or k.startswith(name):
                if v and not _is_placeholder_character_desc(v):
                    return v
    ctx_plot = "\n".join(x for x in (seed, key_events) if x)
    inferred = _infer_sculptor_trait(name, ctx_plot, setting)
    trait_desc = inferred.split("：", 1)[-1].strip() if "：" in inferred else inferred.strip()
    if trait_desc and not _is_placeholder_character_desc(trait_desc):
        return trait_desc
    blob = f"{seed}\n{setting}".strip()
    setting_hint = _plain_setting_hint(setting)
    if name in blob:
        for role in ("画师", "画家", "流浪", "工人", "老板", "师傅", "学生", "记者", "管事", "看守"):
            if role in blob:
                hint = setting_hint or "本节场景"
                return f"{role}，与{hint}直接相关"
        if re.search(r"(作画|壁画|画《|绘画)", blob):
            hint = setting_hint or "猪圈作画"
            return f"画师，在{hint}创作"
        for sent in re.split(r"[。；!\?\n]", seed):
            if name not in sent:
                continue
            tail = sent.split(name, 1)[-1].strip("，,：: 在将向对")
            if 2 <= len(tail) <= 26 and not _is_placeholder_character_desc(tail):
                return tail[:26]
    if setting and len(setting.strip()) >= 6:
        return f"本节主要人物，身处{_plain_setting_hint(setting) or setting[:22].rstrip('，,；; ')}"
    return "本节主要人物，行动推动当前情节"


def parse_character_profile_map(text: Any) -> Dict[str, str]:
    """从背景/前序小节人物块提取「姓名→身份描述」映射。"""
    from narrativeloom.domain.character_names import _is_compound_cast_name

    raw = coerce_display_text(text).strip()
    if not raw:
        return {}
    out: Dict[str, str] = {}
    for entry in _split_character_entries(raw):
        line = entry.lstrip("-·• ").strip()
        if not line or ("：" not in line and ":" not in line):
            continue
        line = line.replace(":", "：")
        name, _, desc = line.partition("：")
        name = name.strip()
        desc = re.sub(r"\s+", " ", desc.strip())
        if not name or len(desc) < 2:
            continue
        if any(p in desc for p in _PLACEHOLDER_CHARACTER_DESC):
            continue
        out[name] = desc
    merged = dict(out)
    for name, desc in out.items():
        if not _is_compound_cast_name(name):
            continue
        root = name.split("·")[0]
        if root and root not in merged:
            merged[root] = desc
    return merged


def lookup_character_profile(
    name: str,
    profiles: Optional[Dict[str, str]],
) -> str:
    """按姓名（含复合名/简称）查找已有介绍。"""
    n = (name or "").strip()
    if not n or not profiles:
        return ""
    if n in profiles:
        return profiles[n]
    for key, desc in profiles.items():
        if n == key or n.startswith(key) or key.startswith(n):
            return desc
        parts = [p for p in re.split(r"[·．\.]", key) if p]
        if n in parts or any(n.startswith(p) or p.startswith(n) for p in parts if len(p) >= 2):
            return desc
    return ""


def extract_sculptor_section_text(text: str) -> str:
    """从职能合并稿中提取【人物塑造师】正文。"""
    sections = parse_merge_role_sections(text or "")
    for title, body in sections:
        if _is_sculptor_section_title(title):
            return (body or "").strip()
    return ""


def normalize_typified_key_events(
    text: Any,
    *,
    min_lines: int = 3,
    max_lines: int = 5,
) -> str:
    """规范类型化核心事件：单句 30～50 字/条，小节总和 ≤300 字。"""
    from narrativeloom.service.llm_client import (
        TYPIFIED_KEY_EVENT_CHARS_MAX,
        TYPIFIED_KEY_EVENT_CHARS_MIN,
        TYPIFIED_KEY_EVENTS_TOTAL_MAX,
    )

    raw = coerce_display_text(text).strip()
    if not raw:
        return raw
    entries: List[str] = []
    for entry in _split_event_entries(raw, max_lines):
        e = re.sub(r"^[-*•·]\s*", "", entry.strip())
        if not e or not key_events_meaningful(e):
            continue
        if len(e) > TYPIFIED_KEY_EVENT_CHARS_MAX:
            e = e[:TYPIFIED_KEY_EVENT_CHARS_MAX]
        entries.append(e)
    out: List[str] = []
    total = 0
    for e in entries:
        if len(out) >= max_lines:
            break
        if out and total + len(e) > TYPIFIED_KEY_EVENTS_TOTAL_MAX:
            break
        out.append(e)
        total += len(e)
    if not out:
        return raw
    while len(out) < min_lines and len(entries) > len(out):
        nxt = entries[len(out)]
        if total + len(nxt) > TYPIFIED_KEY_EVENTS_TOTAL_MAX:
            break
        out.append(nxt)
        total += len(nxt)
    return "\n".join(f"- {e}" for e in out)


def sanitize_typified_characters(
    text: Any,
    *,
    target: int = 2,
    locked_names: Optional[List[str]] = None,
    seed: str = "",
    setting: str = "",
    key_events: str = "",
    prior_characters_block: str = "",
    strict_narrative_allowlist: bool = False,
    global_cast_names: Optional[List[str]] = None,
) -> str:
    """过滤类型化 characters 中的非人物条目，补满目标人数。"""
    from narrativeloom.domain.character_names import (
        _build_sculptor_allowlist,
        _is_subname_of_compound_cast,
        _resolve_cast_name,
        _scrub_cast_name,
        is_false_person_name,
        merge_unique_names,
    )
    from narrativeloom.domain.global_character_list import fallback_name_from_global_cast

    raw = coerce_display_text(text).strip()
    context = f"{seed}\n{setting}\n{key_events}\n{raw}"
    locked = merge_unique_names(list(locked_names or []))
    prior_profiles = parse_character_profile_map(prior_characters_block)
    target = max(2, min(int(target), 8))
    global_cast = merge_unique_names(list(global_cast_names or []), locked)
    plot_allow = _build_sculptor_allowlist(
        seed=seed,
        locked_names=locked,
        plot_sources=[key_events],
        setting_context=setting,
        body=raw,
    )
    allow_set: set[str] = set(global_cast) | set(locked) | set(plot_allow)
    if strict_narrative_allowlist:
        allowlist = plot_allow
        allow_set = set(allowlist) | set(locked) | set(global_cast)
    raw_map: Dict[str, str] = {}
    for entry in _split_character_entries(raw):
        line = entry.lstrip("-·• ").strip()
        if not line or ("：" not in line and ":" not in line):
            continue
        line = line.replace(":", "：")
        name, _, desc = line.partition("：")
        raw_map[name.strip()] = desc.strip()
    kept: List[tuple[str, str]] = []
    seen: set[str] = set()

    def _push(name: str, desc: str = "") -> None:
        cast_so_far = [n for n, _ in kept]
        n = _scrub_cast_name(name, cast_so_far, context=f"{desc}\n{context}")
        if not n or n in seen:
            return
        if _is_subname_of_compound_cast(n, locked + cast_so_far):
            return
        if is_false_person_name(n, context=f"{n}\n{desc}\n{context}"):
            return
        if strict_narrative_allowlist:
            resolved_anchor = _resolve_cast_name(n, locked, context=context) or n
            in_allow = n in allow_set or resolved_anchor in allow_set
            in_locked = n in locked or resolved_anchor in locked
            if not in_allow and not in_locked:
                return
        seen.add(n)
        resolved = _resolve_character_description(
            n,
            desc,
            seed=seed,
            setting=setting,
            key_events=key_events,
            prior_profiles=prior_profiles,
            raw_map=raw_map,
        )
        kept.append((n, resolved))

    for lk in locked:
        if lk and lk not in seen:
            _push(lk, raw_map.get(lk, ""))
    for name, desc in raw_map.items():
        _push(name, desc)

    cast_names = [n for n, _ in kept]

    def _fill_from_plot_allowlist() -> None:
        nonlocal cast_names
        ranked = _sort_allowlist_by_plot(
            _filter_allowlist_subnames(allow_set), key_events
        )
        for candidate in ranked:
            if len(cast_names) >= target:
                break
            if candidate in seen:
                continue
            if _is_subname_of_compound_cast(candidate, locked + cast_names):
                continue
            before = len(kept)
            _push(candidate, raw_map.get(candidate, ""))
            if len(kept) > before:
                cast_names = [n for n, _ in kept]

    _fill_from_plot_allowlist()

    cast_names = [n for n, _ in kept]
    while len(cast_names) < target:
        extra = ""
        if global_cast:
            extra = fallback_name_from_global_cast(cast_names, global_cast, context=context)
        if not extra and allow_set:
            ranked = _sort_allowlist_by_plot(
                _filter_allowlist_subnames(allow_set), key_events
            )
            for candidate in ranked:
                if candidate in cast_names:
                    continue
                if _is_subname_of_compound_cast(candidate, locked + cast_names):
                    continue
                clean = _scrub_cast_name(candidate, cast_names, context=context)
                if clean and clean not in cast_names:
                    extra = clean
                    break
        if not extra and not strict_narrative_allowlist:
            from narrativeloom.domain.character_names import _fallback_supplementary_name

            plot_context = f"{seed}\n{setting}\n{key_events}"
            extra = _fallback_supplementary_name(
                cast_names, full=context, seed=seed, narrative=plot_context
            )
        if not extra and strict_narrative_allowlist:
            from narrativeloom.domain.character_names import extract_cast_from_narrative

            plot_context = f"{seed}\n{setting}\n{key_events}"
            for candidate in extract_cast_from_narrative(plot_context, limit=12):
                resolved = _resolve_cast_name(candidate, locked, context=context) or candidate
                clean = _scrub_cast_name(resolved, cast_names, context=context) or resolved
                if (
                    clean
                    and clean not in cast_names
                    and (clean in allow_set or resolved in allow_set)
                    and not is_false_person_name(clean, context=f"{clean}\n{context}")
                ):
                    extra = clean
                    break
        if not extra or extra in cast_names:
            break
        before = len(kept)
        _push(extra, "")
        if len(kept) == before:
            break
        cast_names = [n for n, _ in kept]

    lines = [f"- {n}：{d}" for n, d in kept[:target]]
    return "\n".join(lines) if lines else raw


def _filter_allowlist_subnames(candidates: Sequence[str]) -> List[str]:
    """去掉被更长正式姓名包含的短片段（如 利亚 ⊂ 玛利亚）。"""
    uniq = list(dict.fromkeys(c for c in candidates if c))
    out: List[str] = []
    for n in sorted(uniq, key=len, reverse=True):
        if any(n != m and n in m for m in uniq):
            continue
        out.append(n)
    return out


def _sort_allowlist_by_plot(candidates: Sequence[str], plot_text: str) -> List[str]:
    plot = plot_text or ""
    return sorted(
        list(candidates),
        key=lambda n: (
            plot.find(n) if n in plot else 10_000,
            -len(n),
        ),
    )


def key_events_to_bullets(text: Any) -> str:
    """将核心事件整理为多行，每行以「· 」开头（Markdown 下行尾两空格换行，便于阅读）。"""
    raw = coerce_display_text(text)
    if not raw or not key_events_meaningful(raw):
        return ""
    lines = [ln.strip() for ln in re.split(r"[\n\r]+", raw) if ln.strip()]
    if len(lines) <= 1 and re.search(r"\s+[-–—]\s+", raw):
        parts = re.split(r"\s+[-–—]\s+", raw)
        lines = [p.strip() for p in parts if p.strip()]
    if len(lines) <= 1:
        tmp: list[str] = []
        for chunk in re.split(r"\s*[-–—]{1,3}\s*", raw):
            chunk = chunk.strip()
            if not chunk:
                continue
            for seg in re.split(r"[；;。]+", chunk):
                seg = seg.strip()
                if seg and len(seg) > 1:
                    tmp.append(seg)
        if tmp:
            lines = tmp
    if len(lines) <= 1 and len(raw) < 800:
        parts = re.split(r"[；;。]+", raw)
        lines = [p.strip() for p in parts if p.strip() and len(p.strip()) > 1]
    if not lines:
        lines = [raw.strip()[:400]] if key_events_meaningful(raw) else []
    if not lines:
        return ""
    out: list[str] = []
    for ln in lines[:12]:
        orig = ln
        ln = re.sub(r"^[\d一二三四五六七八九十]+[\.、\)\]]\s*", "", ln)
        ln = re.sub(r"^[-*•·]\s*", "", ln)
        ln = ln.lstrip("•·　 ")
        if not ln and orig.strip() not in _KEY_EVENTS_TRIVIAL and len(orig.strip()) > 1:
            ln = orig.strip()
        if ln and ln not in _KEY_EVENTS_TRIVIAL:
            out.append(f"· {ln}  ")
    return "\n".join(out).rstrip() if out else ""


def _strip_paren_notes(text: str) -> str:
    t = re.sub(r"[（(][^）)]{0,80}[）)]", "", text)
    return re.sub(r"\s+", " ", t).strip()


def _normalize_char_entry(s: str) -> str:
    """规范为「姓名：说明」，仅在已有冒号且两侧合理时拆分，避免误拆正文。"""
    s = re.sub(r"^[-*•·\s]+", "", (s or "").strip())
    s = _strip_paren_notes(s)
    if not s:
        return ""
    s = s.replace(":", "：")
    if "：" in s:
        name, _, desc = s.partition("：")
        name, desc = name.strip(), desc.strip()
        if 1 < len(name) <= 12 and len(desc) >= 2:
            return f"{name}：{desc}"
        if len(desc) >= 2:
            return f"{name}：{desc}" if name else desc
    return s


def _split_character_entries(characters: str) -> List[str]:
    """按行、& 或「 - 」列表拆人物，不做武断正则切分。"""
    raw = coerce_display_text(characters)
    if not raw:
        return []

    lines: List[str] = []
    for ln in re.split(r"[\n\r]+", raw):
        ln = re.sub(r"^[-*•·\d一二三四五六七八九十\.、\)\]]+\s*", "", ln.strip())
        ln = _strip_paren_notes(ln)
        if ln and ln not in _KEY_EVENTS_TRIVIAL and len(ln) > 1:
            lines.append(_normalize_char_entry(ln))
    lines = [x for x in lines if x]
    if len(lines) >= 2:
        return lines[:5]

    if "&" in raw:
        parts = [_normalize_char_entry(p) for p in raw.split("&")]
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            return parts[:5]

    if re.search(r"\s+-\s+", raw):
        parts = [_normalize_char_entry(p) for p in re.split(r"\s+-\s+", raw)]
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            return parts[:5]

    one = _normalize_char_entry(_strip_paren_notes(raw))
    return [one] if one else []


def _split_event_entries(events: str, max_items: int = 5) -> List[str]:
    raw = coerce_display_text(events)
    if not raw:
        return []
    bullets = key_events_to_bullets(raw)
    if bullets:
        out: List[str] = []
        for ln in bullets.split("\n"):
            ln = re.sub(r"^·\s*", "", ln.strip()).rstrip()
            if ln and ln not in _KEY_EVENTS_TRIVIAL:
                out.append(ln)
            if len(out) >= max_items:
                break
        if out:
            return out[:max_items]
    out: List[str] = []
    for ln in re.split(r"[\n\r]+", raw):
        ln = re.sub(r"^[-*•·\d一二三四五六七八九十\.、\)\]]+\s*", "", _strip_paren_notes(ln.strip()))
        if ln and ln not in _KEY_EVENTS_TRIVIAL and len(ln) > 2:
            out.append(ln)
        if len(out) >= max_items:
            break
    if len(out) <= 1 and re.search(r"\s+[-–—]\s+", raw):
        parts = [p.strip() for p in re.split(r"\s+[-–—]\s+", raw) if p.strip()]
        if len(parts) >= 2:
            out = [re.sub(r"^[-*•·]\s*", "", p) for p in parts[:max_items]]
    if len(out) < max_items:
        for seg in re.split(r"[；;。]+", _strip_paren_notes(raw)):
            seg = re.sub(r"^[-*•·\s]+", "", seg.strip())
            if seg and seg not in _KEY_EVENTS_TRIVIAL and seg not in out:
                out.append(seg)
            if len(out) >= max_items:
                break
    return out[:max_items]


_SCULPTOR_STATUS_CUT = re.compile(
    r"[,，]?\s*(?:本节状态|当前状态|本节中|本节里|"
    r"当前因|当前为|当前正|当前被|当前尝试|当前发现|当前识别|当前处于|当前潜伏).*$",
    re.I,
)


def sanitize_sculptor_description(desc: str, *, max_chars: int = 40) -> str:
    """功能化人物行：去掉标签式用语，精简为短句直接叙述。"""
    s = (desc or "").strip()
    if not s:
        return s
    s = _SCULPTOR_STATUS_CUT.sub("", s).strip()
    s = re.sub(r"(?:动机是|关系是|性格是|身份是|状态是)\s*", "", s)
    s = re.sub(r"[,，]{2,}", "，", s)
    s = re.sub(r"\s+", " ", s).strip("，,、 ")
    if len(s) > max_chars:
        for sep in ("，", ",", "；", ";"):
            if sep in s:
                head = s.split(sep, 1)[0].strip()
                if len(head) >= 8:
                    s = head
                    break
        if len(s) > max_chars:
            s = s[:max_chars]
    return s


def _is_continuity_section_title(title: str) -> bool:
    t = (title or "").strip()
    return "连贯性校验" in t or "Continuity Checker" in t or t in ("【连贯性校验师】", "【Continuity Checker】")


def _card_char_display(entry: str, *, max_chars: int = 88) -> str:
    """卡片展示：与编辑区一致，保留完整人物行（仅做空白与 bullet 规整）。"""
    s = (entry or "").strip().lstrip("-·• ").strip()
    if not s:
        return ""
    if len(s) > max_chars:
        return s[:max_chars]
    return s


def format_typified_brief(data: dict, lang: str = "zh") -> Tuple[str, str, str]:
    """时间地点一行；人物与编辑区一致（完整身份描述）；核心事件为 · 列表。"""
    setting = coerce_display_text(data.get("setting", ""))
    characters = coerce_display_text(data.get("characters", ""))
    events = coerce_display_text(data.get("key_events", ""))
    zh = (lang or "zh") == "zh"
    dash = "—" if zh else "—"
    max_char = 88 if zh else 120

    place_line = _strip_paren_notes(setting.replace("\n", " ")).strip() or dash

    char_entries = [_card_char_display(e, max_chars=max_char) for e in _split_character_entries(characters)]
    char_entries = [e for e in char_entries if e and e not in _KEY_EVENTS_TRIVIAL]
    char_block = "\n".join(f"· {e}" for e in char_entries) if char_entries else dash

    ev_entries = _split_event_entries(events, 5)
    ev_block = "\n".join(f"· {e}" for e in ev_entries) if ev_entries else dash

    return place_line, char_block, ev_block


def unescape_display_text(text: str) -> str:
    """将 JSON 字符串里残留的 \\n、\\\" 等转为可读字符（展示/解析前调用）。"""
    s = (text or "").strip()
    if not s:
        return s
    if "\\n" not in s and "\\t" not in s and '\\"' not in s:
        return s
    if s.count("\n") > s.count("\\n"):
        return s
    out: List[str] = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == "n":
                out.append("\n")
                i += 2
                continue
            if nxt == "t":
                out.append("\t")
                i += 2
                continue
            if nxt == "r":
                out.append("\r")
                i += 2
                continue
            if nxt in "\"\\":
                out.append(nxt)
                i += 2
                continue
            if nxt == "u" and i + 6 <= len(s):
                try:
                    out.append(chr(int(s[i + 2 : i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
        out.append(s[i])
        i += 1
    return "".join(out)


def strip_trailing_json_leak(text: str) -> str:
    """去掉模型误写入正文末尾的 JSON 键值片段。"""
    raw = (text or "").strip()
    if not raw:
        return raw
    cut = re.search(r'"\s*,\s*"(?:process_feedback|outline|variants)"\s*:', raw)
    if cut:
        raw = raw[: cut.start()].rstrip().rstrip('"').rstrip(",").rstrip()
    raw = re.sub(r'"\s*,\s*"process_feedback"\s*:\s*\{.*$', "", raw, flags=re.S).strip()
    return raw


def bullet_text_to_markdown(block: str) -> str:
    """将 · 分行文本转为 Markdown 无序列表。"""
    lines: List[str] = []
    for ln in (block or "").split("\n"):
        ln = ln.strip().lstrip("·").strip()
        if ln and ln not in _KEY_EVENTS_TRIVIAL and ln != "—":
            lines.append(ln)
    if not lines:
        return "—"
    return "\n".join(f"- {ln}" for ln in lines)


def scrub_functional_fragment(fragment: str) -> str:
    """去掉误泄露的 JSON 符号行、空壳标点行等。"""
    raw = strip_trailing_json_leak(unescape_display_text(fragment))
    if not raw:
        return ""
    kept: List[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        body = re.sub(r"^[-*•·]+\s*", "", s)
        if _JSON_JUNK_LINE.match(s) or _JSON_JUNK_LINE.match(body):
            continue
        if body in ("{", "}", "},", "{,", "[", "]", '",', '"'):
            continue
        if re.fullmatch(r"[\{\}\[\],\":\s]+", body):
            continue
        if re.match(r'^"(?:fragment|variants|process_feedback|outline)"\s*:', body, re.I):
            continue
        if re.search(r'"(?:outline|variants)"\s*:\s*"?\s*$', s):
            continue
        kept.append(line.rstrip())
    return "\n".join(kept).strip()


def _normalize_bare_mutation_brackets(raw: str) -> str:
    """将模型输出的裸 ⟦…⟧（未含 mut 关键字）转为标准突变标记。"""
    if not raw or "⟦" not in raw:
        return raw

    def _repl(m: re.Match[str]) -> str:
        inner = m.group(1)
        if re.fullmatch(r"\s*/?\s*mut\s*", inner, flags=re.I):
            return m.group(0)
        return f"{_MUT_OPEN}{inner}{_MUT_CLOSE}"

    return re.sub(r"⟦([^⟧]+)⟧", _repl, raw)


def normalize_mutation_marker_aliases(text: str) -> str:
    """将模型多种突变标记写法统一为 ⟦mut⟧…⟦/mut⟧。"""
    raw = (text or "").replace("\\n", "\n")
    if not raw.strip():
        return raw
    # 模型误用 <<<mut>>> / <<mut>> 等角括号标记
    raw = re.sub(r"<<+\s*/\s*mut\s*>>+", _MUT_CLOSE, raw, flags=re.I)
    raw = re.sub(r"<<+\s*mut\s*>>+", _MUT_OPEN, raw, flags=re.I)
    raw = re.sub(r"<{2,}\s*/?\s*mut\s*>{2,}", _MUT_CLOSE, raw, flags=re.I)
    raw = re.sub(r"⟦\s*/\s*mut\s*⟧", _MUT_CLOSE, raw, flags=re.I)
    raw = re.sub(r"⟦\s*mut\s*⟧", _MUT_OPEN, raw, flags=re.I)
    raw = re.sub(r"\[/mut\]", _MUT_CLOSE, raw, flags=re.I)
    raw = re.sub(r"\[mut\]", _MUT_OPEN, raw, flags=re.I)
    raw = raw.replace("【/突变】", _MUT_CLOSE).replace("【突变】", _MUT_OPEN)
    # 清理未成对残留的 <<< >>>
    raw = re.sub(r"<<+(?![<])|>>+(?!>)", "", raw)
    return _normalize_bare_mutation_brackets(raw)


def _normalize_diff_line(ln: str) -> str:
    s = strip_mutation_markers((ln or "").strip())
    s = re.sub(r"^[-•·]\s*", "", s)
    s = re.sub(r"^【[^】]+】\s*", "", s)
    return re.sub(r"\s+", "", s)


def _line_similar_to_baseline(norm: str, base_norms: Set[str], base_lines: List[str]) -> bool:
    if not norm:
        return True
    if norm in base_norms:
        return True
    from difflib import SequenceMatcher

    for bl in base_lines:
        bn = _normalize_diff_line(bl)
        if bn and SequenceMatcher(None, norm, bn).ratio() >= 0.88:
            return True
    return False


def inject_diff_mutation_markers(variant: str, baseline: str) -> str:
    """无显式标记时，相对基准大纲为新增/改动行注入突变标记。"""
    if not (variant or "").strip() or not (baseline or "").strip():
        return variant
    variant = normalize_mutation_marker_aliases(variant)
    if _MUT_OPEN in variant:
        return variant
    base_lines = [ln for ln in baseline.splitlines() if ln.strip()]
    base_norms = {_normalize_diff_line(ln) for ln in base_lines}
    out: List[str] = []
    for ln in variant.splitlines():
        stripped = ln.strip()
        if not stripped:
            out.append(ln)
            continue
        if stripped.startswith("【") and stripped.endswith("】"):
            out.append(ln)
            continue
        if re.match(r"^#{1,3}\s", stripped):
            out.append(ln)
            continue
        norm = _normalize_diff_line(ln)
        if _line_similar_to_baseline(norm, base_norms, base_lines):
            out.append(ln)
            continue
        bullet_m = re.match(r"^(\s*[-•·]\s*)(.+)$", ln)
        if bullet_m:
            out.append(f"{bullet_m.group(1)}{_MUT_OPEN}{bullet_m.group(2)}{_MUT_CLOSE}")
        else:
            out.append(f"{_MUT_OPEN}{stripped}{_MUT_CLOSE}")
    return "\n".join(out)


def prepare_mutation_display_text(text: str, baseline: str = "") -> str:
    """展示用：规范化标记；必要时按基准大纲 diff 补标。"""
    raw = normalize_mutation_marker_aliases(text or "")
    if _MUT_OPEN not in raw and (baseline or "").strip():
        raw = inject_diff_mutation_markers(raw, baseline)
    return raw


def strip_mutation_markers(text: str) -> str:
    """移除反套路突变标记（含 LLM 误输出的 /mut、\\mut 等），供展示与扩写下游使用。"""
    raw = text or ""
    raw = raw.replace(_MUT_OPEN, "").replace(_MUT_CLOSE, "")
    raw = re.sub(r"⟦/?mut⟧?", "", raw, flags=re.I)
    raw = re.sub(r"(?<![\u4e00-\u9fffA-Za-z])\\?/?mut\b", "", raw, flags=re.I)
    raw = re.sub(r"<<+\s*/?\s*mut\s*>>+", "", raw, flags=re.I)
    raw = re.sub(r"<{2,}|>{2,}", "", raw)
    raw = raw.replace("⟦", "").replace("⟧", "")
    raw = re.sub(r"\s{2,}", " ", raw)
    return raw.strip()


def format_prose_paragraphs(text: str, *, min_para_len: int = 72) -> str:
    """将扩写正文整理为多段落（双换行分隔），提升可读性。"""
    t = (text or "").strip()
    if not t:
        return t
    t = re.sub(r"\r\n?", "\n", t)
    if "\n\n" in t:
        paras = [p.strip() for p in re.split(r"\n{2,}", t) if p.strip()]
        return "\n\n".join(paras)
    if "\n" in t:
        return "\n\n".join(ln.strip() for ln in t.splitlines() if ln.strip())
    sents = re.split(r"(?<=[。！？…])", t)
    sents = [s.strip() for s in sents if s.strip()]
    if len(sents) <= 2:
        return t
    paras: List[str] = []
    buf = ""
    for s in sents:
        buf += s
        if len(buf) >= min_para_len:
            paras.append(buf.strip())
            buf = ""
    if buf.strip():
        if paras and len(buf) < min_para_len // 2:
            paras[-1] = (paras[-1] + buf).strip()
        else:
            paras.append(buf.strip())
    return "\n\n".join(paras) if paras else t


def _split_labeled_plot_clauses(text: str, *, preserve_mutations: bool = False) -> List[str]:
    """将「核心矛盾：…；阻碍：…」或「叙述…因果链：…」拆成多条。"""
    s = (text or "").strip() if preserve_mutations else strip_mutation_markers((text or "").strip())
    if not s:
        return []
    label_pat = (
        r"核心矛盾|主要矛盾|阻碍|障碍|戏剧冲突|冲突点|悬念升级|悬念节点|悬念|"
        r"因果链|关键突变|转折点|高潮点|情节推进|事件顺序|对峙点|"
        r"Core conflict|Obstacle|Dramatic|Suspense|Causal chain"
    )
    parts = re.split(rf"[；;]\s*(?=(?:{label_pat})\s*[：:])", s)
    chunks: List[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if re.search(rf"(?:{label_pat})\s*[：:]", p) and not re.match(rf"^(?:{label_pat})\s*[：:]", p, re.I):
            for lab in ("因果链", "关键突变"):
                if lab in p and re.search(rf"{lab}\s*[：:]", p):
                    sub = re.split(rf"(?={lab}\s*[：:])", p, maxsplit=1)
                    for sp in sub:
                        sp = sp.strip()
                        if sp:
                            chunks.append(sp)
                    break
            else:
                chunks.append(p)
        else:
            chunks.append(p)
    return chunks if chunks else [s]


def expand_plot_conflict_bullets(body: str, *, drop_obstacles: bool = False) -> str:
    """剧情逻辑师 / 冲突设计师：每条分点独占一行。"""
    raw = (body or "").strip()
    if not raw:
        return raw
    bullets: List[str] = []
    for ln in raw.splitlines():
        s = ln.strip().lstrip("-·•").strip()
        if not s:
            continue
        if drop_obstacles and re.match(r"^(阻碍|障碍|角色阻碍|具体阻碍)\s*[：:]", s):
            continue
        for piece in _split_labeled_plot_clauses(s):
            piece = strip_mutation_markers(piece)
            if drop_obstacles and re.match(r"^(阻碍|障碍|角色阻碍|具体阻碍)\s*[：:]", piece):
                continue
            if piece:
                bullets.append(f"- {piece}")
    return "\n".join(bullets) if bullets else raw


def strip_conflict_obstacle_lines(body: str) -> str:
    """冲突设计师：移除「阻碍/障碍」分栏。"""
    return expand_plot_conflict_bullets(body, drop_obstacles=True)


def fragment_to_markdown_bullets(fragment: str, *, preserve_mutations: bool = False) -> str:
    """职能 fragment 转为分行列表（保留换行，不压成一行）。"""
    raw = scrub_functional_fragment(fragment)
    if not raw:
        return "—"
    lines: List[str] = []
    for ln in raw.splitlines():
        ln = re.sub(r"^[-*•·\d一二三四五六七八九十\.、\)\]]+\s*", "", ln.strip())
        if ln and ln not in _KEY_EVENTS_TRIVIAL:
            if re.search(
                r"(?:核心矛盾|阻碍|戏剧冲突|因果链|关键突变|悬念)\s*[：:]",
                ln,
            ):
                lines.extend(_split_labeled_plot_clauses(ln, preserve_mutations=preserve_mutations))
            else:
                lines.append(ln)
    if len(lines) < 2 and re.search(r"\s+-\s+", raw):
        parts = [p.strip() for p in re.split(r"\s+-\s+", raw) if p.strip()]
        if len(parts) >= 2:
            lines = parts
    if not lines:
        one = re.sub(r"\s+", " ", (raw if preserve_mutations else strip_mutation_markers(raw))).strip()
        return f"- {one}" if one else "—"
    if preserve_mutations:
        return "\n".join(f"- {ln}" for ln in lines[:8])
    return "\n".join(f"- {strip_mutation_markers(ln)}" for ln in lines[:8])


def strip_assembly_beat_headers(text: str, beat_heading_word: str) -> str:
    """
    扩写前：去掉小节汇编里的「### 小节 n」类 Markdown 标题行，减少模型照抄进正文。
    beat_heading_word 与界面 T('beat_heading_word') 一致（如「小节」/「Section」）。
    """
    if not (text or "").strip() or not (beat_heading_word or "").strip():
        return (text or "").strip()
    esc = re.escape(beat_heading_word.strip())
    pat = re.compile(rf"^\s*#{{1,6}}\s*(?:\*{{1,2}}\s*)?{esc}\s*\d+(?:\s*\*{{1,2}})?[^\n]*\n?", re.I | re.M)
    t = pat.sub("", text)
    return t.strip()


def split_assembly_into_beats(
    text: str,
    *,
    beat_heading_word: str,
    n: int,
) -> Dict[int, str]:
    """按小节标题切分汇编全文，返回 {beat_index: body}。"""
    raw = strip_mutation_markers((text or "").strip())
    if not raw or n <= 0:
        return {}
    esc = re.escape((beat_heading_word or "").strip())
    patterns = [
        re.compile(
            rf"^#{{1,6}}\s*(?:\*{{1,2}}\s*)?{esc}\s*(\d+)(?:\s*\*{{1,2}})?[^\n]*",
            re.I | re.M,
        ),
        re.compile(r"^【第\s*(\d+)\s*节[^】]*】", re.M),
    ]
    matches: List[Tuple[int, int, int]] = []
    for pat in patterns:
        matches = []
        for m in pat.finditer(raw):
            idx = int(m.group(1)) - 1
            if 0 <= idx < n:
                matches.append((m.start(), m.end(), idx))
        if matches:
            break
    if not matches:
        return {}
    matches.sort(key=lambda x: x[0])
    out: Dict[int, str] = {}
    for i, (_start, end, idx) in enumerate(matches):
        next_start = matches[i + 1][0] if i + 1 < len(matches) else len(raw)
        body = raw[end:next_start].strip()
        if body:
            out[idx] = body
    return out


def sync_assembly_outline_to_beats(
    outline: str,
    beats: List[Optional[Dict[str, Any]]],
    *,
    beat_heading_word: str,
    n: int,
) -> Tuple[str, bool]:
    """
    将反套路/汇编全文写回各小节 merged 字段，并返回带小节标题的汇编文本。
    返回 (assembled_text, beats_updated)。
    """
    cleaned = strip_mutation_markers((outline or "").strip())
    if not cleaned:
        return "", False
    sections = split_assembly_into_beats(
        cleaned, beat_heading_word=beat_heading_word, n=n
    )
    h = (beat_heading_word or "").strip()
    updated = False
    if sections:
        for idx, body in sections.items():
            if idx < 0 or idx >= n or idx >= len(beats):
                continue
            b = beats[idx]
            if not isinstance(b, dict):
                continue
            b = dict(b)
            body = format_functional_merged_outline(body)
            b["merged"] = body
            b["merged_outline"] = body
            if b.get("mode") != "typified":
                b["mode"] = b.get("mode") or "functional"
            beats[idx] = b
            updated = True
        parts: List[str] = []
        for i in range(n):
            b = beats[i]
            if not b:
                continue
            body = (b.get("merged") or b.get("merged_outline") or "").strip()
            if body:
                parts.append(f"### **{h} {i + 1}**\n{body}")
        assembled = "\n\n".join(parts)
        return assembled or cleaned, updated
    if len(beats) == 1 and beats[0] and isinstance(beats[0], dict):
        b = dict(beats[0])
        b["merged"] = cleaned
        b["merged_outline"] = cleaned
        beats[0] = b
        return f"### **{h} 1**\n{cleaned}", True
    return cleaned, False


def scrub_expanded_prose_artifacts(text: str) -> str:
    """
    扩写后：去掉误带入的章节 Markdown 标题、小节编号与相位词行（如「#开端」「### 小节 1」）。
    """
    if not (text or "").strip():
        return ""
    lines = text.splitlines()
    out: list[str] = []
    drop_re = re.compile(
        r"^\s*#+\s*("
        r"小节\s*\d+|第\s*[一二三四五六七八九十百零〇\d]+\s*节|"
        r"Section\s*\d+|"
        r"开端|引入|铺垫|发展|推进|转折|高潮|对峙|收束|"
        r"Opening|Setup|Rising|Turn|Climax|Confrontation|Resolution"
        r")(\b|[·\.\-—\s]|$)",
        re.I,
    )
    bare_section = re.compile(
        r"^\s*(小节|Section)\s*\d+\s*[·\.．]?\s*",
        re.I,
    )
    for line in lines:
        s = line.strip()
        if not s:
            out.append(line if line else "")
            continue
        if drop_re.match(s):
            continue
        if bare_section.match(s) and len(s) < 80:
            continue
        out.append(line)
    return "\n".join(out).strip()


_COPULA_STUCK_ON_NAME = frozenset("是为乃")
_NAME_TRAILING_PARTICLE = frozenset("带进往向到见于的")
_CHAR_NAME_LINE = re.compile(
    r"^[-\s]*([^\s：:\d【】\[\]（）()]{2,12})[：:]",
    re.MULTILINE,
)
_COLON_SPLIT_NAME_SUFFIX = frozenset("丽古娜莎江木提尔克")


def repair_colon_split_name(name: str, desc: str, *, context: str = "") -> Tuple[str, str]:
    """修复「阿依古：丽…」类姓名误拆（阿依古丽等复合名）。"""
    n = (name or "").strip()
    d = (desc or "").strip()
    if not n or not d:
        return n, d
    if _is_protected_compound_name(n):
        return n, d
    ctx = context or ""
    if d[0] not in _COLON_SPLIT_NAME_SUFFIX:
        return n, d
    if not (
        n.startswith(("阿", "艾", "古", "热", "买", "巴", "吾", "陈", "李", "王", "张"))
        or re.fullmatch(r"[\u4e00-\u9fff]{2,3}", n)
    ):
        return n, d
    merged = n + d[0]
    rest = d[1:].lstrip("，,、/ ")
    if (
        not _is_protected_compound_name(n)
        and _is_protected_compound_name(merged)
        and len(merged) == len(n) + 1
        and d[0] in _SCENE_GLUED_ON_NAME
    ):
        return n, d
    if merged in ctx or re.search(re.escape(merged), ctx):
        return merged, rest or d
    if re.fullmatch(r"阿[\u4e00-\u9fff]{2,3}丽", merged):
        return merged, rest or d
    if merged.endswith(tuple(_COLON_SPLIT_NAME_SUFFIX)) and 3 <= len(merged) <= 5:
        if n.startswith(("阿", "艾", "古")) or re.fullmatch(r"[\u4e00-\u9fff]{3,4}", merged):
            return merged, rest or d
    return n, d


_NON_PERSON_LABELS = frozenset(
    {
        "时间",
        "地点",
        "场景",
        "规则",
        "环境",
        "世界",
        "AI",
        "IT",
        "程师",
        "程计划",
        "工程师",
        "计划",
        "地质师",
        "研究员",
        "时间锚点",
        "地点特征",
        "环境细节",
        "世界规则",
        "核心场景",
        "时间地点",
        "地点设定",
        "设定清单",
        "节拍提醒",
        "物理提醒",
        "空间拓展",
        "环境变化",
        "世界物理",
        "场景设定",
        "空间设定",
        "Time anchor",
        "Location",
        "World rules",
        "Environment",
        "Setting",
        "Physical reminder",
        "Space expansion",
        "承接前文",
        "核查",
        "连续性",
        "情节承接",
        "前文承接",
        "衔接说明",
        "对照核查",
        "Prior link",
        "Continuity",
        "Continuity check",
        "Check",
        "高潮点",
        "高潮节点",
        "转折点",
        "情节高潮",
        "Climax",
        "Climax beat",
        "Turning point",
        "核心矛盾",
        "角色阻碍",
        "戏剧冲突",
        "张力点",
        "严谨务",
        "务实",
        "严谨",
        "高潮点",
        "转折点",
        "悬念点",
        "矛盾点",
        "冲突点",
        "节奏点",
        "情节高潮",
        "具体阻碍",
        "悬念",
        "核心冲突",
        "环境细节",
        "时间锚点",
        "地点特征",
        "Core conflict",
        "Character obstacle",
        "Dramatic conflict",
        "两人",
        "三人",
        "他们",
        "她们",
        "大家",
        "照片",
        "旧照",
        "图书",
        "图书馆",
        "黄昏",
        "清晨",
        "午夜",
        "正午",
        "凌晨",
        "傍晚",
        "拂晓",
        "时分",
        "深夜",
        "白天",
        "任务",
        "任务间",
        "安全",
        "紧迫",
        "学术",
        "电脑",
        "地质",
        "毡房",
        "勘探",
        "设备",
        "规则",
        "场景",
        "事项",
        "工作",
        "职责",
        "古代",
        "古代沙",
        "古代沙之",
        "夜晚",
        "黎明",
        "上午",
        "下午",
        "中午",
    }
)
_GEO_SCENE_FALSE_NAME = re.compile(
    r"(古代|现代|当代|未来|异世|沙之|沙漠|王国|国度|学院|绿洲|纪元|时代|文明|异世界|魔法学院|沙之国度)"
)
_SCULPTOR_PLACEHOLDER_DESC = re.compile(
    r"(待在本节|待展开|待补|性格与动机待|动机待|身份待|尚未确定|待定|待写|待补充)"
)
_TIME_SCENE_NON_PERSON = frozenset(
    {
        "黄昏",
        "清晨",
        "午夜",
        "正午",
        "凌晨",
        "傍晚",
        "拂晓",
        "时分",
        "深夜",
        "白天",
        "夜晚",
        "当代",
        "秋季",
        "冬季",
        "夏季",
        "春季",
        "黎明",
        "上午",
        "下午",
        "中午",
    }
)
_JSON_JUNK_LINE = re.compile(
    r"^\s*[-•·]?\s*"
    r"(?:[\{\}\[\],\"]+\s*|"
    r'"(?:fragment|variants|process_feedback|text|outline)"\s*[:,\}\]]?\s*)$',
    re.I,
)
_SCULPTOR_META_PREFIX = re.compile(
    r"^(承接|核查|校验|连续|衔接|对照|备注|说明|提示|注意|补充|回顾|监控|检查|情节|氛围|场景|地点|时间|伏笔|道具|剧情|逻辑|对话|冲突|节奏|世界|环境|物理|空间|设定|提醒|拓展|前文|承接前|高潮|转折|节点)",
)
_SCULPTOR_SECTION_MARKERS = ("人物塑造师", "Character Sculptor")
# 姓名中若含下列片段，多为剧情句误拆（如「李明发起」「旧照片张」）
_VERB_OR_PLOT_IN_NAME = re.compile(
    r"(发起|提议|发现|找到|触发|建议|提出|询问|合作|掉落|翻开|翻找|读取|写下|记录|拍摄|遇见|"
    r"关于|一本|一件|一张|旧照|照片|图书|图书馆|两人|三人|他们|她们|大家|某个|某种|"
    r"首次|再次|随后|然后|最后|开始|结束|进入|离开|对话|冲突|悬念|矛盾|阻碍|"
    r"节|段|幕|场|次|回|章|页|书|本|张|件|个|种|类|型|式|化|性|感|的|了|着|过)"
)
# 剧情节拍误标为「姓名」的常见后缀（李明初到、李明被邀、阿依古丽提…）
_PLOT_BEAT_NAME_SUFFIX = re.compile(
    r"(初到|被邀|被请|被拒|提到|提及|提议|发起|发现|察觉|看见|听见|收到|"
    r"通勤|奔跑|赶回|离开|返回|进入|邀请|带路|找|见|遇|说|问|看|听|拿|举|"
    r"递|停|转|拉|推|敲|开|关|回头|来到|参加|询问|拒绝|展示|试图|随|给|被|"
    r"提|奔|赶|到|邀|请|觉|察|掉|落|读|写|记|拍|翻|开|关|离|返|往|向|于|"
    r"为|谎|修|查|发|揭|改|让|把|将|给|从|在|"
    r"约|抵|追|激|展|示|议|朗|读|打|断|见|到|抵达|约见|"
    r"片|照|馆|店|厅|室|场|区|街|路|市|省|家|"
    r"出现|突然|沉默|首次|犯|却|实|无|用电|回应|坚持|进入|离开|开始|结束)$"
)
_INVALID_NAME_PREFIX = re.compile(
    r"^[但而却且并又也还就才仍若如虽因把被让给从向在以与和对到想]"
)
_VERB_NAME_TAIL = re.compile(
    r"(出现|突然|沉默|首次|犯|却|实|无|用电|回应|坚持|进入|离开|开始|结束|"
    r"激|追|问|说|看|听|走|来|去|地|得|了|着|过|等|后|前|中外|首)$"
)
_SINGLE_CHAR_VERB_TAIL = frozenset(
    "无犯却实说问看听走来去等地得了着过等后前中外首因与时第用制抓止住说面向施触试图觉察"
    "惊认慌怒喜怕抖颤愣呆愣喊叫骂踢砸冲追掏签绑拖挣举撞"
)
_SCULPTOR_GLUED_VERB = frozenset(
    "面向施触试图觉察往到见的地得了着过惊认慌怒喜怕抖颤愣喊叫骂踢砸冲追掏签绑拖挣举撞"
)
_SCENE_GLUED_ON_NAME = frozenset("古国城馆厅室皇朝代纪世疆镇村寺塔堡域油魂")
_BOGUS_NAME_PREFIX = re.compile(r"^(曾是|原来|曾经|如今|以前|当时|当年|其中|作为|一位|一名|一名叫)")
_STANDALONE_ROLE_LABEL = frozenset(
    {"工人", "学生", "导师", "记者", "教授", "祭司", "使者", "工程师", "研究员", "研究生", "馆员", "护林员"}
)
_CN_SURNAMES = (
    "张李王刘陈林赵周马杨黄吴许苏何顾罗郑谢宋唐韩冯于董袁邓曹曾彭蒋蔡余杜叶程魏吕丁沈任姚卢姜崔谭陆汪范金石廖贾夏韦付方邹熊孟秦白江阎薛尹段雷黎史龙陶贺郝龚邵万钱严武戴莫孔向汤"
)
_UYGHUR_NAME_SUFFIX = re.compile(r"(?:买提|古丽|依木|夏木|克力|兰|江|汗|尔|娜|莎|木|提)$")
_STRICT_PERSON_NAME = re.compile(
    rf"^(?:"
    rf"(?:老)?[{_CN_SURNAMES}](?:[\u4e00-\u9fff]{{1,2}}|[\u4e00-\u9fff](?:导师|老师|教授|师傅|工|姐|哥|叔|姨))|"
    rf"阿[\u4e00-\u9fff]{{2,4}}|"
    rf"艾[\u4e00-\u9fff]{{1,3}}|"
    rf"巴[\u4e00-\u9fff]{{1,3}}|"
    rf"古[\u4e00-\u9fff]{{1,2}}|"
    rf"托[\u4e00-\u9fff]{{0,2}}|"
    rf"吾[\u4e00-\u9fff]{{1,4}}|"
    rf"(?:热|穆|哈|卡|赛|吐|买|依|阿|艾)[\u4e00-\u9fff]{{0,2}}(?:买提|古丽|兰|江|汗|克力|依木|夏木|尔|娜|莎|木|提)|"
    rf"[A-Za-z]{{3,16}}"
    rf")$"
)
_EN_NAME_BLOCK = frozenset(
    {"AI", "IT", "OK", "NO", "ID", "UI", "UX", "VR", "AR", "OR", "IF", "TO", "GO", "US", "UK", "EU"}
)
_SETTING_FIELD_LABELS = frozenset(
    {
        "地点",
        "时间",
        "场景",
        "规则",
        "环境",
        "世界",
        "物理",
        "空间",
        "Location",
        "Time",
        "Scene",
        "Rules",
        "Setting",
        "Environment",
    }
)
_SURNAME_SCAN = (
    rf"(?<![\u4e00-\u9fff])(?:老)?[{_CN_SURNAMES}][\u4e00-\u9fff]{{1,2}}"
    rf"(?![师工程员局处室科组队])"
)
_TRAIT_DESC_HINT = re.compile(
    r"(学生|技工|工人|教师|教授|记者|导演|母亲|父亲|女儿|儿子|同事|性格|动机|身份|"
    r"年龄|岁|籍|本地|外地|实习生|负责人|队长|班长|老板|店主|老板娘|导师|"
    r"外祖父|祖父|外祖母|祖母|身世|来历|副队长|钻井|退休|老人|青年|本地|外地|"
    r"好奇|热情|沉默|内向|外向|严谨|伦理|科研|研究|怨恨|漠视|执念|"
    r"Attached|curious|intern|technician|student|mother|daughter)"
)


def _is_setting_field_label(name: str) -> bool:
    n = (name or "").strip()
    return n in _SETTING_FIELD_LABELS or n in _TIME_SCENE_NON_PERSON


_UYGHUR_COMPOUND_NAME = re.compile(
    r"^(?:艾|阿|热|穆|哈|卡|赛|吐|买|依|吾|古|巴|托)[\u4e00-\u9fff]{0,3}(?:买提|古丽|依木|夏木|克力|兰|江|汗|尔|娜|莎|木|提)$"
)


def _is_protected_compound_name(name: str) -> bool:
    """维吾尔/哈萨克式复合名（如艾买提、阿依古丽）不得截断后缀。"""
    n = (name or "").strip()
    return bool(n and (_UYGHUR_COMPOUND_NAME.fullmatch(n) or _UYGHUR_NAME_SUFFIX.search(n) and len(n) >= 3))


def _canonical_person_name(name: str) -> str:
    """将「阿依古丽出现」「但艾尼瓦尔」等规整为真实姓名。"""
    n = _normalize_extracted_name((name or "").strip())
    if not n:
        return ""
    if _is_protected_compound_name(n):
        return n
    for _ in range(4):
        changed = False
        if _INVALID_NAME_PREFIX.match(n):
            n = n[1:]
            changed = True
        for cut in (2, 1):
            if len(n) - cut < 2:
                continue
            base, suf = n[:-cut], n[-cut:]
            if cut == 1 and suf == "提" and base.endswith("买"):
                continue
            if cut == 1 and suf in ("丽", "木", "尔", "兰") and len(base) >= 2:
                if _is_protected_compound_name(n):
                    continue
            tail_hit = (
                (cut == 1 and suf in _SINGLE_CHAR_VERB_TAIL)
                or bool(_VERB_NAME_TAIL.fullmatch(suf))
                or bool(_PLOT_BEAT_NAME_SUFFIX.fullmatch(suf))
            )
            if not tail_hit:
                continue
            if _STRICT_PERSON_NAME.fullmatch(base) and _looks_like_person_name(base):
                if _is_protected_compound_name(n):
                    break
                n = base
                changed = True
                break
        if not changed:
            break
    if len(n) >= 2 and n[-1] in _COPULA_STUCK_ON_NAME:
        base = n[:-1]
        if _STRICT_PERSON_NAME.fullmatch(base) and _looks_like_person_name(base):
            n = base
    if len(n) >= 3 and n[-1] in _NAME_TRAILING_PARTICLE:
        base = n[:-1]
        if _STRICT_PERSON_NAME.fullmatch(base) and _looks_like_person_name(base):
            n = base
    m = re.match(r"^([\u4e00-\u9fff]{2,4})[的对向与和给将把被](?:.+)?$", n)
    if m:
        cand = m.group(1)
        if _STRICT_PERSON_NAME.fullmatch(cand) and _looks_like_person_name(cand):
            n = cand
    if re.fullmatch(r"严谨务|务实.+|.+务$", n) and not _STRICT_PERSON_NAME.fullmatch(n):
        return ""
    return _trim_scene_glued_suffix_from_name(n)


def _trim_scene_glued_suffix_from_name(name: str) -> str:
    """剥离误粘在完整复合名后的场景字（阿依古丽古→阿依古丽，艾买提古→艾买提）。"""
    n = (name or "").strip()
    if not n or _is_protected_compound_name(n) or len(n) < 4:
        return n
    for extra in (2, 1):
        if len(n) <= extra + 2:
            continue
        base = n[:-extra]
        if _is_protected_compound_name(base) and (
            extra == 2 or n[-1] in _SCENE_GLUED_ON_NAME
        ):
            return base
    return n


def _strip_glued_verb_from_name(name: str) -> str:
    """剥离误粘在姓名末尾的动词字（艾买提面→艾买提）。"""
    n = (name or "").strip()
    if not n or _is_protected_compound_name(n):
        return n
    for _ in range(4):
        if len(n) >= 3 and n[-1] in _SCULPTOR_GLUED_VERB:
            base = n[:-1]
            if _is_protected_compound_name(base) or (
                _STRICT_PERSON_NAME.fullmatch(base) and _looks_like_person_name(base)
            ):
                n = base
                continue
        break
    return _trim_scene_glued_suffix_from_name(n)


def _finalize_sculptor_name(name: str, *, context: str = "") -> str:
    """功能化人物行专用：规整姓名，仅向上下文中的完整复合名扩展。"""
    n = _strip_glued_verb_from_name(_normalize_extracted_name((name or "").strip()))
    if not n:
        return ""
    if _BOGUS_NAME_PREFIX.match(n) or n in _STANDALONE_ROLE_LABEL:
        return ""
    ctx = (context or "").strip()
    if ctx:
        best = n
        for m in re.finditer(r"[\u4e00-\u9fff]{2,5}", ctx):
            cand = m.group(0)
            if len(cand) <= len(n) or not cand.startswith(n[: min(2, len(n))]):
                continue
            cand = _strip_glued_verb_from_name(cand)
            if (
                cand
                and _is_protected_compound_name(cand)
                and _STRICT_PERSON_NAME.fullmatch(cand)
                and _looks_like_person_name(cand)
                and len(cand) >= len(best)
            ):
                best = cand
        n = best
    return n if _looks_like_person_name(n) else ""


def _normalize_sculptor_line_name(name: str, *, context: str = "") -> str:
    """人物塑造师展示用姓名：严格规整 + 剧情并列名放宽。"""
    raw = (name or "").strip()
    from narrativeloom.domain.character_names import _is_locked_cast_name, _is_seed_cast_name

    if _is_seed_cast_name(raw, context=context):
        return raw
    fin = _finalize_sculptor_name(raw, context=context)
    if fin:
        return fin
    n = _strip_glued_verb_from_name(raw)
    if not n:
        return ""
    from narrativeloom.domain.character_names import _is_loose_cast_name

    if _is_locked_cast_name(n, context=context):
        return n
    return n if _is_loose_cast_name(n, context=context) else ""


def _is_sculptor_section_title(title: str) -> bool:
    t = (title or "").strip()
    return any(m in t for m in _SCULPTOR_SECTION_MARKERS)


def _looks_like_person_name(name: str) -> bool:
    n = (name or "").strip()
    if not n or n in _NON_PERSON_LABELS:
        return False
    from narrativeloom.domain.character_names import is_false_person_name

    if is_false_person_name(n, context=n):
        return False
    if _GEO_SCENE_FALSE_NAME.search(n):
        return False
    if _is_meta_character_label(n):
        return False
    if n in ("姓名", "人物", "角色", "Name", "Character"):
        return False
    if _BOGUS_NAME_PREFIX.match(n) or n in _STANDALONE_ROLE_LABEL:
        return False
    if re.search(r"^(严谨|务实|状态|动机|性格|身份)", n):
        return False
    if n.endswith("务") and len(n) == 3 and re.search(r"严谨|务实", n):
        return False
    if n in _TIME_SCENE_NON_PERSON or _is_setting_field_label(n):
        return False
    if n.upper() in _EN_NAME_BLOCK or (n.isascii() and len(n) <= 2):
        return False
    if n.endswith("师") and len(n) <= 3:
        return False
    if re.search(r"(工程师|研究员|地质师|技术员|分析师|规划师|设计师)$", n):
        return False
    if _VERB_OR_PLOT_IN_NAME.search(n) and not (
        len(n) <= 3 and _STRICT_PERSON_NAME.match(n)
    ):
        return False
    skip_bits = (
        "锚点",
        "特征",
        "规则",
        "场景",
        "细节",
        "氛围",
        "节拍",
        "设定",
        "地点",
        "时间",
        "环境",
        "世界",
        "提醒",
        "拓展",
        "物理",
        "空间",
        "逻辑",
        "对话",
        "冲突",
        "剧情",
        "道具",
        "伏笔",
        "因果",
        "节奏",
        "承接",
        "核查",
        "校验",
        "前文",
        "连续",
        "衔接",
        "对照",
        "备注",
        "说明",
        "提示",
        "注意",
        "补充",
        "回顾",
        "监控",
        "检查",
        "情节",
        "高潮",
        "节点",
        "转折",
    )
    if any(b in n for b in skip_bits):
        return False
    if re.search(r"(矛盾|阻碍|冲突|悬念|规则|场景|设定|细节|锚点|校验|承接)", n):
        return False
    if re.search(r"(用电|电子|仪器|实验|数据|参数|忌|禁止|违规)", n):
        return False
    if _SCULPTOR_META_PREFIX.match(n):
        return False
    if not _STRICT_PERSON_NAME.match(n):
        return False
    return True


def _is_pure_person_name(name: str) -> bool:
    """严格判定是否为真实人名（排除「李明初到」「阿依古丽出现」类剧情标签）。"""
    n = _normalize_extracted_name((name or "").strip())
    if not n:
        return False
    from narrativeloom.domain.character_names import _is_compound_cast_name

    if _is_compound_cast_name(n):
        return True
    canonical = _canonical_person_name(n)
    if canonical != n:
        return False
    if not _looks_like_person_name(n):
        return False
    if _PLOT_BEAT_NAME_SUFFIX.search(n) and not (
        (_UYGHUR_NAME_SUFFIX.search(n) or re.fullmatch(r"阿[\u4e00-\u9fff]{2,3}丽", n))
        and _STRICT_PERSON_NAME.fullmatch(n)
    ):
        return False
    return bool(_STRICT_PERSON_NAME.fullmatch(n))


def _is_trait_description(description: str) -> bool:
    """人物设定描述（身份/动机），非剧情节拍叙述。"""
    desc = (description or "").strip()
    if not desc:
        return False
    if desc in ("本小节出场人物", "本小节出场角色", "—", "-"):
        return False
    if re.match(r"^本小节出场", desc):
        return False
    if _SCULPTOR_PLACEHOLDER_DESC.search(desc):
        return False
    if _TRAIT_DESC_HINT.search(desc):
        return True
    if re.match(
        r"^(在|他|她|两人|随后|然后|当|把|将|从|向|往|于|初到|被|遭|经|已|正|刚|"
        r"发起|提议|找到|触发|到达|受邀|被邀|看见|听见|提到|提及|邀请)",
        desc,
    ):
        return False
    if re.match(r"^(发现|察觉|找到)", desc):
        if not re.search(r"(外祖父|祖父|外祖母|祖母|父亲|母亲|身世|自己|家族|副队长|队长|身份|原来|竟是)", desc):
            return False
    if re.search(r"(之后|随后|然后|接着|终于|突然|一起|互相|途中|路上|当晚|夜里|清晨)", desc):
        if not _TRAIT_DESC_HINT.search(desc):
            return False
    if _TRAIT_DESC_HINT.search(desc):
        return True
    return len(desc) <= 22 and not re.search(r"(走|跑|来|去|说|问|看|听|拿|找|见|遇|掉|落|读|写)", desc)


def _is_valid_sculptor_person_line(name: str, description: str) -> bool:
    """人物行须为「真实姓名 + 身份/动机」，不得是剧情事件句或设定标签。"""
    n = _canonical_person_name((name or "").strip())
    if _is_setting_field_label(n) or n.upper() in _EN_NAME_BLOCK:
        return False
    from narrativeloom.domain.character_names import _is_seed_cast_name, is_false_person_name

    if is_false_person_name(n, context=f"{n}\n{description}"):
        return False
    if _is_seed_cast_name(n, context=f"{n}\n{description}"):
        desc = (description or "").strip()
        return bool(desc) and len(desc) >= 2
    if not _is_pure_person_name(n):
        return False
    desc = (description or "").strip()
    if not desc:
        return False
    if _VERB_OR_PLOT_IN_NAME.search(n) and not _STRICT_PERSON_NAME.fullmatch(n):
        return False
    if _is_trait_description(desc):
        return True
    if len(desc) <= 40 and not re.match(
        r"^(地点|时间|场景|规则|核心矛盾|阻碍|戏剧冲突|因果链|关键突变)[：:]",
        desc,
    ):
        if not re.fullmatch(r"[\d年月日时分秒\-/\.]+", desc):
            return True
    return False


def filter_character_sculptor_fragment(
    fragment: str,
    *,
    target_total: Optional[int] = None,
    locked_names: Optional[List[str]] = None,
    seed: str = "",
) -> str:
    from narrativeloom.domain.character_names import filter_sculptor_fragment

    return filter_sculptor_fragment(
        fragment,
        target_total=target_total,
        locked_names=locked_names,
        seed=seed,
    )


def _names_from_bullet_lines(text: str) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        m = _CHAR_NAME_LINE.match(line)
        if not m:
            continue
        name = m.group(1).strip()
        name = _normalize_sculptor_line_name(name, context=text)
        if _is_setting_field_label(name):
            continue
        from narrativeloom.domain.character_names import is_false_person_name

        if is_false_person_name(name, context=text):
            continue
        if not _is_pure_person_name(name) or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def extract_character_names_from_text(text: str, *, sculptor_sections_only: bool = False) -> List[str]:
    """Layer 1：仅从结构化 characters / 人物塑造师字段提取，不扫描散文正文。"""
    from narrativeloom.domain.global_character_list import (
        names_from_functional_outline,
        names_from_structured_characters_field,
    )

    raw = (text or "").strip()
    if not raw:
        return []
    if "【" in raw:
        if sculptor_sections_only:
            return names_from_functional_outline(raw)
        return names_from_functional_outline(raw)
    return names_from_structured_characters_field(raw)


def merge_unique_character_names(*name_lists: List[str]) -> List[str]:
    from narrativeloom.domain.character_names import merge_unique_names

    return merge_unique_names(*name_lists)


def ensure_role_blocks_on_own_lines(text: str, role_names: Optional[List[str]] = None) -> str:
    """将行内粘连的【职能名】拆到独立行，便于小节汇编阅读。"""
    raw = (text or "").strip()
    if not raw or "【" not in raw:
        return raw
    aliases = {
        "设定构筑师": "设定构建师",
        "设定建筑师": "设定构建师",
    }
    for src, dst in aliases.items():
        raw = raw.replace(f"【{src}】", f"【{dst}】")
    raw = re.sub(r"([^\n\r])(【[^】]+】)", r"\1\n\2", raw)
    for rn in _known_role_names(role_names):
        raw = re.sub(
            rf"([^\n\r])(?:【)?{re.escape(rn)}(?:】)?\s*[：:]",
            rf"\1\n【{rn}】\n",
            raw,
        )
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def format_functional_merged_outline(text: str, role_names: Optional[List[str]] = None) -> str:
    """规范功能化小节拼合稿：职能标题独立成行，分块之间空行分隔。"""
    raw = ensure_role_blocks_on_own_lines(text, role_names)
    if not raw:
        return ""
    raw = normalize_outline_role_headers(raw, role_names)
    sections = parse_merge_role_sections(raw, role_names=role_names)
    if not sections or sections[0][0] == "【全文】":
        return raw
    return rebuild_merge_sections(sections)


def rebuild_merge_sections(sections: List[Tuple[str, str]]) -> str:
    chunks: List[str] = []
    for title, body in sections:
        b = (body or "").strip()
        chunks.append(f"{title}\n{b}" if b else title)
    return "\n\n".join(chunks)


def assemble_functional_beats_by_role(
    beat_texts: List[str],
    *,
    role_names: Optional[List[str]] = None,
) -> str:
    """功能化多小节汇编：每个人格标题只出现一次，汇总各小节 bullet。"""
    order = _known_role_names(role_names)
    buckets: Dict[str, List[str]] = {rn: [] for rn in order} if order else {}
    extra_order: List[str] = []

    for text in beat_texts:
        if not (text or "").strip():
            continue
        for title, body in parse_merge_role_sections(text, role_names=role_names):
            key = _role_title_key(title)
            if key not in buckets:
                buckets[key] = []
                if key not in extra_order:
                    extra_order.append(key)
            for ln in (body or "").splitlines():
                s = ln.strip()
                if not s:
                    continue
                s = re.sub(r"^[-*•·]+\s*", "", s).strip()
                if s and s not in _KEY_EVENTS_TRIVIAL:
                    buckets[key].append(s)

    if order:
        keys = [k for k in order if buckets.get(k)]
        keys.extend(k for k in extra_order if k not in keys)
    else:
        keys = extra_order or [k for k, v in buckets.items() if v]

    sections: List[Tuple[str, str]] = []
    for key in keys:
        bullets = buckets.get(key) or []
        if not bullets:
            continue
        body = "\n".join(f"- {b}" if not b.startswith("-") else b for b in bullets)
        sections.append((f"【{key}】", body))
    if sections:
        return rebuild_merge_sections(sections)
    return "\n\n".join(t for t in beat_texts if (t or "").strip())


_DEFAULT_FN_ROLE_NAMES = (
    "设定构建师",
    "人物塑造师",
    "剧情逻辑师",
    "冲突设计师",
    "Setting Architect",
    "Character Sculptor",
    "Plot Logician",
    "Conflict Designer",
)


def _known_role_names(role_names: Optional[List[str]] = None) -> List[str]:
    if role_names:
        return [n for n in role_names if (n or "").strip()]
    return list(_DEFAULT_FN_ROLE_NAMES)


def _role_title_key(title: str) -> str:
    return re.sub(r"^[【\[]|[】\]]", "", (title or "").strip()).strip()


def _is_role_header_line(line: str, role_names: Optional[List[str]] = None) -> bool:
    probe = re.sub(r"^[-•·]\s*", "", (line or "").strip())
    if not probe:
        return False
    for rn in _known_role_names(role_names):
        if re.fullmatch(rf"(?:【)?{re.escape(rn)}(?:】)?\s*[：:]?\s*", probe):
            return True
    return False


def normalize_outline_role_headers(text: str, role_names: Optional[List[str]] = None) -> str:
    """将「设定构建师：」等纯文本标题规范为【设定构建师】分块标记。"""
    raw = (text or "").strip()
    if not raw:
        return raw
    names = _known_role_names(role_names)
    if not names:
        return raw
    alt = "|".join(re.escape(n) for n in names)
    out: List[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            out.append("")
            continue
        probe = re.sub(r"^[-•·]\s*", "", stripped)
        m = re.match(rf"^(?:【)?({alt})(?:】)?\s*[：:]\s*(.*)$", probe)
        if m:
            rn = m.group(1)
            rest = (m.group(2) or "").strip()
            out.append(f"【{rn}】")
            if rest:
                out.append(rest if rest.startswith("-") else f"- {rest}")
            continue
        m2 = re.fullmatch(rf"(?:【)?({alt})(?:】)?\s*[：:]?\s*", probe)
        if m2:
            out.append(f"【{m2.group(1)}】")
            continue
        out.append(line)
    return "\n".join(out).strip()


def _find_section_body(staged: List[Tuple[str, str]], role_name: str) -> str:
    for title, body in staged:
        if role_name in title or _role_title_key(title) == role_name:
            return body or ""
    return ""


def _fallback_section_body(role_name: str, staged: List[Tuple[str, str]]) -> str:
    """缺失职能分块时的最小兜底内容。"""
    plot = _find_section_body(staged, "剧情逻辑师") or _find_section_body(staged, "Plot Logician")
    if "冲突" in role_name or "Conflict" in role_name:
        picked: List[str] = []
        for ln in (plot or "").splitlines():
            s = ln.strip().lstrip("-·•").strip()
            if s and re.search(r"(矛盾|阻碍|冲突|张力|对抗|阻力|高潮|阻碍)", s):
                picked.append(s if s.startswith("-") else f"- {s}")
            if len(picked) >= 3:
                break
        if picked:
            return "\n".join(picked)
        return "- 核心矛盾：与本节剧情目标相对立\n- 戏剧冲突：—"
    if "设定" in role_name or "Setting" in role_name:
        return "—"
    if _is_sculptor_section_title(f"【{role_name}】"):
        return "—"
    if "剧情" in role_name or "Plot" in role_name:
        return "—"
    return "—"


def _ordered_unified_sections(
    staged: List[Tuple[str, str]],
    role_names: Optional[List[str]],
) -> List[Tuple[str, str]]:
    """按用户选中的职能顺序输出，并补全缺失分块。"""
    order = _known_role_names(role_names)
    order = [rn for rn in order if not _is_continuity_section_title(f"【{rn}】")]
    if not order:
        return [(t, b) for t, b in staged if not _is_continuity_section_title(t)]
    out: List[Tuple[str, str]] = []
    for rn in order:
        if _is_continuity_section_title(f"【{rn}】"):
            continue
        body = _find_section_body(staged, rn)
        if not (body or "").strip():
            body = _fallback_section_body(rn, staged)
        out.append((f"【{rn}】", body))
    return out


def _orphan_to_bullets(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        one = (text or "").strip()
        return f"- {one}" if one else ""
    out: List[str] = []
    for ln in lines:
        out.append(ln if re.match(r"^[-•·]\s*", ln) else f"- {ln}")
    return "\n".join(out)


def _move_trailing_setting_to_own_section(part: str) -> str:
    """将误挂在上一职能末尾的无标题设定段，拆为【设定构建师】分块。"""
    sections = parse_merge_role_sections(part)
    if not sections or sections[0][0] == "【全文】":
        return part
    last_t, last_b = sections[-1]
    pat = re.compile(
        r"(\n(?:克拉玛依|时间[：:]|场景[：:]|规则[：:]|地点[：:]|\d{4}年)"
        r"[^\n【]*(?:\n(?![【\-])[^\n【]+)*)$",
        re.S,
    )
    m = pat.search(last_b or "")
    if not m:
        return part
    orphan = m.group(1).strip().strip('"')
    last_b = last_b[: m.start()].strip()
    sections[-1] = (last_t, last_b)
    orphan_body = _orphan_to_bullets(orphan)
    has_setting = any("设定构建" in t or "Setting Architect" in t for t, _ in sections)
    if has_setting:
        for i, (t, b) in enumerate(sections):
            if "设定构建" in t or "Setting Architect" in t:
                sections[i] = (t, f"{b}\n{orphan_body}".strip())
                break
    else:
        sections.insert(0, ("【设定构建师】", orphan_body))
    return rebuild_merge_sections(sections)


def _prepend_orphan_setting_to_part(part: str) -> str:
    """后续方案若开头有无标题设定段，补【设定构建师】。"""
    raw = (part or "").strip()
    if not raw or raw.startswith("【"):
        return _move_trailing_setting_to_own_section(raw)
    m = re.match(r"^((?:克拉玛依|时间[：:]|场景[：:]|规则[：:]|地点[：:]|\d{4}年)[^\n【]+(?:\n(?![【])[^\n【]+)*)\s*(?=【)", raw, re.S)
    if m:
        orphan = _orphan_to_bullets(m.group(1).strip())
        rest = raw[m.end() :].lstrip()
        raw = f"【设定构建师】\n{orphan}\n\n{rest}" if rest else f"【设定构建师】\n{orphan}"
    return _move_trailing_setting_to_own_section(raw)


def split_concatenated_unified_plans(
    text: str,
    role_names: Optional[List[str]] = None,
    *,
    max_plans: int = 6,
) -> List[str]:
    """若多个总体方案被模型拼进同一 outline，按重复出现的职能标题拆成多份。"""
    raw = strip_trailing_json_leak(unescape_display_text(text)).strip().strip('"')
    if not raw:
        return []
    markers: List[str] = []
    for n in role_names or []:
        if n:
            markers.append(f"【{n}】")
    for m in ("【设定构建师】", "【人物塑造师】", "【剧情逻辑师】", "【冲突设计师】"):
        if m not in markers:
            markers.append(m)
    split_at = ""
    best_count = 0
    for m in markers:
        cnt = raw.count(m)
        if cnt > best_count:
            best_count = cnt
            split_at = m
    if best_count <= 1 or not split_at:
        return [_prepend_orphan_setting_to_part(raw)]
    parts = [p.strip().strip('"') for p in re.split(rf"(?={re.escape(split_at)})", raw) if p.strip()]
    fixed: List[str] = []
    for i, part in enumerate(parts):
        part = _prepend_orphan_setting_to_part(part) if i > 0 else _move_trailing_setting_to_own_section(part)
        fixed.append(part)
    return fixed[:max_plans]


def _strip_role_header_lines_from_body(body: str, role_names: Optional[List[str]] = None) -> str:
    kept: List[str] = []
    for ln in (body or "").splitlines():
        if _is_role_header_line(ln, role_names):
            continue
        kept.append(ln)
    return "\n".join(kept).strip()


def trim_section_body_leak(body: str) -> str:
    """截断误嵌入下一职能/下一方案的正文。"""
    body = (body or "").strip().strip('"')
    if not body:
        return body
    m = re.search(r"【[^】]+】", body)
    if m and m.start() > 0:
        body = body[: m.start()].strip()
    plain = re.search(
        r"(?:^|\n)(?:[-•·]\s*)?(?:【)?(?:设定构建师|人物塑造师|剧情逻辑师|冲突设计师|"
        r"Setting Architect|Character Sculptor|Plot Logician|Conflict Designer)(?:】)?\s*[：:]",
        body,
    )
    if plain and plain.start() > 0:
        body = body[: plain.start()].strip()
    pat = re.compile(
        r"(\n(?:克拉玛依|时间[：:]|场景[：:]|规则[：:]|地点[：:]|\d{4}年)"
        r"[^\n【]*(?:\n(?![【\-])[^\n【]+)*)$",
        re.S,
    )
    hit = pat.search(body)
    if hit:
        body = body[: hit.start()].strip()
    return body.rstrip('"').strip()


def _normalize_extracted_name(name: str) -> str:
    n = (name or "").strip()
    for prefix in ("导师", "老师", "师傅", "老板", "店主"):
        if n.startswith(prefix) and len(n) > len(prefix) + 1:
            n = n[len(prefix) :]
    for suf in ("教授", "老师", "师傅", "导师", "工程师", "同学", "学生", "新生", "青年", "少年", "少女"):
        if n.endswith(suf) and len(n) > len(suf) + 1:
            n = n[: -len(suf)]
    for suf in ("家", "的", "与", "和", "在旁", "旁边", "一旁"):
        if n.endswith(suf) and len(n) > len(suf) + 1:
            cand = n[: -len(suf)]
            if _STRICT_PERSON_NAME.fullmatch(cand):
                n = cand
    for sep in ("对", "向", "与", "和", "给", "把", "将", "被"):
        idx = n.find(sep, 2)
        if 2 <= idx <= 5:
            cand = n[:idx]
            if _STRICT_PERSON_NAME.fullmatch(cand) and _looks_like_person_name(cand):
                n = cand
                break
    return n


def extract_relation_names(text: str) -> List[str]:
    """从「X的姐姐/导师/同事…」等表述中提取关联人物名。"""
    raw = (text or "").strip()
    if not raw:
        return []
    found: List[str] = []
    for m in re.finditer(
        r"([\u4e00-\u9fff]{2,5})的(?:姐姐|哥哥|弟弟|妹妹|父亲|母亲|儿子|女儿|导师|同事|老板|同伴|朋友|邻居|丈夫|妻子|师父|徒弟|表哥|表姐|表弟|表妹)",
        raw,
    ):
        name = m.group(1).strip()
        if _is_pure_person_name(name) and name not in found:
            found.append(name)
    return found


def _merge_name_fragments(names: List[str], context: str) -> List[str]:
    """去掉「哈尔/吾尔」等被更长姓名（如巴哈尔）覆盖的碎片。"""
    ctx = context or ""
    kept: List[str] = []
    for n in names:
        if not _is_pure_person_name(n):
            continue
        if any(
            other != n and len(other) > len(n) and n in other and other in ctx
            for other in names
        ):
            continue
        if n not in kept:
            kept.append(n)
    return kept


def _scan_plot_name_candidates(text: str, *, limit: int = 8) -> List[str]:
    """按剧情出现频次扫描候选姓名（兜底，补全提取规则漏掉的人名）。"""
    raw = text or ""
    if not raw:
        return []
    counts: Dict[str, int] = {}
    scan_patterns = [
        _SURNAME_SCAN,
        r"(?<![\u4e00-\u9fff])阿[\u4e00-\u9fff]{2,4}(?![师工程员])",
        r"(?<![\u4e00-\u9fff])艾[\u4e00-\u9fff]{1,3}(?![师工程员])",
        r"(?<![\u4e00-\u9fff])巴[\u4e00-\u9fff]{1,3}(?![师工程员])",
        r"(?<![\u4e00-\u9fff])托[\u4e00-\u9fff]{0,2}(?![师工程员])",
        r"(?<![\u4e00-\u9fff])吾[\u4e00-\u9fff]{1,4}(?![师工程员])",
        r"(?<![\u4e00-\u9fff])(?:热|穆|哈|卡|赛|吐|买|依|阿|艾)[\u4e00-\u9fff]{0,2}(?:买提|古丽|兰|江|汗|克力|依木|夏木|尔|娜|莎|木|提)(?![师工程员])",
    ]
    for pat in scan_patterns:
        for m in re.finditer(pat, raw):
            n = _canonical_person_name(m.group(0))
            from narrativeloom.domain.character_names import is_false_person_name

            if n and _is_pure_person_name(n) and not is_false_person_name(n, context=raw):
                counts[n] = counts.get(n, 0) + len(re.findall(re.escape(n), raw))
    ranked = sorted(counts.keys(), key=lambda n: (-counts[n], -len(n), n))
    return _coalesce_person_names(ranked)[:limit]


def _rank_names_by_plot_mentions(names: List[str], plot_text: str) -> List[str]:
    """按剧情出现频次排序，优先保留核心角色。"""
    plot = plot_text or ""

    def score(n: str) -> int:
        return len(re.findall(re.escape(n), plot))

    return sorted(names, key=lambda n: (-score(n), -len(n), names.index(n)))


def _coalesce_person_names(names: List[str]) -> List[str]:
    """合并「王导/王导师」「张阳/张阳谎」等提取重复，保留更完整姓名（维持原顺序）。"""
    kept: List[str] = []
    for n in names:
        if not _is_pure_person_name(n):
            continue
        if any(k.startswith(n) and len(k) > len(n) for k in kept):
            continue
        kept = [k for k in kept if not (n.startswith(k) and len(n) > len(k))]
        if n not in kept:
            kept.append(n)
    return kept


def extract_names_from_narrative(text: str, *, limit: int = 6) -> List[str]:
    """从剧情叙述句中启发式提取人物姓名。"""
    raw = (text or "").strip()
    if not raw:
        return []

    def _keep(name: str, found: List[str]) -> None:
        from narrativeloom.domain.character_names import is_false_person_name

        n = _canonical_person_name(name)
        if not n or not _STRICT_PERSON_NAME.fullmatch(n) or not _is_pure_person_name(n):
            return
        if is_false_person_name(n, context=raw):
            return
        if n not in found:
            found.append(n)

    found: List[str] = []
    name_before_verb = (
        rf"((?:{_SURNAME_SCAN})|"
        rf"(?<![\u4e00-\u9fff])阿[\u4e00-\u9fff]{{2,4}}|"
        rf"(?<![\u4e00-\u9fff])艾[\u4e00-\u9fff]{{1,3}}|"
        rf"(?<![\u4e00-\u9fff])巴[\u4e00-\u9fff]{{1,3}}|"
        rf"(?<![\u4e00-\u9fff])托[\u4e00-\u9fff]{{0,2}}|"
        rf"(?<![\u4e00-\u9fff])吾[\u4e00-\u9fff]{{1,4}}|"
        rf"(?<![\u4e00-\u9fff])(?:热|穆|哈|卡|赛|吐|买|依|阿|艾)[\u4e00-\u9fff]{{0,2}}(?:买提|古丽|兰|江|汗|克力|依木|夏木|尔|娜|莎|木|提))"
    )
    _VERB_BOUNDARY = (
        r"抵达|约见|追问|展示|提议|朗读|打断|发现|邀请|赶到|来到|进入|离开|返回|出现|沉默|突然|"
        r"犯|却|实|无|首|翻|墙|贿|赂|等|用|找|看见|拍照|制止|抓住|喝|醉|挖|埋|提到|听|送|拿|"
        r"给|说|问|看|听|认|出|揭示|逼|听完|察觉|误入|被|将|把|让|向|在|从|改|写|查|揭|谎|赶|"
        r"站|走|答|拿|举|递|停|转|拉|推|敲|开|关|发|端|沉|默|后|旁|抓|完|觉|非|开|放|区|域"
    )
    patterns = [
        r"(?<![\u4e00-\u9fff])托[\u4e00-\u9fff]{0,2}(?=[的与和，,。；\s\-·协助帮助]|$|(?:协助|帮助|展示|出现|提议|进入|离开|为|将|把|让|被|给|说|问|看|听))",
        r"(?<![\u4e00-\u9fff])巴[\u4e00-\u9fff]{1,3}(?=[的与和，,。；\s\-·]|$|(?:展示|出现|提议|端上|交谈|进入|离开|返回|为|将|把|让|被|给|说|问|看|听|拿|举|递|停|转|拉|推|敲|开|关|发|犯|却|实|无|首|激|追|地|得|了|着|过|因|时))",
        r"(?<![\u4e00-\u9fff])阿[\u4e00-\u9fff]{2,4}(?=[的与和，,。；\s\-·]|$|(?:展示|出现|提议|沉默|突然|抵达|约见|追问|朗读|打断|发现|邀请|赶到|来到|进入|离开|返回|为|将|把|让|被|给|向|在|从|改|写|查|揭|谎|赶|说|问|答|看|听|拿|举|递|停|转|拉|推|敲|开|关|发|犯|却|实|无|首|激|追|地|得|了|着|过|因|时|带))",
        r"(?<![\u4e00-\u9fff])吾[\u4e00-\u9fff]{1,4}(?=[的与和，,。；\s\-·]|$|(?:展示|出现|提议|端上|交谈|进入|离开|返回|为|将|把|让|被|给|说|问|看|听|拿|举|递|停|转|拉|推|敲|开|关|发|犯|却|实|无|首|激|追|地|得|了|着|过|因|时|在|旁))",
        r"(?<![\u4e00-\u9fff])艾[\u4e00-\u9fff]{1,3}(?=[的与和，,。；\s\-·]|$|(?:展示|出现|提议|沉默|突然|抵达|约见|追问|朗读|打断|发现|邀请|赶到|来到|进入|离开|返回|为|将|把|让|被|给|向|在|从|改|写|查|揭|谎|赶|说|问|答|看|听|拿|举|递|停|转|拉|推|敲|开|关|发|犯|却|实|无|首|激|追|地|得|了|着|过|因|时))",
        rf"{name_before_verb}(?:{_VERB_BOUNDARY})",
        rf"(?:约见|遇见|见到|拜访|探访|称呼|唤作){name_before_verb}",
        r"(?<![\u4e00-\u9fff])([\u4e00-\u9fff]{2,4}(?:教授|老师|师傅|导师|记者|学生|学员|同事|同学|班长|护林|经理|馆员|主任|新生|青年|少女|少年|男子|女子|大爷|大姐|大哥))(?![师工程员])",
        rf"({_SURNAME_SCAN})(?=[的与和，,。；\s\-·]|$|(?:{_VERB_BOUNDARY}))",
        r"(?<![\u4e00-\u9fff])((?:热|穆|哈|卡|赛|吐|吾|买|依|阿|艾)[\u4e00-\u9fff]{0,2}(?:买提|古丽|兰|江|汗|克力|依木|夏木|尔|娜|莎|木|提))",
        r"(?:与|和|对|向|见|遇|叫|名为|名叫|称呼|唤作)\s*([\u4e00-\u9fff]{2,6})",
        rf"{name_before_verb}(?:为|将|把|让|被|给|向|在|从|改|写|查|揭|谎|赶|{_VERB_BOUNDARY})",
    ]
    for pat in patterns:
        for m in re.finditer(pat, raw):
            g = m.group(1) if m.lastindex else m.group(0)
            _keep(g, found)
            if len(found) >= limit:
                break
        if len(found) >= limit:
            break
    for n in _scan_plot_name_candidates(raw, limit=limit):
        _keep(n, found)
        if len(found) >= limit:
            break
    for n in _names_from_bullet_lines(raw):
        _keep(n, found)
        if len(found) >= limit:
            break
    for n in extract_relation_names(raw):
        _keep(n, found)
        if len(found) >= limit:
            break
    return _coalesce_person_names(found)[:limit]


def _sculptor_line_by_name(body: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for line in (body or "").splitlines():
        s = line.strip()
        if not s or s in ("—", "-"):
            continue
        probe = s if re.match(r"^[-•·]\s*", s) else f"- {s}"
        m = _CHAR_NAME_LINE.match(probe)
        if not m:
            continue
        name = m.group(1).strip()
        rest = probe[m.end() :].strip()
        if not _is_valid_sculptor_person_line(name, rest):
            continue
        out[name] = s if re.match(r"^[-•·]\s*", s) else f"- {s}"
    return out


def _infer_sculptor_trait(name: str, plot_text: str, setting_text: str = "") -> str:
    """从剧情/设定上下文推断一句短身份，禁止「本小节出场」类占位。"""
    ctx = f"{plot_text}\n{setting_text}".strip()
    if not ctx:
        return f"- {name}：关键剧情人物"

    role_words = (
        "导师",
        "记者",
        "学生",
        "研究生",
        "助手",
        "店主",
        "老板",
        "厨师",
        "青年",
        "女子",
        "男子",
        "同事",
        "护工",
        "师傅",
        "技工",
        "实习生",
        "实验员",
        "馆员",
        "商贩",
        "商人",
        "退休",
        "工人",
    )
    for role in role_words:
        if re.search(
            rf"(?:{re.escape(name)}[^，。；\n]{{0,12}}{role}|{role}[^，。；\n]{{0,12}}{re.escape(name)})",
            ctx,
        ):
            return f"- {name}：{role}"

    for sent in re.split(r"[。；!\?\n]", ctx):
        s = sent.strip().lstrip("-·•").strip()
        if name not in s or len(s) <= len(name) + 1:
            continue
        tail = re.split(rf"{re.escape(name)}", s, maxsplit=1)[-1].strip("，,：: 是")
        if not tail:
            continue
        if re.search(
            r"(进|入|来|到|端|说|问|追|进入|离开|返回|第一次|首次|随后|然后|接着|端上|好奇|沉默|回答|交谈|"
            r"抓住|认出|揭示|逼|听完|察觉|误入|的非|开放|区域|的茶馆|的|用|啤酒|贿赂|翻墙|等|找|看见|喝醉|挖|埋|"
            r"教她|教她弹|聊起|记录|发现|同意|带|去)",
            tail,
        ):
            continue
        if re.match(r"^[的地得与和用]", tail):
            continue
        if re.match(r"^(必须|应当|需要|不得不|面临|陷入|争执|抉择|对峙|冲突|悬念)", tail):
            continue
        if _is_trait_description(tail):
            snippet = tail if len(tail) <= 120 else tail[:120]
            return f"- {name}：{snippet}"
        tail = re.sub(r"^(第一次|首次|随后|然后|接着|因|却|但|而|与|和|在|被|把|将|是)", "", tail).strip()
        if 2 <= len(tail) <= 120 and not re.search(
            r"(之后|随后|然后|接着|终于|突然|进|入|来|到|端|说|问|用|贿|啤酒|酒|翻|墙|等|找|看|听|挖|埋)",
            tail,
        ):
            return f"- {name}：{tail}"

    setting = setting_text or ""
    plot = plot_text or ""
    if re.search(r"(市场|摊位|手工艺|乐器|丝绸|商贩)", setting):
        if re.search(rf"{re.escape(name)}", plot) and re.search(r"(教|弹|琴|迁徙|家族)", plot):
            return f"- {name}：外地访学者，对民族手工艺好奇"
        return f"- {name}：集市从业者，熟稔本地风物"
    if re.search(r"(纪念馆|老年|活动中心|老油|退休|口述)", setting):
        if re.search(rf"{re.escape(name)}", plot) and re.search(r"(退休|钻井|笔记|老)", plot):
            return f"- {name}：退休石油工人，健谈怀旧"
        return f"- {name}：外地来访者，做田野记录"
    if re.search(r"(实验室|校园|大学|研究生|仪器)", setting):
        return f"- {name}：青年研究者，追问细节"
    if re.search(rf"{re.escape(name)}", plot):
        if re.search(r"(记者|采访|报道|非虚构)", ctx):
            return f"- {name}：外地记者，刨根问底"
        if re.search(
            rf"{re.escape(name)}[^，。；\n]{{0,12}}(进入|闯入|来访|第一次|首次|来到|误入)",
            plot,
        ):
            return f"- {name}：外来访客，初识本地"
    return f"- {name}：关键剧情人物，动机与性格须在本小节行动中体现"


def _sculptor_line_needs_rewrite(name: str, description: str) -> bool:
    desc = (description or "").strip()
    if _is_meta_character_label(name):
        return True
    if not desc or re.search(r"本小节出场", desc):
        return True
    if re.search(r"与本节冲突相关", desc):
        return True
    if name != _canonical_person_name(name):
        return True
    if not _is_valid_sculptor_person_line(name, desc):
        return True
    return False


def _polish_sculptor_line(
    line: str,
    *,
    plot_text: str,
    setting_text: str = "",
) -> str:
    s = (line or "").strip()
    if not s:
        return ""
    probe = s if re.match(r"^[-•·]\s*", s) else f"- {s}"
    m = _CHAR_NAME_LINE.match(probe)
    if not m:
        return s if re.match(r"^[-•·]\s*", s) else f"- {s}"
    ctx = "\n".join(x for x in (plot_text, setting_text) if x)
    from narrativeloom.utils.display_utils import _normalize_sculptor_line_name

    name = _normalize_sculptor_line_name(m.group(1).strip(), context=ctx)
    rest = probe[m.end() :].strip()
    if not name or not _is_pure_person_name(name):
        return ""
    if _sculptor_line_needs_rewrite(name, rest):
        return _infer_sculptor_trait(name, plot_text, setting_text)
    return f"- {name}：{rest}"


def _brief_sculptor_line(name: str, plot_text: str, setting_text: str = "") -> str:
    """为剧情中出场但缺设定行的人物生成一句短身份。"""
    return _infer_sculptor_trait(name, plot_text, setting_text)


def _plot_narrative_for_cast(sources: List[str]) -> str:
    """职能合并稿中用于识别人物的叙事片段（排除冲突/元叙事块）。"""
    chunks: List[str] = []
    for s in sources or []:
        t = (s or "").strip()
        if not t:
            continue
        if re.search(r"核心矛盾|戏剧冲突|核心冲突|悬念|dramatic conflict|core conflict", t, re.I):
            continue
        chunks.append(t)
    return "\n".join(chunks)


def complete_sculptor_body(
    body: str,
    *,
    plot_sources: List[str],
    setting_sources: Optional[List[str]] = None,
    locked_names: Optional[List[str]] = None,
    sculpt_target: int = 2,
    seed: str = "",
    prior_character_profiles: Optional[Dict[str, str]] = None,
    global_cast_names: Optional[List[str]] = None,
) -> str:
    plot = list(plot_sources or [])
    plot_blob = _plot_narrative_for_cast(plot)
    setting_blob = "\n".join(s for s in (setting_sources or []) if (s or "").strip())
    prior_block = ""
    if prior_character_profiles:
        prior_block = "\n".join(
            f"- {k}：{v}" for k, v in prior_character_profiles.items() if k and v
        )
    out = sanitize_typified_characters(
        body,
        target=sculpt_target,
        locked_names=locked_names,
        seed=seed,
        setting=setting_blob,
        key_events=plot_blob,
        prior_characters_block=prior_block,
        strict_narrative_allowlist=True,
        global_cast_names=global_cast_names,
    )
    return scrub_functional_fragment(out)


_META_NAME_SUFFIX = re.compile(r"^(张力|高潮|转折|悬念|矛盾|冲突|节奏|戏剧|核心|情节|剧情|伏笔|主题)点$")
_ABSTRACT_THEME_SUFFIX = re.compile(
    r"(构图|现实|逻辑|法则|隐喻|象征|主题|命运|救赎|理想|生存|神圣|矛盾|冲突|张力|悬念|伏笔|情节|剧情|车间|时段)$"
)


def _is_meta_character_label(name: str) -> bool:
    n = (name or "").strip()
    if not n:
        return True
    if n in _NON_PERSON_LABELS:
        return True
    if n.endswith("计划") and len(n) <= 5:
        return True
    if _META_NAME_SUFFIX.match(n):
        return True
    if _ABSTRACT_THEME_SUFFIX.search(n):
        return True
    if re.match(r"^(神圣|生存|理想|现实|构图|逻辑|主题|命运|车间|清理|修理|理车|核心|戏剧|情节|剧情)", n):
        return True
    if re.match(r"^(核心|角色|戏剧|情节|剧情)?(矛盾|冲突|阻碍|张力)$", n):
        return True
    if re.search(r"(与本节|关键人物|出场人物|剧情角色)", n):
        return True
    return False


def format_setting_architect_body(body: str) -> str:
    """设定构建师：地点与时间分行展示。"""
    out_lines: List[str] = []
    for ln in (body or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        probe = re.sub(r"^[-•·]\s*", "", s)
        m = re.match(
            r"^地点[：:]\s*(.+?)(?:[，,；;]\s*|\s+)时间[：:]\s*(.+)$",
            probe,
        )
        if m:
            out_lines.append(f"- 地点：{m.group(1).strip().rstrip('，,；;')}")
            out_lines.append(f"- 时间：{m.group(2).strip()}")
            continue
        if probe.startswith("地点") and re.search(r"时间[：:]", probe):
            loc_m = re.match(r"^地点[：:]\s*(.+)$", probe)
            if loc_m:
                rest = loc_m.group(1)
                t_parts = re.split(r"[，,；;]\s*时间[：:]", rest, maxsplit=1)
                if len(t_parts) == 2:
                    out_lines.append(f"- 地点：{t_parts[0].strip().rstrip('，,；;')}")
                    out_lines.append(f"- 时间：{t_parts[1].strip()}")
                    continue
        out_lines.append(s if re.match(r"^[-•·]\s*", s) else f"- {probe}")
    return "\n".join(out_lines)


def fn_outline_homogeneity_snippet(outline: str, *, max_chars: int = 220) -> str:
    """提取已定方案摘要以抑制后续小节同质化。"""
    txt = normalize_outline_role_headers((outline or "").strip(), None)
    if not txt:
        return ""
    sections = parse_merge_role_sections(txt)
    bits: List[str] = []
    for title, body in sections:
        label = re.sub(r"^[【\[]|[】\]]", "", title).strip()
        if any(k in label for k in ("设定构建", "人物塑造", "冲突设计", "Setting", "Sculptor", "Conflict")):
            one = " ".join(
                ln.strip().lstrip("-·•") for ln in (body or "").splitlines() if ln.strip()
            )[:80]
            if one:
                bits.append(f"{label}：{one}")
    snip = "；".join(bits)
    return snip[:max_chars] if snip else txt.replace("\n", " ")[:max_chars]


def build_fn_prior_homogeneity_digest(outlines: List[str]) -> str:
    lines: List[str] = []
    for i, o in enumerate(outlines):
        sn = fn_outline_homogeneity_snippet(o)
        if sn:
            lines.append(f"- 小节{i + 1}：{sn}")
    return "\n".join(lines)


def abbreviate_established_sections(
    body: str,
    *,
    title: str,
    beat_index: int,
    locked_names: Optional[List[str]] = None,
) -> str:
    """后续小节：已知设定/已定人物仅保留变化，避免方案越写越长。"""
    if beat_index <= 0 or not (body or "").strip():
        return body
    locked = [n.strip() for n in (locked_names or []) if (n or "").strip()]
    if "设定构建" in title or "Setting" in title:
        out: List[str] = []
        for ln in body.splitlines():
            s = ln.strip().lstrip("-·•").strip()
            if not s:
                continue
            for lab in ("地点", "时间", "场景", "规则", "Location", "Time", "Scene", "Rules"):
                if s.startswith(f"{lab}：") or s.startswith(f"{lab}:"):
                    val = s.split("：", 1)[-1].split(":", 1)[-1].strip()
                    if len(val) > 36:
                        s = f"{lab}：{val[:36]}"
                    break
            out.append(s if s.startswith("-") else f"- {s}")
        return "\n".join(out)
    if _is_sculptor_section_title(title) and locked:
        out = []
        for ln in body.splitlines():
            probe = ln.strip()
            if not probe:
                continue
            m = _CHAR_NAME_LINE.match(probe if probe.startswith("-") else f"- {probe}")
            if not m:
                out.append(probe)
                continue
            name = _canonical_person_name(m.group(1).strip())
            desc = probe.split("：", 1)[-1].split(":", 1)[-1].strip()
            if name in locked and len(desc) > 44:
                brief = ""
                for pat in (
                    r"当前状态[：:为]?([^；;，,]+)",
                    r"本章[^；;，,。]+",
                    r"状态[：:为]?([^；;，,]+)",
                ):
                    sm = re.search(pat, desc)
                    if sm:
                        brief = sm.group(0).strip()
                        break
                if not brief:
                    segs = [x.strip() for x in re.split(r"[，,；;]", desc) if x.strip()]
                    brief = segs[-1] if segs else desc[:44]
                out.append(f"- {name}：{brief}")
            else:
                out.append(probe if probe.startswith("-") else f"- {name}：{desc}")
        return "\n".join(out)
    return body


def _condense_character_line(s: str, max_chars: int) -> str:
    """压缩人物行时只截断描述，保留完整姓名。"""
    probe = s.strip()
    if "：" in probe or ":" in probe:
        probe = probe.replace(":", "：")
        name, _, desc = probe.partition("：")
        name = name.strip()
        desc = desc.strip()
        if name and desc:
            budget = max(8, max_chars - len(name) - 1)
            if len(desc) > budget:
                desc = desc[:budget]
            return f"{name}：{desc}"
    if len(probe) > max_chars:
        return probe[:max_chars]
    return probe


def condense_role_body(
    body: str,
    *,
    max_lines: int = 8,
    max_chars: int = 160,
    truncate: bool = False,
) -> str:
    """整理职能分块为 bullet 列表；默认保留完整句子，不追加省略号。"""
    raw = (body or "").strip()
    if not raw:
        return raw
    out: List[str] = []
    for ln in raw.splitlines():
        s = ln.strip().lstrip("-·•").strip()
        if not s or s in _KEY_EVENTS_TRIVIAL:
            continue
        if truncate and len(s) > max_chars:
            s = s[: max_chars - 1] + "…"
        elif len(s) > max_chars:
            s = _condense_character_line(s, max_chars)
        out.append(f"- {s}")
        if len(out) >= max_lines:
            break
    return "\n".join(out) if out else raw


def _looks_like_story_outline(text: str) -> bool:
    """多小节汇编/反套路全文，而非【职能】分块稿。"""
    t = (text or "").strip()
    if not t:
        return False
    if re.search(r"^#{1,3}\s", t, re.M):
        return True
    if re.search(r"【第\s*\d+", t):
        return True
    role_blocks = sum(1 for m in ("【设定构建师】", "【人物塑造师】", "【剧情逻辑师】") if m in t)
    if role_blocks == 0 and len(t) > 280 and re.search(r"(小节|节拍|Beat\s+\d)", t, re.I):
        return True
    return False


def normalize_single_unified_outline(
    text: str,
    *,
    role_names: Optional[List[str]] = None,
    lang: str = "zh",
    locked_names: Optional[List[str]] = None,
    character_target_total: Optional[int] = None,
    beat_index: int = 0,
    seed: str = "",
    prior_character_profiles: Optional[Dict[str, str]] = None,
    global_cast_names: Optional[List[str]] = None,
) -> str:
    """清洗单份总体方案：截断杂糅、补全人物塑造师、规范分块。"""
    txt = scrub_functional_fragment(strip_trailing_json_leak(unescape_display_text(text)))
    if not txt:
        return ""
    if _looks_like_story_outline(txt):
        return txt.strip()
    txt = ensure_role_blocks_on_own_lines(txt, role_names)
    txt = normalize_outline_role_headers(txt, role_names)
    sections = parse_merge_role_sections(txt, role_names=role_names)
    if not sections or sections[0][0] == "【全文】":
        if _looks_like_story_outline(txt):
            return txt.strip()
        txt = normalize_outline_role_headers(txt, role_names)
        if role_names and "【" not in txt:
            sections = [(f"【{rn}】", "") for rn in role_names]
        else:
            return txt
    from narrativeloom.domain.character_names import extract_seed_cast_names, merge_unique_names

    locked = merge_unique_names(
        [n.strip() for n in (locked_names or []) if (n or "").strip()],
        extract_seed_cast_names(seed),
    )
    sculpt_target = character_target_total if character_target_total is not None else max(2, len(locked))
    setting_cap = 36 if beat_index > 0 else 44
    plot_cap = 48
    plot_sources: List[str] = []
    narrative_sources: List[str] = []
    setting_sources: List[str] = []
    staged: List[Tuple[str, str]] = []
    for title, body in sections:
        if _is_continuity_section_title(title):
            continue
        body = trim_section_body_leak(body)
        body = _strip_role_header_lines_from_body(body, role_names)
        staged.append((title, body))
        if "剧情逻辑" in title or "Plot Logician" in title:
            plot_sources.append(body)
        elif "设定构建" in title or "Setting" in title:
            setting_sources.append(body)
        else:
            narrative_sources.append(body)
    if not narrative_sources:
        narrative_sources = list(plot_sources)
    all_narrative = list(plot_sources) + list(narrative_sources)
    sculptor_context_sources = [
        b
        for t, b in staged
        if not _is_sculptor_section_title(t)
        and "设定构建" not in t
        and "Setting Architect" not in t
        and (b or "").strip()
    ]
    processed: List[Tuple[str, str]] = []
    for title, body in staged:
        if _is_continuity_section_title(title):
            continue
        if _is_sculptor_section_title(title):
            body = complete_sculptor_body(
                body,
                plot_sources=sculptor_context_sources if sculptor_context_sources else plot_sources,
                setting_sources=setting_sources,
                locked_names=locked,
                sculpt_target=sculpt_target,
                seed=seed,
                prior_character_profiles=prior_character_profiles,
                global_cast_names=global_cast_names,
            )
            if beat_index > 0:
                body = abbreviate_established_sections(
                    body, title=title, beat_index=beat_index, locked_names=locked
                )
            body = condense_role_body(body, max_lines=sculpt_target, max_chars=44)
        elif "设定构建" in title or "Setting" in title:
            body = format_setting_architect_body(body)
            body = abbreviate_established_sections(
                body, title=title, beat_index=beat_index, locked_names=locked
            )
            body = condense_role_body(
                body, max_lines=4, max_chars=setting_cap
            )
        elif "剧情逻辑" in title or "Plot Logician" in title:
            body = expand_plot_conflict_bullets(body)
            body = condense_role_body(body, max_lines=5, max_chars=plot_cap)
        elif "冲突设计" in title or "Conflict" in title:
            body = strip_conflict_obstacle_lines(body)
            body = expand_plot_conflict_bullets(body, drop_obstacles=True)
            body = condense_role_body(body, max_lines=4, max_chars=plot_cap)
        elif "连贯" in title or "Consistency" in title:
            body = condense_role_body(body, max_lines=2, max_chars=36)
        else:
            body = condense_role_body(body, max_lines=3, max_chars=40)
        processed.append((title, scrub_functional_fragment(strip_mutation_markers(body))))
    final = _ordered_unified_sections(processed, role_names)
    return rebuild_merge_sections(final)


def parse_merge_role_sections(
    text: str,
    *,
    role_names: Optional[List[str]] = None,
) -> List[Tuple[str, str]]:
    """解析【职能名】分块拼接稿，返回 (标题, 正文) 列表。"""
    raw = normalize_outline_role_headers((text or "").strip(), role_names)
    if not raw:
        return []
    parts = re.split(r"(【[^】]+】)", raw)
    sections: List[Tuple[str, str]] = []
    title: Optional[str] = None
    body_lines: List[str] = []
    for p in parts:
        chunk = p.strip()
        if not chunk:
            continue
        if chunk.startswith("【") and chunk.endswith("】"):
            if title:
                sections.append((title, "\n".join(body_lines).strip()))
            title = chunk
            body_lines = []
        else:
            body_lines.append(chunk)
    if title:
        sections.append((title, "\n".join(body_lines).strip()))
    if not sections:
        return [("【全文】", raw)]
    return sections


def _strip_orphan_mutation_marks(text: str) -> str:
    return strip_mutation_markers(text)


def _normalize_mutation_line(ln: str) -> str:
    """补全未闭合的突变标记，便于高亮渲染；先清理误输出的 /mut。"""
    t = normalize_mutation_marker_aliases((ln or "").strip())
    t = re.sub(r"(?<![\u4e00-\u9fffA-Za-z])\\?/?mut\s*$", "", t, flags=re.I).strip()
    if _MUT_OPEN in t and _MUT_CLOSE not in t:
        t = re.sub(r"⟧+\s*$", "", t)
        if _MUT_CLOSE not in t:
            t = t + _MUT_CLOSE
    return t


def _mut_highlight_span(inner: str) -> str:
    import html as html_mod

    if not inner:
        return ""
    return f'<span class="nl-mut-highlight">{html_mod.escape(inner)}</span>'


def _html_escape_mutations(text: str) -> str:
    import html as html_mod

    raw = _normalize_mutation_line(normalize_mutation_marker_aliases(text or ""))
    if _MUT_OPEN not in raw and "⟦" not in raw:
        return html_mod.escape(_strip_orphan_mutation_marks(raw))
    parts: List[str] = []
    i = 0
    while i < len(raw):
        start = raw.find(_MUT_OPEN, i)
        bare = raw.find("⟦", i) if start < 0 else -1
        if start < 0 and bare < 0:
            parts.append(html_mod.escape(_strip_orphan_mutation_marks(raw[i:])))
            break
        if start < 0 or (0 <= bare < start):
            parts.append(html_mod.escape(_strip_orphan_mutation_marks(raw[i:bare])))
            end = raw.find("⟧", bare + 1)
            if end < 0:
                parts.append(html_mod.escape(raw[bare:]))
                break
            inner = _strip_orphan_mutation_marks(raw[bare + 1 : end])
            if inner and not re.fullmatch(r"\s*/?\s*mut\s*", inner, flags=re.I):
                parts.append(_mut_highlight_span(inner))
            i = end + 1
            continue
        parts.append(html_mod.escape(_strip_orphan_mutation_marks(raw[i:start])))
        end = raw.find(_MUT_CLOSE, start + len(_MUT_OPEN))
        if end < 0:
            inner = _strip_orphan_mutation_marks(raw[start + len(_MUT_OPEN) :])
            if inner:
                parts.append(_mut_highlight_span(inner))
            break
        inner = _strip_orphan_mutation_marks(raw[start + len(_MUT_OPEN) : end])
        if inner:
            parts.append(_mut_highlight_span(inner))
        i = end + len(_MUT_CLOSE)
    return "".join(parts)


def _outline_line_to_li(ln: str, *, highlight_mutations: bool) -> str:
    import html as html_mod

    ln = re.sub(r"^-\s*", "", (ln or "").strip())
    if not ln:
        return ""
    if highlight_mutations and (_MUT_OPEN in ln or "⟦" in ln or "⟧" in ln):
        inner = _html_escape_mutations(ln)
        core = re.sub(r"^-\s*", "", ln.strip())
        if core.startswith(_MUT_OPEN) and core.endswith(_MUT_CLOSE) and core.count(_MUT_OPEN) == 1:
            return f'<li class="nl-mut-li">{inner}</li>'
        return f"<li>{inner}</li>"
    return f"<li>{html_mod.escape(_strip_orphan_mutation_marks(ln))}</li>"


def _json_object_to_role_outline(obj: Any) -> str:
    """将 English-key JSON 大纲转为【职能】分块文本。"""
    if isinstance(obj, str):
        s = obj.strip()
        if s.startswith("{") and "【" not in s:
            try:
                from narrativeloom.service.llm_client import _parse_json_content

                parsed = _parse_json_content(s)
                if isinstance(parsed, dict):
                    return _json_object_to_role_outline(parsed)
            except Exception:  # noqa: BLE001
                pass
        return s
    if not isinstance(obj, dict):
        return str(obj or "").strip()

    role_patterns = [
        (re.compile(r"world|setting|场景|环境|时空|地点|时间", re.I), "设定构建师"),
        (re.compile(r"character|人物|角色|sculptor", re.I), "人物塑造师"),
        (re.compile(r"plot|剧情|逻辑|情节", re.I), "剧情逻辑师"),
        (re.compile(r"atmosphere|氛围", re.I), "氛围渲染师"),
        (re.compile(r"dialog|对话", re.I), "对话设计师"),
        (re.compile(r"detail|细节", re.I), "细节填充师"),
        (re.compile(r"conflict|冲突", re.I), "冲突设计师"),
        (re.compile(r"consist|连贯|校验|continuity", re.I), "连贯性校验师"),
        (re.compile(r"anti|clich|反套路|mut|trope", re.I), "反套路创意师"),
    ]
    buckets: Dict[str, List[str]] = {}

    def _lines_from_value(val: Any) -> List[str]:
        if val is None:
            return []
        if isinstance(val, dict):
            inner = _json_object_to_role_outline(val)
            if inner and "【" in inner:
                return [ln for ln in inner.splitlines() if ln.strip()]
            return []
        if isinstance(val, list):
            out: List[str] = []
            for item in val:
                t = str(item).strip()
                if t:
                    out.append(t if t.startswith("-") else f"- {t}")
            return out
        text = str(val).strip()
        if not text:
            return []
        if text.startswith("{") and "【" not in text:
            nested = _json_object_to_role_outline(text)
            if nested and "【" in nested:
                return [ln for ln in nested.splitlines() if ln.strip()]
            return []
        out = []
        for ln in text.replace("\\n", "\n").splitlines():
            ln = ln.strip()
            if ln:
                out.append(ln if ln.startswith("-") else f"- {ln}")
        return out

    for key, val in obj.items():
        k = str(key).strip()
        if not k or k in ("process_feedback", "variants", "outline", "_mode"):
            continue
        kn = re.sub(r"[\s_]+", " ", k.lower())
        role = "【全文】"
        for pat, rname in role_patterns:
            if pat.search(kn):
                role = f"【{rname}】"
                break
        lines = _lines_from_value(val)
        if lines:
            buckets.setdefault(role, []).extend(lines)

    order = [
        f"【{n}】"
        for n in _DEFAULT_FN_ROLE_NAMES
        if n and "【" not in n and not _is_continuity_section_title(f"【{n}】")
    ][:8]
    order.extend(
        r
        for r in ("【氛围渲染师】", "【对话设计师】", "【细节填充师】", "【反套路创意师】")
        if not _is_continuity_section_title(r)
    )
    chunks: List[str] = []
    seen: Set[str] = set()
    for role in order:
        if role in buckets:
            chunks.append(f"{role}\n" + "\n".join(buckets[role]))
            seen.add(role)
    for role, lines in buckets.items():
        if role not in seen:
            chunks.append(f"{role}\n" + "\n".join(lines))
    return "\n\n".join(chunks)


def _looks_like_role_json_object(data: dict) -> bool:
    if not isinstance(data, dict):
        return False
    for key in data:
        kn = re.sub(r"[\s_]+", " ", str(key).lower())
        if re.search(r"character|plot|conflict|world|setting|dialog|detail|atmosphere", kn):
            return True
    return False


def repair_antitrope_outline(text: str) -> str:
    """从反套路模型返回中剥离 JSON 包装、代码围栏与转义，还原可读大纲。"""
    from narrativeloom.service.llm_client import _parse_json_content

    raw = strip_trailing_json_leak(unescape_display_text(text or "")).strip()
    if not raw:
        return ""
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*```\s*$", "", raw)
    if raw.startswith("{"):
        data = _parse_json_content(raw)
        if isinstance(data, dict):
            outline_val = data.get("outline")
            if isinstance(outline_val, dict):
                converted = _json_object_to_role_outline(outline_val)
                if converted and "【" in converted:
                    return converted.strip()
            if isinstance(outline_val, str) and outline_val.strip():
                return repair_antitrope_outline(outline_val)
            if _looks_like_role_json_object(data):
                converted = _json_object_to_role_outline(data)
                if converted and "【" in converted:
                    return converted.strip()
            if "outline" in raw[:800] or "variants" in raw[:800]:
                variants = data.get("variants")
                if isinstance(variants, list) and variants:
                    first = variants[0]
                    if isinstance(first, dict):
                        inner = first.get("outline")
                        if inner is not None:
                            return repair_antitrope_outline(
                                inner if isinstance(inner, str) else _json_object_to_role_outline(inner)
                            )
                    if isinstance(first, str) and first.strip():
                        return repair_antitrope_outline(first)
    if raw.startswith("{") and "【" in raw:
        m = re.search(r'"outline"\s*:\s*"([\s\S]+)"\s*[,}]', raw)
        if m:
            inner = m.group(1).replace("\\n", "\n").replace('\\"', '"')
            if "【" in inner:
                return repair_antitrope_outline(inner)
    return raw.strip()


def _inject_section_headers_from_baseline(variant: str, baseline: str) -> str:
    """反套路输出缺小节标题时，按基准汇编补回 ### **小节 n**。"""
    headers: List[str] = []
    for ln in (baseline or "").splitlines():
        lab = _story_section_heading_label(ln.strip())
        if lab:
            headers.append(f"### **{lab}**")
    if not headers:
        return variant
    chunks = re.split(r"(?=【设定构建师】|【Setting Architect】)", variant or "")
    chunks = [c.strip() for c in chunks if c.strip()]
    if len(chunks) <= 1:
        return variant
    out: List[str] = []
    for i, chunk in enumerate(chunks):
        if i < len(headers):
            out.append(headers[i])
        out.append(chunk)
    return "\n\n".join(out)


def _story_outline_mixed_html(
    text: str,
    *,
    highlight_mutations: bool = False,
    mutation_baseline: str = "",
) -> str:
    """含 ### 小节标题 + 【职能】分块的反套路大纲展示。"""
    import html as html_mod

    parts = re.split(r"(?=^#{1,3}\s)", text or "", flags=re.M)
    chunks: List[str] = []
    for part in parts:
        seg = part.strip()
        if not seg:
            continue
        lines = [ln for ln in seg.splitlines() if ln.strip()]
        if not lines:
            continue
        head = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        sec_label = _story_section_heading_label(head)
        if sec_label:
            chunks.append(f'<div class="nl-fn-merge-role"><strong>{html_mod.escape(sec_label)}</strong></div>')
        if body:
            chunks.append(
                outline_to_display_html(
                    body,
                    highlight_mutations=highlight_mutations,
                    role_names=list(_DEFAULT_FN_ROLE_NAMES),
                    outline_kind="roles",
                    mutation_baseline=mutation_baseline,
                )
            )
    return "".join(chunks) if chunks else f'<pre class="nl-outline-pre">{html_mod.escape(text)}</pre>'


def _story_section_heading_label(line: str) -> Optional[str]:
    """识别小节分段标题行（含 ### **小节 n**）。"""
    s = (line or "").strip()
    if not s:
        return None
    m = re.match(r"^#{1,6}\s*(.+)$", s)
    if m:
        label = m.group(1).strip().strip("*").strip()
        if re.match(r"^(小节|Section)\s*\d+", label, re.I):
            return label
    m2 = re.match(r"^【第\s*(\d+)\s*节(?:\s*[·•\-—]\s*(.+?))?\s*】$", s)
    if m2:
        tail = (m2.group(2) or "").strip()
        return f"小节 {m2.group(1)}" + (f" · {tail}" if tail else "")
    if re.match(r"^(小节|Section)\s*\d+\b", s, re.I):
        return s
    return None


def _story_outline_to_html(text: str, *, highlight_mutations: bool = False, mutation_baseline: str = "") -> str:
    """反套路/全文大纲：按小节或职能分块展示。"""
    import html as html_mod

    raw = repair_antitrope_outline(text)
    if highlight_mutations:
        raw = prepare_mutation_display_text(raw, mutation_baseline)
    if not raw:
        return '<p class="nl-empty-dash">—</p>'
    if "【设定构建师】" in raw or "【人物塑造师】" in raw or "【剧情逻辑师】" in raw:
        if not re.search(r"^#{1,3}\s", raw, re.M) and re.search(r"^#{1,3}\s", mutation_baseline or "", re.M):
            raw = _inject_section_headers_from_baseline(raw, mutation_baseline)
        if re.search(r"^#{1,3}\s", raw, re.M):
            return _story_outline_mixed_html(
                raw,
                highlight_mutations=highlight_mutations,
                mutation_baseline=mutation_baseline,
            )
        return outline_to_display_html(
            raw,
            highlight_mutations=highlight_mutations,
            role_names=list(_DEFAULT_FN_ROLE_NAMES),
            outline_kind="roles",
            mutation_baseline=mutation_baseline,
        )
    parts = re.split(r"(?=^#{1,3}\s|【第\s*\d+)", raw, flags=re.M)
    chunks: List[str] = []
    for part in parts:
        seg = part.strip()
        if not seg:
            continue
        lines = [ln for ln in seg.splitlines() if ln.strip()]
        if not lines:
            continue
        head = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        sec_label = _story_section_heading_label(head)
        if sec_label:
            chunks.append(f'<div class="nl-fn-merge-role"><strong>{html_mod.escape(sec_label)}</strong></div>')
        elif re.match(r"^#{1,3}\s", head) or re.match(r"^【第", head):
            label = re.sub(r"^#{1,3}\s*", "", head).strip().strip("*").strip()
            chunks.append(f'<div class="nl-fn-merge-role"><strong>{html_mod.escape(label)}</strong></div>')
        else:
            body = seg
        if not body:
            continue
        if highlight_mutations and _MUT_OPEN in body:
            para = _html_escape_mutations(body).replace("\n", "<br/>")
            chunks.append(f'<p class="nl-story-seg">{para}</p>')
            continue
        md = fragment_to_markdown_bullets(body, preserve_mutations=highlight_mutations)
        if md == "—":
            chunks.append('<p class="nl-empty-dash">—</p>')
        else:
            items = []
            for ln in md.split("\n"):
                ln = re.sub(r"^-\s*", "", ln.strip())
                if ln:
                    if highlight_mutations:
                        li = _outline_line_to_li(ln, highlight_mutations=True)
                        if li:
                            items.append(li)
                    else:
                        items.append(f"<li>{html_mod.escape(ln)}</li>")
            chunks.append(f'<ul class="nl-ul">{"".join(items)}</ul>' if items else f'<p class="nl-story-seg">{html_mod.escape(body)}</p>')
    return "".join(chunks) if chunks else f'<pre class="nl-outline-pre">{html_mod.escape(raw)}</pre>'


def outline_to_display_html(
    text: str,
    *,
    highlight_mutations: bool = False,
    role_names: Optional[List[str]] = None,
    outline_kind: str = "roles",
    mutation_baseline: str = "",
) -> str:
    """将拼合大纲转为 HTML；outline_kind=story 用于反套路全文。"""
    import html as html_mod

    if outline_kind == "story":
        return _story_outline_to_html(
            text,
            highlight_mutations=highlight_mutations,
            mutation_baseline=mutation_baseline,
        )

    roles = _known_role_names(role_names)
    raw = normalize_outline_role_headers(strip_trailing_json_leak(unescape_display_text(text)), roles)
    if highlight_mutations:
        raw = prepare_mutation_display_text(raw, mutation_baseline)
    if not raw:
        return '<p class="nl-empty-dash">—</p>'

    if "【" in raw or any(rn in raw for rn in roles):
        sections = parse_merge_role_sections(raw, role_names=roles)
        if sections and sections[0][0] != "【全文】":
            chunks: List[str] = []
            for title, body in sections:
                if _is_continuity_section_title(title):
                    continue
                label = _role_title_key(title)
                chunks.append(f'<div class="nl-fn-merge-role"><strong>{html_mod.escape(label)}</strong></div>')
                md = fragment_to_markdown_bullets(body, preserve_mutations=highlight_mutations)
                if md == "—":
                    chunks.append('<p class="nl-empty-dash">—</p>')
                else:
                    items = []
                    for ln in md.split("\n"):
                        ln = re.sub(r"^-\s*", "", ln.strip())
                        if ln and not _is_role_header_line(ln, roles):
                            li = _outline_line_to_li(ln, highlight_mutations=highlight_mutations)
                            if li:
                                items.append(li)
                    chunks.append(f'<ul class="nl-ul">{"".join(items)}</ul>' if items else '<p class="nl-empty-dash">—</p>')
            return "".join(chunks)

    if highlight_mutations and (_MUT_OPEN in raw or "⟧" in raw):
        return f'<pre class="nl-outline-pre">{_html_escape_mutations(raw)}</pre>'

    md = fragment_to_markdown_bullets(raw, preserve_mutations=highlight_mutations)
    if md == "—":
        return '<p class="nl-empty-dash">—</p>'
    items: List[str] = []
    in_ul = False
    for ln in md.split("\n"):
        ln = re.sub(r"^-\s*", "", ln.strip())
        if not ln:
            continue
        if _is_role_header_line(ln, roles):
            if in_ul:
                items.append("</ul>")
                in_ul = False
            items.append(
                f'<div class="nl-fn-merge-role"><strong>{html_mod.escape(_role_title_key(ln))}</strong></div>'
            )
            continue
        if not in_ul:
            items.append('<ul class="nl-ul">')
            in_ul = True
        if highlight_mutations and (_MUT_OPEN in ln or "⟦" in ln):
            li = _outline_line_to_li(ln, highlight_mutations=True)
            if li:
                items.append(li)
        else:
            items.append(f"<li>{html_mod.escape(_strip_orphan_mutation_marks(ln))}</li>")
    if in_ul:
        items.append("</ul>")
    return "".join(items) if items else '<p class="nl-empty-dash">—</p>'


def prior_beats_repetition_digest(beat_texts: List[str], *, max_lines: int = 8) -> str:
    """提取前文要点摘要，供生成时避免情节重复。"""
    lines: List[str] = []
    for i, txt in enumerate(beat_texts or []):
        if not (txt or "").strip():
            continue
        for ln in (txt or "").splitlines():
            s = ln.strip().lstrip("-·•").strip()
            if len(s) >= 10 and s not in lines:
                lines.append(s[:120])
            if len(lines) >= max_lines:
                break
        if len(lines) >= max_lines:
            break
    return "\n".join(f"- {ln}" for ln in lines[:max_lines])
