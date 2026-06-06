# -*- coding: utf-8 -*-
"""PlotController（Layer 4）：Beat 人物一致性启发式校验（无额外 LLM 调用）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Set

from narrativeloom.domain.global_character_list import (
    GlobalCharacterList,
    names_from_structured_characters_field,
)


@dataclass
class CharacterConsistencyIssue:
    kind: str
    message: str
    name: str = ""


def check_beat_character_consistency(
    *,
    global_list: GlobalCharacterList,
    current_characters: str,
    locked_names: Optional[Sequence[str]] = None,
) -> List[CharacterConsistencyIssue]:
    """比对本轮 characters 与全局清单，标记改名/消失/突兀新增（启发式）。"""
    issues: List[CharacterConsistencyIssue] = []
    current = names_from_structured_characters_field(current_characters)
    current_set: Set[str] = set(current)
    global_names: Set[str] = set(global_list.names)
    locked: Set[str] = set(locked_names or [])

    for lk in locked:
        if lk and lk not in current_set:
            issues.append(
                CharacterConsistencyIssue(
                    kind="vanished_locked",
                    name=lk,
                    message=f"锁定人物「{lk}」未出现在本节 characters 中",
                )
            )

    for n in current:
        if n in global_names:
            continue
        if n in locked:
            continue
        issues.append(
            CharacterConsistencyIssue(
                kind="unexpected_new",
                name=n,
                message=f"「{n}」不在全局角色清单中，疑似无铺垫新增",
            )
        )

    for gn in global_names:
        if gn in locked and gn not in current_set:
            continue
        if gn in current_set:
            continue
        if gn in locked:
            issues.append(
                CharacterConsistencyIssue(
                    kind="vanished_global",
                    name=gn,
                    message=f"全局人物「{gn}」在本节 characters 中消失",
                )
            )

    return issues


def format_consistency_issues(issues: Sequence[CharacterConsistencyIssue], lang: str = "zh") -> str:
    if not issues:
        return ""
    if lang == "en":
        head = "Character consistency notes:"
    else:
        head = "人物一致性提示："
    return head + "\n" + "\n".join(f"- {x.message}" for x in issues[:6])
