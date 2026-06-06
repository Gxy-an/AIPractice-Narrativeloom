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
    ctx = f"{n}\n{desc}"
    if not n or _REJECT_NAME_FRAG.search(n) or is_false_person_name(n, context=ctx):
        return False
    if _is_seed_cast_name(n, context=ctx):
        return bool((desc or "").strip()) and len((desc or "").strip()) >= 2
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


_DESCRIPTOR_NAME = re.compile(
    r"^(沾满|戴着|戴圆|万物|炭灰|面粉|猪圈|模特|墙上|最后|晚餐|圆框|画笔|油彩|"
    r"双手|一手|一手|背景|前景|画面|构图|颜料|墙壁|墙皮|泥墙|"
    r"严谨|务实|当前|本节|状态|动机|性格|身份|任务|张力|高潮|转折|悬念|"
    r"核心|戏剧|情节|剧情|伏笔|主题|矛盾|冲突|节奏|"
    r"黎明|黄昏|清晨|午夜|正午|凌晨|傍晚|拂晓|深夜|白天|夜晚|上午|下午|中午|"
    r"周一|周二|周三|周四|周五|周六|周日|周天|"
    r"周[一二三四五六日天][上下]?|"
    r"陶罐|瓷罐|旧罐|空罐|"
    r"他|她|它|我|你|您|们|这|那|其|某|各|每|两|三|四|五|六|七|八|九|十|"
    r"十二|一头|一头|一头猪|模特是)"
)

_TIME_POINT_WORDS = frozenset(
    {
        "黎明",
        "黄昏",
        "清晨",
        "午夜",
        "正午",
        "凌晨",
        "傍晚",
        "拂晓",
        "深夜",
        "白天",
        "夜晚",
        "上午",
        "下午",
        "中午",
        "早间",
        "晚间",
        "子时",
        "丑时",
        "寅时",
        "卯时",
        "辰时",
        "巳时",
        "午时",
        "未时",
        "申时",
        "酉时",
        "戌时",
        "亥时",
        "周一",
        "周二",
        "周三",
        "周四",
        "周五",
        "周六",
        "周日",
        "周天",
        "星期一",
        "星期二",
        "星期三",
        "星期四",
        "星期五",
        "星期六",
        "星期日",
        "星期天",
    }
)

_WEEKDAY_TIME_FRAGMENT = re.compile(r"^周[一二三四五六日天][上下]?$")

_OBJECT_LIKE_NAME = re.compile(
    r"^(?:旧|新|小|大|古|破|空|老|红|白|黑|青|黄|灰|铜|铁|木|石|陶|瓷|玻璃|"
    r"银|金|铜|铁|木|石|竹|布|纸|皮|毛|棉|麻|丝|草|花|叶|枝|根|"
    r"猪|狗|猫|鸡|鸭|鱼|鸟|马|牛|羊|"
    r")*(?:"
    r"罐|瓶|杯|碗|盘|碟|壶|筒|桶|箱|盒|笼|篮|盆|缸|槽|锅|炉|灶|烟囱|"
    r"桌|椅|凳|床|柜|架|栏|门|窗|墙|砖|瓦|柱|梁|梯|锁|匙|钥|镜|钟|表|"
    r"伞|扇|绳|线|链|环|针|钉|锤|斧|铲|刀|剪|包|袋|布|毯|席|垫|"
    r"树|花|草|叶|石|岩|沙|泥|土|水|火|烟|雾|雨|雪|风|云|月|日|星|"
    r"照|片|书|本|页|纸|笔|墨|画|卷|"
    r")$"
)


def is_false_person_name(name: str, *, context: str = "") -> bool:
    """时间点、星期片段、器物/环境词等，不得当作人物姓名。"""
    n = (name or "").strip()
    if not n:
        return True
    if _is_compound_cast_name(n) or _is_seed_cast_name(n, context=context):
        return False
    if n in _TIME_POINT_WORDS or _WEEKDAY_TIME_FRAGMENT.match(n):
        return True
    if len(n) == 3 and n[0] == "周" and n[2] in "上下":
        return True
    if _OBJECT_LIKE_NAME.match(n):
        return True
    if _DESCRIPTOR_NAME.search(n):
        return True
    blob = f"{n}\n{context or ''}"
    if re.search(rf"时间[：:]\s*[^\n]*{re.escape(n)}", blob):
        return True
    if re.search(rf"{re.escape(n)}(?:时分|点钟|时光|之后|之前|左右|刚过|将近)", blob):
        return True
    if re.search(rf"周[一二三四五六日天][上下]?午", blob) and re.match(r"^周[一二三四五六日天]", n):
        return True
    if re.search(r"(?:陶|瓷|铁|木|石|旧|空)(?:罐|瓶|杯|碗)", blob) and n in blob:
        if len(n) <= 3 and _OBJECT_LIKE_NAME.match(n):
            return True
    return False


