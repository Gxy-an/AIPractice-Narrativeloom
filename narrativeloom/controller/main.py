# -*- coding: utf-8 -*-
"""
NarrativeLoom-pro(?) 协同叙事：登录 → 创作 → 草稿 → 提交后量表。

"""

from __future__ import annotations

import html
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from narrativeloom.domain import coherence
from narrativeloom.service import drafts_store
from narrativeloom.service import experiment_log
from narrativeloom.utils.display_utils import (
    build_fn_prior_homogeneity_digest,
    coerce_display_text,
    extract_character_names_from_text,
    key_events_meaningful,
    key_events_to_bullets,
    format_functional_merged_outline,
    merge_unique_character_names,
    muffle_markdown_heading_lines,
    normalize_single_unified_outline,
    prior_beats_repetition_digest,
    strip_assembly_beat_headers,
    strip_mutation_markers,
    sync_assembly_outline_to_beats,
    typified_characters_meaningful,
)
from narrativeloom.config.i18n import T, normalize_persona_pool
from narrativeloom.service.llm_client import (
    FN_WORLDVIEW_KEYS,
    recommend_functional_roles,
    brainstorm_segment,
    expand_prose,
    generate_antitrope_full_story,
    generate_unified_functional_plans,
    generate_typified_beat,
    refine_segment,
    review_beat_consistency,
    review_merged_text,
)
from narrativeloom.service.llm_unified import cfg_from_preset, default_api_key_from_env, default_preset_from_env, verify_connection
from narrativeloom.domain.personas import (
    filter_recommended_role_names,
    functional_recommendation_order,
    functional_role_order,
    get_functional_personas,
    get_typified_personas,
    is_antitrope_role,
    is_unified_plan_excluded_role,
    filter_unified_plan_role_names,
    make_beat_labels,
)
from narrativeloom.service.story_rag import build_chunks_from_beats, canon_sheet_from_beats, retrieve_context
from narrativeloom.config.access_gate import render_access_gate
from narrativeloom.config.consent_gate import render_consent_gate
from narrativeloom.front.ui_components import (
    inject_css,
    page_heading,
    render_beat_section_title,
    render_landing_hero,
    render_landing_lang_corner,
    render_lang_select,
    render_prose_block,
    render_sidebar_brand,
    render_unified_plan_carousel,
    unified_plan_pick_key,
    scroll_workspace_to_top,
    render_typified_carousel,
    section_heading,
    render_workspace_story_header,
    wizard_close,
    wizard_open,
)


def _lg() -> str:
    return st.session_state.get("ui_lang", "zh")


def _n_sections() -> int:
    return max(2, min(10, int(st.session_state.get("num_sections", 6))))


def _resize_beat_arrays(n: int) -> None:
    n = max(2, min(10, int(n)))
    st.session_state.num_sections = n
    mapping = {
        "beats": None,
        "beat_edit_events": 0,
        "beat_regen_count": 0,
        "beat_times": 0.0,
    }
    for key, fill in mapping.items():
        arr = list(st.session_state.get(key, []))
        if len(arr) < n:
            arr = arr + [fill] * (n - len(arr))
        elif len(arr) > n:
            arr = arr[:n]
        st.session_state[key] = arr
    cb = int(st.session_state.get("current_beat", 0))
    if cb >= n:
        st.session_state.current_beat = max(0, n - 1)


def _sync_beat_len_to_num_sections() -> None:
    if len(st.session_state.beats) != _n_sections():
        _resize_beat_arrays(_n_sections())


def _body_canon_prefix(lg: str = "zh") -> str:
    en = (lg or "zh") == "en"
    parts: List[str] = []
    s = (st.session_state.get("background_setting") or "").strip()
    c = (st.session_state.get("background_characters") or "").strip()
    preset = st.session_state.get("preset_protagonist_names") or []
    if preset:
        if en:
            parts.append(
                "【Preset protagonist names (must appear in every section)】\n"
                + ", ".join(str(n) for n in preset if n)
            )
        else:
            parts.append("【既定主角姓名（各小节须出现）】\n" + "、".join(str(n) for n in preset if n))
    if s:
        parts.append(("【World setting brief】\n" if en else "【世界设定纲要】\n") + s)
    if c:
        parts.append(("【Character profiles brief】\n" if en else "【人物档案纲要】\n") + c)
    return "\n\n".join(parts)


def _reset_new_story() -> None:
    lg = _lg()
    n = _n_sections()
    st.session_state.story_title = T("default_story_title", lg)
    st.session_state.seed = ""
    st.session_state.current_beat = 0
    st.session_state.beats = [None] * n
    st.session_state.beat_edit_events = [0] * n
    st.session_state.beat_regen_count = [0] * n
    st.session_state.beat_times = [0.0] * n
    st.session_state.beat_start_ts = time.time()
    st.session_state.typified_candidates = []
    st.session_state.typified_snapshot = {}
    st.session_state.functional_candidates = {}
    st.session_state.expanded_prose = ""
    st.session_state.background_setting = ""
    st.session_state.background_characters = ""
    st.session_state.preset_protagonist_names = []
    st.session_state.fn_story_char_total = 2
    st.session_state.typ_story_char_total = 2
    st.session_state.bg_phase_done = True
    st.session_state.fn_recommended_roles = []
    st.session_state.pop("fn_rec_sig", None)
    for i in range(_n_sections()):
        st.session_state.pop(f"fn_rec_roles_{i}", None)
    st.session_state.creation_explain_on = False
    st.session_state.workflow_phase = "beats"
    st.session_state.pop("story_outline_for_expand", None)
    st.session_state.pop("antitrope_full_pack", None)
    st.session_state.pop("fn_locked_worldview", None)
    st.session_state.pop("fn_locked_setting", None)
    for i in range(_n_sections()):
        st.session_state.pop(f"fn_beat_outline_{i}", None)
    st.session_state.pop("draft_asm", None)
    st.session_state.pop("assembly_antitrope_synced", None)
    st.session_state.pop("force_assemble", None)
    st.session_state.pop("_auto_expand_tag", None)
    st.session_state.wizard_done = False
    st.session_state.persona_pool_locked = None


