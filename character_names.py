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
    r"严谨|务实|状态|动机|性格|师$|工程|"
    r"队员$|教授$|工程师$|研究员$|研究生$|生命体$)"
)


def _canonical(name: str) -> str:
    from display_utils import _canonical_person_name

    return _canonical_person_name(name)


def _is_person(name: str) -> bool:
    from display_utils import _is_pure_person_name

    n = _canonical(name)
    if not n or _REJECT_NAME_FRAG.search(n):
        return False
    return bool(_is_pure_person_name(n))


def _valid_sculptor_entry(name: str, desc: str) -> bool:
    from display_utils import _is_valid_sculptor_person_line

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


def _extract_dyads(text: str) -> List[str]:
    """「A与B」并列：两侧分别解析为真实人名。"""
    blob = text or ""
    found: List[str] = []
    for m in _DYAD_SEP.finditer(blob):
        left = _name_at_end(blob[max(0, m.start() - 8) : m.start()], context=blob)
        right = _name_at_start(blob[m.end() : m.end() + 8], context=blob)
        for n in (left, right):
            if n and n not in found:
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
    from display_utils import _is_trait_description

    return _is_trait_description(desc)


def _coalesce_prefix_names(names: List[str]) -> List[str]:
    """合并「阿依古」+「阿依古丽」等前缀重复姓名，保留更长者。"""
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
    return ordered


def parse_colon_lines(text: str, *, context: str = "") -> Dict[str, str]:
    """仅保留「真实姓名 + 身份/动机」行；过滤 安全/毡房/电脑 等非人名标签。"""
    from display_utils import _CHAR_NAME_LINE, repair_colon_split_name

    out: Dict[str, str] = {}
    full = f"{context}\n{text}".strip()
    for line in (text or "").splitlines():
        s = line.strip()
        if not s:
            continue
        probe = s if re.match(r"^[-•·]", s) else f"- {s}"
        m = _CHAR_NAME_LINE.match(probe)
        if not m:
            continue
        raw_name = m.group(1).strip()
        desc = probe.split("：", 1)[-1].split(":", 1)[-1].strip() if ("：" in probe or ":" in probe) else ""
        if not desc:
            continue
        raw_name, desc = repair_colon_split_name(raw_name, desc, context=full)
        from display_utils import _is_setting_field_label

        if _is_setting_field_label(raw_name):
            continue
        name = _canonical(raw_name)
        if not name or not _valid_sculptor_entry(name, desc):
            continue
        if name in out:
            continue
        out[name] = f"- {name}：{desc}"
    if not out and full:
        for line in (text or "").splitlines():
            s = line.strip()
            if not s or "：" not in s and ":" not in s:
                continue
            probe = s if re.match(r"^[-•·]", s) else f"- {s}"
            parts = probe.lstrip("-•· ").split("：", 1)
            if len(parts) != 2:
                parts = probe.lstrip("-•· ").split(":", 1)
            if len(parts) != 2:
                continue
            raw_name, desc = repair_colon_split_name(parts[0].strip(), parts[1].strip(), context=full)
            name = _canonical(raw_name)
            if name and desc and _valid_sculptor_entry(name, desc) and name not in out:
                out[name] = f"- {name}：{desc}"
    return out


def extract_cast_from_narrative(text: str, *, limit: int = 8) -> List[str]:
    """从剧情文本提取人物：并列结构 + display_utils 严格扫描。"""
    from display_utils import extract_names_from_narrative, extract_relation_names

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
    from display_utils import _infer_sculptor_trait

    return _infer_sculptor_trait(name, context, context).split("：", 1)[-1]


def _trim_sculptor_line(line: str, *, context: str = "") -> str:
    from display_utils import repair_colon_split_name

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
    name = _canonical(name)
    desc = re.sub(r"\s+", " ", desc.strip())
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
    narrative = "\n".join(s for s in (plot_sources or []) if (s or "").strip())
    extract_blob = f"{body}\n{narrative}".strip()
    full = f"{extract_blob}\n{setting_context}".strip()
    target = max(1, min(int(target), 14))
    locked = merge_unique_names(list(locked_names or []))

    valid_lines = parse_colon_lines(body, context=full)
    narrative_cast = extract_cast_from_narrative(extract_blob, limit=max(target + 4, 10))
    dyads = _extract_dyads(extract_blob)

    cast: List[str] = []
    for n in locked:
        if n and _is_person(n) and n not in cast:
            cast.append(n)
    for n in list(valid_lines.keys()) + dyads + narrative_cast:
        if n and _is_person(n) and n not in cast:
            cast.append(n)

    while len(cast) < target:
        added = False
        for n in narrative_cast:
            if n and _is_person(n) and n not in cast:
                cast.append(n)
                added = True
                break
        if not added:
            break

    cast = cast[:target]
    cast = _coalesce_prefix_names(cast)

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
        from display_utils import parse_merge_role_sections, _is_sculptor_section_title

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
    locked = merge_unique_names(list(locked_names or []))
    valid = parse_colon_lines(fragment, context=fragment)
    main = extract_cast_from_narrative(fragment, limit=target_total or 8)
    dyads = _extract_dyads(fragment)

    cast: List[str] = []
    for n in locked + list(valid.keys()) + dyads + main:
        if _is_person(n) and n not in cast:
            cast.append(n)
    if target_total and target_total > 0:
        cast = cast[: max(target_total, len(locked))]

    lines = [
        _trim_sculptor_line(valid[n], context=fragment) if n in valid else f"- {n}：{_brief_trait(n, fragment)}"
        for n in cast
    ]
    return "\n".join(lines) if lines else ""