def _is_locked_cast_name(
    name: str,
    *,
    locked: Optional[List[str]] = None,
    context: str = "",
) -> bool:
    """锁定/种子既定人物：不受 2～4 字宽松规则与 strict 姓名字符集限制。"""
    n = (name or "").strip()
    if not n:
        return False
    for lk in locked or []:
        if n == lk or lk.startswith(n) or n.startswith(lk):
            return True
    return _is_seed_cast_name(n, context=context)


def _is_narrative_cast_candidate(name: str, *, context: str = "") -> bool:
    """从叙事文本补人时用的较严规则：禁止把形容词/代词片段当人名。"""
    n = (name or "").strip()
    if not n or _REJECT_NAME_FRAG.search(n) or is_false_person_name(n, context=context):
        return False
    if _is_compound_cast_name(n):
        return True
    if _is_seed_cast_name(n, context=context):
        return True
    if _is_person(n):
        return True
    if re.search(r"[·．\.]", n):
        return False
    if len(n) < 2 or len(n) > 4:
        return False
    if re.search(r"(的$|地$|得$|着$|了$|过$|在$|把$|被$|与$|和$|及$|或$)", n):
        return False
    return bool(re.fullmatch(r"[\u4e00-\u9fff]{2,4}", n))


def _is_loose_cast_name(name: str, *, context: str = "") -> bool:
    """剧情并列中的短人名（兼容旧调用）；功能化补人请优先用 _is_narrative_cast_candidate。"""
    return _is_narrative_cast_candidate(name, context=context)


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


def _is_compound_cast_name(name: str) -> bool:
    """「达芬奇·狗剩」类复合名；纯结构判定，不调用 _is_person 以免与 display_utils 循环。"""
    n = (name or "").strip()
    if not n or not re.search(r"[·．\.]", n):
        return False
    parts = [p for p in re.split(r"[·．\.]", n) if p]
    return bool(parts) and all(re.fullmatch(r"[\u4e00-\u9fffA-Za-z]+", p) for p in parts)


def _is_seed_cast_name(name: str, *, context: str = "") -> bool:
    n = (name or "").strip()
    if not n or len(n) < 2 or len(n) > 24:
        return False
    if _REJECT_NAME_FRAG.search(n):
        return False
    if _is_compound_cast_name(n):
        return True
    ctx = (context or "").strip()
    if not ctx or n not in ctx:
        return False
    if _DESCRIPTOR_NAME.search(n):
        return False
    if re.match(rf"^{re.escape(n)}(?=[在将向对把被给让与和、，,。；：:\s]|$)", ctx):
        return bool(re.fullmatch(r"[\u4e00-\u9fffA-Za-z]{2,12}", n))
    return False


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
            n = (raw or "").strip()
            if not n:
                continue
            resolved = resolve_name(n) or n
            if _is_compound_cast_name(resolved) or _is_seed_cast_name(resolved, context=resolved):
                canon = resolved
            else:
                canon = resolved if resolved and _is_person(resolved) else ""
            if canon and canon not in seen:
                seen.add(canon)
                out.append(canon)
    return out


def _resolve_cast_name(name: str, anchors: List[str], *, context: str = "") -> str:
    """将剧情中的简称（如「达芬奇」）对齐到种子全名（「达芬奇·狗剩」）。"""
    n = (name or "").strip()
    if not n:
        return ""
    for a in anchors:
        if not a:
            continue
        if n == a:
            return a
        if a.startswith(n) or n.startswith(a):
            return a
        parts = [p for p in re.split(r"[·．\.]", a) if p]
        if n in parts:
            return a
    expanded = expand_name_from_context(n, context)
    if expanded:
        for a in anchors:
            if expanded == a or a.startswith(expanded) or expanded.startswith(a):
                return a
        if _is_narrative_cast_candidate(expanded, context=context):
            return expanded
    return n if _is_narrative_cast_candidate(n, context=context) else ""


def _build_sculptor_allowlist(
    *,
    seed: str,
    locked_names: Optional[List[str]],
    plot_sources: List[str],
    setting_context: str = "",
    body: str = "",
) -> List[str]:
    """人物塑造师允许出现的姓名：种子/锁定优先，其余须出现在其它职能叙事中。"""
    _ = body
    narrative = "\n".join(s for s in (plot_sources or []) if (s or "").strip())
    cross = "\n".join(x for x in (seed, narrative, setting_context) if (x or "").strip())
    anchors = merge_unique_names(list(locked_names or []), extract_seed_cast_names(seed))
    allow: List[str] = []
    for n in anchors:
        if n and n not in allow:
            allow.append(n)
    for raw in extract_cast_from_narrative(cross, limit=12):
        resolved = _resolve_cast_name(raw, anchors, context=cross)
        if resolved and resolved not in allow:
            allow.append(resolved)
    for a in list(anchors):
        for part in re.split(r"[·．\.]", a):
            if len(part) >= 2 and part in cross and a not in allow:
                allow.append(a)
                break
    return allow