def _init_state() -> None:
    defaults: Dict[str, Any] = {
        "app_access_granted": False,
        "informed_consent_accepted": False,
        "logged_in": False,
        "ui_lang": "zh",
        "llm_cfg": None,
        "login_preset": default_preset_from_env(),
        "custom_base": "",
        "custom_model": "",
        "ui_nav": "new",
        "story_title": "我的故事",
        "seed": "",
        "persona_pool": "genre",
        "creation_explain_on": False,
        "workflow_phase": "beats",
        "num_sections": 6,
        "current_beat": 0,
        "beats": [None] * 6,
        "beat_edit_events": [0] * 6,
        "beat_regen_count": [0] * 6,
        "beat_times": [0.0] * 6,
        "beat_start_ts": time.time(),
        "typified_candidates": [],
        "typified_snapshot": {},
        "functional_candidates": {},
        "expanded_prose": "",
        "background_setting": "",
        "background_characters": "",
        "bg_phase_done": True,
        "fn_recommended_roles": [],
        "fn_story_char_total": 2,
        "typ_story_char_total": 2,
        "preset_protagonist_names": [],
        "fn_locked_setting": "",
        "post_survey_phase": False,
        "likert_u": 3,
        "likert_i": 3,
        "likert_c": 3,
        "likert_s": 3,
        "writing_experience": "新手",
        "pool_migrated": False,
        "marketing_page": "home",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if "creation_explain_on" not in st.session_state and st.session_state.get("show_explanations"):
        st.session_state.creation_explain_on = bool(st.session_state.get("show_explanations"))
    _nav_legacy = {
        "新建创作": "new",
        "草稿箱": "drafts",
        "帮助": "help",
        "设置": "settings",
    }
    if st.session_state.ui_nav in _nav_legacy:
        st.session_state.ui_nav = _nav_legacy[st.session_state.ui_nav]
    if not st.session_state.pool_migrated:
        st.session_state.persona_pool = normalize_persona_pool(st.session_state.persona_pool)
        st.session_state.pool_migrated = True
    if "wizard_done" not in st.session_state:
        st.session_state.wizard_done = any(b is not None for b in st.session_state.get("beats", []))
    if "persona_pool_locked" not in st.session_state:
        st.session_state.persona_pool_locked = None
    if st.session_state.wizard_done and st.session_state.persona_pool_locked is None:
        st.session_state.persona_pool_locked = normalize_persona_pool(st.session_state.persona_pool)
    _sync_beat_len_to_num_sections()


def _nav_labels() -> Dict[str, str]:
    lg = _lg()
    return {
        "drafts": T("nav_drafts", lg),
    }


def _beat_to_text(b: Optional[Dict[str, Any]], lang: str) -> str:
    if not b:
        return ""
    if b.get("mode") == "typified":
        if lang == "en":
            return (
                f"Setting:\n{b.get('setting','')}\n"
                f"Characters:\n{b.get('characters','')}\n"
                f"Key events:\n{b.get('key_events','')}"
            )
        return (
            f"地点/设定：{b.get('setting','')}\n"
            f"人物：{b.get('characters','')}\n"
            f"核心事件：{b.get('key_events','')}"
        )
    raw = (b.get("merged") or b.get("merged_outline") or "").strip()
    return format_functional_merged_outline(raw) if raw else ""


def _assemble_all_beats_text(lg: str, n: int) -> str:
    """小节汇编：各小节分开呈现，小节标题加粗（不按人格跨节整合）。"""
    h = T("beat_heading_word", lg)
    parts: List[str] = []
    for i in range(n):
        b = st.session_state.beats[i]
        if not b:
            continue
        parts.append(f"### **{h} {i + 1}**\n{_beat_to_text(b, lg)}")
    return "\n\n".join(parts)


def _locked_character_names(beat_idx: int, lg: str) -> List[str]:
    """前文、背景与创意种子中已登场/既定人物（只增不减）。"""
    from narrativeloom.domain.character_names import (
        extract_seed_cast_names,
        filter_valid_cast_names,
        parse_preset_protagonist_names,
    )

    lists: List[List[str]] = []
    preset = st.session_state.get("preset_protagonist_names") or []
    if preset:
        lists.append(list(preset))
    seed = (st.session_state.get("seed") or "").strip()
    if seed:
        lists.append(extract_seed_cast_names(seed))
    bg = (st.session_state.get("background_characters") or "").strip()
    if bg:
        lists.append(extract_character_names_from_text(bg))
    for i in range(beat_idx):
        b = st.session_state.beats[i]
        if not isinstance(b, dict):
            continue
        if b.get("mode") == "typified":
            ch = (b.get("characters") or "").strip()
            if ch:
                lists.append(extract_character_names_from_text(ch))
        else:
            merged = (b.get("merged") or "").strip()
            if merged:
                lists.append(
                    extract_character_names_from_text(merged, sculptor_sections_only=True)
                )
    merged = merge_unique_character_names(*lists)
    ctx = f"{seed}\n{bg}"
    filtered = filter_valid_cast_names(merged, preserve=list(preset), context=ctx)
    for p in preset:
        if p and p not in filtered:
            filtered.insert(0, p)
    return filtered


def _prior_beat_char_target(beat_idx: int, pool: str) -> int:
    """上一小节确认/使用的人物目标数（后续小节下限参考）。"""
    if beat_idx <= 0:
        return 0
    if pool == "genre":
        internal_key = f"_typ_char_target_{beat_idx - 1}"
        prev_key = f"typ_char_total_{beat_idx - 1}"
        story_key = "typ_story_char_total"
    else:
        internal_key = f"_fc_char_target_{beat_idx - 1}"
        prev_key = f"fn_char_total_{beat_idx - 1}"
        story_key = "fn_story_char_total"
    if internal_key in st.session_state:
        return max(2, int(st.session_state[internal_key]))
    if prev_key in st.session_state:
        return max(2, int(st.session_state[prev_key]))
    return max(2, int(st.session_state.get(story_key) or 2))


def _extract_setting_baseline(outline: str) -> str:
    """从功能化拼合稿提取设定构建师内容，供后续小节锁定时空。"""
    from narrativeloom.utils.display_utils import parse_merge_role_sections

    raw = (outline or "").strip()
    if not raw:
        return ""
    for title, body in parse_merge_role_sections(raw):
        if "设定构建" in title or "Setting Architect" in title:
            return (body or "").strip()[:1200]
    return ""


def _fn_plan_labels(lg: str, beat_idx: int) -> List[str]:
    """四案标题仅显示方案 A/B/C/D，世界观说明放在 caption 中。"""
    _ = beat_idx
    return [T("plan_a", lg), T("plan_b", lg), T("plan_c", lg), T("plan_d", lg)]


def _arc_char_growth(beat_idx: int, n_sections: int, base: int, max_cap: int) -> int:
    """随叙事推进略增可用人头（开端=基线，发展+1，高潮+2）。"""
    n = max(2, int(n_sections))
    if beat_idx <= 0:
        return min(max_cap, max(2, base))
    ratio = beat_idx / max(1, n - 1)
    if ratio < 0.34:
        growth = 0
    elif ratio < 0.67:
        growth = 1
    else:
        growth = 2
    return min(max_cap, max(2, base + growth))


def _default_character_target(beat_idx: int, lg: str) -> int:
    """功能化：基线来自向导或上一小节，且覆盖前文锁定人物。"""
    locked = _locked_character_names(beat_idx, lg)
    if beat_idx <= 0:
        base = int(st.session_state.get("fn_story_char_total") or 2)
        return min(14, max(base, len(locked), 2))
    prev_target = _prior_beat_char_target(beat_idx, "function")
    return min(14, max(prev_target, len(locked), 2))


def _default_typified_character_target(beat_idx: int, lg: str) -> int:
    """类型化：基线来自向导或上一小节，且覆盖种子与前文锁定人物。"""
    locked = _locked_character_names(beat_idx, lg)
    if beat_idx <= 0:
        base = int(st.session_state.get("typ_story_char_total") or 2)
        return min(8, max(base, len(locked), 2))
    prev_target = _prior_beat_char_target(beat_idx, "genre")
    return min(8, max(prev_target, len(locked), 2))


def _sync_beat_char_target(beat_idx: int, lg: str, pool: str) -> None:
    """进入小节时初始化目标人数（不覆盖用户已手动设定的值）。"""
    if pool == "genre":
        suggested = _default_typified_character_target(beat_idx, lg)
        key = f"typ_char_total_{beat_idx}"
    else:
        suggested = _default_character_target(beat_idx, lg)
        key = f"fn_char_total_{beat_idx}"
    if key not in st.session_state:
        st.session_state[key] = suggested
        if pool == "genre":
            st.session_state[f"_typ_char_target_{beat_idx}"] = suggested


def _apply_typified_char_target(beat_idx: int, char_target: int) -> int:
    """写入类型化小节人物目标（仅用非 widget 键，避免与 number_input 冲突）。"""
    val = max(2, int(char_target))
    st.session_state[f"_typ_char_target_{beat_idx}"] = val
    return val


def _resolve_typified_char_target(beat_idx: int, lg: str) -> int:
    """解析当前小节类型化人物目标；重新生成时优先使用用户刚提交的值。"""
    pending_key = f"_typ_regen_char_target_{beat_idx}"
    if pending_key in st.session_state:
        return _apply_typified_char_target(beat_idx, int(st.session_state.pop(pending_key)))
    for key in (f"_typ_char_target_{beat_idx}", f"typ_char_total_{beat_idx}"):
        if key in st.session_state:
            return max(2, int(st.session_state[key]))
    return max(2, _default_typified_character_target(beat_idx, lg))


def _resanitize_typified_candidates(
    beat_idx: int,
    lg: str,
    labels: List[Tuple[str, str]],
    candidates: List[Tuple[str, Dict[str, Any]]],
    char_target: int,
) -> List[Tuple[str, Dict[str, Any]]]:
    """按目标人数二次规范化各题材候选，确保卡片与存储一致。"""
    from narrativeloom.utils.display_utils import sanitize_typified_characters

    locked = _locked_character_names(beat_idx, lg)
    target = max(int(char_target), len(locked), 2)
    prior = _prior_characters_block(beat_idx, labels, lg) if beat_idx > 0 else ""
    seed = st.session_state.get("seed") or ""
    out: List[Tuple[str, Dict[str, Any]]] = []
    for name, data in candidates:
        item = dict(data)
        item["characters"] = sanitize_typified_characters(
            item.get("characters", ""),
            target=target,
            locked_names=locked,
            seed=seed,
            setting=str(item.get("setting", "")),
            key_events=str(item.get("key_events", "")),
            prior_characters_block=prior,
            strict_narrative_allowlist=False,
            max_characters=8,
            lang=lg,
        )
        out.append((name, item))
    return out


def _prior_summary(idx: int, labels: List[Tuple[str, str]], lg: str) -> str:
    """按小节顺序拼接已定正文纲要，供后续小节严格承接（线性递进）。"""
    if idx <= 0:
        return ""
    parts: List[str] = []
    budget = 7200
    used = 0
    for i in range(idx):
        b = st.session_state.beats[i]
        if not isinstance(b, dict):
            continue
        ti, hi = labels[i]
        body = _beat_to_text(b, lg).strip()
        if not body:
            continue
        block = f"## {ti} · {hi}\n{body}"
        allow = min(len(block), 2000)
        piece = block[:allow]
        if used + len(piece) + 4 > budget:
            piece = piece[: max(0, budget - used - 4)]
        if piece.strip():
            parts.append(piece.strip())
            used += len(piece) + 4
        if used >= budget:
            break
    return "\n\n".join(parts) if parts else ""


TYPIFIED_GEN_COUNT = 0  # 0 表示并行生成全部类型化人格，不截断
TYPIFIED_MAX_WORKERS = max(1, min(10, int(os.getenv("TYPIFIED_MAX_WORKERS", "4"))))


def _clear_beat_candidate_state() -> None:
    """切换小节或重新生成前清空候选，避免旧卡片与加载态叠在一起。"""
    st.session_state.typified_candidates = []
    st.session_state.typified_snapshot = {}
    st.session_state.functional_candidates = {}
    st.session_state.pop("_fc_beat_idx", None)
    st.session_state.pop("_typ_beat_idx", None)


def _clear_typified_ui_keys(beat_idx: int) -> None:
    """清除小节级 Streamlit 控件键，避免切换/加载时旧卡片与编辑区叠影。"""
    prefixes = (
        f"tw_set_{beat_idx}_",
        f"tw_ch_{beat_idx}_",
        f"tw_ev_{beat_idx}_",
    )
    for k in list(st.session_state.keys()):
        sk = str(k)
        if any(sk.startswith(p) for p in prefixes):
            st.session_state.pop(k, None)
    for k in (
        f"typ_page_{beat_idx}",
        f"typ_picked_{beat_idx}",
        f"unified_plan_page_{beat_idx}",
        f"unified_plan_pick_{beat_idx}",
        f"merge_preview_{beat_idx}",
    ):
        st.session_state.pop(k, None)


def _prior_characters_block(
    beat_idx: int, labels: List[Tuple[str, str]], lg: str
) -> str:
    """汇总背景、向导预设与前序小节已定人物，供各题材/职能在本节更新（非重置）。"""
    from narrativeloom.utils.display_utils import extract_sculptor_section_text

    parts: List[str] = []
    preset = st.session_state.get("preset_protagonist_names") or []
    if preset:
        parts.append(
            f"【向导既定主角（各小节须出现）】\n" + "、".join(n for n in preset if n)
        )
    bg = (st.session_state.get("background_characters") or "").strip()
    if bg:
        parts.append(f"【背景人物档案】\n{bg[:2000]}")
    for i in range(beat_idx):
        b = st.session_state.beats[i]
        if not isinstance(b, dict):
            continue
        ch = ""
        if b.get("mode") == "typified":
            ch = (b.get("characters") or "").strip()
        elif b.get("mode") == "functional":
            outline = (
                st.session_state.get(f"fn_beat_outline_{i}")
                or b.get("merged_outline")
                or ""
            )
            ch = extract_sculptor_section_text(str(outline))
        if not ch:
            continue
        ti = labels[i][0] if i < len(labels) else f"Section {i + 1}"
        parts.append(f"【第{i + 1}节 · {ti} 已定人物】\n{ch[:1200]}")
    return "\n\n".join(parts)


def _kickoff_beat_generation(
    idx: int,
    pool: str,
    *,
    char_target: Optional[int] = None,
) -> None:
    """生成阶段一：清空旧 UI 状态并标记 generating，立即 rerun 以只显示 spinner。"""
    if pool == "genre" and char_target is not None:
        val = _apply_typified_char_target(idx, char_target)
        st.session_state[f"_typ_regen_char_target_{idx}"] = val  # 生成阶段读取，勿写 widget 键
    _clear_beat_candidate_state()
    _clear_typified_ui_keys(idx)
    st.session_state["_generating_beat_idx"] = idx
    st.session_state["_generating_pool"] = pool
    st.rerun()


def _run_generating_beat(
    idx: int,
    pool: str,
    lg: str,
    llm_cfg: Dict[str, Any],
    feedback_process: bool,
    canon: str,
    rag: str,
    labels: List[Tuple[str, str]],
) -> None:
    """生成阶段二：仅 spinner，单次 API 批次，完成后 rerun 展示候选。"""
    gen_pool = st.session_state.get("_generating_pool") or pool
    try:
        with st.spinner(T("auto_gen_running", lg)):
            status = st.empty()
            if gen_pool == "genre":
                n_personas = len(get_typified_personas(lg))
                status.caption(
                    T("gen_status_typified", lg).format(n=n_personas, done=0)
                )
            else:
                status.caption(T("gen_status_unified", lg))
            _generate_beat_candidates(
                idx,
                gen_pool,
                lg,
                llm_cfg,
                feedback_process,
                canon,
                rag,
                labels,
                status=status if gen_pool == "genre" else None,
            )
    except Exception as e:  # noqa: BLE001
        st.session_state.pop("_generating_beat_idx", None)
        st.session_state.pop("_generating_pool", None)
        st.error(str(e))
        st.stop()
    st.session_state.pop("_generating_beat_idx", None)
    st.session_state.pop("_generating_pool", None)
    st.rerun()


def _llm_cfg_fingerprint(cfg: Dict[str, Any]) -> str:
    return "|".join(
        [
            str(cfg.get("provider") or ""),
            str(cfg.get("model") or ""),
            str(cfg.get("base_url") or "")[:80],
            str(cfg.get("api_key") or "")[:16],
        ]
    )


def _rag_bundle(idx: int, labels: List[Tuple[str, str]], *, typified: bool = False) -> Tuple[str, str]:
    lg = _lg()
    prior_beats = [st.session_state.beats[i] for i in range(max(0, idx))]
    canon = canon_sheet_from_beats(
        prior_beats, background_prefix=_body_canon_prefix(lg), lang=lg
    )
    if typified and idx <= 0:
        return canon[:1200] if canon else "", ""
    texts = [_beat_to_text(st.session_state.beats[i], lg) for i in range(idx)]
    chunks = build_chunks_from_beats([t for t in texts if t.strip()])
    title, hint = labels[idx]
    tail = "\n".join(texts[-3:] if typified else texts[-5:]) if texts else ""
    cap = 2000 if typified else 3200
    query = f"{st.session_state.seed}\n{tail}\n{title}\n{hint}\n{canon}"[:cap]
    top_k = 2 if typified else 4
    rag = retrieve_context(query=query, chunks=chunks, top_k=top_k)
    if typified and rag:
        rag = rag[:900]
    return (canon[:1200] if typified and canon else canon), rag


def _preview_text(s: Any, n: int = 200) -> str:
    t = coerce_display_text(s).replace("\n", " ").strip()
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _render_process_feedback(label: str, pf: Any, lang: str) -> None:
    """创作界面开启「创作解释」时，在候选卡片展示可折叠解释。"""
    if not st.session_state.get("creation_explain_on", False):
        return
    with st.expander(f"{T('creation_explain', lang)} · {label}", expanded=False):
        if not pf:
            st.caption(T("creation_explain_missing", lang))
            return
        if isinstance(pf, dict):
            st.markdown(
                f"**{T('pf_goal', lang)}** {pf.get('creative_goal','')}\n\n"
                f"**{T('pf_rationale', lang)}** {pf.get('design_rationale','')}\n\n"
                f"**{T('pf_technique', lang)}** {pf.get('narrative_technique','')}"
            )
        else:
            st.write(str(pf))


def _parallel_typified(
    beat_idx: int,
    llm_cfg: Dict[str, Any],
    feedback_process: bool,
    canon: str,
    rag: str,
    labels: List[Tuple[str, str]],
    lang: str,
    *,
    status: Any = None,
    char_target: Optional[int] = None,
) -> List[Tuple[str, Dict[str, Any]]]:
    seed = st.session_state.seed
    title, hint = labels[beat_idx]
    prior = _prior_summary(beat_idx, labels, lang)
    locked_chars = _locked_character_names(beat_idx, lang)
    preset = list(st.session_state.get("preset_protagonist_names") or [])
    prior_chars = _prior_characters_block(beat_idx, labels, lang) if beat_idx > 0 else ""
    if char_target is None:
        char_target = max(_resolve_typified_char_target(beat_idx, lang), len(locked_chars), 2)
    else:
        char_target = max(int(char_target), len(locked_chars), 2)
    _apply_typified_char_target(beat_idx, char_target)
    personas = get_typified_personas(lang)
    if TYPIFIED_GEN_COUNT > 0:
        personas = personas[:TYPIFIED_GEN_COUNT]
    results_map: Dict[str, Dict[str, Any]] = {}
    n_total = len(personas)
    done_count = 0

    def job(persona: Tuple[str, str]) -> Tuple[str, Dict[str, Any]]:
        name, ph = persona
        last_err: Optional[Exception] = None
        for attempt in range(4):
            try:
                return name, generate_typified_beat(
                    genre_name=name,
                    genre_hint=ph,
                    seed=seed,
                    beat_title=title,
                    beat_hint=hint,
                    prior_summary=prior,
                    feedback_process=feedback_process,
                    llm_cfg=llm_cfg,
                    canon_sheet=canon,
                    rag_excerpt=rag,
                    lang=lang,
                    locked_character_names=locked_chars,
                    prior_characters_block=prior_chars,
                    beat_index=beat_idx,
                    num_sections=len(labels),
                    character_target_total=char_target,
                    preset_protagonist_names=preset,
                )
            except Exception as e:  # noqa: BLE001
                last_err = e
                msg = str(e).lower()
                if attempt >= 3 or (
                    "429" not in msg and "too many" not in msg and "rate" not in msg
                ):
                    raise
                time.sleep(1.2 * (attempt + 1))
        if last_err:
            raise last_err
        raise RuntimeError("typified generation failed")

    workers = min(TYPIFIED_MAX_WORKERS, len(personas))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(job, p) for p in personas]
        for fu in as_completed(futs):
            nm, data = fu.result()
            results_map[nm] = data
            done_count += 1
            if status is not None:
                status.caption(
                    T("gen_status_typified", lang).format(n=n_total, done=done_count)
                )
    results: List[Tuple[str, Dict[str, Any]]] = []
    for name, _ in get_typified_personas(lang)[: len(personas)]:
        data = results_map.get(name) or {"setting": "", "characters": "", "key_events": ""}
        results.append((name, data))
    return results


