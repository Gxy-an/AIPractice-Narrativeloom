# -*- coding: utf-8 -*-
"""功能化创作：人物姓名识别与人物塑造师分块补全（严格模式）。"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set

_DYAD_SEP = re.compile(r"[与和、]")

# 含下列片段的一律不是人名（设定/场景/冲突标签误拆）
_REJECT_NAME_FRAG = re.compile(
    r"(任务|安全|规则|场景|地点|时间|设备|毡房|勘探|电脑|地质|紧迫|学术|冲突|悬念|矛盾|"
    r"高潮|转折|节奏|情节|剧情|环境|世界|物理|空间|设定|承接|核查|连续|监控|检查|"
    r"氛围|道具|伏笔|因果|逻辑|对话|提醒|拓展|节点|抉择|样本|陈列|诚信|突破|原则|"
    r"严谨|务实|状态|动机|性格|师$|工程|计划$|程计划|"
    r"队员$|教授$|工程师$|研究员$|研究生$|生命体$)"
)


def _canonical(name: str) -> str:
    from narrativeloom.utils.display_utils import _canonical_person_name

    return _canonical_person_name(name)


def _is_person(name: str) -> bool:
    from narrativeloom.utils.display_utils import _is_pure_person_name

    n = _canonical(name)
    if not n or _REJECT_NAME_FRAG.search(n):
        return False
    return bool(_is_pure_person_name(n))


def _valid_sculptor_entry(name: str, desc: str) -> bool:
    from narrativeloom.utils.display_utils import _is_valid_sculptor_person_line

    n = _canonical(name)
    if not n or _REJECT_NAME_FRAG.search(n):
        return False
    return bool(_is_valid_sculptor_person_line(n, desc))


def _mentions(text: str, name: str) -> int:
    return len(re.findall(re.escape(name), text or ""))


def _name_at_end(segment: str, *, context: str) -> str:
    seg = segment or ""
    for ln in (2, 3, 4):
        if len(seg) >= ln:
            raw = seg[-ln:]
            n = _canonical(raw)
            if n and n == raw and _is_person(n):
                return n
    return ""


def _name_at_start(segment: str, *, context: str) -> str:
    seg = segment or ""
    for ln in (2, 3, 4):
        if len(seg) >= ln:
            raw = seg[:ln]
            n = _canonical(raw)
            if n and n == raw and _is_person(n):
                return n
    return ""


def _is_loose_cast_name(name: str, *, context: str = "") -> bool:
    """剧情/冲突分块中的并列人名（如凯拉与雷欧），放宽至 2～4 字。"""
    from narrativeloom.utils.display_utils import (
        _BOGUS_NAME_PREFIX,
        _STANDALONE_ROLE_LABEL,
        _is_setting_field_label,
        _strip_glued_verb_from_name,
    )

    n = _strip_glued_verb_from_name((name or "").strip())
    if not n or len(n) < 2 or len(n) > 4:
        return False
    if _is_setting_field_label(n) or _BOGUS_NAME_PREFIX.match(n) or n in _STANDALONE_ROLE_LABEL:
        return False
    if _REJECT_NAME_FRAG.search(n):
        return False
    if re.search(r"(因果|戏剧|冲突|悬念|核心|突变|链|矛盾|阻碍|争执|必须|抉择)", n):
        return False
    if _is_person(n):
        return True
    return bool(re.fullmatch(r"[\u4e00-\u9fff]{2,4}", n))


_DYAD_PAIR = re.compile(
    r"([\u4e00-\u9fff]{2,4})[与和、]([\u4e00-\u9fff]{2,4})"
    r"(?=争执|必须|抉择|发现|对峙|合作|对话|分歧|联手|冲突|犹豫|离开|进入|赶到|相遇|告别|，|,|。|；|\s|$)"
)


def _extract_dyads(text: str) -> List[str]:
    """「A与B」并列：两侧分别解析为真实人名。"""
    from narrativeloom.utils.display_utils import _strip_glued_verb_from_name

    blob = text or ""
    found: List[str] = []
    for m in _DYAD_PAIR.finditer(blob):
        for g in m.groups():
            n = _strip_glued_verb_from_name(g)
            if _is_loose_cast_name(n, context=blob) and n not in found:
                found.append(n)
    for m in _DYAD_SEP.finditer(blob):
        left = _name_at_end(blob[max(0, m.start() - 8) : m.start()], context=blob)
        right = _name_at_start(blob[m.end() : m.end() + 8], context=blob)
        for raw in (left, right):
            n = _strip_glued_verb_from_name(raw) if raw else ""
            if n and _is_loose_cast_name(n, context=blob) and n not in found:
                found.append(n)
    return found


def _extract_quoted(text: str) -> List[str]:
    found: List[str] = []
    for m in re.finditer(r"[「「\"']([\u4e00-\u9fffA-Za-z]{2,6})[」」\"']", text or ""):
        n = _canonical(m.group(1))
        if n and _is_person(n) and n not in found:
            found.append(n)
    return found


def _extract_new_role(text: str) -> List[str]:
    found: List[str] = []
    for m in re.finditer(
        r"新增角色[：:]\s*[「「\"']?([\u4e00-\u9fffA-Za-z]{2,6})",
        text or "",
    ):
        n = _canonical(m.group(1))
        if n and _is_person(n) and n not in found:
            found.append(n)
    return found


def canonical_name(name: str) -> str:
    return _canonical(name)


def resolve_name(name: str, *, context: str = "") -> str:
    _ = context
    n = _canonical(name)
    return n if n and _is_person(n) else ""


def is_person_name(name: str, *, context: str = "") -> bool:
    _ = context
    return _is_person(name)


def is_valid_trait(desc: str) -> bool:
    from narrativeloom.utils.display_utils import _is_trait_description

    return _is_trait_description(desc)


def _coalesce_prefix_names(names: List[str]) -> List[str]:
    """合并「阿依古」+「阿依古丽」、以及「阿依古丽」+误拆「古丽」等重复姓名。"""
    ordered: List[str] = []
    for n in names:
        if not n:
            continue
        replaced = False
        for i, k in enumerate(ordered):
            if k.startswith(n) and len(k) > len(n):
                replaced = True
                break
            if n.startswith(k) and len(n) > len(k):
                ordered[i] = n
                replaced = True
                break
        if not replaced and n not in ordered:
            ordered.append(n)
    drop: Set[str] = set()
    for a in ordered:
        for b in ordered:
            if a != b and len(b) >= 2 and len(a) > len(b) and a.endswith(b):
                drop.add(b)
    return [n for n in ordered if n not in drop]


def _dedupe_suffix_name_keys(out: Dict[str, str]) -> Dict[str, str]:
    """合并「阿依古丽」与误拆的「古丽」「阿依古丽古」等同人后缀名。"""
    if not out:
        return out
    from narrativeloom.utils.display_utils import _is_protected_compound_name, _trim_scene_glued_suffix_from_name

    normalized: Dict[str, str] = {}
    for k, v in out.items():
        canon = _trim_scene_glued_suffix_from_name(k)
        if canon in normalized:
            continue
        line = v
        if canon != k:
            line = re.sub(rf"^{re.escape(k)}\s*：", f"{canon}：", line)
            line = re.sub(rf"^- {re.escape(k)}\s*：", f"- {canon}：", line)
        normalized[canon] = line
    out = normalized
    drop: Set[str] = set()
    keys = list(out.keys())
    for a in keys:
        for b in keys:
            if a != b and len(b) >= 2 and len(a) > len(b) and a.endswith(b):
                drop.add(b)
            if (
                a != b
                and _is_protected_compound_name(b)
                and a.startswith(b)
                and len(a) == len(b) + 1
            ):
                drop.add(a)
    if not drop:
        return out
    return {k: v for k, v in out.items() if k not in drop}


def parse_colon_lines(text: str, *, context: str = "") -> Dict[str, str]:
    """仅保留「真实姓名 + 身份/动机」行；与类型化人格相同，按行解析，不用叙事扫描误拆。"""
    from narrativeloom.utils.display_utils import (
        _is_setting_field_label,
        _normalize_sculptor_line_name,
        _split_character_entries,
        repair_colon_split_name,
    )

    out: Dict[str, str] = {}
    full = f"{context}\n{text}".strip()
    for entry in _split_character_entries(text or ""):
        line = entry.lstrip("-·• ").strip()
        if "：" not in line and ":" not in line:
            continue
        line = line.replace(":", "：")
        name, _, desc = line.partition("：")
        name, desc = repair_colon_split_name(name.strip(), desc.strip(), context=full)
        from narrativeloom.utils.display_utils import _normalize_sculptor_line_name

        name = _normalize_sculptor_line_name(name, context=full)
        if _is_setting_field_label(name):
            continue
        if not name or not _valid_sculptor_entry(name, desc):
            continue
        if name in out:
            continue
        out[name] = f"- {name}：{desc}"
    return _dedupe_suffix_name_keys(out)


_SEED_COMPOUND_NAME = re.compile(
    r"([\u4e00-\u9fffA-Za-z]{2,12}(?:[·．\.][\u4e00-\u9fffA-Za-z]{1,10})+)"
    r"(?=[在将向对把被给让与和、，,。；：:\s]|$)"
)
_SEED_LEAD_ACTOR = re.compile(
    r"^[\s「『\"'（(]*"
    r"([\u4e00-\u9fffA-Za-z]{2,12}(?:[·．\.][\u4e00-\u9fffA-Za-z]{1,10})+|[\u4e00-\u9fff]{2,5})"
    r"(?=[在将向对把被给让与和、，,。；]|$)"
)


def _is_seed_cast_name(name: str, *, context: str = "") -> bool:
    n = (name or "").strip()
    if not n or len(n) < 2 or len(n) > 24:
        return False
    if _REJECT_NAME_FRAG.search(n):
        return False
    if re.search(r"[·．\.]", n):
        parts = [p for p in re.split(r"[·．\.]", n) if p]
        if parts and all(re.fullmatch(r"[\u4e00-\u9fffA-Za-z]+", p) for p in parts):
            return True
    if _is_person(n):
        return True
    return _is_loose_cast_name(n, context=context)


def extract_seed_cast_names(text: str, *, limit: int = 6) -> List[str]:
    """从创意种子提取既定主角/人名（含「达芬奇·狗剩」等带点复合名）。"""
    blob = (text or "").strip()
    if not blob:
        return []

    found: List[str] = []
    for pat in (_SEED_COMPOUND_NAME, _SEED_LEAD_ACTOR):
        for m in pat.finditer(blob):
            n = m.group(1).strip()
            if _is_seed_cast_name(n, context=blob) and n not in found:
                found.append(n)

    for n in extract_cast_from_narrative(blob, limit=limit):
        if n not in found:
            found.append(n)

    ranked = sorted(found, key=lambda n: (-_mentions(blob, n), found.index(n)))
    return ranked[:limit]


def extract_cast_from_narrative(text: str, *, limit: int = 8) -> List[str]:
    """从剧情文本提取人物：并列结构 + display_utils 严格扫描。"""
    from narrativeloom.utils.display_utils import extract_names_from_narrative, extract_relation_names

    blob = (text or "").strip()
    if not blob:
        return []

    cast: List[str] = []
    for n in _extract_dyads(blob) + _extract_quoted(blob) + _extract_new_role(blob):
        if n not in cast:
            cast.append(n)
    for n in extract_relation_names(blob):
        if n not in cast:
            cast.append(n)
    for n in extract_names_from_narrative(blob, limit=limit):
        if n not in cast:
            cast.append(n)

    ranked = sorted(cast, key=lambda n: (-_mentions(blob, n), cast.index(n)))
    out: List[str] = []
    for n in ranked:
        if _is_person(n) and n not in out:
            out.append(n)
        if len(out) >= limit:
            break
    return out


def merge_unique_names(*lists: List[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for lst in lists:
        for raw in lst or []:
            n = resolve_name(raw)
            if n and n not in seen:
                seen.add(n)
                out.append(n)
    return out


def _brief_trait(name: str, context: str) -> str:
    from narrativeloom.utils.display_utils import _infer_sculptor_trait

    return _infer_sculptor_trait(name, context, context).split("：", 1)[-1]


def expand_name_from_context(name: str, context: str) -> str:
    """若上下文存在更长全名（如 艾买→艾买提），补全姓名；禁止向动词尾字扩展。"""
    from narrativeloom.utils.display_utils import _finalize_sculptor_name, _is_protected_compound_name

    n = _finalize_sculptor_name(_canonical(name), context=context)
    if not n or not (context or "").strip():
        return n
    best = n
    for m in re.finditer(r"[\u4e00-\u9fff]{2,5}", context):
        cand = _finalize_sculptor_name(m.group(0), context=context)
        if (
            cand
            and cand.startswith(n[: min(2, len(n))])
            and len(cand) > len(best)
            and _is_person(cand)
            and _is_protected_compound_name(cand)
        ):
            best = cand
    return best


def _trim_sculptor_line(line: str, *, context: str = "") -> str:
    from narrativeloom.utils.display_utils import _finalize_sculptor_name, repair_colon_split_name

    s = (line or "").strip()
    if not s:
        return s
    probe = s if re.match(r"^[-•·]", s) else f"- {s}"
    if "：" in probe:
        name, _, desc = probe.lstrip("-•· ").partition("：")
    elif ":" in probe:
        name, _, desc = probe.lstrip("-•· ").partition(":")
    else:
        return probe
    name, desc = repair_colon_split_name(name.strip(), desc.strip(), context=context)
    from narrativeloom.utils.display_utils import _normalize_sculptor_line_name, sanitize_sculptor_description

    name = _normalize_sculptor_line_name(name, context=context)
    desc = sanitize_sculptor_description(re.sub(r"\s+", " ", desc.strip()))
    if not name:
        return probe
    return f"- {name}：{desc}"


def complete_sculptor_section(
    body: str,
    *,
    plot_sources: List[str],
    setting_context: str = "",
    locked_names: Optional[List[str]] = None,
    target: int = 2,
) -> str:
    """补全人物塑造师：仅输出真实人物，人数对齐 target。"""
    from narrativeloom.utils.display_utils import _scan_plot_name_candidates, extract_relation_names

    narrative = "\n".join(s for s in (plot_sources or []) if (s or "").strip())
    extract_blob = f"{body}\n{narrative}".strip()
    full = f"{extract_blob}\n{setting_context}".strip()
    target = max(1, min(int(target), 14))
    locked = merge_unique_names(list(locked_names or []))

    valid_lines = parse_colon_lines(body, context=full)
    narrative_cast = _scan_plot_name_candidates(extract_blob, limit=max(target * 2, 12))
    narrative_cast.extend(extract_relation_names(extract_blob))
    dyads = _extract_dyads(extract_blob)

    pool: List[str] = []
    for n in locked:
        if n and (_is_person(n) or _is_loose_cast_name(n, context=full)) and n not in pool:
            pool.append(n)
    for n in list(valid_lines.keys()) + dyads + narrative_cast:
        if n and (_is_person(n) or _is_loose_cast_name(n, context=full)) and n not in pool:
            pool.append(n)
    if len(pool) < target:
        for n in _scan_plot_name_candidates(narrative, limit=max(target * 3, 20)):
            if n and (_is_person(n) or _is_loose_cast_name(n, context=full)) and n not in pool:
                pool.append(n)
        for n in dyads:
            if n not in pool:
                pool.append(n)

    cast = _coalesce_prefix_names(pool)[:target]
    while len(cast) < target:
        added = False
        for n in _scan_plot_name_candidates(f"{narrative}\n{extract_blob}", limit=30) + dyads:
            if n and (_is_person(n) or _is_loose_cast_name(n, context=full)) and n not in cast:
                cast.append(n)
                added = True
                if len(cast) >= target:
                    break
        if not added:
            break
    cast = cast[:target]

    lines: List[str] = []
    for n in cast:
        picked = valid_lines.get(n)
        if not picked:
            for k, v in valid_lines.items():
                if n.startswith(k) or k.startswith(n):
                    picked = v
                    break
        if picked:
            lines.append(_trim_sculptor_line(picked, context=full))
        else:
            lines.append(f"- {n}：{_brief_trait(n, full)}")
    return "\n".join(lines) if lines else "—"


def extract_character_names(text: str, *, sculptor_sections_only: bool = False) -> List[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    if "【" in raw:
        from narrativeloom.utils.display_utils import parse_merge_role_sections, _is_sculptor_section_title

        sections = parse_merge_role_sections(raw)
        if sections and sections[0][0] != "【全文】":
            narrative = "\n".join(
                b for t, b in sections
                if not _is_sculptor_section_title(t) and "设定构建" not in t
            )
            names: List[str] = []
            if sculptor_sections_only:
                for title, body in sections:
                    if _is_sculptor_section_title(title):
                        names.extend(parse_colon_lines(body, context=narrative).keys())
            else:
                names.extend(_extract_dyads(narrative))
                names.extend(extract_cast_from_narrative(narrative))
                for title, body in sections:
                    if _is_sculptor_section_title(title):
                        names.extend(parse_colon_lines(body, context=narrative).keys())
            return merge_unique_names(names)
    return merge_unique_names(
        list(parse_colon_lines(raw, context=raw).keys()) + extract_cast_from_narrative(raw)
    )


def filter_sculptor_fragment(
    fragment: str,
    *,
    target_total: Optional[int] = None,
    locked_names: Optional[List[str]] = None,
) -> str:
    target = max(2, int(target_total or 2))
    locked = merge_unique_names(list(locked_names or []))
    return complete_sculptor_section(
        fragment,
        plot_sources=[fragment],
        locked_names=locked,
        target=target,
    )