def _is_blocked_sculptor_invention(
    name: str,
    *,
    anchors: List[str],
    cross: str = "",
) -> bool:
    """拒绝描述词/模板泄漏名；允许剧情或塑造师块中的合法新角色。"""
    n = (name or "").strip()
    if not n or is_false_person_name(n, context=f"{n}\n{cross}"):
        return True
    if _resolve_cast_name(n, anchors, context=cross) in anchors:
        return False
    if n in cross or any(p in cross for p in re.split(r"[·．\.]", n) if len(p) >= 2):
        return False
    if re.match(r"^阿依古", n) and not re.search(r"阿依古", cross) and not any(
        "阿依古" in a for a in anchors
    ):
        return True
    return False


def _sculptor_fill_candidates(
    valid_lines: Dict[str, str],
    *,
    anchors: List[str],
    cross: str,
    full: str,
) -> List[str]:
    """塑造师块中可用于补位的合法姓名（不含已锁定/叙事既定者）。"""
    anchor_set = set(anchors)
    out: List[str] = []
    for name, line in valid_lines.items():
        desc = line.split("：", 1)[-1] if "：" in line else ""
        if name in anchor_set or name in out:
            continue
        if not _valid_sculptor_entry(name, desc):
            continue
        if _is_blocked_sculptor_invention(name, anchors=anchors, cross=cross):
            continue
        out.append(name)
    if not out:
        for name in extract_cast_from_narrative(valid_lines and "\n".join(valid_lines.values()) or "", limit=8):
            if name in anchor_set or name in out:
                continue
            if _is_narrative_cast_candidate(name, context=full) and not _is_blocked_sculptor_invention(
                name, anchors=anchors, cross=cross
            ):
                out.append(name)
    return out


def _fallback_supplementary_name(existing: List[str], *, full: str, seed: str) -> str:
    """人数仍不足时，从设定/剧情角色词推断一个不与既有重复的中文名。"""
    blob = f"{seed}\n{full}"
    role_hints = (
        "房东",
        "老板",
        "管事",
        "看守",
        "邻居",
        "同伴",
        "助手",
        "模特",
        "教授",
        "学生",
        "村民",
        "路人",
    )
    for hint in role_hints:
        if hint not in blob:
            continue
        for m in re.finditer(rf"({hint}[\u4e00-\u9fff]{{0,2}})", blob):
            cand = m.group(1)
            if len(cand) >= 2 and cand not in existing and _is_narrative_cast_candidate(cand, context=blob):
                return cand
    idx = len(existing) + 1
    generic = f"配角{idx}"
    while generic in existing:
        idx += 1
        generic = f"配角{idx}"
    return generic


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
    seed: str = "",
) -> str:
    """补全人物塑造师：种子/锁定人物强制保留；补满 target；拒绝描述词与模板泄漏。"""
    narrative = "\n".join(s for s in (plot_sources or []) if (s or "").strip())
    extract_blob = f"{body}\n{narrative}".strip()
    full = f"{seed}\n{extract_blob}\n{setting_context}".strip()
    target = max(1, min(int(target), 14))
    cross = "\n".join(x for x in (seed, narrative, setting_context) if (x or "").strip())
    anchors = _build_sculptor_allowlist(
        seed=seed,
        locked_names=locked_names,
        plot_sources=list(plot_sources or []),
        setting_context=setting_context,
    )
    valid_lines = parse_colon_lines(body, context=full)
    fill_candidates = _sculptor_fill_candidates(
        valid_lines, anchors=anchors, cross=cross, full=full
    )

    cast: List[str] = []
    for n in anchors:
        if len(cast) >= target:
            break
        resolved = _resolve_cast_name(n, anchors, context=full) or n
        if resolved not in cast:
            cast.append(resolved)
    for n in fill_candidates:
        if len(cast) >= target:
            break
        resolved = _resolve_cast_name(n, anchors, context=full) or n
        if resolved and resolved not in cast:
            cast.append(resolved)
    while len(cast) < target:
        extra = _fallback_supplementary_name(cast, full=full, seed=seed)
        if extra in cast:
            break
        cast.append(extra)
    cast = cast[:target]

    lines: List[str] = []
    for n in cast:
        picked = valid_lines.get(n)
        if not picked:
            for k, v in valid_lines.items():
                if n == k or n.startswith(k) or k.startswith(n):
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
    seed: str = "",
) -> str:
    target = max(2, int(target_total or 2))
    locked = merge_unique_names(list(locked_names or []), extract_seed_cast_names(seed))
    return complete_sculptor_section(
        fragment,
        plot_sources=[fragment],
        locked_names=locked,
        target=target,
        seed=seed,
    )