def _generate_unified_functional(
    beat_idx: int,
    llm_cfg: Dict[str, Any],
    feedback_process: bool,
    canon: str,
    rag: str,
    labels: List[Tuple[str, str]],
    lang: str,
    roles: List[Tuple[str, str]],
) -> Dict[str, Any]:
    title, hint = labels[beat_idx]
    prior = _prior_summary(beat_idx, labels, lang)
    locked_chars = _locked_character_names(beat_idx, lang)
    char_target = int(
        st.session_state.get(f"fn_char_total_{beat_idx}", _default_character_target(beat_idx, lang))
    )
    char_target = max(2, char_target, len(locked_chars))
    st.session_state[f"_fc_char_target_{beat_idx}"] = char_target
    prior_texts = [_beat_to_text(st.session_state.beats[i], lang) for i in range(beat_idx)]
    digest = prior_beats_repetition_digest(prior_texts)
    prior_outlines: List[str] = []
    for i in range(beat_idx):
        sn = st.session_state.get(f"fn_beat_outline_{i}") or ""
        if sn.strip():
            prior_outlines.append(sn)
        elif st.session_state.beats[i] and st.session_state.beats[i].get("mode") == "functional":
            prior_outlines.append(str(st.session_state.beats[i].get("merged_outline") or ""))
    homogeneity = build_fn_prior_homogeneity_digest(prior_outlines, lang=lang)
    locked_wv = st.session_state.get("fn_locked_worldview")
    prior_chars = _prior_characters_block(beat_idx, labels, lang)
    return generate_unified_functional_plans(
        roles=roles,
        seed=st.session_state.seed or "",
        beat_title=title,
        beat_hint=hint,
        prior_summary=prior,
        feedback_process=feedback_process,
        llm_cfg=llm_cfg,
        canon_sheet=canon,
        rag_excerpt=rag,
        lang=lang,
        locked_character_names=locked_chars,
        character_target_total=char_target,
        anti_repetition_digest=digest,
        beat_index=beat_idx,
        num_sections=len(labels),
        locked_worldview=locked_wv if beat_idx > 0 else None,
        prior_beat_homogeneity_digest=homogeneity,
        locked_setting_baseline=st.session_state.get("fn_locked_setting") or "",
        prior_characters_block=prior_chars,
    )


def _ensure_fn_recommendations(
    lg: str,
    llm_cfg: Dict[str, Any],
    beat_idx: int,
    labels: List[Tuple[str, str]],
    *,
    force: bool = False,
) -> List[str]:
    """根据种子与故事架构刷新功能化职能推荐列表。

    默认使用本地启发式（无 API）；仅点击「重新推荐」时调用模型，避免每次 rerun 触发慢请求。
    """
    cache_key = f"fn_rec_roles_{beat_idx}"
    if not force and cache_key in st.session_state:
        rec = list(st.session_state[cache_key])
        mk = f"fn_multi_{beat_idx}"
        if mk not in st.session_state:
            st.session_state[mk] = rec
        return rec

    title, hint = labels[beat_idx]
    prior = _prior_summary(beat_idx, labels, lg)
    n_sec = len(labels)
    rec = recommend_functional_roles(
        seed=st.session_state.seed or "",
        story_title=st.session_state.story_title or "",
        beat_idx=beat_idx,
        beat_title=title,
        beat_hint=hint,
        prior_summary=prior,
        num_sections=n_sec,
        background_setting=st.session_state.get("background_setting", ""),
        background_characters=st.session_state.get("background_characters", ""),
        lang=lg,
        llm_cfg=llm_cfg,
        use_llm=force,
    )
    rec = filter_recommended_role_names(rec, lg)
    st.session_state[cache_key] = rec
    st.session_state.fn_recommended_roles = rec
    mk = f"fn_multi_{beat_idx}"
    if force or mk not in st.session_state:
        st.session_state[mk] = rec
    return rec


