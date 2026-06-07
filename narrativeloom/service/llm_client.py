# -*- coding: utf-8 -*-
"""叙事生成、RAG 增强、中等强度一致性审查、微调与头脑风暴。"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

from narrativeloom.config.settings import PROJECT_ROOT
from narrativeloom.utils.display_utils import (
    coerce_display_text,
    filter_character_sculptor_fragment,
    format_prose_paragraphs,
    key_events_meaningful,
    normalize_single_unified_outline,
    parse_merge_role_sections,
    scrub_expanded_prose_artifacts,
    scrub_functional_fragment,
    split_concatenated_unified_plans,
    strip_trailing_json_leak,
    normalize_typified_key_events,
    sanitize_typified_characters,
    typified_characters_meaningful,
    unescape_display_text,
)
from narrativeloom.service.llm_unified import _normalize_base_url, complete_chat, default_api_key_from_env, env_llm_defaults
from narrativeloom.domain.personas import (
    antitrope_role_name,
    antitrope_role_task,
    functional_role_order,
    filter_unified_plan_role_names,
    get_functional_parallel_personas,
    get_functional_personas,
    is_character_sculptor_role,
    is_continuity_checker_role,
    is_unified_plan_excluded_role,
    typified_cast_focus,
)
from narrativeloom.domain.character_names import extract_seed_cast_names, merge_unique_names

load_dotenv(PROJECT_ROOT / ".env")


TYPIFIED_KEY_EVENT_CHARS_MIN = 30
TYPIFIED_KEY_EVENT_CHARS_MAX = 50
TYPIFIED_KEY_EVENTS_TOTAL_MAX = 300
PROSE_CHARS_PER_SECTION_MIN = 800
PROSE_CHARS_PER_SECTION_MAX = 1000

_PROSE_SECTION_STYLE_ZH = (
    "禁止平铺直叙与流水账；每小节须含至少两处带引号的对话、若干动作描写与环境氛围"
    "（光线、气味、声响、触感等感官细节），句式长短错落，场景有画面感与张力；"
    "用展示代替告知（show, don't tell），避免「然后…接着…」式罗列。"
)
_PROSE_SECTION_STYLE_EN = (
    "Avoid flat summary narration; each section needs at least two quoted dialogue beats, "
    "concrete action, and sensory setting (light, sound, smell, texture); "
    "vary sentence rhythm; show don't tell—no 'and then… and then…' event lists."
)


def _clamp_section_count(num_sections: int) -> int:
    return max(1, min(10, int(num_sections or 1)))


def _prose_length_budget(num_sections: int) -> tuple[int, int]:
    n = _clamp_section_count(num_sections)
    return n * PROSE_CHARS_PER_SECTION_MIN, n * PROSE_CHARS_PER_SECTION_MAX


def _arc_key_events_range(beat_idx: int, num_sections: int) -> tuple[int, int]:
    """开篇 3 条；发展 3～4 条；高潮 4～5 条。"""
    phase = _story_arc_phase(beat_idx, num_sections, "")
    if phase == "opening":
        return 3, 3
    if phase == "development":
        return 3, 4
    return 4, 5


def _arc_key_events_spec(ke_min: int, ke_max: int, lang: str) -> str:
    if ke_min == ke_max:
        return f"exactly {ke_min} lines" if lang == "en" else f"恰好 {ke_min} 条"
    if lang == "en":
        return f"{ke_min}–{ke_max} lines"
    return f"{ke_min}～{ke_max} 条"


def _arc_phase_label(phase: str, lang: str) -> str:
    if lang == "en":
        return {"opening": "opening", "development": "development", "climax": "climax"}.get(phase, phase)
    return {"opening": "开篇", "development": "发展", "climax": "高潮"}.get(phase, phase)


def _json_sanitize(s: str) -> str:
    """轻度修复模型常见 JSON 瑕疵（不改变合法 JSON 语义）。"""
    t = s.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.I)
    t = re.sub(r"\s*```\s*$", "", t)
    t = t.replace("\ufeff", "")
    t = t.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    t = re.sub(r",\s*}", "}", t)
    t = re.sub(r",\s*]", "]", t)
    return t


def _extract_typified_fields_loose(text: str) -> Dict[str, Any]:
    """JSON 无法解析时，尽力用正则抽出三字段（应对未转义引号等）。"""
    out: Dict[str, Any] = {}
    for key in ("setting", "characters", "key_events"):
        m = re.search(rf'["\']?{key}["\']?\s*:\s*"([\s\S]*?)"\s*,', text)
        if not m:
            m = re.search(rf'["\']?{key}["\']?\s*:\s*"([\s\S]*?)"\s*\}}', text)
        if m:
            val = m.group(1).replace("\\n", "\n").replace('\\"', '"')
            out[key] = val.strip()
    return out


def _parse_json_content(raw: str) -> Dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        return {}
    candidates = [_json_sanitize(raw)]
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        inner = _json_sanitize(raw[start : end + 1])
        if inner not in candidates:
            candidates.append(inner)
    for cand in candidates:
        if not cand:
            continue
        try:
            data = json.loads(cand)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    loose = _extract_typified_fields_loose(raw)
    return loose if loose else {}


def _repair_typified_key_events(data: Dict[str, Any], raw: str) -> None:
    """补全被解析丢掉的 key_events，或从备用字段/原始文本中恢复。"""
    if key_events_meaningful(data.get("key_events")):
        return
    for alt in (
        "plot_events",
        "events",
        "beats",
        "core_events",
        "情节要点",
        "核心情节",
        "核心事件",
        "事件链",
    ):
        v = data.get(alt)
        if key_events_meaningful(v):
            data["key_events"] = coerce_display_text(v)
            return
    loose = _extract_typified_fields_loose(raw)
    lv = loose.get("key_events")
    if key_events_meaningful(lv):
        data["key_events"] = str(lv).strip()
        return
    # 若整段 JSON 损坏，至少保留 raw 中与 key_events 相关的片段（弱兜底）
    m = re.search(
        r'["\']?key_events["\']?\s*:\s*"([\s\S]{12,4000}?)"\s*[,}]',
        raw,
        re.I,
    )
    if m:
        cand = m.group(1).replace("\\n", "\n").replace('\\"', '"').strip()
        if key_events_meaningful(cand):
            data["key_events"] = cand


def _backfill_typified_key_events(
    cfg: Dict[str, Any],
    *,
    setting: str,
    characters: str,
    seed: str,
    beat_title: str,
    beat_hint: str,
    genre_name: str,
    genre_hint: str,
    prior_summary: str,
    lang: str,
    ke_min: int = 3,
    ke_max: int = 3,
) -> str:
    """主生成 JSON 截断或漏字段时，单独补全 key_events（一次短调用）。"""
    ke_spec = _arc_key_events_spec(ke_min, ke_max, lang)
    if lang == "en":
        system = (
            "You write ONLY the key_events string for one story section. Output JSON only, no markdown: "
            f'{{"key_events":"..."}} . The value is ONE string with {ke_spec} separated by \\n; '
            "each line starts with hyphen-minus followed by space as a bullet; "
            f"each line about {TYPIFIED_KEY_EVENT_CHARS_MIN}–{TYPIFIED_KEY_EVENT_CHARS_MAX} words, "
            "one concrete causal beat that advances the plot; match the genre persona angle."
        )
        user = (
            f"Sparkles: {seed}\nSection: {beat_title} — {beat_hint}\nGenre persona: {genre_name} ({genre_hint})\n"
            f"Prior summary (follow causally):\n{(prior_summary or '')[:4000]}\n\n"
            f"LOCKED setting:\n{setting}\n\nLOCKED characters:\n{characters}\n"
        )
    else:
        system = (
            "你只负责补全一个小节的「核心事件」字段。只输出 JSON，不要 Markdown："
            f'{{"key_events":"……"}} 。key_events 为单个字符串，内含 {ke_spec}，用 \\n 换行；'
            f"每行以「- 」开头；每条 {TYPIFIED_KEY_EVENT_CHARS_MIN}～{TYPIFIED_KEY_EVENT_CHARS_MAX} 字，"
            "写具体动作、冲突或转折，须明显推动本节情节向前；必须与上方已定设定、人物一致，并体现题材人格「"
            + genre_name
            + "」的典型节奏；禁止空话、禁止只输出一个减号、禁止复述设定原文。"
        )
        user = (
            f"创意种子：{seed}\n当前小节：{beat_title} — {beat_hint}\n题材人格：{genre_name}（{genre_hint}）\n"
            f"已定前文摘要（须承接）：\n{(prior_summary or '')[:4000]}\n\n"
            f"【已定设定】\n{setting}\n\n【已定人物】\n{characters}\n"
            "请只输出事件链，不要重复描写环境与人物小传。"
        )
    raw = complete_chat(cfg, system, user, temperature=0.55, max_tokens=900)
    data = _parse_json_content(raw)
    ke = ""
    if isinstance(data, dict):
        ke = coerce_display_text(data.get("key_events", ""))
    if not key_events_meaningful(ke):
        loose = _extract_typified_fields_loose(raw)
        ke = str(loose.get("key_events", "")).strip()
    return ke.strip() if key_events_meaningful(ke) else ""


def _backfill_typified_characters(
    cfg: Dict[str, Any],
    *,
    setting: str,
    key_events: str,
    seed: str,
    beat_title: str,
    beat_hint: str,
    genre_name: str,
    genre_hint: str,
    prior_summary: str,
    locked_names: Optional[List[str]] = None,
    lang: str,
    character_target_total: Optional[int] = None,
) -> str:
    """主生成 JSON 漏字段时，单独补全 characters。"""
    locked_txt = "、".join(locked_names or []) if locked_names else ""
    char_target = max(2, int(character_target_total or max(2, len(locked_names or []))))
    if lang == "en":
        system = (
            "You write ONLY the characters string for one story section. Output JSON only: "
            f'{{"characters":"..."}} . The value is ONE string with exactly {char_target} lines separated by \\n; '
            "each line starts with '- Name: role/relationship/in-scene action (8–18 words, concise; no long biography)'. "
            "Only real people—never machines, patrol devices, or AI systems as characters."
        )
        user = (
            f"Sparkles: {seed}\nSection: {beat_title} — {beat_hint}\nGenre persona: {genre_name} ({genre_hint})\n"
            f"Prior summary:\n{(prior_summary or '')[:4000]}\n\n"
            f"LOCKED setting:\n{setting}\n\nLOCKED key_events:\n{key_events}\n"
        )
        if locked_txt:
            user += f"\nLOCKED NAMES (must all appear): {locked_txt}\n"
    else:
        system = (
            "你只负责补全一个小节的「人物」字段。只输出 JSON："
            f'{{"characters":"……"}} 。characters 为单个字符串，内含恰好 {char_target} 行，用 \\n 换行；'
            "每行以「- 」开头，格式「姓名：身份/关系/本节行动」（每行 12～28 字，精炼短句，禁止年龄履历式长传记）；"
            "仅写真实人物，禁止把机器、设备、嗅探器、巡逻装置、AI 系统当作人物。"
            "须与设定、核心事件一致，并体现题材人格「"
            + genre_name
            + "」的典型人物配置。"
        )
        user = (
            f"创意种子：{seed}\n当前小节：{beat_title} — {beat_hint}\n题材人格：{genre_name}（{genre_hint}）\n"
            f"已定前文摘要：\n{(prior_summary or '')[:4000]}\n\n"
            f"【已定设定】\n{setting}\n\n【已定核心事件】\n{key_events}\n"
        )
        if locked_txt:
            user += f"\n【锁定姓名（须全部出现）】{locked_txt}\n"
    raw = complete_chat(cfg, system, user, temperature=0.58, max_tokens=1000)
    data = _parse_json_content(raw)
    ch = ""
    if isinstance(data, dict):
        ch = coerce_display_text(data.get("characters", ""))
    if not typified_characters_meaningful(ch):
        loose = _extract_typified_fields_loose(raw)
        ch = str(loose.get("characters", "")).strip()
    return ch.strip() if typified_characters_meaningful(ch) else ""


def _functional_extract_variants(data: Dict[str, Any], raw: str) -> list:
    """从模型返回中取出 variants 列表，兼容字符串嵌套、误用 dict 等情况。"""
    if not isinstance(data, dict):
        return []
    v = data.get("variants")
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        sub = _parse_json_content(_json_sanitize(v))
        if isinstance(sub, dict) and isinstance(sub.get("variants"), list):
            return sub["variants"]
        try:
            arr = json.loads(_json_sanitize(v))
            if isinstance(arr, list):
                return arr
        except json.JSONDecodeError:
            pass
    if isinstance(v, dict):
        vals = [x for x in v.values() if isinstance(x, (dict, str))]
        if vals:
            return vals
    loose = _parse_json_content(raw)
    if isinstance(loose, dict) and isinstance(loose.get("variants"), list):
        return loose["variants"]
    return []


def _functional_normalize_fragment(obj: Any) -> tuple[str, Any]:
    """取出 fragment 文本；若模型把整段 JSON 塞进 fragment，则向内剥离。"""
    pf: Any = None
    if isinstance(obj, str):
        frag = obj.strip()
    elif isinstance(obj, dict):
        frag = (obj.get("fragment") or obj.get("text") or obj.get("outline") or "") or ""
        if isinstance(frag, dict):
            frag = str(frag)
        frag = str(frag).strip()
        pf = obj.get("process_feedback")
    else:
        frag = str(obj or "").strip()
    for _ in range(6):
        if not frag.startswith("{") or len(frag) < 10:
            break
        head = frag[: min(8000, len(frag))]
        if '"fragment"' not in head and "'fragment'" not in head and '"variants"' not in head:
            break
        inner = _parse_json_content(frag)
        if not inner:
            try:
                inner = json.loads(_json_sanitize(frag))
            except json.JSONDecodeError:
                inner = {}
        if not isinstance(inner, dict):
            break
        if isinstance(inner.get("fragment"), str) and inner["fragment"].strip():
            frag = inner["fragment"].strip()
            continue
        inner_vars = inner.get("variants")
        if isinstance(inner_vars, list) and inner_vars:
            # 多个 variant 时不得只取第一个，否则 functional_slot_bundle 无法按方案索引；
            # 保留整段 JSON 字符串，交由上层按 slot 解析。
            if len(inner_vars) > 1:
                break
            picked_txt = ""
            for cand in inner_vars:
                if isinstance(cand, dict) and (str(cand.get("fragment") or "").strip()):
                    picked_txt = str(cand["fragment"]).strip()
                    break
            if picked_txt:
                frag = picked_txt
                continue
        break
    return frag, pf


def _unescape_json_string_chunk(raw: str) -> str:
    """将 JSON 字符串体内的 \\n、\\\"、\\uXXXX 等转为可读字符（不依赖整段 JSON 可解析）。"""
    out: list[str] = []
    i = 0
    while i < len(raw):
        if raw[i] == "\\" and i + 1 < len(raw):
            nxt = raw[i + 1]
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
            if nxt == "u" and i + 6 <= len(raw):
                try:
                    cp = int(raw[i + 2 : i + 6], 16)
                    out.append(chr(cp))
                    i += 6
                    continue
                except ValueError:
                    pass
            out.append(raw[i])
            i += 1
            continue
        out.append(raw[i])
        i += 1
    return "".join(out)


