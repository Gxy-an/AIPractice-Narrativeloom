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
    r"严谨|务实|状态|动机|性格|工程|计划$|程计划|"
    r"交换|分享|交易|传递|假装|佯装|装作|"
    r"(?<![\u4e00-\u9fff])(?:队员|教授|工程师|研究员|研究生|生命体)$)"
)
_ACTION_OR_NOUN_NAME = frozenset(
    {
        "交换",
        "分享",
        "交易",
        "传递",
        "消息",
        "警告",
        "警觉",
        "警惕",
        "假装",
        "佯装",
        "装作",
    }
)


def _canonical(name: str) -> str:
    from narrativeloom.utils.display_utils import _canonical_person_name

    return _canonical_person_name(name)


def _is_person(name: str) -> bool:
    from narrativeloom.utils.display_utils import _is_pure_person_name

    n = _canonical(name)
    if not n or _REJECT_NAME_FRAG.search(n):
        return False
    if re.match(r"^老[\u4e00-\u9fff]{1,2}$", n):
        return True
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
    r"严谨|务实|当前|本节|状态|动机|性格|任务|张力|高潮|转折|悬念|"
    r"核心|戏剧|情节|剧情|伏笔|主题|矛盾|冲突|节奏|"
    r"黎明|黄昏|清晨|午夜|正午|凌晨|傍晚|拂晓|深夜|白天|夜晚|上午|下午|中午|"
    r"周一|周二|周三|周四|周五|周六|周日|周天|"
    r"周[一二三四五六日天][上下]?|"
    r"陶罐|瓷罐|旧罐|空罐|"
    r"走廊|尽头|深处|远处|方向|油田|油城|宿舍|大厅|核验|新村|管控|"
    r"探井|内务|特工|荧光|消毒|玛依|克拉玛|"
    r"苏联|美国|英国|法国|日本|德国|"
    r"任何|飘着|散着|弥漫|悬浮|漂浮|麦秸|半透明|"
    r"时被|当时|当夜|当被|"
    r"他|她|它|我|你|您|们|这|那|其|某|各|每|两|三|四|五|六|七|八|九|十|"
    r"十二|一头|模特是|交换|分享|交易)"
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
    r"照|片|书|本|页|纸|笔|墨|画|卷|墨|水|"
    r")$"
)


_DEVICE_OR_MACHINE = re.compile(
    r"(?:嗅探器|探测器|扫描仪|监控器|监视器|警报器|报警器|无人机|机器人|"
    r"终端机|处理器|计算机|服务器|执法器|巡逻机|机械|机甲|"
    r"装置|设备|仪器|器械|程序|系统|算法|型号|S-\d|Model)"
)
_ABSTRACT_THEME_NAME = re.compile(
    r"^(神圣|生存|理想|现实|构图|逻辑|主题|命运|车间|清理|修理|理车|核心|戏剧|情节|剧情)?"
    r"(构图|现实|逻辑|法则|隐喻|象征|主题|命运|矛盾|冲突|张力|生存|神圣|理想|现实|车间|时段)$"
)
_ENVIRONMENT_PLACE_SUFFIX = re.compile(
    r"(尽头|深处|远处|方向|油田|油城|宿舍|大厅|走廊|核验|新村|管控区|探井|工人村|"
    r"核验室|大厅里|通道|出口|入口|转角|拐角|尽头处)$"
)
_ENVIRONMENT_PLACE_WORD = re.compile(
    r"(走廊|油田|油城|宿舍|大厅|核验|新村|管控|探井|内务|特工|荧光|消毒|"
    r"玛依油田|克拉玛依|油field|identity hall)"
)
_COUNTRY_OR_BLOC_NAME = frozenset(
    {
        "苏联",
        "美国",
        "英国",
        "法国",
        "日本",
        "德国",
        "中国",
        "俄国",
        "俄罗斯",
    }
)
_ADVERB_GLUED_NAME_SUFFIX = ("远远", "忽然", "突然", "悄悄", "缓缓", "猛然")