def _generate_beat_candidates(
    idx: int,
    pool: str,
    lg: str,
    llm_cfg: Dict[str, Any],
    feedback_process: bool,
    canon: str,
    rag: str,
    labels: List[Tuple[str, str]],
    *,
    status: Any = None,
) -> None:
    """并行生成当前小节候选（类型化或功能化）。"""
    if pool == "genre":
        char_target = max(_resolve_typified_char_target(idx, lg), len(_locked_character_names(idx, lg)), 2)
        _apply_typified_char_target(idx, char_target)
        raw_candidates = _parallel_typified(
            idx,
            llm_cfg,
            feedback_process,
            canon,
            rag,
            labels,
            lg,
            status=status,
            char_target=char_target,
        )
        st.session_state.typified_candidates = _resanitize_typified_candidates(
            idx, lg, labels, raw_candidates, char_target
        )
        st.session_state["_typ_beat_idx"] = idx
        st.session_state.typified_snapshot = {
            nm: {
                "setting": coerce_display_text(d.get("setting", "")),
                "characters": coerce_display_text(d.get("characters", "")),
                "key_events": coerce_display_text(d.get("key_events", "")),
            }
            for nm, d in st.session_state.typified_candidates
        }
        st.session_state[f"typ_page_{idx}"] = 0
        st.session_state.pop(f"typ_picked_{idx}", None)
    else:
        fn_roles = _parallel_roles_for_generation(idx, lg)
        if not fn_roles:
            st.warning(T("fn_recommend_empty", lg))
            return
        fc = _generate_unified_functional(
            idx, llm_cfg, feedback_process, canon, rag, labels, lg, fn_roles
        )
        fn_role_names = [r for r, _ in fn_roles]
        locked_chars = _locked_character_names(idx, lg)
        char_target = max(
            2,
            int(st.session_state.get(f"_fc_char_target_{idx}", _default_character_target(idx, lg))),
            len(locked_chars),
        )
        from narrativeloom.utils.display_utils import parse_character_profile_map

        prior_profiles = parse_character_profile_map(
            _prior_characters_block(idx, labels, lg)
        )
        norm_variants: List[Dict[str, Any]] = []
        for item in fc.get("variants") or []:
            outline = str(item.get("outline") or "").strip()
            if outline:
                outline = normalize_single_unified_outline(
                    outline,
                    role_names=fn_role_names,
                    lang=lg,
                    locked_names=locked_chars,
                    character_target_total=char_target,
                    beat_index=idx,
                    seed=st.session_state.get("seed") or "",
                    prior_character_profiles=prior_profiles,
                )
            norm_variants.append({**item, "outline": outline})
        st.session_state.functional_candidates = {**fc, "variants": norm_variants}
        st.session_state["_fc_beat_idx"] = idx
    st.session_state.beat_regen_count[idx] += 1


def _process_pending_beat_confirm(
    *,
    idx: int,
    n: int,
    labels: List[Tuple[str, str]],
    lg: str,
    llm_cfg: Dict[str, Any],
    feedback_process: bool,
    role_order: List[str],
) -> bool:
    """处理「确认本小节」队列任务；返回 True 表示已处理（调用方应 st.stop）。"""
    key = f"_pending_confirm_{idx}"
    payload = st.session_state.pop(key, None)
    if not payload:
        return False

    _clear_typified_ui_keys(idx)
    title, hint = labels[idx]
    canon, rag = _rag_bundle(idx, labels)
    with st.spinner(T("confirm_running", lg)):
        if payload.get("pool") == "genre":
            sel = payload["sel"]
            s = payload["setting"]
            ch = payload["characters"]
            ev = payload["key_events"]
            dsel = st.session_state.typified_snapshot.get(sel, {})
            snap = st.session_state.typified_snapshot.get(sel, {})
            user_edited = 1 if (
                s != snap.get("setting", "")
                or ch != snap.get("characters", "")
                or ev != snap.get("key_events", "")
            ) else 0
            reg = max(0, st.session_state.beat_regen_count[idx] - 1)
            st.session_state.beat_edit_events[idx] = user_edited + reg
            elapsed = max(0.0, time.time() - st.session_state.beat_start_ts)
            st.session_state.beat_times[idx] = round(elapsed, 2)
            beat_raw = {"setting": s, "characters": ch, "key_events": ev}
            reviewed = beat_raw
            if feedback_process:
                reviewed = review_beat_consistency(
                    llm_cfg,
                    canon_sheet=canon,
                    rag_excerpt=rag,
                    beat=beat_raw,
                    lang=lg,
                )
            summary_line = (reviewed.get("setting") or "")[:80]
            kv = reviewed.get("key_events", ev)
            if not key_events_meaningful(coerce_display_text(kv)):
                kv = ev
            if not key_events_meaningful(coerce_display_text(kv)):
                kv = coerce_display_text(dsel.get("key_events", ""))
            norm_ev = key_events_to_bullets(kv)
            if not (norm_ev or "").strip():
                norm_ev = key_events_to_bullets(ev) or key_events_to_bullets(dsel.get("key_events", ""))
            if not (norm_ev or "").strip():
                norm_ev = coerce_display_text(kv)
            st.session_state.beats[idx] = {
                "mode": "typified",
                "persona": sel,
                "setting": reviewed.get("setting", s),
                "characters": reviewed.get("characters", ch),
                "key_events": (norm_ev or ev).strip(),
                "summary_line": summary_line + ("…" if len(summary_line) >= 80 else ""),
                "process_feedback": dsel.get("process_feedback"),
                "review_notes": reviewed.get("review_notes", ""),
            }
        else:
            mt = (payload.get("merged_text") or "").strip()
            chosen_roles = payload.get("chosen_roles") or []
            fc = st.session_state.functional_candidates or {}
            selected2 = [r for r in chosen_roles if r in fc]
            if not selected2:
                selected2 = list(role_order)
            user_edited = int(payload.get("user_edited", 0))
            reg = max(0, st.session_state.beat_regen_count[idx] - 1)
            st.session_state.beat_edit_events[idx] = user_edited + reg
            elapsed = max(0.0, time.time() - st.session_state.beat_start_ts)
            st.session_state.beat_times[idx] = round(elapsed, 2)
            merged_final = mt
            rnote = ""
            if feedback_process:
                merged_final, rnote = review_merged_text(
                    llm_cfg,
                    canon_sheet=canon,
                    rag_excerpt=rag,
                    merged_text=mt,
                    lang=lg,
                )
            notes = (rnote or "").strip()
            st.session_state.beats[idx] = {
                "mode": "functional",
                "personas": ",".join(selected2) if selected2 else "—",
                "merged": merged_final,
                "merged_outline": merged_final,
                "summary_line": merged_final[:80].replace("\n", " ")
                + ("…" if len(merged_final) > 80 else ""),
                "review_notes": notes,
            }
            st.session_state.pop(payload.get("sig_key") or f"_fc_sig_{idx}", None)

        _clear_beat_candidate_state()
        next_idx = min(n - 1, idx + 1)
        st.session_state.current_beat = next_idx
        st.session_state.beat_start_ts = time.time()
        st.session_state["force_assemble"] = True
        if idx < n - 1:
            st.session_state["_auto_gen_beat"] = next_idx
        all_done = all(st.session_state.beats[i] for i in range(n))
        if all_done and idx == n - 1:
            if payload.get("pool") == "function":
                st.session_state.workflow_phase = "antitrope"
            else:
                _run_auto_expand_all(llm_cfg, lg, n)

    st.session_state["_nl_scroll_top"] = True
    st.rerun()
    return True


def _active_functional_roles(beat_idx: int, lg: str) -> List[Tuple[str, str]]:
    all_p = get_functional_personas(lg)
    lookup = dict(all_p)
    order = functional_recommendation_order(lg)
    chosen = st.session_state.get(f"fn_multi_{beat_idx}") or st.session_state.get("fn_recommended_roles") or []
    chosen = filter_recommended_role_names(list(chosen), lg)
    if not chosen:
        chosen = order[:5]
    sorted_names = sorted(
        [n for n in chosen if n in lookup],
        key=lambda x: order.index(x) if x in order else 99,
    )
    if not sorted_names:
        sorted_names = order[:4]
    return [(n, lookup[n]) for n in sorted_names]


def _parallel_roles_for_generation(beat_idx: int, lg: str) -> List[Tuple[str, str]]:
    """总体方案统筹用职能（不含反套路、连贯性校验师）。"""
    return [
        (r, t)
        for r, t in _active_functional_roles(beat_idx, lg)
        if not is_unified_plan_excluded_role(r, lg)
    ]


def _apply_antitrope_outline_to_assembly(outline: str, lg: str, n: int) -> str:
    """反套路方案采用后：写回各小节 merged，并同步小节汇编 draft_asm。"""
    h = T("beat_heading_word", lg)
    beats = st.session_state.beats
    assembled, updated = sync_assembly_outline_to_beats(
        outline,
        beats,
        beat_heading_word=h,
        n=n,
    )
    if updated:
        st.session_state.beats = beats
        for i in range(n):
            b = st.session_state.beats[i]
            if isinstance(b, dict):
                body = (b.get("merged") or "").strip()
                if body:
                    st.session_state[f"fn_beat_outline_{i}"] = body
    if not assembled:
        return ""
    if not updated and not assembled.strip():
        assembled = _assemble_all_beats_text(lg, n)
    st.session_state["draft_asm"] = assembled
    st.session_state["assembly_antitrope_synced"] = True
    st.session_state["force_assemble"] = True
    return assembled


def _run_auto_expand_all(llm_cfg: Dict[str, Any], lg: str, n: int) -> None:
    if not all(st.session_state.beats[i] for i in range(n)):
        return
    h = T("beat_heading_word", lg)
    outline_override = (st.session_state.pop("story_outline_for_expand", None) or "").strip()
    if outline_override:
        assembled_full = _apply_antitrope_outline_to_assembly(outline_override, lg, n)
        body_in = strip_assembly_beat_headers(assembled_full, h) if assembled_full else outline_override
    else:
        assembled_full = (st.session_state.get("draft_asm") or "").strip() or _assemble_all_beats_text(lg, n)
        body_in = strip_assembly_beat_headers(assembled_full, h)
    if not (body_in or "").strip():
        return
    tag = hash(assembled_full.strip())
    if st.session_state.get("_auto_expand_tag") == tag and (st.session_state.expanded_prose or "").strip():
        return
    beat_objs = [st.session_state.beats[i] for i in range(n) if st.session_state.beats[i]]
    full_canon = canon_sheet_from_beats(
        beat_objs, background_prefix=_body_canon_prefix(lg), lang=lg
    )
    all_chunks = build_chunks_from_beats(
        [_beat_to_text(st.session_state.beats[i], lg) for i in range(n) if st.session_state.beats[i]]
    )
    rag_full = retrieve_context(
        query=f"{st.session_state.seed}\n{full_canon}"[:2000],
        chunks=all_chunks,
        top_k=5,
    )
    st.session_state.expanded_prose = ""
    try:
        nt, pr = expand_prose(
            seed=st.session_state.seed,
            beats_combined=body_in,
            llm_cfg=llm_cfg,
            canon_sheet=full_canon,
            rag_excerpt=rag_full,
            lang=lg,
            num_sections=n,
        )
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "429" in msg or "rate" in msg.lower() or "too many" in msg.lower():
            raise RuntimeError(
                "扩写请求过于频繁，API 限流（429）。请等待 1～2 分钟后重试，"
                "或降低并发生成频率。"
            ) from e
        raise
    st.session_state.expanded_prose = pr
    if nt:
        st.session_state.story_title = nt
    st.session_state["_auto_expand_tag"] = tag
    st.session_state["draft_asm"] = assembled_full


