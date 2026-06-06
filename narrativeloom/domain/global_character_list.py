# -*- coding: utf-8 -*-
"""全局角色清单（Layer 1）：仅从 Beat 结构化 characters 字段拆分姓名，不依赖正文 NER。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from narrativeloom.domain.character_names import extract_seed_cast_names, merge_unique_names


@dataclass
class GlobalCharacterEntry:
    name: str
    profile: str = ""
    source: str = ""


@dataclass
class GlobalCharacterList:
    entries: List[GlobalCharacterEntry] = field(default_factory=list)

    @property
    def names(self) -> List[str]:
        return [e.name for e in self.entries if e.name]

    def profile_map(self) -> Dict[str, str]:
        return {e.name: e.profile for e in self.entries if e.name and e.profile}

    def format_for_prompt(self, lang: str = "zh", *, max_chars: int = 2400) -> str:
        if not self.entries:
            return ""
        lines: List[str] = []
        if lang == "en":
            lines.append("【Global Character List — reuse exact names; no unexplained renames】")
        else:
            lines.append("【全局角色清单（须沿用下列正式姓名，禁止无原因改名）】")
        for e in self.entries:
            if e.profile:
                lines.append(f"- {e.name}：{e.profile}")
            else:
                lines.append(f"- {e.name}")
            if sum(len(x) + 1 for x in lines) > max_chars:
                break
        return "\n".join(lines)[:max_chars]

    def merge(self, other: GlobalCharacterList) -> GlobalCharacterList:
        seen: Dict[str, GlobalCharacterEntry] = {e.name: e for e in self.entries if e.name}
        for e in other.entries:
            if not e.name:
                continue
            prev = seen.get(e.name)
            if not prev or (e.profile and not prev.profile):
                seen[e.name] = e
        return GlobalCharacterList(entries=list(seen.values()))


def names_from_structured_characters_field(text: Any) -> List[str]:
    """从 characters 结构化字段提取正式姓名（行 / & / Name：desc），不做散文 NER。"""
    from narrativeloom.domain.character_names import is_false_person_name
    from narrativeloom.utils.display_utils import (
        _names_from_bullet_lines,
        _split_character_entries,
        coerce_display_text,
    )

    raw = coerce_display_text(text).strip()
    if not raw:
        return []

    if "&" in raw and not re.search(r"^[-*•·]", raw, re.M):
        parts = [p.strip() for p in raw.split("&") if p.strip()]
        if len(parts) >= 2:
            raw = "\n".join(
                p if "：" in p or ":" in p else f"{p}："
                for p in parts
            )

    names = _names_from_bullet_lines(raw)
    if names:
        return merge_unique_names(names)

    out: List[str] = []
    for entry in _split_character_entries(raw):
        line = entry.lstrip("-·• ").strip().replace(":", "：")
        if "：" in line:
            name = line.split("：", 1)[0].strip()
        else:
            name = line.strip()
        if not name or is_false_person_name(name, context=raw):
            continue
        if name not in out:
            out.append(name)
    return merge_unique_names(out)


def profiles_from_structured_characters_field(text: Any) -> Dict[str, str]:
    from narrativeloom.utils.display_utils import parse_character_profile_map

    return parse_character_profile_map(text)


def names_from_functional_outline(outline: str) -> List[str]:
    """功能化：仅解析【人物塑造师】结构化行，不扫描剧情正文。"""
    from narrativeloom.utils.display_utils import extract_sculptor_section_text

    body = extract_sculptor_section_text(outline or "")
    if not body:
        return []
    return names_from_structured_characters_field(body)


def build_global_character_list(
    *,
    seed: str = "",
    background: str = "",
    prior_beats: Optional[Sequence[Any]] = None,
    lang: str = "zh",
) -> GlobalCharacterList:
    """汇总种子、背景与前序 Beat 的结构化 characters，构建全局角色清单。"""
    _ = lang
    entries: Dict[str, GlobalCharacterEntry] = {}

    def _register(names: List[str], profiles: Dict[str, str], source: str) -> None:
        for n in names:
            if not n:
                continue
            prof = profiles.get(n, "")
            prev = entries.get(n)
            if not prev:
                entries[n] = GlobalCharacterEntry(name=n, profile=prof, source=source)
            elif prof and not prev.profile:
                entries[n] = GlobalCharacterEntry(name=n, profile=prof, source=source or prev.source)

    seed = (seed or "").strip()
    if seed:
        _register(extract_seed_cast_names(seed), {}, "seed")

    bg = (background or "").strip()
    if bg:
        _register(
            names_from_structured_characters_field(bg),
            profiles_from_structured_characters_field(bg),
            "background",
        )

    for i, beat in enumerate(prior_beats or []):
        if not isinstance(beat, dict):
            continue
        src = f"beat_{i + 1}"
        if beat.get("mode") == "typified":
            ch = (beat.get("characters") or "").strip()
            if ch:
                _register(
                    names_from_structured_characters_field(ch),
                    profiles_from_structured_characters_field(ch),
                    src,
                )
        else:
            merged = (beat.get("merged") or beat.get("merged_outline") or "").strip()
            if merged:
                from narrativeloom.utils.display_utils import extract_sculptor_section_text

                sculptor_body = extract_sculptor_section_text(merged)
                _register(
                    names_from_functional_outline(merged),
                    profiles_from_structured_characters_field(sculptor_body),
                    src,
                )

    ordered = list(entries.values())
    seed_order = extract_seed_cast_names(seed)
    if seed_order:
        ordered.sort(
            key=lambda e: (
                0 if e.name in seed_order else 1,
                seed_order.index(e.name) if e.name in seed_order else 999,
                e.name,
            )
        )
    return GlobalCharacterList(entries=ordered)


def fallback_name_from_global_cast(
    existing: List[str],
    global_cast: Sequence[str],
    *,
    context: str = "",
) -> str:
    """从全局清单补位，不扫描散文正文。"""
    from narrativeloom.domain.character_names import (
        _is_subname_of_compound_cast,
        _scrub_cast_name,
    )

    ex = set(existing)
    for n in global_cast:
        if not n or n in ex:
            continue
        if _is_subname_of_compound_cast(n, existing):
            continue
        clean = _scrub_cast_name(n, existing, context=context)
        if clean and clean not in ex:
            return clean
    return ""