def _final_display_unescape(s: str) -> str:
    """展示前：若仍残留 JSON 字符串转义写法，转为真实换行。"""
    return unescape_display_text(s)


_VARIANT_FRAGMENT_HEAD = re.compile(r'"(?:fragment|text|outline)"\s*:\s*"', re.I)


def _extract_fragment_strings_loose(blob: str) -> list[str]:
    """
    当 _parse_json_content 失败或结构异常时，从疑似 {\"variants\":[...]} 的文本中
    顺序抽出各 fragment 字符串（仅处理双引号包裹的标准片段字段）。
    """
    out: list[str] = []
    pos = 0
    blob = (blob or "").strip()
    while True:
        m = _VARIANT_FRAGMENT_HEAD.search(blob, pos)
        if not m:
            break
        j = m.end()
        buf: list[str] = []
        while j < len(blob):
            c = blob[j]
            if c == "\\":
                if j + 1 < len(blob):
                    buf.append(blob[j : j + 2])
                    j += 2
                else:
                    j += 1
                continue
            if c == '"':
                break
            buf.append(c)
            j += 1
        raw = "".join(buf)
        piece = _unescape_json_string_chunk(raw).strip()
        if piece:
            out.append(piece)
        pos = max(pos + 1, j + 1)
    return out


def _looks_like_wrapped_variants_json(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 12:
        return False
    if not re.match(r"^\s*\{", t):
        return False
    head = t[:12000]
    return bool(re.search(r'(?i)"\s*variants\s*"\s*:', head))


def functional_fragment_display(frag: Any) -> str:
    """供界面展示：从职能 variant 中取出纯文本要点，剥离误嵌套的 JSON。"""
    s, _ = _functional_normalize_fragment(frag)
    return scrub_functional_fragment(_final_display_unescape((s or "").strip()))


def functional_slot_bundle(frag: Any, slot_index: int) -> tuple[str, Any]:
    """
    取第 slot_index 个方案对应的展示文本与 process_feedback。
    兼容模型把整段 {\"variants\":[...]} 误塞进单个 variant 或 fragment 字段的情况。
    """
    cur: Any = frag
    pf_out: Any = None
    for _ in range(8):
        txt, pf = _functional_normalize_fragment(cur)
        if pf is not None:
            pf_out = pf
        t = (txt or "").strip()
        if not _looks_like_wrapped_variants_json(t):
            return (_final_display_unescape(t), pf_out)
        data = _parse_json_content(t)
        arr = _functional_extract_variants(data, t) if isinstance(data, dict) else []
        if not arr:
            loose_frags = _extract_fragment_strings_loose(t)
            if loose_frags:
                si = max(0, min(int(slot_index), len(loose_frags) - 1))
                nxt = loose_frags[si]
                if isinstance(nxt, str) and _looks_like_wrapped_variants_json(nxt):
                    cur = nxt
                    continue
                return (_final_display_unescape(nxt), pf_out)
            return (_final_display_unescape(t), pf_out)
        si = max(0, min(int(slot_index), len(arr) - 1))
        cur = arr[si]
        if isinstance(cur, dict) and cur.get("process_feedback") is not None:
            pf_out = cur.get("process_feedback")
    out = functional_fragment_display(cur)
    if _looks_like_wrapped_variants_json(out):
        lf = _extract_fragment_strings_loose(out)
        if lf:
            si = max(0, min(int(slot_index), len(lf) - 1))
            out = lf[si]
    return (_final_display_unescape(str(out or "").strip()), pf_out)


def functional_slot_bundle_from_pack(variants_list: Any, slot_index: int) -> tuple[str, Any]:
    """
    从顶层 variants 列表中取第 slot_index 项的展示文本与 process_feedback。

    常见误排版：三个方案被塞进 variants[0] 的嵌套 JSON，而 variants[1]、[2] 为空。
    此时若当前槽为空，则回退用 [0] 按同一 slot_index 再解包一次。
    """
    arr = list(variants_list or [])
    si = max(0, min(int(slot_index), max(0, len(arr) - 1)))
    item: Any = arr[si] if arr else {}
    frag_raw = item if isinstance(item, (dict, str)) else str(item)
    txt, pf = functional_slot_bundle(frag_raw, si)
    if (txt or "").strip():
        return (txt.strip(), pf)
    if si > 0 and arr:
        base = arr[0]
        br = base if isinstance(base, (dict, str)) else str(base)
        t2, p2 = functional_slot_bundle(br, si)
        if (t2 or "").strip():
            return (t2.strip(), p2 if p2 is not None else pf)
    return ((txt or "").strip(), pf)


def _cfg_or_env(llm_cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if llm_cfg:
        return llm_cfg
    key = default_api_key_from_env()
    base, model = env_llm_defaults()
    if not key:
        raise RuntimeError("未登录且未配置环境变量 API Key（MIMO_API_KEY 或 OPENAI_API_KEY）。")
    return {
        "provider": "openai_compat",
        "api_key": key,
        "base_url": base,
        "model": model,
    }


def review_beat_consistency(
    llm_cfg: Optional[Dict[str, Any]],
    *,
    canon_sheet: str,
    rag_excerpt: str,
    beat: Dict[str, Any],
    lang: str = "zh",
) -> Dict[str, Any]:
    """
    中等强度审查：对齐人物姓名、称谓与地点线索；必要时修订三字段。
    """
    cfg = _cfg_or_env(llm_cfg)
    if lang == "en":
        system = (
            "You are a narrative consistency editor. Enforce the canon list for names and titles; "
            "fix location/time contradictions with minimal edits. Never blank out key_events or replace with a single dash; "
            "keep at least 3 substantive beats if the input had them. Output JSON only: "
            "setting, characters, key_events, review_notes (short English)."
        )
        user = (
            f"Canon:\n{canon_sheet or '(none)'}\n\nRetrieved excerpts:\n{rag_excerpt or '(none)'}\n\n"
            f"Beat JSON:\n{json.dumps(beat, ensure_ascii=False)}\n\nReturn revised JSON."
        )
    else:
        system = (
            "你是叙事一致性编辑。必须严格依据「设定清单」统一人物姓名与称谓，"
            "禁止同一角色出现不同姓名或莫名改名。地点与时间若与清单冲突须修正。"
            "在保持剧情走向与事件逻辑的前提下做最小修改。"
            "key_events 须保留输入中的事件链：禁止清空、禁止仅输出「-」「无」等占位；"
            "若原文已有多条事件，修订后仍须至少 3 条可辨的独立要点。"
            "只输出 JSON：setting, characters, key_events, review_notes（简短中文说明做了哪些对齐）。"
        )
        user = (
            f"设定清单与已定信息：\n{canon_sheet or '（尚无已定稿）'}\n\n"
            f"检索到的相关前文摘录：\n{rag_excerpt or '（无）'}\n\n"
            f"待审查小节 JSON：\n{json.dumps(beat, ensure_ascii=False)}\n\n"
            "请输出修订后的完整 JSON。"
        )
    raw = complete_chat(cfg, system, user, temperature=0.2, max_tokens=2048)
    data = _parse_json_content(raw)
    if not data:
        return {**beat, "review_notes": "Review parse failed." if lang == "en" else "审查解析失败，保留原文。"}
    out = {
        "setting": data.get("setting", beat.get("setting", "")),
        "characters": data.get("characters", beat.get("characters", "")),
        "key_events": data.get("key_events", beat.get("key_events", "")),
        "review_notes": data.get("review_notes", ""),
    }
    for _k in ("setting", "characters", "key_events"):
        v = out.get(_k)
        if isinstance(v, list):
            out[_k] = "\n".join(str(x).strip() for x in v if str(x).strip())
        elif v is not None and not isinstance(v, str):
            out[_k] = str(v).strip()
    if not key_events_meaningful(out.get("key_events")):
        out["key_events"] = coerce_display_text(beat.get("key_events", ""))
    return out


def review_merged_text(
    llm_cfg: Optional[Dict[str, Any]],
    *,
    canon_sheet: str,
    rag_excerpt: str,
    merged_text: str,
    lang: str = "zh",
) -> tuple[str, str]:
    """对职能人格拼接文本做一致性润色，返回 (修订文本, 说明)。"""
    cfg = _cfg_or_env(llm_cfg)
    if lang == "en":
        system = (
            "You are a narrative editor. Align names with the canon with minimal edits. "
            "Output JSON: merged, review_notes."
        )
        user = f"Canon:\n{canon_sheet or '(none)'}\n\nExcerpts:\n{rag_excerpt or '(none)'}\n\nText:\n{merged_text}"
    else:
        system = (
            "你是叙事编辑。根据设定清单统一人物称谓与地点表述，做最小幅度改写。"
            "只输出 JSON：merged（修订后全文）, review_notes（简短说明）。"
        )
        user = (
            f"设定清单：\n{canon_sheet or '（无）'}\n\n前文摘录：\n{rag_excerpt or '（无）'}\n\n"
            f"待处理文本：\n{merged_text}"
        )
    raw = complete_chat(cfg, system, user, temperature=0.25, max_tokens=4096)
    data = _parse_json_content(raw)
    if not data:
        return merged_text, "Skipped" if lang == "en" else "审查跳过"
    return data.get("merged", merged_text) or merged_text, data.get("review_notes", "") or ""


def _story_arc_phase(beat_idx: int, num_sections: int, prior_summary: str) -> str:
    """根据小节位置与已定前文判断故事发展阶段。"""
    n = max(2, int(num_sections))
    if not (prior_summary or "").strip() and beat_idx <= 0:
        return "opening"
    ratio = beat_idx / max(1, n - 1)
    if ratio < 0.28:
        return "opening"
    if ratio < 0.72:
        return "development"
    return "climax"


def _heuristic_functional_roles(
    *,
    seed: str,
    beat_hint: str,
    prior_summary: str,
    beat_idx: int,
    num_sections: int,
    lang: str,
) -> List[str]:
    """根据种子、故事发展阶段与已定前文，规则推荐 4～6 个并行职能。"""
    order = functional_role_order(lang)
    text = f"{seed}\n{beat_hint}\n{prior_summary}".lower()
    phase = _story_arc_phase(beat_idx, num_sections, prior_summary)

    def hit(*keys: str) -> bool:
        return any(k.lower() in text for k in keys)

    scores: Dict[str, int] = {r: 0 for r in order}
    if hit("对话", "台词", "口角", "争吵", "dialogue", "conversation", "said"):
        scores[order[4]] += 3
    if hit("恐怖", "悬疑", "氛围", "紧张", "horror", "mystery", "atmosphere", "dread", "suspense"):
        scores[order[3]] += 3
    if hit("伏笔", "细节", "道具", "线索", "foreshadow", "detail", "prop", "clue"):
        scores[order[5]] += 2
    if hit("冲突", "矛盾", "对抗", "战争", "斗争", "conflict", "tension", "clash", "obstacle"):
        scores[order[6]] += 3
    if hit("人物", "角色", "性格", "关系", "character", "protagonist", "motivation"):
        scores[order[1]] += 3
    if hit("世界", "场景", "地点", "时代", "规则", "背景", "world", "setting", "location", "era"):
        scores[order[0]] += 2
    if hit("情节", "因果", "推进", "plot", "logic", "beat", "twist"):
        scores[order[2]] += 2

    if phase == "opening":
        scores[order[0]] += 3
        scores[order[1]] += 3
        scores[order[2]] += 2
        scores[order[6]] += 1
    elif phase == "development":
        scores[order[2]] += 2
        scores[order[5]] += 2
        scores[order[4]] += 1
        scores[order[1]] += 1
    else:
        scores[order[6]] += 3
        scores[order[3]] += 2
        scores[order[2]] += 2

    if beat_idx <= 0 and not (prior_summary or "").strip():
        scores[order[0]] += 2
        scores[order[1]] += 2
    else:
        scores[order[7]] += 4
        scores[order[2]] += 1

    ranked = sorted(order, key=lambda x: (-scores[x], order.index(x)))
    picked: List[str] = []
    for role in ranked:
        if scores[role] <= 0 and len(picked) >= 4:
            continue
        picked.append(role)
        if len(picked) >= 6:
            break
    if order[7] not in picked and ((prior_summary or "").strip() or beat_idx > 0):
        picked = picked[:5] + [order[7]]
    while len(picked) < 4:
        for role in order:
            if role not in picked:
                picked.append(role)
            if len(picked) >= 4:
                break
    picked = picked[:5]
    at = antitrope_role_name(lang)
    if (phase in ("development", "climax") or beat_idx > 0) and at not in picked:
        picked.append(at)
    return picked[:6]


def recommend_functional_roles(
    *,
    seed: str,
    story_title: str,
    beat_idx: int,
    beat_title: str,
    beat_hint: str,
    prior_summary: str,
    num_sections: int = 6,
    background_setting: str = "",
    background_characters: str = "",
    lang: str = "zh",
    llm_cfg: Optional[Dict[str, Any]] = None,
    use_llm: bool = True,
) -> List[str]:
    """
    统筹推荐本小节应并行调用的功能化人格（4～6 个），顺序按职能逻辑排列。
    LLM 失败时回退启发式。
    """
    order = functional_role_order(lang)
    phase = _story_arc_phase(beat_idx, num_sections, prior_summary)
    base = _heuristic_functional_roles(
        seed=seed,
        beat_hint=beat_hint,
        prior_summary=prior_summary,
        beat_idx=beat_idx,
        num_sections=num_sections,
        lang=lang,
    )
    if not use_llm:
        return base

    cfg = _cfg_or_env(llm_cfg)
    roles_lines = "\n".join(
        f"- {n}: {t[:80]}…" if len(t) > 80 else f"- {n}: {t}"
        for n, t in get_functional_personas(lang)
    )
    arch = (background_setting or "").strip()[:400]
    if (background_characters or "").strip():
        arch += "\n" + (background_characters or "").strip()[:400]
    phase_zh = {"opening": "开篇", "development": "发展", "climax": "高潮收束"}.get(phase, phase)
    if lang == "en":
        system = (
            "You are a narrative production planner. Pick 4–6 PARALLEL roles from the list for ONE story beat. "
            "Output JSON only: {\"roles\": [\"Role Name\", ...]} using EXACT role names from the list. "
            "Analyze story development stage (opening / rising / climax) from prior beats and beat position; "
            "match roles to what THIS beat still needs. Include Continuity Checker when prior story exists. "
            "Optionally include Anti-Cliché Innovator (post-merge trope pass) in development/climax or when prior beats exist."
        )
        user = (
            f"Title: {story_title}\nSparkles: {seed}\nBeat: {beat_title} — {beat_hint}\n"
            f"Beat {beat_idx + 1} of {num_sections} · arc phase: {phase}\n"
            f"Optional canon:\n{arch or '(none)'}\n"
            f"Prior beats (story so far):\n{(prior_summary or '(none)')[:4500]}\n\n"
            f"Available roles:\n{roles_lines}\n\n"
            f"Heuristic suggestion: {', '.join(base)}\n"
            "Return 4–6 role names."
        )
    else:
        system = (
            "你是叙事生产统筹。从下列「并行职能」中为当前小节挑选 4～6 个，"
            "须结合故事已发展到哪一阶段（开篇/发展/高潮）与已定前文，针对性补缺，而非固定套路。"
            "只输出 JSON：{\"roles\": [\"职能名\", ...]}，职能名必须与列表完全一致。"
            "「连贯性校验师」不参与总体方案拼合，勿将其列入本请求的 roles。"
            "发展/高潮阶段或已有前文时，可酌情纳入「反套路创意师」（拼合后做突变润色，不并行生成片段）。"
        )
        user = (
            f"标题：{story_title}\n创意种子：{seed}\n当前小节：{beat_title} — {beat_hint}\n"
            f"第 {beat_idx + 1}/{num_sections} 节 · 故事阶段判断：{phase_zh}\n"
            f"可选基线设定：\n{arch or '（无）'}\n"
            f"【已定前文与故事走向】\n{(prior_summary or '（无）')[:4500]}\n\n"
            f"可选职能：\n{roles_lines}\n\n"
            f"规则初筛建议：{', '.join(base)}\n"
            "请返回 4～6 个职能名。"
        )
    try:
        raw = complete_chat(cfg, system, user, temperature=0.35, max_tokens=400)
        data = _parse_json_content(raw)
        if isinstance(data, dict) and isinstance(data.get("roles"), list):
            rec_order = order + [antitrope_role_name(lang)]
            valid = {n for n, _ in get_functional_personas(lang)}
            out = [str(x).strip() for x in data["roles"] if str(x).strip() in valid]
            if 4 <= len(out) <= 6:
                return sorted(out, key=lambda x: rec_order.index(x) if x in rec_order else 99)
            if len(out) >= 3:
                while len(out) < 4:
                    for role in order:
                        if role not in out:
                            out.append(role)
                        if len(out) >= 4:
                            break
                return sorted(out[:6], key=lambda x: rec_order.index(x) if x in rec_order else 99)
    except Exception:  # noqa: BLE001
        pass
    return base


def generate_typified_beat(
    *,
    genre_name: str,
    genre_hint: str,
    seed: str,
    beat_title: str,
    beat_hint: str,
    prior_summary: str,
    feedback_process: bool,
    llm_cfg: Optional[Dict[str, Any]] = None,
    canon_sheet: str = "",
    rag_excerpt: str = "",
    lang: str = "zh",
    locked_character_names: Optional[List[str]] = None,
    prior_characters_block: str = "",
    beat_index: int = 0,
    num_sections: int = 6,
    character_target_total: Optional[int] = None,
) -> Dict[str, Any]:
    cfg = _cfg_or_env(llm_cfg)
    locked = merge_unique_names(
        [n.strip() for n in (locked_character_names or []) if (n or "").strip()],
        extract_seed_cast_names(seed),
    )
    locked_txt = "、".join(locked) if locked else ""
    char_target = max(2, int(character_target_total or max(2, len(locked))))
    cast_focus = typified_cast_focus(genre_name, lang)
    extra_slots = max(0, char_target - len(locked))
    char_spec_en = f"exactly {char_target} lines"
    char_spec_zh = f"恰好 {char_target} 行"
    ke_min, ke_max = _arc_key_events_range(beat_index, num_sections)
    arc_phase = _story_arc_phase(beat_index, num_sections, prior_summary)
    ke_spec = _arc_key_events_spec(ke_min, ke_max, lang)
    arc_label = _arc_phase_label(arc_phase, lang)
    proc = ""
    if feedback_process:
        proc = (
            "Also include top-level process_feedback with creative_goal, design_rationale, narrative_technique — "
            "each at least one full sentence; never omit keys or leave them empty."
            if lang == "en"
            else (
                "另外必须在 JSON 顶层输出 process_feedback 对象，含 creative_goal、design_rationale、narrative_technique 三个键，"
                "且每项各至少一句具体中文，禁止省略键、禁止空字符串。"
            )
        )
    if lang == "en":
        system = (
            "You are a literary fiction planning assistant. Output JSON only, no markdown fences. "
            "Fields: setting, characters, key_events (strings). "
            "JSON rules: every string value must be valid JSON — escape internal double-quotes as \\\" "
            "or avoid ASCII double-quotes inside values (use single quotes or paraphrase). "
            "Prioritize story quality: concrete imagery, causal clarity, character voice, and emotional stakes. "
            "LENGTH BUDGET: setting + characters + key_events together under ~200 English words. "
            "setting: ONE line — time + place (~15–28 words). "
            f"characters: {char_spec_en}, each starts with '- ', format "
            "'Name: role, relationship, in-scene action (8–18 words; concise, not a biography)'. "
            f"key_events: {ke_spec}, each starts with '- ', "
            f"each {TYPIFIED_KEY_EVENT_CHARS_MIN}–{TYPIFIED_KEY_EVENT_CHARS_MAX} words, "
            "vivid causal beats that clearly advance the plot; no prose paragraphs. "
            f"This section is in the {arc_label} arc of the story. "
            "If a canon list is given, reuse exact character names. "
            "SEED CAST: If sparkles name protagonists, you MUST keep those exact names and roles—do not replace them with new characters. "
            "CHARACTER CONTINUITY: If prior character profiles are given, the characters field MUST update them—"
            "keep every locked name unchanged; refresh motives, relationships, and in-scene status for this beat; "
            "you may add at most one new named character if the genre persona demands it. "
            "CONTINUITY: If prior sections text is provided, this section MUST causally follow them; do not reset the timeline "
            "or ignore established facts unless the seed demands a deliberate jump (then signal it clearly). "
            "DIVERSITY: You ONLY represent this genre persona; setting and characters must reflect THIS genre's "
            "distinct motifs, scene types, and conflict hooks — clearly different from what other genre personas would produce "
            "(do not reuse the same location template or character roster with synonym swaps). "
            + proc
        )
        user = (
            f"Sparkles: {seed}\nGenre persona: {genre_name} ({genre_hint})\n"
            f"Current section: {beat_title} — {beat_hint}\n"
        )
        if (prior_summary or "").strip():
            user += (
                "\nLOCKED PRIOR STORY (ordered sections — you MUST extend this linearly; no orphan reboot):\n"
                + (prior_summary or "").strip()[:2800]
                + "\n"
            )
        else:
            user += "\nPrior sections: (none yet — opening phase).\n"
        if canon_sheet:
            user += f"\nCanon (must follow):\n{(canon_sheet or '')[:1200]}\n"
        if rag_excerpt:
            user += f"\nRetrieved context (RAG):\n{(rag_excerpt or '')[:800]}\n"
        if (prior_characters_block or "").strip():
            user += (
                "\nPRIOR CHARACTER PROFILES (update on this basis; do not reset cast):\n"
                + prior_characters_block.strip()[:2000]
                + "\n"
            )
        if locked_txt:
            user += f"\nLOCKED NAMES (must all appear in characters, unchanged spelling): {locked_txt}\n"
        seed_cast = extract_seed_cast_names(seed)
        if seed_cast:
            user += (
                f"\nSEED CAST (must all appear in characters, exact spelling): "
                f"{', '.join(seed_cast)}\n"
            )
        user += (
            "Write one strong candidate section outline that could stand beside other genre personas. "
            "Avoid clichés and generic placeholders. Emphasize genre-specific differentiation in setting and cast."
        )
        if cast_focus:
            user += f"\n[{genre_name} cast focus] {cast_focus}"
        if extra_slots > 0 and locked:
            user += (
                f"\nBesides locked names, add {extra_slots} supporting characters unique to [{genre_name}]; "
                "names and roles must differ sharply from parallel genre personas—no shared template cast."
            )
    else:
        system = (
            "你是文学向叙事策划助手。只输出 JSON，不要 Markdown 围栏。语言：中文。"
            "须含 setting, characters, key_events 三字段，均为字符串。"
            "JSON 硬性要求：三个字段的值里禁止出现未转义的英文双引号 \"；"
            "若需引号请用中文直角引号「」或单引号，或对引号写作 \\\"。否则会导致解析失败。"
            "以故事质量为最高优先级：设定要有具体时间地点与感官细节；人物写清姓名与本节行动驱动即可，避免长篇小传；"
            "因果清晰、避免空泛套话与口号式描写。"
            "【篇幅】三字段中文总字数（不含空白）约 300～420 字；信息密度高但避免长篇散文。"
            "setting：仅一行，写清时间+地点（约 30～55 字）。"
            f"characters：{char_spec_zh}，每行以「- 」开头，格式「姓名：身份/关系/本节行动」（每行 12～28 字，精炼短句，禁止年龄履历式长传记）。"
            f"key_events：{ke_spec}，每行以「- 」开头，"
            f"每条 {TYPIFIED_KEY_EVENT_CHARS_MIN}～{TYPIFIED_KEY_EVENT_CHARS_MAX} 字，"
            "写具体动作、冲突或转折，须明显推动本节情节向前，鼓励意外与画面感。"
            f"本节处于叙事弧「{arc_label}」阶段。"
            "【硬性】characters 与 key_events 均不得为空、不得只输出「—」或单个减号；若信息不足须合理补全。"
            "【题材差异化硬性要求】你只代表当前题材人格「"
            + genre_name
            + "」：setting 与 characters 必须写出该题材独有的母题、场景类型、人物身份与矛盾抓手，"
            "与并行输出的其它题材版本在「地点/空间」「叙事视角」「人物配置」上必须拉开显著差距，"
            "禁止与其它题材共用同一段落式模板或仅替换同义词。"
            f"key_events 须为 {ke_spec}；每一行必须以「- 」开头且单独承载一条完整事件或转折；"
            "禁止在一行内用多个「-」串联；禁止只输出一个「-」或空字符串；每条信息具体。若提供设定清单，人物姓名须与清单完全一致。"
            "【种子人物】若创意种子已给出主角姓名（含「·」的复合名），characters 必须全部保留且不得改名或替换为其它人物。"
            "【连续性】若下方提供「已定前文」，本节必须在其人物状态、时间线与因果链上自然递进，禁止无视前文后果或擅自重置故事。"
            "【人物承接】若提供「已定人物档案」，characters 须在其基础上更新：所有已锁定姓名必须保留且不得改名；"
            "为每位已登场人物补充或调整本节的状态、动机与关系；可按当前题材人格新增至多一名新角色。"
            "【人物硬性要求】仅列真实人物（人类或具名角色），禁止把机器、设备、嗅探器、巡逻装置、AI 系统写成人物。"
            + proc
        )
        user = (
            f"创意种子：{seed}\n题材人格：{genre_name}（{genre_hint}）\n"
            f"当前小节：{beat_title} — {beat_hint}\n"
        )
        if (prior_summary or "").strip():
            user += (
                "\n【已定前文（按小节顺序，须线性承接）】\n"
                + (prior_summary or "").strip()[:2800]
                + "\n"
            )
        else:
            user += "\n【已定前文】（尚无，本节可为开篇阶段）\n"
        if canon_sheet:
            user += f"\n【设定清单（须严格遵守）】\n{(canon_sheet or '')[:1200]}\n"
        if rag_excerpt:
            user += f"\n【相关前文摘录（RAG）】\n{(rag_excerpt or '')[:800]}\n"
        if (prior_characters_block or "").strip():
            user += (
                "\n【已定人物档案（须在此基础上更新，禁止重置已有人物）】\n"
                + prior_characters_block.strip()[:2000]
                + "\n"
            )
        if locked_txt:
            user += f"\n【锁定姓名（characters 中必须全部出现，拼写不变）】{locked_txt}\n"
        seed_cast = extract_seed_cast_names(seed)
        if seed_cast:
            if lang == "en":
                user += (
                    f"\nSEED CAST (must all appear in characters, exact spelling): "
                    f"{', '.join(seed_cast)}\n"
                )
            else:
                user += f"\n【创意种子既定人物（须全部出现在 characters，禁止替换或改名）】{'、'.join(seed_cast)}\n"
        user += (
            "请生成高完成度小节纲要，并确保与同批其它题材人格候选在设定与人物上明显可区分。"
        )
        if cast_focus:
            user += f"\n【{genre_name}人物配置】{cast_focus}"
        if extra_slots > 0 and locked:
            user += (
                f"\n除锁定人物外，须再写 {extra_slots} 名体现「{genre_name}」题材特色的配角；"
                "其姓名、职业、关系须与其它题材人格并行候选显著不同，禁止共用同一套配角模板。"
            )
    raw = complete_chat(cfg, system, user, temperature=0.84, max_tokens=1500 if not feedback_process else 1900)
    data = _parse_json_content(raw)
    if not data:
        data = {"setting": raw[:400], "characters": "", "key_events": ""}
    for _k in ("setting", "characters", "key_events"):
        v = data.get(_k)
        if isinstance(v, list):
            data[_k] = "\n".join(str(x).strip() for x in v if str(x).strip())
        elif v is not None and not isinstance(v, str):
            data[_k] = str(v).strip()
    _repair_typified_key_events(data, raw)
    if not key_events_meaningful(data.get("key_events")):
        loose = _extract_typified_fields_loose(raw)
        ke_loose = str(loose.get("key_events", "")).strip()
        if key_events_meaningful(ke_loose):
            data["key_events"] = ke_loose
    if not key_events_meaningful(data.get("key_events")):
        bf = _backfill_typified_key_events(
            cfg,
            setting=str(data.get("setting", "")),
            characters=str(data.get("characters", "")),
            seed=seed,
            beat_title=beat_title,
            beat_hint=beat_hint,
            genre_name=genre_name,
            genre_hint=genre_hint,
            prior_summary=prior_summary or "",
            lang=lang,
            ke_min=ke_min,
            ke_max=ke_max,
        )
        if bf:
            data["key_events"] = bf
    data["key_events"] = normalize_typified_key_events(
        data.get("key_events", ""),
        min_lines=ke_min,
        max_lines=ke_max,
    )
    if not typified_characters_meaningful(data.get("characters")):
        ch_bf = _backfill_typified_characters(
            cfg,
            setting=str(data.get("setting", "")),
            key_events=str(data.get("key_events", "")),
            seed=seed,
            beat_title=beat_title,
            beat_hint=beat_hint,
            genre_name=genre_name,
            genre_hint=genre_hint,
            prior_summary=prior_summary or "",
            locked_names=locked,
            lang=lang,
            character_target_total=char_target,
        )
        if ch_bf:
            data["characters"] = ch_bf
    data["characters"] = sanitize_typified_characters(
        data.get("characters", ""),
        target=char_target,
        locked_names=locked,
        seed=seed,
        setting=str(data.get("setting", "")),
        key_events=str(data.get("key_events", "")),
        prior_characters_block=prior_characters_block,
        plan_index=abs(hash(genre_name)) % 997,
    )
    if not typified_characters_meaningful(data.get("characters")) and (data.get("setting") or "").strip():
        data["characters"] = "- （待补全人物）"
    return data


def _extract_sculptor_names_from_outline(outline: str, *, locked: Optional[List[str]] = None) -> List[str]:
    """从总体方案中提取人物塑造师姓名（不含锁定/种子主角）。"""
    from narrativeloom.utils.display_utils import parse_merge_role_sections, _is_sculptor_section_title

    locked_set = set(locked or [])
    names: List[str] = []
    for title, body in parse_merge_role_sections(outline):
        if not _is_sculptor_section_title(title):
            continue
        for ln in (body or "").splitlines():
            probe = ln.strip().lstrip("-·• ")
            if "：" not in probe:
                continue
            name = probe.split("：", 1)[0].strip()
            if name and name not in locked_set and name not in names:
                names.append(name)
    return names


UNIFIED_FN_PLAN_COUNT = 4

FN_WORLDVIEW_KEYS = ("historical", "contemporary", "scifi", "fantasy")
_MUT_OPEN = "⟦mut⟧"
_MUT_CLOSE = "⟦/mut⟧"


def _normalize_unified_plan_item(item: Any) -> tuple[str, str, Any]:
    if isinstance(item, dict):
        txt = str(
            item.get("outline") or item.get("merged") or item.get("fragment") or item.get("text") or ""
        ).strip()
        cast = str(item.get("cast") or item.get("characters") or "").strip()
        return txt, cast, item.get("process_feedback")
    return str(item or "").strip(), "", None


def _coerce_unified_plan_variants(
    variants: list,
    *,
    plan_count: int,
    feedback_process: bool,
    lang: str = "zh",
    locked_character_names: Optional[List[str]] = None,
    character_target_total: Optional[int] = None,
    role_names: Optional[List[str]] = None,
    beat_index: int = 0,
    seed: str = "",
    prior_character_profiles: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    locked = merge_unique_names(
        [n.strip() for n in (locked_character_names or []) if (n or "").strip()],
        extract_seed_cast_names(seed),
    )
    sculpt_target = character_target_total if character_target_total is not None else max(2, len(locked))
    from narrativeloom.utils.display_utils import merge_functional_cast_into_outline

    used_cast_names: List[str] = []
    expanded: List[Dict[str, Any]] = []
    for item in variants:
        txt, cast, pf = _normalize_unified_plan_item(item)
        if not (txt or "").strip() and not (cast or "").strip():
            expanded.append({"outline": "", "process_feedback": pf if feedback_process else None})
            continue
        if (cast or "").strip():
            txt = merge_functional_cast_into_outline(
                cast, txt, role_names=role_names, lang=lang
            )
        for piece in split_concatenated_unified_plans(txt, role_names, max_plans=plan_count):
            plan_index = len(expanded)
            normalized = normalize_single_unified_outline(
                piece,
                role_names=role_names,
                lang=lang,
                locked_names=locked,
                character_target_total=sculpt_target,
                beat_index=beat_index,
                seed=seed,
                prior_character_profiles=prior_character_profiles,
                plan_index=plan_index,
                avoid_character_names=used_cast_names,
            )
            expanded.append({"outline": normalized, "process_feedback": pf if feedback_process else None})
            for n in _extract_sculptor_names_from_outline(normalized, locked=locked):
                if n not in used_cast_names:
                    used_cast_names.append(n)
            if len(expanded) >= plan_count:
                break
        if len(expanded) >= plan_count:
            break
    out = expanded[:plan_count]
    while len(out) < plan_count:
        out.append({"outline": "", "process_feedback": None})
    return out


def _coerce_antitrope_variants(
    variants: list,
    *,
    plan_count: int,
) -> List[Dict[str, Any]]:
    """反套路全文大纲：不做职能分块规范化，仅清洗 JSON 泄漏。"""
    from narrativeloom.utils.display_utils import normalize_mutation_marker_aliases, repair_antitrope_outline, strip_trailing_json_leak, unescape_display_text

    expanded: List[Dict[str, Any]] = []
    for item in variants:
        txt, _cast, pf = _normalize_unified_plan_item(item)
        txt = repair_antitrope_outline(strip_trailing_json_leak(unescape_display_text(txt))).strip()
        if txt:
            txt = normalize_mutation_marker_aliases(txt).strip()
            expanded.append({"outline": txt, "process_feedback": pf})
        else:
            expanded.append({"outline": "", "process_feedback": pf})
        if len(expanded) >= plan_count:
            break
    out = expanded[:plan_count]
    while len(out) < plan_count:
        out.append({"outline": "", "process_feedback": None})
    return out


_UNIFIED_FN_WORLDVIEW_ZH = (
    "【四案世界观基底硬性要求】恰好 4 个 variant，各绑定一种世界观，禁止混用或互换：\n"
    "variant[0]/方案A：历史架空基调（借鉴真实历史质感但允许合理虚构与时代挪移，禁止无解释穿越）\n"
    "variant[1]/方案B：当代现实基调（当下或近未来≤10年，真实社会逻辑，无超自然）\n"
    "variant[2]/方案C：未来科幻基调（科技/太空/近未来思潮，技术规则须自洽）\n"
    "variant[3]/方案D：奇幻架空基调（魔法/神话/异世界，须写明规则或代价）\n"
    "四版在地点类型、人物职业、矛盾来源上须彼此不可互换；禁止四版同为「导师+研究生+遗址/实验室」模板。"
)

_UNIFIED_FN_WORLDVIEW_EN = (
    "Exactly 4 variants, each locked to ONE worldview: "
    "A historical alt-world, B contemporary realism, C science fiction, D fantasy alt-world. "
    "No mixing; settings and casts must not be interchangeable across variants."
)

_UNIFIED_FN_INTRA_WORLDVIEW_ZH = (
    "【已定世界观】用户已选定世界观为「{label}」。四个 variant 均须严格处于该世界观内，"
    "但须在冲突类型、场景空间、人物关系组合、叙事节奏上彼此显著不同；"
    "禁止四版重复同一人物配置套路（如反复「导师+学生+遗址」）。"
)

_UNIFIED_FN_INTRA_AXES_ZH = (
    "四案须在下列轴心上拉开差距（仍属同一世界观）：\n"
    "方案A：人际信任/误解轴\n方案B：环境或空间谜团轴\n"
    "方案C：制度/规则/权限博弈轴\n方案D：意外事件打乱计划轴\n"
    "【硬性】四案的人物塑造师须给出不同的人物状态、关系张力与新增角色设定（若需新增）；"
    "禁止四版复制粘贴同一组姓名+同一身份描述。"
    "剧情逻辑师、冲突设计师、细节填充师、对话设计师的内容禁止仅做同义改写；"
    "须采用不同冲突类型、不同场景动作、不同信息揭示顺序与不同道具细节。"
)

_UNIFIED_FN_INTRA_AXES_EN = (
    "Four variants share the locked worldview but must differ on: "
    "A interpersonal, B environmental mystery, C institutional rules, D disruptive accident."
)

_UNIFIED_FN_TONE_ZH = (
    "【创作气质】不必一味写实、严肃、公文式或调查报告体；鼓励轻松幽默、有趣、感人、浪漫、"
    "情感浓烈、抽象诗意、不落俗套、出人意料的表达；可适度浪漫主义与非主流创意，"
    "避免四案都像「任务简报」。"
)

_UNIFIED_FN_BULLET_FORMAT_ZH = (
    "【分条格式】剧情逻辑师：因果链、关键突变各占独立一行（以「- 」开头）；"
    "冲突设计师：仅写核心矛盾、戏剧冲突、悬念（禁止输出「阻碍」「障碍」「角色阻碍」栏）；"
    "禁止用分号把多条挤在同一行。"
)

_UNIFIED_FN_LENGTH_ZH = (
    "【篇幅控制·易读】设定/剧情/冲突/细节等职能以 2–4 条 bullet 为宜，每条≤32 字；"
    "设定构建师仅写地点/时间/场景/规则四项；剧情逻辑师≤4 条；冲突设计师≤4 条。"
    "【人物塑造师】每人一行须写身份/性格/关系（≤40 字，自然短句，禁止半句截断）；"
    "禁止「动机是」「关系是」「本节状态」等标签；禁止单独写本节状态句。"
    "人物姓名须完整（如「阿依古丽」「艾买提」），禁止误截为「古丽」「艾买」等短名；禁止姓名中间插入冒号。"
)

_UNIFIED_FN_BREVITY_ZH = (
    "【承接前文·简写】若【已定前文】已交代人物身份、地点时间与世界规则，"
    "设定构建师与人物塑造师对已知信息仅一句带过（只写变化/新状态），"
    "把篇幅留给本小节新剧情、新冲突与新细节；禁止重抄完整人设与场景说明。"
)


def _unified_fn_prior_cap(beat_index: int, num_sections: int, feedback_process: bool) -> int:
    """随小节推进压缩前文注入量，抑制方案越写越长。"""
    n = max(2, int(num_sections))
    ratio = beat_index / max(1, n - 1)
    if ratio < 0.28:
        return 3000 if feedback_process else 2200
    if ratio < 0.72:
        return 2400 if feedback_process else 1700
    return 2000 if feedback_process else 1400


def _unified_fn_length_guidance(beat_index: int, num_sections: int, lang: str) -> str:
    """按叙事弧动态收紧功能化方案篇幅。"""
    phase = _story_arc_phase(beat_index, num_sections, "")
    if lang == "en":
        if phase == "opening":
            return (
                "LENGTH: 2-4 bullets per role block, ≤28 words each; "
                "character sculptor ≤40 words per line."
            )
        if phase == "development":
            return (
                "LENGTH: 2-3 bullets per role block, ≤24 words each; "
                "setting architect ≤3 items (one-line recap for known facts); "
                "character sculptor ≤32 words per line."
            )
        return (
            "LENGTH: 2-3 bullets per role block, ≤20 words each; "
            "setting architect ≤2 items; plot logic ≤3 bullets; "
            "character sculptor ≤28 words per line; no repeating earlier beats."
        )
    if phase == "opening":
        return _UNIFIED_FN_LENGTH_ZH
    if phase == "development":
        return (
            "【篇幅控制·发展段】各职能分块 2～3 条 bullet，每条≤26 字；"
            "设定构建师最多 3 项（已知地点/时间一句带过）；"
            "剧情逻辑师≤3 条；冲突设计师≤3 条；"
            "人物塑造师每人一行≤32 字（只写状态变化，禁止重抄人设）。"
        )
    return (
        "【篇幅控制·高潮段】各职能分块 2～3 条 bullet，每条≤22 字；"
        "设定构建师最多 2 项；剧情逻辑师≤3 条；冲突设计师≤3 条；"
        "人物塑造师每人一行≤28 字；禁止复述前文已写情节。"
    )


def _worldview_label(key: str, lang: str) -> str:
    labels = {
        "historical": ("历史架空", "Historical alt-world"),
        "contemporary": ("当代现实", "Contemporary realism"),
        "scifi": ("未来科幻", "Science fiction"),
        "fantasy": ("奇幻架空", "Fantasy alt-world"),
    }
    pair = labels.get(key, ("", ""))
    return pair[0] if lang != "en" else pair[1]


def generate_unified_functional_plans(
    *,
    roles: List[Tuple[str, str]],
    seed: str,
    beat_title: str,
    beat_hint: str,
    prior_summary: str,
    feedback_process: bool,
    llm_cfg: Optional[Dict[str, Any]] = None,
    canon_sheet: str = "",
    rag_excerpt: str = "",
    lang: str = "zh",
    locked_character_names: Optional[List[str]] = None,
    character_target_total: Optional[int] = None,
    anti_repetition_digest: str = "",
    plan_count: int = UNIFIED_FN_PLAN_COUNT,
    beat_index: int = 0,
    locked_worldview: Optional[str] = None,
    prior_beat_homogeneity_digest: str = "",
    locked_setting_baseline: str = "",
    num_sections: int = 6,
    prior_characters_block: str = "",
) -> Dict[str, Any]:
    """一次统筹全部职能，返回 plan_count 个完整小节总体方案（含【职能】分块）。"""
    cfg = _cfg_or_env(llm_cfg)
    ke_min, ke_max = _arc_key_events_range(beat_index, num_sections)
    arc_phase = _story_arc_phase(beat_index, num_sections, prior_summary)
    arc_label = _arc_phase_label(arc_phase, lang)
    ke_spec = _arc_key_events_spec(ke_min, ke_max, lang)
    roles = [(n, t) for n, t in roles if not is_unified_plan_excluded_role(n, lang)]
    locked = merge_unique_names(
        [n.strip() for n in (locked_character_names or []) if (n or "").strip()],
        extract_seed_cast_names(seed),
    )
    seed_cast = extract_seed_cast_names(seed)
    role_names = [n for n, _ in roles]
    roles_block = "\n".join(f"- {n}：{t}" for n, t in roles)
    headers = "、".join(f"【{n}】" for n in role_names)
    prior_cap = _unified_fn_prior_cap(beat_index, num_sections, feedback_process)
    length_block = _unified_fn_length_guidance(beat_index, num_sections, lang)
    pf_instr = (
        'Each variant includes non-empty "process_feedback" with creative_goal, design_rationale, narrative_technique.'
        if feedback_process and lang == "en"
        else (
            '每个 variant 须含非空 process_feedback（creative_goal、design_rationale、narrative_technique）。'
            if feedback_process
            else ""
        )
    )
    sculpt_target = character_target_total if character_target_total is not None else max(2, len(locked))
    arc_events_en = (
        f"Narrative arc: {arc_label}. Plot Logic role must output {ke_spec} bullet lines "
        f"({TYPIFIED_KEY_EVENT_CHARS_MIN}–{TYPIFIED_KEY_EVENT_CHARS_MAX} words each), each a causal story beat."
    )
    arc_events_zh = (
        f"【叙事弧·关键事件】本节为「{arc_label}」阶段；【剧情逻辑师】须输出 {ke_spec} bullet，"
        f"每条 {TYPIFIED_KEY_EVENT_CHARS_MIN}～{TYPIFIED_KEY_EVENT_CHARS_MAX} 字，写因果推进与转折；"
        "冲突设计师、对话设计师、细节填充师须配合上述事件密度，勿重复堆砌已知信息。"
    )
    has_sculptor = any(is_character_sculptor_role(n, lang) for n in role_names)
    setting_fmt = (
        "Setting Architect: use SEPARATE bullet lines for 地点 and 时间 (never combine on one line); "
        "then 场景 and 规则 if needed. "
        if lang == "en"
        else "【设定构建师】必须用独立两行分别写「- 地点：…」「- 时间：…」，禁止把地点与时间写在同一行；可再写场景、规则。"
    )
    wv_block = _UNIFIED_FN_WORLDVIEW_EN if lang == "en" else _UNIFIED_FN_WORLDVIEW_ZH
    if beat_index > 0 and locked_worldview:
        if lang == "en":
            wv_block = (
                f"Locked worldview: {_worldview_label(locked_worldview, lang)}. "
                "All 4 variants MUST stay in this worldview but differ on conflict, scene, and relationships. "
                + _UNIFIED_FN_INTRA_AXES_EN
            )
        else:
            wv_block = (
                _UNIFIED_FN_INTRA_WORLDVIEW_ZH.format(label=_worldview_label(locked_worldview, lang))
                + "\n"
                + _UNIFIED_FN_INTRA_AXES_ZH
            )
    elif locked_worldview and beat_index == 0 and locked_setting_baseline:
        if lang == "en":
            wv_block = (
                f"Locked worldview: {_worldview_label(locked_worldview, lang)}. "
                "All 4 variants share this worldview; differentiate on conflict axes only. "
                + _UNIFIED_FN_INTRA_AXES_EN
            )
        else:
            wv_block = (
                _UNIFIED_FN_INTRA_WORLDVIEW_ZH.format(label=_worldview_label(locked_worldview, lang))
                + "\n"
                + _UNIFIED_FN_INTRA_AXES_ZH
            )

    if lang == "en":
        system = (
            f"You are the narrative orchestrator. Output JSON only. "
            f'Return exactly {{"variants":[...]}} with {plan_count} objects. '
            f'Each variant.outline is ONE complete beat merge: role sections {headers}, '
            "each section bullet lines starting with '- '. All roles must collaborate without contradiction. "
            f"{setting_fmt} "
            "Variants must differ sharply. Do NOT repeat events already in prior beats; only new causal steps. "
            + arc_events_en
            + " "
            + length_block
            + " "
            + wv_block
            + pf_instr
        )
        user = (
            f"Sparkles: {seed}\nBeat: {beat_title} — {beat_hint}\nRoles:\n{roles_block}\n"
        )
    else:
        system = (
            f"你是叙事统筹，协调下列职能一次产出完整小节拼合稿。只输出 JSON。"
            f'必须返回 {{"variants":[...]}}，恰好 {plan_count} 个对象。'
            f"每个 variant 须为独立对象，含 cast 与 outline 两键。"
            f"cast：先完成人物构思，恰好 {sculpt_target} 行，每行「- 姓名：身份/性格/关系」（禁止占位句）；"
            "四案新增配角姓名不得重复（种子锁定人物除外），各案配角身份描述须各不相同。"
            f"outline：仅含除人物塑造师外的其它职能分块（可省略【人物塑造师】，系统会注入 cast）；"
            f"每个 variants 数组元素是独立对象，禁止把 {plan_count} 个方案拼进同一个 outline 字符串。"
            f'每个 variant.outline 仅含一套职能分块（人物塑造师由 cast 提供），'
            "分块内每行以「- 」开头（JSON 字符串内用真实换行，禁止输出字面量 \\n）；各职能内容互相呼应、不得矛盾。"
            f"{setting_fmt}"
            f"{_UNIFIED_FN_TONE_ZH}"
            f"{_UNIFIED_FN_BULLET_FORMAT_ZH}"
            f"{length_block}"
            + arc_events_zh
            + (_UNIFIED_FN_BREVITY_ZH if beat_index > 0 else "")
            + "【篇幅】各职能分块精炼可读，禁止用省略号截断；"
            "人物塑造师每行用自然短句写清身份、性格与关系（承接前文），禁止占位句。"
            "【冲突设计师】只写核心矛盾、戏剧冲突、悬念三类 bullet，禁止「阻碍/障碍」栏。"
            "【人物塑造师】禁止使用「动机是」「关系是」「本节状态」等标签；禁止单独写本节状态句；"
            "同一姓名不得拆成「阿依古丽」与「古丽」两条。"
            "【种子人物】若创意种子已给出主角姓名，人物塑造师必须全部保留，禁止替换为其它人物。"
            "【姓名完整性】须使用设定清单与前文中的完整人名，禁止截断（如「艾买提」不得写成「艾买」，「阿依古丽」不得写成「古丽」）。"
            f"【人物塑造师】分块仅写真实人物姓名，每行「角色名：……」；"
            f"恰好 {sculpt_target} 人（不多不少），缺一人则视为不合格；"
            "禁止写「性格与动机待展开」「本小节出场人物」「任务」「张力点」「核心矛盾」等非人名条目；"
            "禁止把动词片段、形容词片段当人名（如「韩星收」「韩星的」「阿米尔对宝」「严谨务」应分别规整为「韩星」「阿米尔」或丢弃）；"
            f"剧情逻辑师、氛围渲染师、冲突设计师等其它分块只能使用人物塑造师已列出的姓名，禁止新增未列出人物。"
            "四个总体方案须显著不同：人物状态、剧情走向、冲突焦点、细节道具均须彼此不可互换，禁止四版同质化。"
            "【连续性】禁止复述已定前文已发生的事件；只写本小节新增因果推进，人物状态须承接前文但四案推进角度须各异。"
            + wv_block
            + pf_instr
        )
        user = (
            f"创意种子：{seed}\n当前小节：{beat_title} — {beat_hint}\n"
            f"纳入统筹的职能：\n{roles_block}\n"
        )
    if seed_cast:
        if lang == "en":
            user += (
                f"\nSEED CAST (must all appear in Character Sculptor, exact spelling, no replacements): "
                f"{', '.join(seed_cast)}\n"
            )
        else:
            user += f"\n【创意种子既定人物（人物塑造师须全部保留，禁止替换或改名）】{'、'.join(seed_cast)}\n"
    if (prior_summary or "").strip():
        user += f"\n【已定前文】\n{(prior_summary or '')[:prior_cap]}\n"
        if beat_index > 0 and lang == "zh":
            user += (
                f"\n{_UNIFIED_FN_BREVITY_ZH}\n"
                "已定人物与基础设定请简写，仅补充本小节新变化。\n"
            )
    else:
        user += "\n【已定前文】（尚无）\n"
    if anti_repetition_digest.strip():
        user += f"\n【避免重复】下列内容前文已写过，勿在本小节再次复述：\n{anti_repetition_digest[:1200]}\n"
    if prior_beat_homogeneity_digest.strip():
        user += (
            f"\n【避免与已定小节同质化】下列为已定稿小节的设定/人物/冲突摘要，"
            "本小节四案须在推进新因果的同时，避免重复相同场景类型、人物关系模板与矛盾套路：\n"
            f"{prior_beat_homogeneity_digest[:1600]}\n"
        )
    if canon_sheet:
        user += f"\n【设定清单】\n{(canon_sheet or '')[:2000]}\n"
    if rag_excerpt:
        user += f"\n【相关摘录】\n{(rag_excerpt or '')[:1500]}\n"
    if locked_setting_baseline.strip():
        user += (
            f"\n【锁定时空设定（四案必须共用，仅可微调细节，禁止换场景/时代/世界观）】\n"
            f"{locked_setting_baseline.strip()[:1200]}\n"
        )
    if has_sculptor and locked:
        user += f"\n【前文已定人物须保留】{'、'.join(locked)}\n"
    if has_sculptor and sculpt_target > 0:
        extra = max(0, sculpt_target - len(locked))
        user += (
            f"\n【人物塑造师硬性要求】恰好 {sculpt_target} 名真实角色（每人一行，禁止占位句）；"
            f"其它职能分块只能引用这 {sculpt_target} 人的姓名，不得新增；"
            "前文已定人物须保留且不得改名。"
        )
        if extra > 0 and locked:
            user += f" 除已锁定的 {len(locked)} 人外，须再新增 {extra} 名新角色。"
        user += "\n"
    user += f"\n请输出 {plan_count} 个总体方案 JSON。"
    if lang == "zh" and beat_index == 0 and not locked_worldview:
        user += f"\n{_UNIFIED_FN_WORLDVIEW_ZH}"
    elif lang == "zh" and locked_worldview and beat_index > 0:
        user += (
            f"\n【重要】四案均须处于已定世界观「{_worldview_label(locked_worldview, lang)}」内，"
            "禁止再生成历史/当代/科幻/奇幻四种不同世界观；只在冲突类型与事件角度上差异化。\n"
            "【承接前文差异化】已定人物须保留，但四案须给出不同的人物状态更新、关系变化与新角色设定；"
            "禁止四版使用相同剧情句模板或相同细节道具组合。\n"
        )

    out_tokens = 2800 if feedback_process else 2400
    if beat_index > 0:
        phase = _story_arc_phase(beat_index, num_sections, prior_summary)
        if phase == "development":
            out_tokens = min(out_tokens, 2600 if feedback_process else 2200)
        elif phase == "climax":
            out_tokens = min(out_tokens, 2400 if feedback_process else 2000)
    raw = complete_chat(cfg, system, user, temperature=0.94, max_tokens=out_tokens)
    data = _parse_json_content(raw)
    variants = _functional_extract_variants(data, raw) if isinstance(data, dict) else []
    loose_outlines = _extract_fragment_strings_loose(raw)
    if len(loose_outlines) > len(variants):
        variants = [{"outline": o, "process_feedback": None} for o in loose_outlines]
    if not variants:
        frag0, _ = _functional_normalize_fragment(raw)
        if frag0.strip():
            variants = [{"outline": frag0}]
    from narrativeloom.utils.display_utils import parse_character_profile_map

    prior_profiles = parse_character_profile_map(prior_characters_block)
    coerced = _coerce_unified_plan_variants(
        variants,
        plan_count=plan_count,
        feedback_process=feedback_process,
        lang=lang,
        locked_character_names=locked,
        character_target_total=sculpt_target,
        role_names=role_names,
        beat_index=beat_index,
        seed=seed,
        prior_character_profiles=prior_profiles,
    )
    return {"_mode": "unified", "variants": coerced}


_ANTITROPE_ANGLES_ZH = (
    "【三版差异化硬性要求】禁止三版仅换词或只改一处：\n"
    "方案A：颠覆读者对因果/真相的预期（我以为X，其实Y）\n"
    "方案B：核心角色动机反转（表面目标≠真实欲望，关系重组）\n"
    "方案C：类型/氛围错位（严肃变荒诞、浪漫变冷峻、悬疑变日常等）\n"
    "每版至少 8 处 ⟦mut⟧ 标记，分布在小节与职能分块中；标记内容不得与其它版重复。"
)

_ANTITROPE_ANGLES_EN = (
    "Three variants MUST use distinct anti-cliché strategies: "
    "A subverts expected causality; B flips character motives; C mismatches genre/tone. "
    "At least 8 mutation markers per variant; no duplicated mutation patterns across variants."
)


def generate_antitrope_full_story(
    *,
    full_outline: str,
    seed: str,
    llm_cfg: Optional[Dict[str, Any]] = None,
    canon_sheet: str = "",
    lang: str = "zh",
    variant_count: int = 3,
) -> Dict[str, Any]:
    """对全部小节汇编大纲做反套路突变；突变句用 ⟦mut⟧…⟦/mut⟧ 包裹以便高亮。"""
    cfg = _cfg_or_env(llm_cfg)
    base = (full_outline or "").strip()
    if not base:
        return {"variants": [{"outline": "", "process_feedback": None}] * variant_count}
    task = antitrope_role_task(lang)
    if lang == "en":
        system = (
            "You are the Anti-Cliché Innovator. Output JSON only. "
            f'Return {{"variants":[...]}} with {variant_count} full-story outline upgrades. '
            f"Each variant.outline is the COMPLETE multi-section outline with the same section headers as input. "
            f"Wrap ONLY newly changed phrases in {_MUT_OPEN}...{_MUT_CLOSE} markers. "
            "At least 5 distinct mutations per variant across sections; mutate motives, conflict, imagery, tone. "
            "Do NOT emit bare /mut or \\mut literals. "
            f"{_ANTITROPE_ANGLES_EN}"
        )
        user = f"Sparkles: {seed}\n\nFULL OUTLINE:\n{base[:12000]}\n"
    else:
        system = (
            "你是反套路创意师。只输出 JSON。"
            f"返回 {variant_count} 个 variant，每个 variant.outline 为完整多小节大纲替换稿，"
            "保留原有小节/分块结构；须完整保留输入中的 ### **小节 n** 标题行（不得删除或合并）；"
            "仅对突变处用 "
            f"{_MUT_OPEN}…{_MUT_CLOSE} 包裹（未改处不要标记）。"
            f"每版至少 5 处突变，须分布在不同小节或职能分块；"
            "突变须触及人物动机、冲突走向、细节意象、对话语气或场景氛围，勿只改一词。"
            "三版突变角度须明显不同，保持整体因果连贯。"
            f"{_ANTITROPE_ANGLES_ZH}"
            "outline 必须是中文【职能名】分块正文（如【人物塑造师】），"
            "禁止用 English key 的 JSON 对象（如 character_builder、plot_logician）代替正文。"
            f"禁止输出 <<<、>>>、<<mut>> 等角括号标记；禁止输出裸露的 /mut、\\mut、mut 字面量；"
            f"只使用 {_MUT_OPEN}…{_MUT_CLOSE} 成对标记。"
            f"职能说明：{task}"
        )
        user = f"创意种子：{seed}\n\n【全部小节汇编大纲】\n{base[:12000]}\n"
    if canon_sheet:
        user += f"\n【设定清单】\n{canon_sheet[:2500]}\n"
    user += f"\n请输出 {variant_count} 个反套路升级大纲；三版须按上述 A/B/C 策略显著分化。"
    raw = complete_chat(cfg, system, user, temperature=0.96, max_tokens=8000)
    data = _parse_json_content(raw)
    variants = _functional_extract_variants(data, raw) if isinstance(data, dict) else []
    loose_outlines = _extract_fragment_strings_loose(raw)
    if len(loose_outlines) > len(variants):
        variants = [{"outline": o, "process_feedback": None} for o in loose_outlines]
    if not variants:
        frag0, _ = _functional_normalize_fragment(raw)
        if frag0.strip():
            variants = [{"outline": frag0}]
    coerced = _coerce_antitrope_variants(variants, plan_count=variant_count)
    return {"variants": coerced}


def generate_functional_variants(
    *,
    role_name: str,
    role_task: str,
    seed: str,
    beat_title: str,
    beat_hint: str,
    prior_summary: str,
    feedback_process: bool,
    llm_cfg: Optional[Dict[str, Any]] = None,
    canon_sheet: str = "",
    rag_excerpt: str = "",
    lang: str = "zh",
    character_target_total: Optional[int] = None,
    locked_character_names: Optional[List[str]] = None,
    setting_architect_active: bool = False,
) -> Dict[str, Any]:
    """单次调用返回恰好 3 个 variant，降低请求次数与卡顿。"""
    cfg = _cfg_or_env(llm_cfg)
    locked = merge_unique_names(
        [n.strip() for n in (locked_character_names or []) if (n or "").strip()],
        extract_seed_cast_names(seed),
    )
    sculpt = is_character_sculptor_role(role_name, lang)
    gen_temp = 0.93 if sculpt else 0.88
    sculpt_target = (
        character_target_total if character_target_total is not None else max(2, len(locked))
        if sculpt
        else None
    )
    sculpt_scope_only = sculpt and not setting_architect_active
    prior_cap = 4500 if feedback_process else 3200
    canon_cap = 2000
    rag_cap = 1500
    out_tokens = 2800 if feedback_process else 1600
    if feedback_process:
        vinstr = (
            'Each variant object MUST include "fragment" (string) plus non-empty "process_feedback": '
            '{"creative_goal":"...", "design_rationale":"...", "narrative_technique":"..."} — '
            "all three subfields must be at least one full sentence; never omit keys or leave them empty."
            if lang == "en"
            else (
                "每个 variant 必须同时含 fragment（string）与非空的 process_feedback 对象；"
                "process_feedback 须含 creative_goal、design_rationale、narrative_technique 三个键，"
                "且每项各至少一句具体中文，禁止省略键、禁止空字符串。"
                "禁止把整段 {\"variants\":[...]} 再嵌套进某个 variant 的 fragment；fragment 只许写要点文本。"
            )
        )
    else:
        vinstr = (
            'Each variant object only contains "fragment" (string).'
            if lang == "en"
            else "每个 variant 仅含 fragment 字符串。"
        )
    if lang == "en":
        system = (
            "You are one role in a writing team. Output JSON only, no markdown. "
            "Return exactly {\"variants\": [ {...}, {...}, {...} ]} with THREE variants. "
            "Each variant's fragment is a BRIEF outline only (not narrative prose): "
            + (
                f"exactly {sculpt_target} lines; each line is ONE named character "
                "('- Name: motive/relationship'); no world/physics/space/environment bullets. "
                if sculpt
                else "2–5 short lines separated by newline; each line starts with '- '; each line <= 90 characters; "
            )
            + "concrete beats for YOUR role only. No dialogue scenes, no multi-paragraph storytelling. "
            "CONTINUITY: If prior locked story is provided, every beat must logically extend that state; "
            "do not contradict or erase prior consequences unless explicitly flagged. "
            "Variants must differ in angle and emphasis. Never nest a full {\"variants\":[...]} JSON inside any fragment. "
            + (
                " Character Sculptor: A/B/C must use sharply different character rosters and temperaments."
                if sculpt
                else ""
            )
            + (
                " Character Sculptor ONLY: never output setting/world/physics/space/reminder lines; "
                "do not copy Setting Architect bullets from canon."
                if sculpt_scope_only
                else ""
            )
            + vinstr
        )
        user = (
            f"Sparkles: {seed}\nRole: {role_name} — {role_task}\n"
            f"Section: {beat_title} — {beat_hint}\n"
        )
        if (prior_summary or "").strip():
            user += (
                "\nLOCKED PRIOR STORY (ordered — your beats MUST nest into this causal chain):\n"
                + (prior_summary or "").strip()[:prior_cap]
                + "\n"
            )
        else:
            user += "\nPrior story: (none — opening).\n"
        if canon_sheet:
            user += f"\nCanon:\n{(canon_sheet or '')[:canon_cap]}\n"
        if rag_excerpt:
            user += f"\nRetrieved excerpts:\n{(rag_excerpt or '')[:rag_cap]}\n"
        if sculpt and sculpt_target is not None:
            user += (
                f"\nHARD RULE (Character Sculptor): fragment has EXACTLY {sculpt_target} lines — "
                f"each line ONE named person only ('- Name: motive/relationship'). "
                f"({len(locked)} locked from prior beats — keep all, only add traits/relations; never remove/rename). "
                "FORBIDDEN: world/physics/space lines; meta lines like 'Prior link', 'Check', 'Continuity' as bullet labels; "
                "only '- CharacterName: trait/motive/relation/state' per line.\n"
                "DIVERSITY: Variants A/B/C must differ sharply in cast and temperament.\n"
            )
            if sculpt_scope_only:
                user += (
                    "Setting Architect is NOT active in this beat — do NOT pad character count with non-person bullets.\n"
                )
            if locked:
                user += f"Locked character names (must all appear): {', '.join(locked)}\n"
            elif not (prior_summary or "").strip():
                user += (
                    "OPENING BEAT: Each variant should propose a distinct character lineup "
                    "(different names and personality mixes per variant).\n"
                )
        user += "Produce JSON with exactly 3 brief-outline variants."
    else:
        system = (
            "你是叙事创作团队中的单一职能角色。只输出 JSON，不要 Markdown 围栏。中文。"
            "必须返回 {\"variants\": [ {...}, {...}, {...} ]}，恰好三个对象。"
            "每个 variant 的 fragment 只能是「简要概述要点」，禁止写成叙事散文或完整故事。"
            + (
                f"fragment 格式：恰好 {sculpt_target} 行，每行「- 角色名：身份/性格/关系与行动（自然叙述，禁止「动机是」「关系是」「本节状态」）」；"
                "禁止物理提醒、空间拓展、承接前文、核查、连续性说明等元叙事标签行。"
                if sculpt and sculpt_target is not None
                else "fragment 格式：2～5 行短句，每行必须以「- 」开头；每行不超过 90 字；"
                "只写与本职能相关的可执行要点（关键词、节拍、提醒），不要场景描写与对白。"
            )
            + "三份概述须在角度与侧重点上明显不同，禁止仅换同义词。"
            + (
                "【人物塑造师】不得单独写「承接前文」「核查」等行；前文承接与一致性应融入各角色行的设定文字中。"
                if sculpt
                else "【连续性】若提供已定前文，每条要点必须能嵌入该因果链，禁止与前文人物状态或事件后果相矛盾。"
            )
            + "禁止把整段 JSON（含 variants 数组）塞进单个 fragment；每个 variant.fragment 只能是纯文本要点。"
            + (
                "【人物塑造师】三份 variant 的人物姓名、性格类型、关系结构必须显著差异化，"
                "须使用完整人名（如「艾买提」不得写成「艾买」），"
                "禁止三版同质化或仅替换同义词；开篇小节三版须尽量使用不同人物阵容与性格对比。"
                if sculpt
                else ""
            )
            + (
                "【人物塑造师范围】本节拍未启用设定构建师：禁止输出世界观/物理/空间/环境类条目，"
                "不得用「物理提醒」「空间拓展」等标签凑人数；人数目标仅统计具名角色。"
                if sculpt_scope_only
                else ""
            )
            + vinstr
        )
        user = (
            f"创意种子：{seed}\n职能：{role_name} — {role_task}\n"
            f"当前小节：{beat_title} — {beat_hint}\n"
        )
        if (prior_summary or "").strip():
            user += (
                "\n【已定前文（须承接；概述要点须嵌入已有故事线）】\n"
                + (prior_summary or "").strip()[:prior_cap]
                + "\n"
            )
        else:
            user += "\n【已定前文】（尚无，可按种子自由起势）\n"
        if canon_sheet:
            user += f"\n【设定清单】\n{(canon_sheet or '')[:canon_cap]}\n"
        if rag_excerpt:
            user += f"\n【相关前文摘录】\n{(rag_excerpt or '')[:rag_cap]}\n"
        if sculpt and sculpt_target is not None:
            user += (
                f"\n【人物塑造师硬性要求】fragment 恰好 {sculpt_target} 行，每行一名具名角色（「- 姓名：…」）。"
                f"前文已登场 {len(locked)} 人须全部保留，只补充画像/动机/关系；可新增角色至目标人数。"
                "禁止无姓名泛称；禁止「承接前文」「核查」「高潮点」「高潮节点」等非角色标签行；"
                "禁止把设定清单/物理提醒/空间拓展/环境规则当作人物条目。\n"
                "【差异化】方案 A/B/C 的人物配置须明显不同。\n"
            )
            if sculpt_scope_only:
                user += "【范围】未选设定构建师：勿写任何世界物理或场景规则行，人数仅由角色行构成。\n"
            if locked:
                user += f"【前文已定人物（须全部出现）】{ '、'.join(locked) }\n"
            elif not (prior_summary or "").strip():
                user += "【开篇】三版请给出不同的人物阵容与气质组合，避免姓名与性格高度雷同。\n"
        user += "请输出恰好三个「概述型」variant 的 JSON。"
    raw = complete_chat(cfg, system, user, temperature=gen_temp, max_tokens=out_tokens)
    data = _parse_json_content(raw)
    variants = _functional_extract_variants(data, raw) if isinstance(data, dict) else []
    if (
        len(variants) == 1
        and isinstance(variants[0], str)
        and _looks_like_wrapped_variants_json(variants[0])
    ):
        variants = _functional_extract_variants(_parse_json_content(variants[0]), variants[0])
    normalized = []
    for item in variants[:3]:
        frag, pfb = _functional_normalize_fragment(item)
        normalized.append({"fragment": frag, "process_feedback": pfb})
    while len(normalized) < 3:
        normalized.append({"fragment": "", "process_feedback": None})
    if not any((x.get("fragment") or "").strip() for x in normalized):
        frag0, pf0 = _functional_normalize_fragment(raw)
        if frag0.strip():
            normalized[0] = {"fragment": frag0, "process_feedback": pf0}
    coerced = []
    for i in range(3):
        txt, pfb_slot = functional_slot_bundle_from_pack(normalized, i)
        base_item = normalized[i] if i < len(normalized) and isinstance(normalized[i], dict) else {}
        eff_pf = pfb_slot if pfb_slot is not None else base_item.get("process_feedback")
        coerced.append({"fragment": txt, "process_feedback": eff_pf})
    for item in coerced:
        item["fragment"] = scrub_functional_fragment(item.get("fragment") or "")
    if sculpt:
        for item in coerced:
            item["fragment"] = filter_character_sculptor_fragment(
                item.get("fragment") or "",
                target_total=sculpt_target,
                locked_names=locked,
                seed=seed,
            )
    return {"variants": coerced}


def generate_antitrope_upgrade_variants(
    *,
    merged_text: str,
    seed: str,
    beat_title: str,
    beat_hint: str,
    prior_summary: str,
    llm_cfg: Optional[Dict[str, Any]] = None,
    canon_sheet: str = "",
    rag_excerpt: str = "",
    lang: str = "zh",
) -> Dict[str, Any]:
    """仅对「当前节拍拼接槽」全文做反套路突变，返回 3 个可替换该槽位的完整候选（不重跑各职能）。"""
    cfg = _cfg_or_env(llm_cfg)
    role = antitrope_role_name(lang)
    task = antitrope_role_task(lang)
    base = (merged_text or "").strip()
    if not base:
        return {"variants": [{"fragment": "", "process_feedback": None}] * 3}

    sections = parse_merge_role_sections(base)
    section_titles = [t for t, _ in sections]
    blocks_hint = "\n".join(f"- {t}" for t in section_titles) if section_titles else "- (preserve 【Role】 blocks from input)"

    if lang == "en":
        system = (
            "You are the Anti-Cliché Innovator on a writing team. Output JSON only. "
            f"Role: {role} — {task} "
            "Return exactly {\"variants\": [ {...}, {...}, {...} ]} with THREE upgraded outlines. "
            "Each variant.fragment is ONE complete replacement for the user's current beat merge slot only "
            "(not separate per-role regen). Keep every 【Role Title】 section from the input, same order; "
            "mutate bullet content anti-cliché; keep continuity. Three variants differ in surprise angle. "
            "Never nest JSON inside fragment."
        )
        user = (
            f"Sparkles: {seed}\nSection: {beat_title} — {beat_hint}\n\n"
            f"Section headers to preserve:\n{blocks_hint}\n\n"
            f"CURRENT BEAT MERGE SLOT (mutate this text only):\n{base[:8000]}\n"
        )
        if (prior_summary or "").strip():
            user += "\nPrior locked story:\n" + (prior_summary or "").strip()[:6500] + "\n"
        if canon_sheet:
            user += f"\nCanon:\n{canon_sheet}\n"
        if rag_excerpt:
            user += f"\nRAG:\n{rag_excerpt}\n"
        user += "Produce 3 anti-cliché upgraded full-merge variants."
    else:
        system = (
            "你是叙事团队中的「反套路创意师」。只输出 JSON，不要 Markdown 围栏。中文。"
            f"职能说明：{task} "
            "必须返回 {\"variants\": [ {...}, {...}, {...} ]}，恰好三个对象。"
            "每个 variant.fragment 是「当前节拍拼接槽」的唯一替换全文（不是让各职能重新生成）。"
            "必须保留输入中每一个【职能名】分块标题及顺序，分块内「- 」要点行；"
            "在槽位全文上做反套路创意突变，绝对避免俗套；须与已定前文因果一致。"
            f"突变处须用 {_MUT_OPEN}…{_MUT_CLOSE} 包裹以便界面高亮；禁止只输出裸 ⟦⟧ 箭头。"
            "三份候选突变角度须明显不同。禁止把 JSON 嵌进 fragment。"
        )
        user = (
            f"创意种子：{seed}\n当前小节：{beat_title} — {beat_hint}\n\n"
            f"【须保留的分块标题】\n{blocks_hint}\n\n"
            f"【当前节拍拼接槽·仅此全文待突变】\n{base[:8000]}\n"
        )
        if (prior_summary or "").strip():
            user += "\n【已定前文（升级后须可嵌入）】\n" + (prior_summary or "").strip()[:6500] + "\n"
        if canon_sheet:
            user += f"\n【设定清单】\n{canon_sheet}\n"
        if rag_excerpt:
            user += f"\n【相关前文摘录】\n{rag_excerpt}\n"
        user += "请输出三个反套路升级后的完整拼合候选。"
    raw = complete_chat(cfg, system, user, temperature=0.92, max_tokens=3200)
    data = _parse_json_content(raw)
    variants = _functional_extract_variants(data, raw) if isinstance(data, dict) else []
    normalized = []
    for item in variants[:3]:
        frag, pfb = _functional_normalize_fragment(item)
        normalized.append({"fragment": frag, "process_feedback": pfb})
    while len(normalized) < 3:
        normalized.append({"fragment": "", "process_feedback": None})
    if not any((x.get("fragment") or "").strip() for x in normalized):
        frag0, pf0 = _functional_normalize_fragment(raw)
        if frag0.strip():
            normalized[0] = {"fragment": frag0, "process_feedback": pf0}
    coerced = []
    for i in range(3):
        txt, pfb_slot = functional_slot_bundle_from_pack(normalized, i)
        base_item = normalized[i] if i < len(normalized) and isinstance(normalized[i], dict) else {}
        eff_pf = pfb_slot if pfb_slot is not None else base_item.get("process_feedback")
        coerced.append({"fragment": txt, "process_feedback": eff_pf})
    for item in coerced:
        item["fragment"] = scrub_functional_fragment(item.get("fragment") or "")
    return {"variants": coerced}


def expand_functional_section(
    *,
    seed: str,
    beat_title: str,
    beat_hint: str,
    merged_outline: str,
    llm_cfg: Optional[Dict[str, Any]] = None,
    canon_sheet: str = "",
    rag_excerpt: str = "",
    lang: str = "zh",
) -> str:
    """将职能概述拼接稿扩写为本小节叙事正文（确认后调用）。"""
    cfg = _cfg_or_env(llm_cfg)
    outline = (merged_outline or "").strip()
    if lang == "en":
        system = (
            "You are a fiction writer. Expand the role-outline notes into a single continuous section of prose. "
            "Multiple paragraphs, scene work, dialogue where natural, clear causal flow. "
            f"Target {PROSE_CHARS_PER_SECTION_MIN}–{PROSE_CHARS_PER_SECTION_MAX} words for this section only. "
            + _PROSE_SECTION_STYLE_EN
            + " Honor the canon list for names. "
            "Do NOT output Markdown '#' headings, section numbers, or phase labels like 'Opening'; start directly in scene."
        )
        user = (
            f"Sparkles: {seed}\nSection: {beat_title} — {beat_hint}\n\n"
            f"Role outlines merged:\n{outline}\n\nWrite this section only."
        )
        if canon_sheet:
            user = f"Canon:\n{canon_sheet}\n\n" + user
        if rag_excerpt:
            user = f"Context excerpts:\n{rag_excerpt}\n\n" + user
    else:
        system = (
            "你是中文小说作者。根据各职能的「概述要点」拼接稿，扩写为**本小节独立叙事正文**。"
            "多段落：场景、动作、对白与心理穿插，因果清楚，与前文摘要自然衔接；"
            "至少两处引号对话，并写清环境氛围与人物动作，避免只列事件梗概。"
            f"篇幅目标 {PROSE_CHARS_PER_SECTION_MIN}～{PROSE_CHARS_PER_SECTION_MAX} 字（单节正文，勿写成整章长篇）。"
            + _PROSE_SECTION_STYLE_ZH
            + "严格遵守设定清单中人物称谓；不要输出 JSON、不要复述职能标签堆砌。"
            "禁止输出以 # 开头的标题行、禁止写「小节1」「#开端」等结构标签；正文从第一段叙事直接起笔。"
        )
        user = (
            f"创意种子：{seed}\n当前小节：{beat_title} — {beat_hint}\n\n"
            f"【职能概述合并稿】\n{outline}\n\n请只写本小节正文。"
        )
        if canon_sheet:
            user = f"【设定清单】\n{canon_sheet}\n\n" + user
        if rag_excerpt:
            user = f"【相关前文摘录】\n{rag_excerpt}\n\n" + user
    raw = (complete_chat(cfg, system, user, temperature=0.72, max_tokens=8000) or "").strip()
    return scrub_expanded_prose_artifacts(raw)


def generate_functional_fragment(
    *,
    role_name: str,
    role_task: str,
    seed: str,
    beat_title: str,
    beat_hint: str,
    prior_summary: str,
    feedback_process: bool,
    llm_cfg: Optional[Dict[str, Any]] = None,
    canon_sheet: str = "",
    rag_excerpt: str = "",
    lang: str = "zh",
) -> Dict[str, Any]:
    """兼容：取三变体中的第一个。"""
    pack = generate_functional_variants(
        role_name=role_name,
        role_task=role_task,
        seed=seed,
        beat_title=beat_title,
        beat_hint=beat_hint,
        prior_summary=prior_summary,
        feedback_process=feedback_process,
        llm_cfg=llm_cfg,
        canon_sheet=canon_sheet,
        rag_excerpt=rag_excerpt,
        lang=lang,
    )
    v0 = (pack.get("variants") or [{}])[0]
    return {"fragment": v0.get("fragment", ""), "process_feedback": v0.get("process_feedback")}


def continuity_advice(
    llm_cfg: Optional[Dict[str, Any]],
    *,
    seed: str,
    canon_sheet: str,
    rag_excerpt: str,
    section_title: str,
    section_hint: str,
    prior_summary: str,
    draft_fragments_summary: str,
    lang: str = "zh",
) -> str:
    """连贯性校验师：单一文本建议，不提供多方案选项。"""
    cfg = _cfg_or_env(llm_cfg)
    if lang == "en":
        system = (
            "You are a continuity advisor. Read canon, prior summary, and draft fragments for ONE section. "
            "Output plain prose only (no JSON, no numbered options, no 'Variant A/B'). "
            "Give 3–6 sentences: alignment checks, timeline/character risks, and concrete fix suggestions."
        )
        user = (
            f"Sparkles: {seed}\nSection: {section_title} — {section_hint}\n"
            f"Prior summary:\n{prior_summary}\n\nCanon:\n{canon_sheet or '(none)'}\n\n"
            f"Excerpts:\n{rag_excerpt or '(none)'}\n\nDraft material:\n{draft_fragments_summary}\n"
        )
    else:
        system = (
            "你是连贯性校验师。根据设定清单、前文摘要与本节素材，输出一段纯文字建议（禁止 JSON、禁止编号方案、禁止「方案A/B」）。"
            "用 4～8 句中文：指出与已定设定/前文的衔接点、潜在时间线或人物状态风险，并给出可执行的修改提示。"
        )
        user = (
            f"创意种子：{seed}\n当前小节：{section_title} — {section_hint}\n"
            f"已发生剧情摘要：\n{prior_summary}\n\n【设定清单】\n{canon_sheet or '（无）'}\n\n"
            f"【相关前文摘录】\n{rag_excerpt or '（无）'}\n\n【本节素材草稿】\n{draft_fragments_summary}\n"
        )
    return (complete_chat(cfg, system, user, temperature=0.35, max_tokens=900) or "").strip()


def _world_complexity_hint_zh(level: str) -> str:
    lv = (level or "medium").strip().lower()
    if lv not in ("simple", "medium", "complex"):
        lv = "medium"
    return {
        "simple": "简单：地点与规则线索较少，1～2 个主场景即可写透，动线清楚。",
        "medium": "中等：2～4 个互相关联的场景或时间层次，信息密度适中。",
        "complex": "复杂：社会结构、空间布局或规则约束可多线交织，但仍须具体可感、可画出示意图，避免玄学堆砌。",
    }[lv]


def _world_complexity_hint_en(level: str) -> str:
    lv = (level or "medium").strip().lower()
    if lv not in ("simple", "medium", "complex"):
        lv = "medium"
    return {
        "simple": "Simple: fewer locations/rules; 1–2 anchor scenes with clear geography.",
        "medium": "Medium: 2–4 linked scenes or time layers; moderate detail density.",
        "complex": "Complex: richer institutions, geography, or constraints; still concrete and drawable, not abstract maze-stacking.",
    }[lv]


def generate_background_block(
    *,
    role_name: str,
    role_task: str,
    seed: str,
    story_title: str,
    existing_setting: str,
    existing_characters: str,
    llm_cfg: Optional[Dict[str, Any]] = None,
    lang: str = "zh",
    main_char_count: int = 3,
    world_complexity: str = "medium",
    background_focus: str = "world",
) -> str:
    """背景阶段：世界设定或人物档案纲要（纯文本）。"""
    cfg = _cfg_or_env(llm_cfg)
    n = max(1, min(6, int(main_char_count)))
    focus = (background_focus or "world").strip().lower()
    if focus not in ("world", "people"):
        focus = "world"
    if lang == "en":
        system = (
            f"You are {role_name}. {role_task} "
            "Output structured plain text with short headings and bullets. "
            "No dialogue, no full story. About 250–450 words."
        )
        user = (
            f"Title: {story_title}\nSparkles: {seed}\n\n"
            f"Existing world notes (may extend, not contradict):\n{existing_setting or '(none)'}\n\n"
            f"Existing character notes:\n{existing_characters or '(none)'}\n\n"
            "Hard constraints for THIS generation:\n"
            f"- {_world_complexity_hint_en(world_complexity)}\n"
            f"- Named core cast target count: {n} (each with name + motive or relationship).\n"
        )
        if focus == "world":
            user += "- Focus this output on WORLD / SCENES; keep people minimal but consistent with the cast count.\n"
        else:
            user += "- Focus this output on CHARACTER DOSSIERS; keep world notes only as context for those people.\n"
    else:
        system = (
            f"你是{role_name}。{role_task}"
            + "输出结构化纯文本（可用小标题与分点），不要对白与完整故事。"
            + "篇幅约 350～600 字，信息具体可执行。"
        )
        user = (
            f"故事标题：{story_title}\n创意种子：{seed}\n\n"
            f"已有世界设定（可补充，勿自相矛盾）：\n{existing_setting or '（无）'}\n\n"
            f"已有人物档案：\n{existing_characters or '（无）'}\n\n"
            "【本次生成硬性约束】\n"
            f"- {_world_complexity_hint_zh(world_complexity)}\n"
            f"- 核心主要人物（须有名有姓、可贯穿故事）人数：{n} 位；每人至少一句动机或关系。\n"
        )
        if focus == "world":
            user += "- 本条任务侧重「世界/场景」：人物只写与场景强相关的最小集合，勿写成完整人物小传列表。\n"
        else:
            user += "- 本条任务侧重「人物档案」：世界/地点只写与人物处境直接相关的环境，勿喧宾夺主。\n"
    return (complete_chat(cfg, system, user, temperature=0.75, max_tokens=2200) or "").strip()


def generate_background_variants(
    *,
    role_name: str,
    role_task: str,
    seed: str,
    story_title: str,
    existing_setting: str,
    existing_characters: str,
    llm_cfg: Optional[Dict[str, Any]] = None,
    lang: str = "zh",
    main_char_count: int = 3,
    world_complexity: str = "medium",
    background_focus: str = "world",
) -> list[str]:
    """背景阶段：一次生成三条可并行选择的纲要（与类型化「多方案」一致）。"""
    cfg = _cfg_or_env(llm_cfg)
    n = max(1, min(6, int(main_char_count)))
    focus = (background_focus or "world").strip().lower()
    if focus not in ("world", "people"):
        focus = "world"
    if lang == "en":
        system = (
            f"You are {role_name}. {role_task} "
            "Output JSON only: {\"options\":[\"...\",\"...\",\"...\"]} with EXACTLY THREE strings. "
            "Each string is concise structured plain text (short headings + bullets), mutually distinct in angle; "
            "each 140–240 words; no dialogue, no full story scene. "
            "For spatial layout, describe concrete, filmable geography (rooms, streets, terrain, movement) — "
            "avoid dream-within-a-maze layering or abstract dimensional stacking unless the sparkles explicitly demand fantasy. "
            "Escape any double quotes inside strings as \\\" or avoid ASCII double quotes."
        )
        user = (
            f"Title: {story_title}\nSparkles: {seed}\n\n"
            f"Existing world notes (may extend, not contradict):\n{existing_setting or '(none)'}\n\n"
            f"Existing character notes:\n{existing_characters or '(none)'}\n\n"
            "Hard constraints for ALL three options (they must differ in angle while respecting these):\n"
            f"- {_world_complexity_hint_en(world_complexity)}\n"
            f"- Named core cast target count: {n}.\n"
        )
        if focus == "world":
            user += "- Focus: WORLD / SCENES; people minimal but aligned with the cast count.\n"
        else:
            user += "- Focus: CHARACTER DOSSIERS; world only as context for those people.\n"
    else:
        system = (
            f"你是{role_name}。{role_task}"
            "只输出 JSON：{\"options\":[\"纲要一\",\"纲要二\",\"纲要三\"]}，恰好三个字符串。"
            "三条须在切入角度、要素组合或叙事重心上明显不同，禁止仅换同义词。"
            "每条为结构化纯文本（小标题+分点），每条约 180～320 字；不要对白、不要完整故事成篇。"
            "「空间结构」指可被直接想象或画出的具体场景布局（街区、建筑内外、自然地貌、动线距离等），"
            "禁止写成多层梦境迷宫、无限嵌套、玄学层级等非写实套话；除非种子明确要求奇幻，否则以写实为主。"
            "字符串内禁止未转义的英文双引号 \"，请用「」或单引号。"
        )
        user = (
            f"故事标题：{story_title}\n创意种子：{seed}\n\n"
            f"已有世界设定（可补充，勿自相矛盾）：\n{existing_setting or '（无）'}\n\n"
            f"已有人物档案：\n{existing_characters or '（无）'}\n\n"
            "【三条纲要须共同遵守的硬性约束】\n"
            f"- {_world_complexity_hint_zh(world_complexity)}\n"
            f"- 核心主要人物（须有名有姓）人数：{n} 位；三条方案可在角度上不同，但人数档位须一致。\n"
        )
        if focus == "world":
            user += "- 侧重「世界/场景」：人物只写与场景强相关的最小集合。\n"
        else:
            user += "- 侧重「人物档案」：世界只写与人物处境直接相关的环境。\n"
    raw = complete_chat(cfg, system, user, temperature=0.78, max_tokens=3600)
    data = _parse_json_content(raw)
    opts = data.get("options") if isinstance(data, dict) else None
    if not isinstance(opts, list):
        opts = []
    out = [str(x).strip() for x in opts[:3] if str(x).strip()]
    while len(out) < 3:
        out.append("")
    if not any(out):
        fb = generate_background_block(
            role_name=role_name,
            role_task=role_task,
            seed=seed,
            story_title=story_title,
            existing_setting=existing_setting,
            existing_characters=existing_characters,
            llm_cfg=llm_cfg,
            lang=lang,
            main_char_count=n,
            world_complexity=world_complexity,
            background_focus=focus,
        )
        out[0] = (fb or "").strip()
    return out[:3]


def _repair_expand_prose_raw(raw: str) -> Tuple[str, str]:
    """
    修复模型将 prose 拆成多个 \"...\";\"...\" 片段导致的非法 JSON。
    """
    text = _json_sanitize((raw or "").strip())
    if not text:
        return "", ""

    data = _parse_json_content(text)
    if isinstance(data, dict):
        title = str(data.get("title") or data.get("story_title") or "").strip()
        prose = str(data.get("prose") or data.get("body") or data.get("text") or data.get("content") or "").strip()
        if prose and not prose.lstrip().startswith('{"') and "prose" not in prose[:80]:
            return title, prose

    title = ""
    tm = re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.S)
    if tm:
        title = tm.group(1).replace("\\n", "\n").replace('\\"', '"').strip()

    pm = re.search(r'"prose"\s*:\s*"(.*)', text, re.S | re.I)
    if not pm:
        if text.startswith("{") and '"prose"' in text:
            inner = text[text.find('"prose"'):]
            pm = re.search(r'"prose"\s*:\s*"(.*)', inner, re.S | re.I)
        else:
            return title, scrub_expanded_prose_artifacts(text)

    rest = pm.group(1)
    parts = re.split(r'"\s*;\s*"', rest)
    cleaned: List[str] = []
    for i, p in enumerate(parts):
        p = p.replace("\\n", "\n").replace('\\"', '"')
        if i == len(parts) - 1:
            p = re.sub(r'"\s*\}\s*$', "", p, flags=re.S)
            p = re.sub(r'"\s*,\s*"title".*$', "", p, flags=re.S | re.I)
        p = p.strip().strip('"')
        if p:
            cleaned.append(p)
    prose = "\n\n".join(cleaned).strip()
    if not prose:
        prose = re.sub(r'^[\s\S]*?"prose"\s*:\s*"?', "", text, count=1, flags=re.I)
        prose = re.sub(r'"\s*\}\s*$', "", prose).strip().strip('"')
    return title, prose


def expand_prose(
    *,
    seed: str,
    beats_combined: str,
    llm_cfg: Optional[Dict[str, Any]] = None,
    canon_sheet: str = "",
    rag_excerpt: str = "",
    lang: str = "zh",
    num_sections: int = 6,
) -> Tuple[str, str]:
    """
    将小节汇编扩写为连贯长叙事。
    返回 (title, prose)：title 为模型建议的整篇标题（可能为空）；prose 为正文。
    总篇幅与小节数正相关：每节约 800～1000 字（中英文同），须含对话、环境、动作等细节。
    """
    cfg = _cfg_or_env(llm_cfg)
    bc = (beats_combined or "").strip()
    n_sec = _clamp_section_count(num_sections)
    prose_min, prose_max = _prose_length_budget(n_sec)
    max_tokens = min(16000, max(5000, prose_max * 2))
    if lang == "en":
        system = (
            "You are an accomplished literary fiction writer. Expand the beat compilation into "
            "publishable literary prose with genuine style: vary sentence rhythm (lyrical long lines "
            "against sharp short beats); use concrete sensory detail, metaphor, synesthesia, and "
            "subtext in dialogue; allow brief interior monologue and controlled lyricism. "
            "Avoid reportage, clichés, and flat subject-verb-object chains. "
            "Honor the outline's causality while letting scenes breathe with atmosphere and tension. "
            f"Aim for roughly {prose_min}–{prose_max} words total ({n_sec} sections × {PROSE_CHARS_PER_SECTION_MIN}–{PROSE_CHARS_PER_SECTION_MAX} words each). "
            "Do not exceed the upper bound. "
            + _PROSE_SECTION_STYLE_EN
            + " "
            "Output ONE JSON object ONLY, no markdown fences, keys exactly: "
            '{"title":"Short literary title for the whole piece, 4–12 words, no section numbers","prose":"..."} . '
            "The prose MUST NOT use Markdown '#' headings, section numbering, or meta labels like 'Opening'; "
            "start directly in scene. "
            "CRITICAL: prose must be ONE JSON string; use \\n\\n between paragraphs, NEVER \";\" between quoted chunks."
        )
        user = f"Sparkles: {seed}\n\n"
        if canon_sheet:
            user += f"Canon:\n{canon_sheet}\n\n"
        if rag_excerpt:
            user += f"Excerpts:\n{rag_excerpt}\n\n"
        user += f"Beat compilation ({n_sec} sections):\n{bc}\n\nReturn JSON with title and prose."
    else:
        system = (
            "你是资深中文文学小说作者。根据小节汇编扩写为具有文学质感的长叙事："
            "句式长短错落，适当运用比喻、通感、象征与留白；"
            "环境描写服务情绪与主题，动作与心理交织，对话须有潜台词与人物口吻，"
            "每小节至少两处引号对话，场景切换处补足光线/气味/声响等感官细节；"
            "禁止通篇「谁做了什么」的主谓宾流水账、公文腔与网络套话。"
            "在严守汇编因果与人物称谓的前提下，让场景有呼吸感与张力，意象要具体可感，"
            "可适度运用诗性语句，但避免堆砌辞藻或空洞抒情。"
            f"总篇幅目标约 {prose_min}～{prose_max} 字（共 {n_sec} 个小节，每节约 {PROSE_CHARS_PER_SECTION_MIN}～{PROSE_CHARS_PER_SECTION_MAX} 字，与小节数正相关）；"
            "不得超过上限，避免冗长重复。"
            + _PROSE_SECTION_STYLE_ZH
            + "严格遵守人物称谓与设定清单。"
            "【输出格式】只输出一个 JSON 对象，不要 Markdown 代码围栏；键名固定为："
            '{"title":"……","prose":"……"} 。'
            "title 为整篇作品的文学性标题（6～24 字），不要含小节号、不要「#开端」等相位词，不要复述正文首句。"
            "prose 为扩写后的完整正文：禁止在 prose 中使用「#」「##」等 Markdown 标题行；"
            "禁止以小节编号或「小节1」「#开端」等作为开头；正文从第一段叙事直接起笔。"
            "【JSON 硬性】prose 必须是单个 JSON 字符串；段落之间用 \\n\\n，禁止用 \";\" 拼接多个引号字符串；"
            "正文内的英文双引号须转义为 \\\"。"
            "若模型未输出换行，也须在场景切换、对话前后、时间跳跃处主动分段。"
        )
        user = f"创意种子：{seed}\n\n"
        if canon_sheet:
            user += f"【人物与设定清单（必须遵守）】\n{canon_sheet}\n\n"
        if rag_excerpt:
            user += f"【前文摘录】\n{rag_excerpt}\n\n"
        user += f"小节汇编（共 {n_sec} 节）：\n{bc}\n\n请输出上述 JSON。"
    raw = (complete_chat(cfg, system, user, temperature=0.82, max_tokens=max_tokens, retry_attempts=8, retry_pause=3.0) or "").strip()
    title, prose = _repair_expand_prose_raw(raw)
    if not prose:
        data = _parse_json_content(raw)
        if isinstance(data, dict):
            title = title or str(data.get("title") or data.get("story_title") or "").strip()
            prose = str(data.get("prose") or data.get("body") or data.get("text") or data.get("content") or "").strip()
    if prose:
        prose = scrub_expanded_prose_artifacts(prose)
        prose = format_prose_paragraphs(prose)
        if prose.lstrip().startswith("{") and '"prose"' in prose[:120]:
            _, prose2 = _repair_expand_prose_raw(prose)
            if prose2:
                prose = format_prose_paragraphs(scrub_expanded_prose_artifacts(prose2))
    else:
        prose = format_prose_paragraphs(scrub_expanded_prose_artifacts(raw))
    if title:
        title = re.sub(r'[#"\'「」]', "", title).strip()[:48]
    return title, prose


def refine_segment(
    llm_cfg: Optional[Dict[str, Any]],
    *,
    original: str,
    instruction: str,
    lang: str = "zh",
) -> str:
    cfg = _cfg_or_env(llm_cfg)
    if lang == "en":
        system = (
            "You are a professional editor. Revise the text per instructions; keep voice and coherence. "
            "Output only the revised prose."
        )
    else:
        system = "你是专业编辑。按用户指示修订正文，保持叙事连贯与人称一致，直接输出修订后正文，不要解释。"
    user = f"【原文 / Original】\n{original}\n\n【要求 / Instructions】\n{instruction}"
    return complete_chat(cfg, system, user, temperature=0.55, max_tokens=8192)


def brainstorm_segment(
    llm_cfg: Optional[Dict[str, Any]],
    *,
    original: str,
    instruction: str,
    lang: str = "zh",
) -> str:
    cfg = _cfg_or_env(llm_cfg)
    if lang == "en":
        system = (
            "You are a creative partner. From the text and prompt, propose 2–3 divergent directions. "
            "Use headings 'Variant A', 'Variant B', etc. English."
        )
    else:
        system = (
            "你是创意写作搭档。基于原文与用户灵感，给出 2～3 个发散方案，"
            "用「变体 A」「变体 B」等标题分段，中文，可略长。"
        )
    user = f"【当前文本】\n{original}\n\n【头脑风暴方向】\n{instruction}"
    return complete_chat(cfg, system, user, temperature=0.92, max_tokens=4096)