def _landing() -> None:
    lg = _lg()
    inject_css("landing")
    render_landing_lang_corner("ui_lang_select")
    render_landing_hero(lg)

    env_key = default_api_key_from_env()
    if env_key and not (st.session_state.get("login_api_key") or "").strip():
        st.session_state.login_api_key = env_key
    if env_key and not st.session_state.get("login_preset"):
        st.session_state.login_preset = default_preset_from_env()

    _LOGIN_PRESETS = (
        "小米 MiMo",
        "DeepSeek Chat",
        "OpenAI",
        "Claude (Anthropic)",
        "Gemini (Google)",
        "自定义 OpenAI 兼容网关",
    )

    _sp, login_col, _sp2 = st.columns([1, 1.15, 1])
    with login_col:
        c1, c2 = st.columns([1, 1])
        with c1:
            preset = st.selectbox(
                T("model_service", lg),
                list(_LOGIN_PRESETS),
                index=_LOGIN_PRESETS.index(st.session_state.login_preset)
                if st.session_state.login_preset in _LOGIN_PRESETS
                else 0,
                key="login_preset_sel",
            )
            st.session_state.login_preset = preset
        with c2:
            api_key = st.text_input(
                T("api_key", lg),
                type="password",
                placeholder=T("api_placeholder", lg),
                key="login_api_key",
            )
        if preset == "自定义 OpenAI 兼容网关":
            st.session_state.custom_base = st.text_input(
                "Base URL",
                value=st.session_state.custom_base or "https://api.openai.com/v1",
                key="login_base",
            )
            st.session_state.custom_model = st.text_input(
                "Model ID",
                value=st.session_state.custom_model or "gpt-4o-mini",
                key="login_model_custom",
            )
        elif preset == "OpenAI":
            st.text_input(
                "Model ID",
                value=st.session_state.custom_model or "gpt-4o-mini",
                key="login_model_oai",
            )
            st.session_state.custom_base = "https://api.openai.com/v1"
        else:
            st.session_state.custom_base = ""
            if preset == "Claude (Anthropic)":
                st.text_input(
                    "Model ID",
                    value=st.session_state.custom_model or "claude-sonnet-4-20250514",
                    key="login_model_claude",
                )
            elif preset == "Gemini (Google)":
                st.text_input(
                    "Model ID",
                    value=st.session_state.custom_model or "gemini-1.5-flash",
                    key="login_model_gem",
                )
            elif preset == "小米 MiMo":
                st.text_input(
                    "Model ID",
                    value=st.session_state.custom_model or "mimo-v2-flash",
                    key="login_model_mimo",
                )
            else:
                st.session_state.custom_model = ""

        err = st.empty()
        btn_start, btn_skip = st.columns(2)
        with btn_start:
            start_clicked = st.button(
                T("start", lg), type="primary", key="login_start_btn", use_container_width=True
            )
        with btn_skip:
            skip_clicked = st.button(
                T("login_skip_verify", lg),
                type="secondary",
                key="login_skip_verify_btn",
                use_container_width=True,
            )
        if start_clicked or skip_clicked:
            if not (api_key or "").strip():
                err.error(T("api_key_required", lg))
            else:
                progress = st.progress(0, text=T("login_progress_init", lg))
                progress.progress(15, text=T("login_progress_cfg", lg))
                model_ov = st.session_state.custom_model or ""
                if preset == "OpenAI":
                    model_ov = st.session_state.get("login_model_oai", model_ov)
                elif preset == "Claude (Anthropic)":
                    model_ov = st.session_state.get("login_model_claude", model_ov)
                elif preset == "Gemini (Google)":
                    model_ov = st.session_state.get("login_model_gem", model_ov)
                elif preset == "小米 MiMo":
                    model_ov = st.session_state.get("login_model_mimo", model_ov)
                cfg = cfg_from_preset(preset, api_key.strip(), st.session_state.custom_base, model_ov)
                fp = _llm_cfg_fingerprint(cfg)
                ok, msg = True, ""
                if skip_clicked:
                    progress.progress(85, text=T("login_progress_skip", lg))
                elif st.session_state.get("_llm_cfg_fp") == fp:
                    progress.progress(85, text=T("login_progress_cached", lg))
                else:
                    progress.progress(45, text=T("login_progress_verify", lg))
                    ok, msg = verify_connection(cfg)
                if not ok:
                    progress.empty()
                    err.error(T("connection_failed", lg).format(msg=msg))
                else:
                    progress.progress(100, text=T("login_progress_done", lg))
                    st.session_state.llm_cfg = cfg
                    st.session_state["_llm_cfg_fp"] = fp
                    st.session_state.logged_in = True
                    progress.empty()
                    st.rerun()


def _sidebar_nav() -> None:
    lg = _lg()
    render_sidebar_brand(lg)
    render_lang_select("ui_lang_select")
    labs = _nav_labels()
    cur = st.session_state.ui_nav if st.session_state.ui_nav == "drafts" else "new"
    st.markdown('<div class="nl-side-nav">', unsafe_allow_html=True)
    if st.button(
        labs["drafts"],
        key="sidebar_nav_drafts",
        use_container_width=True,
        type="primary" if cur == "drafts" else "secondary",
    ):
        if cur != "drafts":
            st.session_state.ui_nav = "drafts"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    if st.button(T("logout", lg), use_container_width=True, type="secondary"):
        st.session_state.logged_in = False
        st.session_state.llm_cfg = None
        st.session_state.post_survey_phase = False
        st.session_state.pop("_nav_end_marker", None)
        st.rerun()
    if st.button(T("new_story_btn", lg), use_container_width=True, key="btn_new_story", type="secondary"):
        _reset_new_story()
        st.session_state.ui_nav = "new"
        st.rerun()


def _settings_panel() -> None:
    lg = _lg()
    if st.button(T("clear_progress", lg), type="secondary"):
        n = _n_sections()
        for k in (
            "beats",
            "current_beat",
            "typified_candidates",
            "functional_candidates",
            "expanded_prose",
            "beat_regen_count",
            "beat_edit_events",
            "beat_times",
            "background_setting",
            "background_characters",
            "bg_phase_done",
        ):
            if k == "beats":
                st.session_state[k] = [None] * n
            elif k in ("beat_regen_count", "beat_edit_events"):
                st.session_state[k] = [0] * n
            elif k == "beat_times":
                st.session_state[k] = [0.0] * n
            elif k == "current_beat":
                st.session_state[k] = 0
            elif k in ("background_setting", "background_characters"):
                st.session_state[k] = ""
            elif k == "bg_phase_done":
                st.session_state[k] = False
            else:
                st.session_state[k] = [] if k.endswith("candidates") else None
        st.session_state.pop("draft_asm", None)
        st.session_state.pop("_auto_expand_tag", None)
        st.session_state.pop("bg_world_options", None)
        st.session_state.pop("bg_char_options", None)
        st.session_state.pop("_fn_phase_pending", None)
        st.session_state.workflow_phase = "beats"
        st.session_state.pop("story_outline_for_expand", None)
        st.session_state.pop("antitrope_full_pack", None)
        st.session_state["bg_main_char_count"] = 3
        st.session_state["bg_world_complexity"] = "medium"
        st.session_state["creation_explain_on"] = False
        st.rerun()


def _help_panel() -> None:
    lg = _lg()
    if lg == "en":
        st.info(
            "Fill title and sparkles → choose persona mode → run Story creation for each section → "
            "compile & expand → refine or brainstorm → save drafts. Use Finish & submit for feedback."
        )
    else:
        st.info(
            "填写标题与灵感种子 → 选择人格模式 → 各小节点击「故事创作」→ 汇编扩写 → "
            "故事编辑器微调/头脑风暴 → 保存草稿。「完成并提交」后填写体验反馈。"
        )


def _drafts_panel() -> None:
    lg = _lg()
    if st.button(T("back_to_work", lg), type="secondary", key="drafts_back_work"):
        st.session_state.ui_nav = "new"
        st.rerun()
    drafts = drafts_store.list_drafts()
    if not drafts:
        st.caption(T("no_drafts", lg))
        return
    for d in drafts:
        cols = st.columns([3, 1, 1])
        with cols[0]:
            st.write(f"**{d.get('story_title', '—')}** · {d.get('updated_at', '')}")
        with cols[1]:
            if st.button(T("load", lg), key=f"ld_{d['_id']}"):
                st.session_state.story_title = d.get("story_title", "我的故事")
                st.session_state.seed = d.get("seed", "")
                beats = d.get("beats") or []
                st.session_state.num_sections = max(2, min(10, int(d.get("num_sections", len(beats) or 6))))
                st.session_state.beats = beats
                _sync_beat_len_to_num_sections()
                st.session_state.expanded_prose = d.get("expanded_prose", "")
                st.session_state.persona_pool = normalize_persona_pool(d.get("persona_pool", "genre"))
                st.session_state.current_beat = int(d.get("current_beat", 0))
                st.session_state.background_setting = d.get("background_setting", "")
                st.session_state.background_characters = d.get("background_characters", "")
                preset = d.get("preset_protagonist_names")
                if isinstance(preset, list):
                    st.session_state.preset_protagonist_names = [str(n) for n in preset if n]
                else:
                    st.session_state.preset_protagonist_names = []
                st.session_state.bg_phase_done = bool(d.get("bg_phase_done", False))
                wo = d.get("bg_world_options")
                if isinstance(wo, list):
                    st.session_state["bg_world_options"] = wo
                else:
                    st.session_state.pop("bg_world_options", None)
                co = d.get("bg_char_options")
                if isinstance(co, list):
                    st.session_state["bg_char_options"] = co
                else:
                    st.session_state.pop("bg_char_options", None)
                st.session_state.wizard_done = True
                st.session_state.persona_pool_locked = normalize_persona_pool(d.get("persona_pool", "genre"))
                st.session_state.ui_nav = "new"
                if d.get("draft_asm"):
                    st.session_state["draft_asm"] = d.get("draft_asm")
                bc = d.get("bg_main_char_count")
                if bc is not None:
                    try:
                        st.session_state["bg_main_char_count"] = max(1, min(6, int(bc)))
                    except (TypeError, ValueError):
                        st.session_state["bg_main_char_count"] = 3
                cx = d.get("bg_world_complexity")
                if cx in ("simple", "medium", "complex"):
                    st.session_state["bg_world_complexity"] = cx
                st.rerun()
        with cols[2]:
            if st.button(T("delete", lg), key=f"rm_{d['_id']}"):
                drafts_store.delete_draft(d["_id"])
                st.rerun()