def looks_like_environment_or_place_name(name: str, *, context: str = "") -> bool:
    """环境/地点/国家名，不得当作人物姓名。"""
    n = (name or "").strip()
    if not n:
        return True
    if n in _COUNTRY_OR_BLOC_NAME:
        return True
    if _ENVIRONMENT_PLACE_SUFFIX.search(n):
        return True
    if re.search(r"(油田|油城|宿舍|大厅|走廊|核验|新村|管控|探井)", n):
        return True
    if re.match(r"^(走廊|导师|内务|核验|荧光|消毒|玛依|克拉玛)", n):
        return True
    blob = context or ""
    if blob and re.search(
        rf"(?:地点|时间|场景|规则|位于|地处)[：:\s][^\n]*{re.escape(n)}",
        blob,
    ):
        return True
    if blob and re.search(rf"{re.escape(n)}(?:里|内|中|处|方向|的)", blob):
        if len(n) <= 5 and not re.search(r"(陌生人|教授|师傅|医师|学生|记者)$", n):
            return True
    return False


def parse_user_protagonist_names(text: str) -> List[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    parts = re.split(r"[,，、\n;；|]+", raw)
    out: List[str] = []
    for p in parts:
        n = p.strip()
        if not n or n in out:
            continue
        from narrativeloom.domain.character_names import _is_compound_cast_name

        if _is_compound_cast_name(n):
            out.append(n)
            continue
        if looks_like_environment_or_place_name(n):
            continue
        if is_false_person_name(n, context=n):
            continue
        out.append(n)
    return out


def adaptive_character_target(
    *,
    beat_index: int,
    base: int,
    locked_count: int,
    pool: str = "function",
) -> int:
    """随情节推进缓慢扩容，但不超过上限。"""
    base = max(2, int(base or 2))
    locked_count = max(0, int(locked_count or 0))
    arc_bonus = min(2, max(0, beat_index // 2))
    if beat_index <= 0:
        target = max(base, locked_count, 2)
    else:
        target = max(base + arc_bonus, locked_count)
    cap = 8 if pool in ("genre", "typified") else 14
    return min(cap, max(2, target))


def _resolve_longest_cast_in_context(
    name: str,
    context: str,
    *,
    locked: Optional[List[str]] = None,
) -> str:
    """将「铁牛远远→赵铁牛」「韩星结→韩星」等规整为上下文完整人名。

    禁止把叙事短语（如「艾买提在天山驿站」）误扩展为人名。
    """
    n = (name or "").strip()
    if not n or not context:
        return n
    locked = [x for x in (locked or []) if (x or "").strip()]

    if n in locked:
        return n
    for lk in locked:
        if n == lk:
            return lk
        if re.search(r"[·．\.]", lk):
            parts = [p for p in re.split(r"[·．\.]", lk) if p]
            if n in parts:
                return lk

    _GLUED_TAIL = _ADVERB_GLUED_NAME_SUFFIX + ("结", "端", "处", "深", "警", "清", "起", "藏", "都")
    looks_glued = any(n.endswith(suf) and len(n) > len(suf) + 1 for suf in _GLUED_TAIL)
    if (
        not looks_glued
        and _is_narrative_cast_candidate(n, context=context)
        and n in context
        and not is_false_person_name(n, context=n)
    ):
        return n

    stem = n
    for suf in _GLUED_TAIL:
        if stem.endswith(suf) and len(stem) > len(suf) + 1:
            candidate = stem[: -len(suf)]
            if candidate in context:
                stem = candidate
                break
            for lk in locked:
                if candidate in lk or lk.endswith(candidate):
                    stem = lk
                    break
            else:
                continue
            break

    valid_names: List[str] = []
    for lk in locked:
        if lk not in valid_names:
            valid_names.append(lk)
    for cand in extract_cast_from_narrative(context, limit=16):
        if cand not in valid_names and (
            _is_narrative_cast_candidate(cand, context=context)
            or _is_seed_cast_name(cand, context=context)
            or cand in locked
        ):
            valid_names.append(cand)

    best = stem
    for cand in valid_names:
        if not cand or cand == stem:
            continue
        if cand.endswith(stem) and len(cand) <= len(stem) + 2:
            if len(cand) >= len(best):
                best = cand
        elif stem.endswith(cand) and len(stem) > len(cand):
            if _is_narrative_cast_candidate(cand, context=context):
                best = cand
        elif stem in cand and cand in locked and len(cand) >= len(best):
            best = cand

    for lk in locked:
        if (stem in lk or lk.endswith(stem)) and len(lk) >= len(best):
            best = lk

    if len(best) > 4 and not (
        _is_compound_cast_name(best)
        or re.search(r"(陌生人|人影|身影|老者|少年|女子|男子|掌柜|店主|特工)$", best)
    ):
        if _is_narrative_cast_candidate(stem, context=context):
            return stem
    if re.search(r"[向与的在给了把被将分享交换]", best):
        if _is_narrative_cast_candidate(stem, context=context):
            return stem
        return n if _is_narrative_cast_candidate(n, context=context) else stem
    return best or n


def is_false_person_name(name: str, *, context: str = "") -> bool:
    """时间点、星期片段、器物/环境词、设备名、抽象主题词等，不得当作人物姓名。"""
    n = (name or "").strip()
    if not n:
        return True
    if re.fullmatch(r"(特工|官员|核验官|守卫|老僧)", n):
        return False
    if _DEVICE_OR_MACHINE.search(n):
        return True
    if _is_compound_cast_name(n) or _is_seed_cast_name(n, context=context):
        return False
    if looks_like_environment_or_place_name(n, context=context):
        return True
    if _ABSTRACT_THEME_NAME.match(n):
        return True
    if "的" in n and not _is_compound_cast_name(n):
        return True
    if n in _ACTION_OR_NOUN_NAME:
        return True
    if re.search(r"假装|佯装|装作", n):
        return True
    if n.endswith("警") and len(n) <= 5:
        return True
    if re.search(r"(在一|在旁|在场|在此|在此地|一旁|一边)$", n):
        return True
    if re.search(r"车间", n) and len(n) <= 6:
        return True
    if re.match(r"^(个人|国家|社会|艺术|生存|理想|神圣|核心).{0,2}(安危|现实|矛盾|冲突|构图|逻辑)$", n):
        return True
    if len(n) >= 3 and re.search(r"(假|借|贷|问|说|看|听|走|跑|来|去|在|到|向|把|被|将|给|让|叫|请|想|能|会|可|应|该|须|需)$", n):
        stem = n[:-1]
        if stem and re.search(rf"{re.escape(stem)}[假借贷问说看听走来去到向把被将给让叫请想能会可应该须需]", context or n):
            return True
    if n in _TIME_POINT_WORDS or _WEEKDAY_TIME_FRAGMENT.match(n):
        return True
    if len(n) == 3 and n[0] == "周" and n[2] in "上下":
        return True
    if _OBJECT_LIKE_NAME.match(n):
        return True
    if n in ("墨水", "红墨", "颜料", "骨片", "银币"):
        return True
    if n in ("假借", "采访", "接近", "观察", "发现", "清理", "整理", "威胁", "调解"):
        return True
    if re.search(r"假借", n):
        return True
    if re.match(r"^[假借][采访访]", n) or n in ("间时", "假采访", "假借访"):
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


_SCENE_FRAGMENT = re.compile(
    r"(猪圈|墙上|壁画|视频|作画|模特|晚餐|颜料|偷|拍|在猪|圈作|圈墙|的达|芬奇|"
    r"乡村|城镇|城市|地区|场景|地点|时间|型号|系列|编号|"
    r"要毁|毁掉|毁颜|颜料|威胁|关键|剧情|本节|出场|行动|动机|"
    r"铁匠|管事|庄园|契约|墨水|红墨|网红|想借|借网|"
    r"车间|清理|修理|时段|构图|神圣|生存|现实|"
    r"走廊|油田|油城|宿舍|大厅|核验|新村|探井|"
    r"猪|网|红)"
)


def _looks_like_scene_fragment(name: str) -> bool:
    n = (name or "").strip()
    if not n or _is_compound_cast_name(n):
        return False
    if len(n) >= 3 and n[-1] in "前后里外中内":
        return True
    if len(n) >= 4 and n.endswith("时") and not _is_person(n):
        return True
    if len(n) >= 3 and n.endswith("时") and re.search(r"(发现|清理|整理|修理|清理|采访|接近|观察)", n):
        return True
    return bool(_SCENE_FRAGMENT.search(n))


def _looks_like_place_name_token(name: str, *, context: str = "") -> bool:
    """「托斯卡乡村」等地名片段，不得当作人物。"""
    n = (name or "").strip()
    blob = context or ""
    if not n or not blob:
        return False
    if re.search(
        rf"{re.escape(n)}(?:乡村|古镇|古城|城市|小镇|地区|区域|国家|省份|省|州|岛|半岛|平原|流域|山区|草原|沙漠|港口|码头)",
        blob,
    ):
        return True
    if re.search(rf"(?:地点|位于|地处)[：:\s][^\n]*{re.escape(n)}", blob):
        return True
    return False


def _is_narrative_cast_candidate(name: str, *, context: str = "") -> bool:
    """从叙事文本补人时用的较严规则：禁止把形容词/代词片段当人名。"""
    n = (name or "").strip()
    if not n or _REJECT_NAME_FRAG.search(n) or is_false_person_name(n, context=context):
        return False
    if _looks_like_place_name_token(n, context=context):
        return False
    if _looks_like_scene_fragment(n):
        return False
    if _is_compound_cast_name(n):
        return True
    if _is_seed_cast_name(n, context=context):
        return True
    if _is_person(n):
        return True
    if re.search(r"[·．\.]", n):
        return False
    if len(n) < 2:
        return False
    if len(n) > 4 and not re.search(r"(陌生人|人影|身影|老者|少年|女子|男子|掌柜|店主)$", n):
        return False
    if len(n) > 6:
        return False
    if re.search(r"(的$|地$|得$|着$|了$|过$|在$|把$|被$|与$|和$|及$|或$)", n):
        return False
    if re.search(r"(陌生人|人影|身影|老者|少年|女子|男子|掌柜|店主|特工|官员|核验官)$", n):
        return True
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
    r"([\u4e00-\u9fffA-Za-z]{2,10}(?:[·．\.][\u4e00-\u9fffA-Za-z]{1,8})+)"
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
    if re.search(rf"[-·•]\s*{re.escape(n)}\s*：", ctx):
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


_VERB_AFTER_NAME = (
    "看见",
    "看到",
    "说道",
    "威胁",
    "发现",
    "赶走",
    "砸碎",
    "停在",
    "偷拍",
    "遇到",
    "遇见",
    "见到",
    "出面",
    "撞见",
    "调解",
    "撞见",
    "拿出",
    "掏出",
    "假借",
    "接近",
    "采访",
    "观察",
    "监视",
    "跟踪",
    "砸碎",
    "假装",
    "佯装",
    "装作",
    "撕下",
    "追问",
    "看守",
    "一旁",
)
_VERB_AFTER_NAME_RE = "|".join(
    sorted({re.escape(v) for v in _VERB_AFTER_NAME}, key=len, reverse=True)
)


_VERB_NAME_TAIL = (
    "出面",
    "撞见",
    "看见",
    "听见",
    "调解",
    "假借",
    "采访",
    "接近",
    "观察",
    "发现",
    "清理",
)


def _strip_verbed_name_tail(name: str) -> str:
    n = (name or "").strip()
    for tail in sorted(_VERB_NAME_TAIL, key=len, reverse=True):
        if n.endswith(tail) and len(n) > len(tail):
            return n[: -len(tail)]
    return n


def _extract_verbed_cn_names(text: str, *, limit: int = 8) -> List[str]:
    """剧情句中「朱塞佩看见…」「韩星假借…」类 2～4 字人名（动词锚定，避免误拆）。"""
    blob = text or ""
    if not blob:
        return []
    found: List[str] = []
    verbs = sorted(_VERB_AFTER_NAME, key=len, reverse=True)
    for m in re.finditer("|".join(re.escape(v) for v in verbs), blob):
        vstart = m.start()
        if vstart < 2:
            continue
        picked = ""
        for size in (4, 3, 2):
            if vstart < size:
                continue
            name = blob[vstart - size : vstart]
            if not re.fullmatch(r"[\u4e00-\u9fff]+", name):
                continue
            name = _strip_verbed_name_tail(name)
            if not name or not _is_narrative_cast_candidate(name, context=blob):
                continue
            picked = name
            break
        if picked and picked not in found:
            found.append(picked)
        if len(found) >= limit:
            break
    for m in re.finditer(r"([\u4e00-\u9fff]{2,4})(?=见[\u4e00-\u9fff])", blob):
        name = m.group(1)
        if name.endswith(("撞", "听", "看")) and len(name) >= 3:
            name = name[:-1]
        name = _strip_verbed_name_tail(name)
        if not name or not _is_narrative_cast_candidate(name, context=blob):
            continue
        if name not in found:
            found.append(name)
        if len(found) >= limit:
            break
    return found


def extract_cast_from_narrative(text: str, *, limit: int = 8) -> List[str]:
    """从剧情文本提取人物：并列结构 + display_utils 严格扫描。"""
    from narrativeloom.utils.display_utils import extract_names_from_narrative, extract_relation_names

    blob = (text or "").strip()
    if not blob:
        return []

    cast: List[str] = []
    for n in (
        _extract_verbed_cn_names(blob, limit=limit)
        + _extract_dyads(blob)
        + _extract_quoted(blob)
        + _extract_new_role(blob)
    ):
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
        if n in out:
            continue
        if _is_narrative_cast_candidate(n, context=blob) or _is_person(n):
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
    allow_body_unanchored: bool = False,
) -> List[str]:
    """人物塑造师允许出现的姓名：种子/锁定优先，其余须出现在其它职能叙事中。"""
    narrative = "\n".join(s for s in (plot_sources or []) if (s or "").strip())
    cross = "\n".join(
        x for x in (seed, body, narrative, setting_context) if (x or "").strip()
    )
    plot_cross = "\n".join(
        x for x in (seed, narrative, setting_context) if (x or "").strip()
    )
    anchors = merge_unique_names(list(locked_names or []), extract_seed_cast_names(seed))
    allow: List[str] = []
    for n in anchors:
        if n and n not in allow:
            allow.append(n)
    for raw in extract_cast_from_narrative(plot_cross, limit=12):
        resolved = _resolve_cast_name(raw, anchors, context=plot_cross) or raw
        clean = _scrub_cast_name(
            resolved, allow, context=plot_cross, locked=anchors
        ) or resolved
        if clean and clean not in allow:
            allow.append(clean)
    if (body or "").strip():
        for name, line in parse_colon_lines(body, context=cross).items():
            desc = line.split("：", 1)[-1] if "：" in line else ""
            if _is_blocked_sculptor_invention(name, anchors=anchors, cross=plot_cross):
                continue
            if not _valid_sculptor_entry(name, desc):
                continue
            # 在功能化塑造师场景下，允许正文中出现且通过校验的姓名成为 allowlist（即使未出现在其它叙事片段中）
            grounded = (
                name in plot_cross
                or any(
                    p in plot_cross
                    for p in re.split(r"[·．\.]", name)
                    if len(p) >= 2
                )
                or _is_compound_cast_name(name)
                or name in anchors
                or (allow_body_unanchored and name in body)
            )
            if not grounded:
                continue
            clean = _scrub_cast_name(name, allow, context=plot_cross, locked=anchors)
            if clean and clean not in allow:
                allow.append(clean)
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
    """拒绝描述词/模板泄漏名；cross 须为种子+剧情叙事，不含塑造师正文。"""
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
    allowlist: Optional[List[str]] = None,
) -> List[str]:
    """塑造师块中可用于补位的合法姓名（须出现在跨职能白名单内）。"""
    anchor_set = set(anchors)
    allowed = list(allowlist or anchors)
    allow_set = set(allowed)
    out: List[str] = []
    for name, line in valid_lines.items():
        desc = line.split("：", 1)[-1] if "：" in line else ""
        if name in anchor_set or name in out:
            continue
        resolved = _resolve_cast_name(name, anchors, context=cross) or name
        if resolved not in allow_set and name not in allow_set:
            continue
        if not _valid_sculptor_entry(name, desc):
            continue
        if _is_blocked_sculptor_invention(name, anchors=anchors, cross=cross):
            continue
        out.append(resolved if resolved in allow_set else name)
    return out


def _cast_name_collides(existing: List[str], candidate: str) -> bool:
    """同一人物的不同误拆写法（马可 / 马可·猪倌 / 马可惊）视为冲突。"""
    c = (candidate or "").strip()
    if not c:
        return True
    c_root = re.split(r"[·．\.]", c, maxsplit=1)[0]
    for raw in existing:
        e = (raw or "").strip()
        if not e:
            continue
        if c == e:
            return True
        e_root = re.split(r"[·．\.]", e, maxsplit=1)[0]
        if len(c_root) >= 2 and len(e_root) >= 2 and c_root == e_root and c != e:
            return True
        if len(c) >= 2 and len(e) >= 2 and (e.startswith(c) or c.startswith(e)) and c != e:
            return True
    return False


def _trim_embedded_cast_name(name: str, context: str) -> str:
    """若姓名前缀粘连（如查周教授→周教授），对齐到上下文中的较短真名。"""
    n = (name or "").strip()
    if len(n) <= 3 or not context:
        return n
    for title in ("教授", "师傅", "医师", "医生", "同学", "学生", "老板", "僧"):
        for size in (1, 2):
            m = re.search(rf"([\u4e00-\u9fff]{{{size}}}{re.escape(title)})$", n)
            if not m or len(n) <= len(m.group(1)):
                continue
            cand = m.group(1)
            if cand in context or _is_narrative_cast_candidate(cand, context=context):
                n = cand
                break
        else:
            continue
        break
    if len(n) <= 3:
        return n
    best = n
    for m in re.finditer(r"[\u4e00-\u9fff]{2,4}", context):
        cand = m.group(0)
        if len(cand) >= len(n) or cand == n or not n.endswith(cand):
            continue
        if not _is_narrative_cast_candidate(cand, context=context):
            continue
        if len(cand) >= len(best) or best == name:
            best = cand
    return best


def _scrub_cast_name(
    name: str,
    existing: List[str],
    *,
    context: str = "",
    locked: Optional[List[str]] = None,
) -> str:
    """规整姓名并剔除动词粘连、前缀重复、占位配角名等。"""
    from narrativeloom.utils.display_utils import (
        _INVALID_NAME_PREFIX,
        _canonical_person_name,
        _normalize_sculptor_line_name,
    )

    locked_all = merge_unique_names(list(locked or []) + list(existing or []))
    raw = (name or "").strip()
    if not raw or re.fullmatch(r"配角\d+", raw):
        return ""
    if _INVALID_NAME_PREFIX.match(raw):
        return ""
    if re.search(r"假装|佯装|装作", raw):
        m = re.search(r"([\u4e00-\u9fff]{2,4})假装", context)
        if m:
            raw = m.group(1)
        else:
            return ""
    if _is_compound_cast_name(raw) or _is_seed_cast_name(raw, context=context):
        canon = raw
    else:
        canon = _normalize_sculptor_line_name(raw, context=context) or _canonical_person_name(raw)
        if not canon and _is_narrative_cast_candidate(raw, context=context):
            canon = raw
    skip_expand = (
        canon in locked_all
        or _is_compound_cast_name(canon)
        or _is_seed_cast_name(canon, context=context)
    )
    if canon and not skip_expand:
        expanded = expand_name_from_context(canon, context)
        if expanded:
            canon = expanded
        canon = _trim_embedded_cast_name(canon, context)
        resolved = _resolve_longest_cast_in_context(canon, context, locked=locked_all)
        if resolved:
            canon = resolved
    if not canon or re.fullmatch(r"配角\d+", canon):
        return ""
    if len(canon) >= 4 and canon.endswith("出面"):
        stem = canon[:-2]
        if stem and _is_narrative_cast_candidate(stem, context=context):
            canon = stem
    if is_false_person_name(canon, context=f"{canon}\n{context}"):
        return ""
    if _looks_like_scene_fragment(canon):
        return ""
    if not (
        _is_narrative_cast_candidate(canon, context=context)
        or _is_seed_cast_name(canon, context=context)
        or _is_compound_cast_name(canon)
        or re.search(r"(陌生人|人影|身影|特工|官员|核验官)$", canon)
    ):
        return ""
    if _cast_name_collides(existing, canon):
        return ""
    if _is_subname_of_compound_cast(canon, existing):
        return ""
    if len(canon) >= 3 and re.search(r"(假|借|贷)$", canon):
        stem = canon[:-1]
        if stem and re.search(rf"{re.escape(stem)}[假借贷]", context):
            stem_canon = _normalize_sculptor_line_name(stem, context=context) or _canonical_person_name(stem)
            if stem_canon and not is_false_person_name(stem_canon, context=f"{stem_canon}\n{context}"):
                if not _cast_name_collides(existing, stem_canon) and not _is_subname_of_compound_cast(
                    stem_canon, existing
                ):
                    return stem_canon
            return ""
    return canon


def _is_subname_of_compound_cast(name: str, anchors: List[str]) -> bool:
    """复合名（如达芬奇·狗剩）的片段（狗剩）不得单独入列。"""
    n = (name or "").strip()
    if not n:
        return False
    for anchor in anchors:
        a = (anchor or "").strip()
        if not a or n == a:
            continue
        if re.search(r"[·．\.]", a):
            parts = [p for p in re.split(r"[·．\.]", a) if p]
            if n in parts:
                return True
    return False


def _fallback_supplementary_names(
    existing: List[str],
    *,
    full: str,
    seed: str,
    narrative: str = "",
    limit: int = 12,
    plan_index: int = 0,
    avoid_names: Optional[List[str]] = None,
) -> List[str]:
    """从剧情/设定叙事中提取可用于补位的真实姓名（按优先级排序）。"""
    import random

    plot_blob = "\n".join(x for x in (seed, narrative, full) if (x or "").strip())
    events_blob = "\n".join(x for x in (seed, narrative) if (x or "").strip())
    avoid = {
        (n or "").strip()
        for n in (avoid_names or [])
        if (n or "").strip()
    }
    ranked = [
        n
        for n in extract_cast_from_narrative(plot_blob, limit=16)
        if _is_narrative_cast_candidate(n, context=plot_blob)
    ]
    in_events = sorted(
        [n for n in ranked if n in events_blob],
        key=lambda n: (-_mentions(events_blob, n), -len(n), ranked.index(n) if n in ranked else 99),
    )
    extras = [n for n in ranked if n not in in_events]
    rng = random.Random(hash((seed, plan_index, len(existing))))
    rng.shuffle(extras)
    ordered = in_events + extras
    out: List[str] = []
    for n in ordered:
        if n in avoid:
            continue
        if _is_subname_of_compound_cast(n, existing + out):
            continue
        clean = _scrub_cast_name(n, existing + out, context=plot_blob, locked=existing)
        if clean and clean not in existing and clean not in out and clean not in avoid:
            out.append(clean)
        if len(out) >= limit:
            break
    if len(out) >= limit:
        return out
    for role_noun in ("特工", "官员", "核验官", "守卫", "僧"):
        if role_noun in plot_blob and role_noun not in existing and role_noun not in out:
            if _is_narrative_cast_candidate(role_noun, context=plot_blob):
                out.append(role_noun)
            if len(out) >= limit:
                return out
    role_hints = (
        "铁匠",
        "管家",
        "神父",
        "商人",
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
        "僧",
        "师傅",
    )
    for hint in role_hints:
        if hint not in plot_blob:
            continue
        for m in re.finditer(rf"(?<![\u4e00-\u9fff])([\u4e00-\u9fff]{{1,2}}{re.escape(hint)})", plot_blob):
            clean = _scrub_cast_name(
                m.group(1), existing + out, context=plot_blob, locked=existing
            )
            if clean and clean not in existing and clean not in out:
                out.append(clean)
            if len(out) >= limit:
                return out
    for m in re.finditer(r"(老[\u4e00-\u9fff]{1,2})(?![\u4e00-\u9fff])", plot_blob):
        clean = _scrub_cast_name(
            m.group(1), existing + out, context=plot_blob, locked=existing
        )
        if clean and clean not in existing and clean not in out:
            out.append(clean)
        if len(out) >= limit:
            return out
    return out


def _fallback_supplementary_name(
    existing: List[str],
    *,
    full: str,
    seed: str,
    narrative: str = "",
    plan_index: int = 0,  # 新参数：计划索引，用于名字多样性
) -> str:
    """人数仍不足时，优先从剧情/设定叙事中提取尚未入列的真实姓名。"""
    names = _fallback_supplementary_names(
        existing, full=full, seed=seed, narrative=narrative, limit=1, plan_index=plan_index
    )
    return names[0] if names else ""


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
    prior_character_profiles: Optional[Dict[str, str]] = None,
    functional_mode: bool = False,
) -> str:
    """补全人物塑造师：统一走 sanitize_typified_characters 管线。"""
    from narrativeloom.utils.display_utils import sanitize_typified_characters

    prior_block = ""
    if prior_character_profiles:
        prior_block = "\n".join(
            f"- {k}：{v}" for k, v in prior_character_profiles.items() if k and v
        )
    narrative = "\n".join(s for s in (plot_sources or []) if (s or "").strip())
    out = sanitize_typified_characters(
        body,
        target=target,
        locked_names=locked_names,
        seed=seed,
        setting=setting_context,
        key_events=narrative,
        prior_characters_block=prior_block,
        strict_narrative_allowlist=True,
    )
    return out if (out or "").strip() else "—"


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