def _story_editor(llm_cfg: Dict[str, Any]) -> None:
    lg = _lg()
    n = _n_sections()
    h = T("beat_heading_word", lg)
    assembled_fallback = _assemble_all_beats_text(lg, n)
    base_text = (
        (st.session_state.expanded_prose or "").strip()
        or (st.session_state.get("draft_asm") or "").strip()
        or assembled_fallback.strip()
    )
    with st.expander(T("editor_title", lg), expanded=False):
        if "_editor_buf_next" in st.session_state:
            st.session_state["editor_buf"] = st.session_state.pop("_editor_buf_next")
        st.caption(T("editor_caption", lg))
        left, mid, right = st.columns([1, 0.35, 1])
        with left:
            # Streamlit：带 key 的控件只在首次使用 value；参考区须每轮同步正文来源
            st.session_state["editor_ref_readonly"] = base_text
            st.text_area(
                T("ref_orig", lg),
                height=320,
                disabled=True,
                key="editor_ref_readonly",
                label_visibility="visible",
            )
        with mid:
            if st.button(T("load_editor", lg), key="ed_load"):
                st.session_state["editor_buf"] = base_text
                st.rerun()
            if st.button(T("push_story", lg), key="ed_push"):
                out = (st.session_state.get("editor_buf") or "").strip()
                if out:
                    st.session_state.expanded_prose = out
                    st.success(T("editor_updated", lg))
                    st.rerun()
                else:
                    st.error(T("merge_empty_err", lg))
        with right:
            st.radio(
                T("mode", lg),
                [T("refine", lg), T("brainstorm", lg)],
                horizontal=True,
                key="ed_mode_radio",
            )
            st.text_input(T("prompt_hint", lg), key="ed_prompt_in")
            st.text_area(
                T("edit_area", lg),
                value=st.session_state.get("editor_buf", base_text),
                height=260,
                key="editor_buf",
            )
            if st.button(T("gen_from_prompt", lg), type="primary", key="ed_gen"):
                buf = (st.session_state.get("editor_buf") or "").strip()
                if not base_text and not buf:
                    st.error(T("fill_seed_first", lg))
                else:
                    src = buf or base_text
                    instr = (st.session_state.get("ed_prompt_in") or "").strip() or T("default_refine_instruction", lg)
                    with st.spinner("…"):
                        try:
                            mode = st.session_state.get("ed_mode_radio", T("refine", lg))
                            if mode == T("brainstorm", lg):
                                new_t = brainstorm_segment(
                                    llm_cfg, original=src, instruction=instr, lang=lg
                                )
                            else:
                                new_t = refine_segment(llm_cfg, original=src, instruction=instr, lang=lg)
                            st.session_state["_editor_buf_next"] = new_t
                            st.rerun()
                        except Exception as e:  # noqa: BLE001
                            st.error(str(e))


def _render_antitrope_workflow(llm_cfg: Dict[str, Any], lg: str, n: int) -> None:
    """全部小节定稿后：对完整大纲做反套路突变，再扩写全文。"""
    section_heading(T("antitrope_phase_title", lg))
    st.caption(T("antitrope_phase_hint", lg))
    h = T("beat_heading_word", lg)
    assembled = _assemble_all_beats_text(lg, n)
    full_outline = assembled.strip()
    mutation_baseline = assembled.strip()

    if st.button(T("antitrope_gen_btn", lg), key="antitrope_full_gen", type="primary"):
        beat_objs = [st.session_state.beats[i] for i in range(n) if st.session_state.beats[i]]
        canon = canon_sheet_from_beats(
            beat_objs, background_prefix=_body_canon_prefix(lg), lang=lg
        )
        with st.spinner(T("antitrope_running", lg)):
            try:
                pack = generate_antitrope_full_story(
                    full_outline=full_outline,
                    seed=st.session_state.seed or "",
                    llm_cfg=llm_cfg,
                    canon_sheet=canon,
                    lang=lg,
                )
                st.session_state.antitrope_full_pack = pack
                st.session_state[f"unified_plan_page_{n}"] = 0
                st.session_state[f"unified_plan_pick_{n}"] = 0
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(str(e))

    pack = st.session_state.get("antitrope_full_pack") or {}
    variants = pack.get("variants") or []
    if variants:
        antitrope_labels = [T("plan_a", lg), T("plan_b", lg), T("plan_c", lg)][: len(variants)]
        st.markdown(
            '<p class="nl-muted-line"><span class="nl-mut-highlight">高亮</span> '
            + "表示反套路突变处（相对已定大纲的新增或改动）。</p>",
            unsafe_allow_html=True,
        )
        render_unified_plan_carousel(
            lg,
            n,
            variants,
            feedback_renderer=_render_process_feedback,
            highlight_mutations=True,
            role_layout=False,
            cards_per_page=1,
            show_section_heading=False,
            plan_labels=antitrope_labels,
            mutation_baseline=mutation_baseline,
        )

    skip_col, apply_col = st.columns(2)
    with skip_col:
        if st.button(T("antitrope_skip_btn", lg), key="antitrope_skip", type="secondary", use_container_width=True):
            st.session_state.workflow_phase = "done"
            try:
                with st.spinner(T("auto_expand_running", lg)):
                    _run_auto_expand_all(llm_cfg, lg, n)
            except Exception as e:  # noqa: BLE001
                st.error(str(e))
                st.stop()
            st.rerun()
    with apply_col:
        if st.button(
            T("antitrope_apply_expand_btn", lg),
            key="antitrope_apply",
            type="primary",
            use_container_width=True,
        ):
            if variants:
                plan_i = int(st.session_state.get(unified_plan_pick_key(n), 0))
                if 0 <= plan_i < len(variants):
                    outline = str(variants[plan_i].get("outline") or "").strip()
                    if outline:
                        _apply_antitrope_outline_to_assembly(outline, lg, n)
            st.session_state.workflow_phase = "done"
            try:
                with st.spinner(T("auto_expand_running", lg)):
                    _run_auto_expand_all(llm_cfg, lg, n)
            except Exception as e:  # noqa: BLE001
                st.error(str(e))
                st.stop()
            st.rerun()


def _render_creation_wizard(lg: str) -> None:
    """创作前：小节数、人格模式、灵感与选项确认。"""
    if "wiz_seed" not in st.session_state:
        st.session_state.wiz_seed = st.session_state.get("seed", "")
    if "wiz_title" not in st.session_state:
        st.session_state.wiz_title = st.session_state.get("story_title", "")
    if "wiz_char_total" not in st.session_state:
        st.session_state.wiz_char_total = int(
            st.session_state.get("fn_story_char_total")
            or st.session_state.get("typ_story_char_total")
            or 2
        )
    if "wiz_protagonists" not in st.session_state:
        preset = st.session_state.get("preset_protagonist_names") or []
        sep = ", " if lg == "en" else "、"
        st.session_state.wiz_protagonists = sep.join(preset) if preset else ""
    wizard_open(lg)
    c1, c2 = st.columns([1, 1])
    with c1:
        st.select_slider(
            T("num_sections_label", lg),
            options=list(range(2, 11)),
            value=int(st.session_state.get("num_sections", 6)),
            key="wiz_ns",
        )
    with c2:
        st.radio(
            T("persona_mode", lg),
            ["genre", "function"],
            index=0 if st.session_state.persona_pool == "genre" else 1,
            format_func=lambda x: T("pool_genre", lg) if x == "genre" else T("pool_function", lg),
            horizontal=True,
            key="wiz_pool",
        )
    wc1, wc2 = st.columns([1, 1])
    with wc1:
        st.select_slider(
            T("wiz_char_total_label", lg),
            options=list(range(2, 9)),
            value=int(st.session_state.get("wiz_char_total", 2)),
            key="wiz_char_total",
            help=T("wiz_char_total_help", lg),
        )
    with wc2:
        st.text_input(
            T("wiz_protagonists_label", lg),
            key="wiz_protagonists",
            placeholder=T("wiz_protagonists_ph", lg),
            help=T("wiz_protagonists_help", lg),
        )
    wt1, wt2 = st.columns([1, 1])
    with wt1:
        st.text_input(
            T("story_title_label", lg),
            key="wiz_title",
        )
    with wt2:
        st.text_area(T("sparkles", lg), height=88, key="wiz_seed")
    st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
    _wb_l, _wb_c, _wb_r = st.columns([2, 2, 2])
    with _wb_c:
        if st.button(T("wizard_confirm", lg), type="primary", key="wiz_go", use_container_width=True):
            seed_v = (st.session_state.get("wiz_seed") or "").strip()
            if not seed_v:
                st.error(T("fill_seed_first", lg))
                return
            nt = int(st.session_state.get("wiz_ns", 6))
            _resize_beat_arrays(nt)
            st.session_state.seed = seed_v
            title_v = (st.session_state.get("wiz_title") or "").strip()
            st.session_state.story_title = title_v or T("default_story_title", lg)
            po = st.session_state.get("wiz_pool", "genre")
            st.session_state.persona_pool = po if po in ("genre", "function") else "genre"
            st.session_state.persona_pool_locked = st.session_state.persona_pool
            char_base = int(st.session_state.get("wiz_char_total", 2))
            st.session_state.fn_story_char_total = char_base
            st.session_state.typ_story_char_total = char_base
            from narrativeloom.domain.character_names import parse_preset_protagonist_names

            st.session_state.preset_protagonist_names = parse_preset_protagonist_names(
                st.session_state.get("wiz_protagonists") or ""
            )
            st.session_state.creation_explain_on = False
            st.session_state.wizard_done = True
            st.rerun()
    wizard_close()


def _workspace(llm_cfg: Dict[str, Any]) -> None:
    inject_css("workspace")
    lg = _lg()
    if not st.session_state.get("wizard_done", False):
        _render_creation_wizard(lg)
        return

    _sync_beat_len_to_num_sections()
    n = _n_sections()
    if (
        st.session_state.get("workflow_phase") == "antitrope"
        and normalize_persona_pool(
            st.session_state.get("persona_pool_locked") or st.session_state.get("persona_pool", "genre")
        )
        == "function"
        and all(st.session_state.beats[i] for i in range(n))
    ):
        _render_antitrope_workflow(llm_cfg, lg, n)
        return

    config_locked = st.session_state.get("persona_pool_locked") in ("genre", "function")
    labels = make_beat_labels(n, lg)
    idx = min(max(0, int(st.session_state.current_beat)), n - 1)
    st.session_state.current_beat = idx
    title, hint = labels[idx]

    if st.session_state.pop("_nl_scroll_top", False):
        scroll_workspace_to_top()
    st.markdown('<div id="nl-workspace-top"></div>', unsafe_allow_html=True)
    render_workspace_story_header(lg, st.session_state.story_title, st.session_state.seed or "")
    st.toggle(T("creation_explain", lg), key="creation_explain_on")
    feedback_process = bool(st.session_state.get("creation_explain_on", False))

    st.caption(T("section_progress_hint", lg))
    tab_cols = st.columns(n)
    for bi in range(n):
        with tab_cols[bi]:
            done = st.session_state.beats[bi] is not None
            lbl = "✓" if done else str(bi + 1)
            if st.button(
                lbl,
                key=f"sec_tab_{bi}",
                type="primary" if bi == idx else "secondary",
                use_container_width=True,
            ):
                st.session_state.current_beat = bi
                st.session_state.pop("_generating_beat_idx", None)
                st.session_state.pop("_generating_pool", None)
                _clear_beat_candidate_state()
                _clear_typified_ui_keys(bi)
                st.session_state.pop("_auto_gen_beat", None)
                for i in range(_n_sections()):
                    st.session_state.pop(f"fn_rec_roles_{i}", None)
                st.rerun()

    locked_pl = st.session_state.get("persona_pool_locked")
    genre_lock_full = bool(config_locked and locked_pl == "genre")
    role_order = functional_recommendation_order(lg)

    def _sort_roles(chosen: List[str]) -> List[str]:
        return sorted(chosen, key=lambda x: role_order.index(x) if x in role_order else 99)

    if genre_lock_full:
        pool = "genre"
        pane = st.container()
    else:
        pool = "genre"
        if not config_locked:
            opts_ns = list(range(2, 11))
            cur_n = len(st.session_state.beats)
            want_n = st.select_slider(
                T("num_sections_label", lg),
                options=opts_ns,
                value=int(st.session_state.get("num_sections", cur_n)),
                key="num_sec_sl",
            )
            if want_n != cur_n:
                _resize_beat_arrays(int(want_n))
                st.rerun()
        if locked_pl in ("genre", "function"):
            pool = locked_pl
        else:
            pool = st.radio(
                T("persona_mode", lg),
                ["genre", "function"],
                index=0 if st.session_state.persona_pool == "genre" else 1,
                format_func=lambda x: T("pool_genre", lg) if x == "genre" else T("pool_function", lg),
                horizontal=True,
                key="ws_persona_side",
            )
            st.session_state.persona_pool = pool
        pane = st.container()

    with pane:
        _sync_beat_char_target(idx, lg, pool)
        if not config_locked:
            st.session_state.seed = st.text_area(
                T("sparkles", lg), value=st.session_state.seed, height=64, key="ws_seed"
            )

        if pool == "function":
            _ensure_fn_recommendations(lg, llm_cfg, idx, labels)
            role_names = filter_unified_plan_role_names(role_order, lg)
            st.multiselect(
                T("roles_merge", lg),
                role_names,
                key=f"fn_multi_{idx}",
            )

        if not (st.session_state.seed or "").strip():
            st.warning(T("fill_seed_first", lg))
        else:
            all_beats_done = all(st.session_state.beats[i] for i in range(n))
            canon, rag = _rag_bundle(idx, labels, typified=(pool == "genre"))

            if all_beats_done:
                st.success(T("section_done", lg))
                st.caption(T("auto_expand_hint", lg))
            else:
                render_beat_section_title(lg, idx + 1, title, hint)

            if not all_beats_done and _process_pending_beat_confirm(
                idx=idx,
                n=n,
                labels=labels,
                lg=lg,
                llm_cfg=llm_cfg,
                feedback_process=feedback_process,
                role_order=role_order,
            ):
                st.stop()

            if not all_beats_done:
                gen_idx = st.session_state.get("_generating_beat_idx")
                if gen_idx is not None and gen_idx != idx:
                    st.caption(T("gen_busy_other_beat", lg))
                    st.stop()

                has_typ = bool(st.session_state.typified_candidates)
                has_fn = bool(st.session_state.functional_candidates)
                typ_ready = has_typ and st.session_state.get("_typ_beat_idx") == idx
                fn_ready = has_fn and st.session_state.get("_fc_beat_idx") == idx
                need_gen = st.session_state.beats[idx] is None and not typ_ready and not fn_ready
                auto_gen = st.session_state.pop("_auto_gen_beat", None) == idx

                if gen_idx == idx:
                    _run_generating_beat(
                        idx, pool, lg, llm_cfg, feedback_process, canon, rag, labels
                    )
                    st.stop()

                if need_gen or auto_gen:
                    _kickoff_beat_generation(idx, pool)

                elif pool == "genre" and typ_ready:
                    locked_chars = _locked_character_names(idx, lg)
                    char_min = max(2, len(locked_chars))
                    if idx > 0:
                        char_min = max(char_min, _prior_beat_char_target(idx, "genre"))
                    char_default = _default_typified_character_target(idx, lg)
                    if f"typ_char_total_{idx}" not in st.session_state:
                        st.session_state[f"typ_char_total_{idx}"] = char_default
                    st.number_input(
                        T("typ_char_count_label", lg),
                        min_value=char_min,
                        max_value=8,
                        step=1,
                        key=f"typ_char_total_{idx}",
                        help=T("typ_char_count_hint", lg).format(
                            names="、".join(locked_chars) if locked_chars else T("fn_char_none", lg)
                        ),
                    )
                    live_char_target = int(
                        st.session_state.get(f"typ_char_total_{idx}", char_default)
                    )
                    st.session_state[f"_typ_char_target_{idx}"] = live_char_target
                    if idx == 0:
                        st.session_state.typ_story_char_total = live_char_target
                    if st.button(T("typ_regen_plans", lg), key=f"typ_regen_{idx}", type="secondary"):
                        st.session_state.typ_story_char_total = live_char_target
                        _kickoff_beat_generation(idx, "genre", char_target=live_char_target)
                    lookup = {nm: d for nm, d in st.session_state.typified_candidates}
                    sel = render_typified_carousel(
                        lg,
                        idx,
                        st.session_state.typified_candidates,
                        feedback_renderer=_render_process_feedback,
                        locked_character_names=locked_chars,
                        character_target_total=live_char_target,
                        renormalize_on_render=True,
                        seed=st.session_state.get("seed") or "",
                        prior_characters_block=_prior_characters_block(idx, labels, lg),
                    )
                    dsel = lookup[sel]
                    st.caption(f"{T('current_edit', lg)}: {sel}")
                    s = st.text_area(
                        T("location_setting", lg),
                        value=coerce_display_text(dsel.get("setting", "")),
                        height=80,
                        key=f"tw_set_{idx}_{sel}",
                    )
                    ch = st.text_area(
                        T("characters", lg),
                        value=coerce_display_text(dsel.get("characters", "")),
                        height=80,
                        key=f"tw_ch_{idx}_{sel}",
                    )
                    ev = st.text_area(
                        T("key_events", lg),
                        value=coerce_display_text(dsel.get("key_events", "")),
                        height=100,
                        key=f"tw_ev_{idx}_{sel}",
                    )
                    st.markdown('<div class="nl-confirm-wrap">', unsafe_allow_html=True)
                    if st.button(T("confirm_section", lg), type="primary", key=f"ok_typ_{idx}"):
                        if not typified_characters_meaningful(ch):
                            st.error(T("characters_confirm_err", lg))
                        elif not key_events_meaningful(ev):
                            st.error(T("key_events_confirm_err", lg))
                        else:
                            st.session_state[f"_pending_confirm_{idx}"] = {
                                "pool": "genre",
                                "sel": sel,
                                "setting": s,
                                "characters": ch,
                                "key_events": ev,
                            }
                            st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

                elif (
                    pool == "function"
                    and st.session_state.functional_candidates
                    and st.session_state.get("_fc_beat_idx") == idx
                ):
                    fc = st.session_state.functional_candidates
                    variants = fc.get("variants") or []
                    locked_chars = _locked_character_names(idx, lg)
                    chosen_roles = filter_unified_plan_role_names(
                        _sort_roles(list(st.session_state.get(f"fn_multi_{idx}", role_order))),
                        lg,
                    )
                    char_min = max(1, len(locked_chars))
                    if idx > 0:
                        char_min = max(char_min, _prior_beat_char_target(idx, "function"))
                    char_default = _default_character_target(idx, lg)
                    if f"fn_char_total_{idx}" not in st.session_state:
                        st.session_state[f"fn_char_total_{idx}"] = char_default
                    st.number_input(
                        T("fn_char_count_label", lg),
                        min_value=char_min,
                        max_value=14,
                        step=1,
                        key=f"fn_char_total_{idx}",
                        help=T("fn_char_count_hint", lg).format(
                            names="、".join(locked_chars) if locked_chars else T("fn_char_none", lg)
                        ),
                    )
                    live_char_target = int(
                        st.session_state.get(f"fn_char_total_{idx}", char_default)
                    )
                    st.session_state[f"_fc_char_target_{idx}"] = live_char_target
                    if idx == 0:
                        st.session_state.fn_story_char_total = int(
                            st.session_state.get(f"fn_char_total_{idx}", char_default)
                        )
                    if st.button(T("fn_regen_plans", lg), key=f"fn_regen_plans_{idx}", type="secondary"):
                        st.session_state.fn_story_char_total = int(
                            st.session_state.get(f"fn_char_total_{idx}", char_default)
                        )
                        _kickoff_beat_generation(idx, "function")

                    plan_labels = _fn_plan_labels(lg, idx)
                    from narrativeloom.utils.display_utils import parse_character_profile_map

                    prior_profiles = parse_character_profile_map(
                        _prior_characters_block(idx, labels, lg)
                    )
                    plan_i = render_unified_plan_carousel(
                        lg,
                        idx,
                        variants,
                        feedback_renderer=_render_process_feedback,
                        role_names=chosen_roles,
                        locked_character_names=locked_chars,
                        character_target_total=live_char_target,
                        renormalize_on_render=True,
                        seed=st.session_state.get("seed") or "",
                        beat_index=idx,
                        prior_character_profiles=prior_profiles,
                        cards_per_page=2,
                        plan_labels=plan_labels,
                    )
                    merge_sync_key = f"_fn_merge_sync_pick_{idx}"
                    if 0 <= plan_i < len(variants):
                        raw_outline = str(variants[plan_i].get("outline") or "").strip()
                        if raw_outline and (
                            st.session_state.get(merge_sync_key) != plan_i
                            or not (st.session_state.get(f"merge_preview_{idx}") or "").strip()
                        ):
                            mt = normalize_single_unified_outline(
                                raw_outline,
                                role_names=chosen_roles,
                                lang=lg,
                                locked_names=locked_chars,
                                character_target_total=live_char_target,
                                beat_index=idx,
                                seed=st.session_state.get("seed") or "",
                                prior_character_profiles=prior_profiles,
                            )
                            st.session_state[f"merge_preview_{idx}"] = format_functional_merged_outline(
                                mt, chosen_roles
                            )
                            st.session_state[merge_sync_key] = plan_i
                    default_outline = ""
                    if 0 <= plan_i < len(variants):
                        default_outline = str(variants[plan_i].get("outline") or "").strip()

                    st.text_area(
                        T("assembly_slots_title", lg),
                        height=240,
                        key=f"merge_preview_{idx}",
                        label_visibility="collapsed",
                    )

                    st.markdown('<div class="nl-confirm-wrap">', unsafe_allow_html=True)
                    if st.button(T("confirm_section", lg), type="primary", key=f"ok_fn_{idx}"):
                        mt = (st.session_state.get(f"merge_preview_{idx}") or "").strip()
                        if not mt:
                            st.error(T("merge_empty_err", lg))
                        else:
                            char_default = _default_character_target(idx, lg)
                            mt = normalize_single_unified_outline(
                                mt,
                                role_names=chosen_roles,
                                lang=lg,
                                locked_names=locked_chars,
                                character_target_total=live_char_target,
                                beat_index=idx,
                                seed=st.session_state.get("seed") or "",
                                prior_character_profiles=prior_profiles,
                            )
                            user_edited = 1 if mt != (default_outline or "").strip() else 0
                            pick_i = int(st.session_state.get(unified_plan_pick_key(idx), plan_i))
                            if pick_i < 0 or pick_i >= len(FN_WORLDVIEW_KEYS):
                                pick_i = max(0, min(plan_i, len(FN_WORLDVIEW_KEYS) - 1))
                            if not st.session_state.get("fn_locked_worldview"):
                                st.session_state.fn_locked_worldview = FN_WORLDVIEW_KEYS[pick_i]
                            if idx == 0 and not (st.session_state.get("fn_locked_setting") or "").strip():
                                st.session_state.fn_locked_setting = _extract_setting_baseline(mt)
                            st.session_state[f"fn_beat_outline_{idx}"] = mt
                            st.session_state[f"_pending_confirm_{idx}"] = {
                                "pool": "function",
                                "merged_text": mt,
                                "chosen_roles": chosen_roles,
                                "user_edited": user_edited,
                                "sig_key": f"_fc_sig_{idx}",
                            }
                            st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)
    assembled = _assemble_all_beats_text(lg, n)
    if st.session_state.pop("force_assemble", False) and assembled:
        st.session_state["draft_asm"] = assembled

    draft_asm = (st.session_state.get("draft_asm") or "").strip()
    if assembled.strip() and not draft_asm:
        st.session_state["draft_asm"] = assembled
    elif st.session_state.get("assembly_antitrope_synced") and assembled.strip():
        st.session_state["draft_asm"] = assembled
    with st.expander(T("section_assembly", lg), expanded=False):
        st.text_area(T("section_assembly", lg), height=360, key="draft_asm")

    if st.button(T("expand", lg)):
        outline_override = (st.session_state.get("story_outline_for_expand") or "").strip()
        body = (st.session_state.get("draft_asm") or "").strip() or assembled.strip()
        if outline_override:
            body = _apply_antitrope_outline_to_assembly(outline_override, lg, n) or body
            st.session_state.pop("story_outline_for_expand", None)
        if not body:
            st.error(T("expand_err", lg))
        else:
            beat_objs = [st.session_state.beats[i] for i in range(n) if st.session_state.beats[i]]
            full_canon = canon_sheet_from_beats(
        beat_objs, background_prefix=_body_canon_prefix(lg), lang=lg
    )
            all_chunks = build_chunks_from_beats(
                [_beat_to_text(st.session_state.beats[i], lg) for i in range(n) if st.session_state.beats[i]]
            )
            rag_full = retrieve_context(
                query=f"{st.session_state.seed}\n{full_canon}"[:2000],
                chunks=all_chunks,
                top_k=5,
            )
            hw = T("beat_heading_word", lg)
            body_in = strip_assembly_beat_headers(body, hw)
            with st.spinner("…"):
                try:
                    new_title, prose_out = expand_prose(
                        seed=st.session_state.seed,
                        beats_combined=body_in,
                        llm_cfg=llm_cfg,
                        canon_sheet=full_canon,
                        rag_excerpt=rag_full,
                        lang=lg,
                        num_sections=n,
                    )
                    st.session_state.expanded_prose = prose_out
                    if new_title:
                        st.session_state.story_title = new_title
                    st.session_state.pop("_auto_expand_tag", None)
                except Exception as e:  # noqa: BLE001
                    st.error(str(e))

    if (st.session_state.expanded_prose or "").strip():
        section_heading(T("prose_title", lg))
        render_prose_block(st.session_state.expanded_prose)

    _story_editor(llm_cfg)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    c_a, c_b, _ = st.columns(3)
    with c_a:
        if st.button(T("save_draft", lg)):
            payload = {
                "story_title": st.session_state.story_title,
                "seed": st.session_state.seed,
                "beats": st.session_state.beats,
                "num_sections": n,
                "expanded_prose": st.session_state.expanded_prose,
                "draft_asm": st.session_state.get("draft_asm", ""),
                "persona_pool": st.session_state.persona_pool,
                "current_beat": st.session_state.current_beat,
                "background_setting": st.session_state.background_setting,
                "background_characters": st.session_state.background_characters,
                "preset_protagonist_names": st.session_state.get("preset_protagonist_names") or [],
                "bg_phase_done": st.session_state.bg_phase_done,
                "bg_world_options": st.session_state.get("bg_world_options"),
                "bg_char_options": st.session_state.get("bg_char_options"),
                "bg_main_char_count": int(st.session_state.get("bg_main_char_count", 3)),
                "bg_world_complexity": str(st.session_state.get("bg_world_complexity", "medium")),
            }
            did = drafts_store.save_draft(payload)
            st.success(T("draft_saved", lg).format(id=did))
    with c_b:
        ready = all(st.session_state.beats[i] for i in range(n)) and (
            (st.session_state.expanded_prose or "").strip()
            or (st.session_state.get("draft_asm") or "").strip()
        )
        if st.button(T("submit_done", lg), disabled=not ready):
            payload = {
                "story_title": st.session_state.story_title,
                "seed": st.session_state.seed,
                "beats": st.session_state.beats,
                "num_sections": n,
                "expanded_prose": st.session_state.expanded_prose,
                "draft_asm": st.session_state.get("draft_asm", ""),
                "persona_pool": st.session_state.persona_pool,
                "current_beat": st.session_state.current_beat,
                "background_setting": st.session_state.background_setting,
                "background_characters": st.session_state.background_characters,
                "preset_protagonist_names": st.session_state.get("preset_protagonist_names") or [],
                "bg_phase_done": st.session_state.bg_phase_done,
                "bg_world_options": st.session_state.get("bg_world_options"),
                "bg_char_options": st.session_state.get("bg_char_options"),
                "bg_main_char_count": int(st.session_state.get("bg_main_char_count", 3)),
                "bg_world_complexity": str(st.session_state.get("bg_world_complexity", "medium")),
                "submitted": True,
            }
            drafts_store.save_draft(payload)
            st.session_state.post_survey_phase = True
            st.rerun()
        if not ready:
            st.caption(T("submit_hint", lg))

def _survey() -> None:
    inject_css("workspace")
    lg = _lg()
    page_heading(T("survey_title", lg), T("survey_caption", lg))
    st.slider(T("likert_u", lg), 1, 5, int(st.session_state.get("likert_u", 3)), key="likert_u")
    st.slider(T("likert_i", lg), 1, 5, int(st.session_state.get("likert_i", 3)), key="likert_i")
    st.slider(T("likert_c", lg), 1, 5, int(st.session_state.get("likert_c", 3)), key="likert_c")
    st.slider(T("likert_s", lg), 1, 5, int(st.session_state.get("likert_s", 3)), key="likert_s")
    if st.button(T("submit_feedback", lg), type="primary"):
        n = len(st.session_state.beats)
        final_text = st.session_state.expanded_prose or st.session_state.get("draft_asm", "")
        final_chars = len((final_text or "").replace("\n", ""))
        texts2 = [_beat_to_text(st.session_state.beats[i], lg) for i in range(n)]
        n_conf2, _ = coherence.analyze_story([t for t in texts2 if t.strip()])
        beat_rows = []
        for i in range(n):
            b = st.session_state.beats[i] if i < len(st.session_state.beats) else None
            persona_s = ""
            if isinstance(b, dict):
                persona_s = b.get("persona") or b.get("personas") or ""
            bt = st.session_state.beat_times[i] if i < len(st.session_state.beat_times) else 0.0
            be = st.session_state.beat_edit_events[i] if i < len(st.session_state.beat_edit_events) else 0
            beat_rows.append(
                {
                    "beat_index": i + 1,
                    "beat_seconds": bt,
                    "beat_edit_events": be,
                    "selected_personas": persona_s,
                    "notes": (b or {}).get("review_notes", "") if isinstance(b, dict) else "",
                }
            )
        pool_label = "genre" if st.session_state.persona_pool == "genre" else "function"
        experiment_log.log_session_summary(
            persona_pool=pool_label,
            feedback_mode="ai_notes_on"
            if st.session_state.get("creation_explain_on", False)
            else "ai_notes_off",
            writing_experience=st.session_state.writing_experience,
            beat_rows=beat_rows,
            final_char_count=final_chars,
            coherence_conflict_count=n_conf2,
            likert={
                "understanding": int(st.session_state.get("likert_u", 3)),
                "inspiration": int(st.session_state.get("likert_i", 3)),
                "cognitive_load": int(st.session_state.get("likert_c", 3)),
                "satisfaction": int(st.session_state.get("likert_s", 3)),
            },
            notes="post_submit_survey",
        )
        st.session_state.post_survey_phase = False
        st.success(T("survey_success", lg))


def main() -> None:
    st.set_page_config(
        page_title="NarrativeLoom-pro",
        page_icon="✒",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _init_state()
    render_access_gate()
    render_consent_gate()

    if not st.session_state.logged_in:
        _landing()
        return

    if st.session_state.post_survey_phase:
        _survey()
        with st.sidebar:
            if st.button(T("back_home", _lg())):
                st.session_state.post_survey_phase = False
                st.rerun()
        return

    llm_cfg = st.session_state.llm_cfg
    assert isinstance(llm_cfg, dict)

    with st.sidebar:
        _sidebar_nav()

    nav = st.session_state.ui_nav
    if nav == "drafts":
        inject_css("workspace")
        page_heading(T("drafts_title", _lg()))
        _drafts_panel()
    else:
        st.session_state.ui_nav = "new"
        _workspace(llm_cfg)

    st.session_state["_nav_end_marker"] = st.session_state.ui_nav


if __name__ == "__main__":
    main()
