# -*- coding: utf-8 -*-
"""NarrativeLoom-pro 页面组件（对齐产品参考稿布局）。"""

from __future__ import annotations

import hashlib
import html
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

import streamlit as st

from narrativeloom.utils.display_utils import (
    bullet_text_to_markdown,
    filter_character_sculptor_fragment,
    format_typified_brief,
    fragment_to_markdown_bullets,
    parse_merge_role_sections,
)
from narrativeloom.domain.personas import is_character_sculptor_role
from narrativeloom.config.i18n import T
from narrativeloom.front.ui_design import PageMode, get_global_css

CARDS_PER_PAGE = 2
UNIFIED_PLANS_PER_PAGE = 2


def inject_css(mode: PageMode = "landing") -> None:
    st.markdown(get_global_css(mode), unsafe_allow_html=True)


def scroll_workspace_to_top() -> None:
    """确认小节并进入下一节后，将主区域滚回顶部。"""
    js_html = """<script>
        (function () {
          try {
            const doc = window.parent.document;
            const main = doc.querySelector("section.main")
              || doc.querySelector('[data-testid="stAppViewContainer"]')
              || doc.documentElement;
            if (main && main.scrollTo) main.scrollTo({ top: 0, behavior: "smooth" });
            else window.parent.scrollTo({ top: 0, behavior: "smooth" });
          } catch (e) {
            window.parent.scrollTo(0, 0);
          }
        })();
        </script>"""
    if hasattr(st, "iframe"):
        # st.iframe 不接受 height=0，用 1px 隐藏 iframe 仅执行滚动脚本
        st.iframe(js_html, height=1)
    else:
        import streamlit.components.v1 as components

        components.html(js_html, height=0)


def render_lang_select(key: str = "ui_lang_select") -> None:
    """工作区语言切换（请仅调用一次）。"""
    lg = st.session_state.get("ui_lang", "zh")
    st.markdown('<div class="nl-lang-bar">', unsafe_allow_html=True)
    choice = st.selectbox(
        T("lang_label", lg),
        ["zh", "en"],
        index=0 if lg == "zh" else 1,
        format_func=lambda x: "中文" if x == "zh" else "English",
        key=key,
        label_visibility="collapsed",
    )
    st.markdown("</div>", unsafe_allow_html=True)
    if choice != st.session_state.ui_lang:
        st.session_state.ui_lang = choice
        st.rerun()


def render_landing_lang_corner(key: str = "ui_lang_select") -> None:
    """起始页右上角小号语言切换。"""
    lg = st.session_state.get("ui_lang", "zh")
    st.markdown('<div class="nl-landing-lang-anchor"></div>', unsafe_allow_html=True)
    choice = st.selectbox(
        T("lang_label", lg),
        ["zh", "en"],
        index=0 if lg == "zh" else 1,
        format_func=lambda x: "中文" if x == "zh" else "English",
        key=key,
        label_visibility="collapsed",
    )
    if choice != st.session_state.ui_lang:
        st.session_state.ui_lang = choice
        st.rerun()


def render_sidebar_brand(lg: str) -> None:
    st.markdown(
        f"""
<div class="nl-sidebar-brand">
  <span class="mark" aria-hidden="true">✒</span>
  <span class="name">{html.escape(T("app_title", lg))}</span>
</div>
""",
        unsafe_allow_html=True,
    )


def render_landing_hero(lg: str) -> None:
    st.markdown(
        f"""
<div class="nl-landing-wrap">
  <h1 class="nl-landing-title">{html.escape(T("app_title", lg))}</h1>
  <p class="nl-landing-tag">{html.escape(T("tagline1", lg))}</p>
  <p class="nl-landing-tag2">{html.escape(T("tagline2", lg))}</p>
</div>
""",
        unsafe_allow_html=True,
    )


def landing_login_open() -> None:
    st.markdown('<div class="nl-login-card">', unsafe_allow_html=True)


def landing_login_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def wizard_open(lg: str) -> None:
    page_heading(T("wizard_title", lg), T("wizard_caption", lg))


def wizard_close() -> None:
    pass


def render_fn_role_card_header(
    role_name: str,
    *,
    apply_label: str = "",
    apply_key: str = "",
) -> bool:
    """职能卡标题行；右侧可选「应用」按钮。返回是否点击应用。"""
    clicked = False
    if apply_label and apply_key:
        col_title, col_btn = st.columns([6, 1], gap="small", vertical_alignment="center")
        with col_title:
            st.markdown(
                f'<div class="nl-fn-module nl-fn-module-instack nl-fn-role-card">'
                f'<div class="nl-fn-module-head">'
                f'<span class="nl-fn-module-role">{html.escape(role_name)}</span>'
                f"</div></div>",
                unsafe_allow_html=True,
            )
        with col_btn:
            clicked = st.button(
                apply_label,
                key=apply_key,
                type="secondary",
                use_container_width=True,
            )
    else:
        st.markdown(
            f'<div class="nl-fn-module nl-fn-module-instack nl-fn-role-card">'
            f'<div class="nl-fn-module-head">'
            f'<span class="nl-fn-module-role">{html.escape(role_name)}</span>'
            f"</div></div>",
            unsafe_allow_html=True,
        )
    return clicked


def section_heading(title: str) -> None:
    st.markdown(
        f'<p class="nl-serif-h2">{html.escape(title)}</p>',
        unsafe_allow_html=True,
    )


def page_heading(title: str, subtitle: str = "") -> None:
    sub = (
        f'<p class="nl-muted-line">{html.escape(subtitle)}</p>'
        if subtitle
        else ""
    )
    st.markdown(
        f'<p class="nl-serif-h1">{html.escape(title)}</p>{sub}',
        unsafe_allow_html=True,
    )


def render_workspace_story_header(lg: str, story_title: str, seed_text: str) -> None:
    sp = (seed_text or "").strip() or T("sparkles_empty", lg)
    st.markdown(
        f'<p class="nl-serif-h1">{html.escape(T("story_heading", lg))}: {html.escape(story_title)}</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p style="margin:0 0 0.35rem;font-weight:600;color:var(--nl-text);">{html.escape(T("sparkles", lg))}</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="nl-sparkle-box">{html.escape(sp)}</div>',
        unsafe_allow_html=True,
    )


def render_beat_section_title(lg: str, beat_index: int, title: str, hint: str = "") -> None:
    """仅展示小节序号，不显示相位词。"""
    _ = hint
    st.markdown(
        f'<p class="nl-beat-heading">{html.escape(T("beat_heading_word", lg))} {beat_index}</p>',
        unsafe_allow_html=True,
    )


def render_beat_rail_html(n: int, current: int, done_mask: List[bool]) -> str:
    pills = []
    for i in range(n):
        cls = "nl-beat-pill"
        if done_mask[i]:
            cls += " nl-done"
        elif i == current:
            cls += " nl-current"
        label = "✓" if done_mask[i] else str(i + 1)
        pills.append(f'<span class="{cls}">{label}</span>')
    return f'<div class="nl-beat-rail">{"".join(pills)}</div>'


def render_prose_block(prose: str) -> None:
    from narrativeloom.utils.display_utils import format_prose_paragraphs

    formatted = format_prose_paragraphs(prose or "")
    parts = [p.strip() for p in formatted.split("\n\n") if p.strip()]
    if not parts:
        parts = [(prose or "").strip()]
    body = "".join(f'<p class="nl-prose-p">{html.escape(p)}</p>' for p in parts)
    st.markdown(
        f'<article class="nl-prose-full">{body}</article>',
        unsafe_allow_html=True,
    )


def render_fn_outline(text: str) -> None:
    t = (text or "").strip() or "—"
    st.markdown(
        f'<div class="nl-fn-outline">{html.escape(t).replace(chr(10), "<br/>")}</div>',
        unsafe_allow_html=True,
    )


def _bullet_lines_to_ul_html(block: str) -> str:
    md = bullet_text_to_markdown(block)
    if md == "—":
        return '<p class="nl-empty-dash">—</p>'
    items = []
    for ln in md.split("\n"):
        ln = re.sub(r"^-\s*", "", ln.strip())
        if ln:
            items.append(f"<li>{html.escape(ln)}</li>")
    return f'<ul class="nl-ul">{"".join(items)}</ul>' if items else '<p class="nl-empty-dash">—</p>'


def render_typified_carousel(
    lg: str,
    beat_idx: int,
    candidates: List[Tuple[str, Dict[str, Any]]],
    *,
    feedback_renderer: Optional[Callable[[str, Any, str], None]] = None,
) -> str:
    """横向翻页展示类型化人格候选；卡片内可滚动、等高。"""
    names = [nm for nm, _ in candidates]
    page_key = f"typ_page_{beat_idx}"
    pick_key = f"typ_picked_{beat_idx}"
    pages = max(1, (len(candidates) + CARDS_PER_PAGE - 1) // CARDS_PER_PAGE)
    pi = int(st.session_state.get(page_key, 0))
    pi = max(0, min(pi, pages - 1))
    st.session_state[page_key] = pi

    picked = st.session_state.get(pick_key)
    if picked not in names:
        picked = names[0]
        st.session_state[pick_key] = picked

    section_heading(T("candidates_title", lg))
    st.caption(T("candidates_carousel_hint", lg))

    nav_l, nav_m, nav_r = st.columns([1, 3, 1])
    with nav_l:
        if st.button(
            "◀ " + T("carousel_prev", lg),
            key=f"typ_car_prev_{beat_idx}",
            disabled=pi <= 0,
            use_container_width=True,
            type="secondary",
        ):
            st.session_state[page_key] = pi - 1
            st.rerun()
    with nav_m:
        st.markdown(
            f'<p class="nl-carousel-page">{html.escape(T("carousel_page", lg).format(cur=pi + 1, total=pages))}</p>',
            unsafe_allow_html=True,
        )
    with nav_r:
        if st.button(
            T("carousel_next", lg) + " ▶",
            key=f"typ_car_next_{beat_idx}",
            disabled=pi >= pages - 1,
            use_container_width=True,
            type="secondary",
        ):
            st.session_state[page_key] = pi + 1
            st.rerun()

    slice_ = candidates[pi * CARDS_PER_PAGE : (pi + 1) * CARDS_PER_PAGE]
    cols = st.columns(CARDS_PER_PAGE, gap="medium")
    lbl_place = T("brief_time_place", lg)
    lbl_char = T("brief_characters", lg)
    lbl_ev = T("brief_events", lg)

    for col_i in range(CARDS_PER_PAGE):
        with cols[col_i]:
            if col_i >= len(slice_):
                st.markdown('<div class="nl-typ-card-spacer"></div>', unsafe_allow_html=True)
                continue
            name, data = slice_[col_i]
            picked_cls = " is-picked" if name == picked else ""
            place, chars_block, ev_block = format_typified_brief(data, lg)
            st.markdown('<div class="nl-typ-col-wrap">', unsafe_allow_html=True)
            card_html = (
                f'<div class="nl-fn-module nl-typ-as-fn{picked_cls}">'
                f'<div class="nl-fn-module-head">'
                f'<span class="nl-fn-module-role">{html.escape(name)}</span>'
                f"</div>"
                f'<div class="nl-fn-module-body nl-typ-fn-body">'
                f'<div class="nl-typ-field"><span class="nl-typ-lbl">{html.escape(lbl_place)}</span>'
                f'<p class="nl-typ-txt">{html.escape(place)}</p></div>'
                f'<div class="nl-typ-field"><span class="nl-typ-lbl">{html.escape(lbl_char)}</span>'
                f'{_bullet_lines_to_ul_html(chars_block)}</div>'
                f'<div class="nl-typ-field"><span class="nl-typ-lbl">{html.escape(lbl_ev)}</span>'
                f'{_bullet_lines_to_ul_html(ev_block)}</div>'
                f"</div></div>"
            )
            st.markdown(card_html, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            if feedback_renderer:
                feedback_renderer(name, data.get("process_feedback"), lg)
            st.markdown('<div class="nl-typ-pick-wrap">', unsafe_allow_html=True)
            _pc1, _pc2, _pc3 = st.columns([1, 1.2, 1])
            with _pc2:
                if st.button(
                    T("pick_this_beat", lg),
                    key=f"typ_pick_{beat_idx}_{name}",
                    type="primary",
                    use_container_width=True,
                ):
                    st.session_state[pick_key] = name
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    return str(st.session_state[pick_key])


def render_fn_role_dual_carousel(
    lg: str,
    beat_idx: int,
    role_name: str,
    variants: List[Dict[str, Any]],
    *,
    plan_labels: Optional[List[str]] = None,
    feedback_renderer: Optional[Callable[[str, Any, str], None]] = None,
) -> None:
    """职能四方案：每页 2 张卡，横向翻页，每张卡可「采用此方案」。"""
    labels = plan_labels or [
        T("plan_a", lg),
        T("plan_b", lg),
        T("plan_c", lg),
        T("plan_d", lg),
    ]
    slug = fn_role_slug(role_name)
    page_key = f"fn_role_pg_{beat_idx}_{slug}"
    sel_key = fn_variant_sel_key(beat_idx, role_name)
    nvar = min(4, len(variants))
    pages = max(1, (nvar + CARDS_PER_PAGE - 1) // CARDS_PER_PAGE)
    pi = int(st.session_state.get(page_key, 0))
    pi = max(0, min(pi, pages - 1))
    st.session_state[page_key] = pi
    cur_sel = int(st.session_state.get(sel_key, 0))
    if cur_sel < 0 or cur_sel >= max(1, nvar):
        cur_sel = 0
        st.session_state[sel_key] = 0

    st.markdown(
        f'<p class="nl-fn-role-section-title">{html.escape(role_name)}</p>',
        unsafe_allow_html=True,
    )
    nav_l, nav_m, nav_r = st.columns([1, 3, 1])
    with nav_l:
        if st.button(
            "◀",
            key=f"fn_rp_prev_{beat_idx}_{slug}",
            disabled=pi <= 0,
            use_container_width=True,
            type="secondary",
        ):
            st.session_state[page_key] = pi - 1
            st.rerun()
    with nav_m:
        st.markdown(
            f'<p class="nl-carousel-page">{html.escape(T("carousel_page", lg).format(cur=pi + 1, total=pages))}</p>',
            unsafe_allow_html=True,
        )
    with nav_r:
        if st.button(
            "▶",
            key=f"fn_rp_next_{beat_idx}_{slug}",
            disabled=pi >= pages - 1,
            use_container_width=True,
            type="secondary",
        ):
            st.session_state[page_key] = pi + 1
            st.rerun()

    slice_ = list(enumerate(variants[:nvar]))[pi * CARDS_PER_PAGE : (pi + 1) * CARDS_PER_PAGE]
    cols = st.columns(CARDS_PER_PAGE, gap="medium")
    for col_i in range(CARDS_PER_PAGE):
        with cols[col_i]:
            if col_i >= len(slice_):
                continue
            vi, vdata = slice_[col_i]
            frag_raw = str(vdata.get("fragment") or "").strip()
            if frag_raw and is_character_sculptor_role(role_name, lg):
                frag_raw = filter_character_sculptor_fragment(frag_raw)
            picked_cls = " is-picked" if vi == cur_sel else ""
            plan_lab = labels[vi] if vi < len(labels) else str(vi + 1)
            body_inner = _fragment_to_ul_html(frag_raw) if frag_raw else '<p class="nl-empty-dash">—</p>'
            st.markdown(
                f'<div class="nl-fn-module nl-typ-as-fn{picked_cls}">'
                f'<div class="nl-fn-module-head">'
                f'<span class="nl-fn-module-role">{html.escape(plan_lab)}</span>'
                f"</div>"
                f'<div class="nl-fn-module-body nl-typ-fn-body">{body_inner}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
            if feedback_renderer:
                feedback_renderer(f"{role_name} · {plan_lab}", vdata.get("process_feedback"), lg)
            st.markdown('<div class="nl-typ-pick-wrap">', unsafe_allow_html=True)
            _a1, _a2, _a3 = st.columns([1, 1.2, 1])
            with _a2:
                if st.button(
                    T("pick_this_beat", lg),
                    key=f"fn_adopt_{beat_idx}_{slug}_{vi}",
                    type="primary" if vi == cur_sel else "secondary",
                    use_container_width=True,
                ):
                    st.session_state[sel_key] = vi
                    st.session_state[f"_fn_sync_pending_{beat_idx}"] = {
                        "role": role_name,
                        "idx": vi,
                    }
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)


def fn_role_slug(role_name: str) -> str:
    """职能名 → 稳定短键（用于 Streamlit widget key）。"""
    return hashlib.md5(role_name.encode("utf-8")).hexdigest()[:10]


def fn_variant_page_key(beat_idx: int, role_name: str) -> str:
    return f"fn_var_page_{beat_idx}_{fn_role_slug(role_name)}"


def fn_variant_sel_key(beat_idx: int, role_name: str) -> str:
    return f"fn_var_sel_{beat_idx}_{fn_role_slug(role_name)}"


def _fragment_to_ul_html(
    fragment: str,
    *,
    highlight_mutations: bool = False,
    mutation_baseline: str = "",
) -> str:
    from narrativeloom.utils.display_utils import _outline_line_to_li, prepare_mutation_display_text

    raw = fragment or ""
    if highlight_mutations:
        raw = prepare_mutation_display_text(raw, mutation_baseline)
    md = fragment_to_markdown_bullets(raw, preserve_mutations=highlight_mutations)
    if md == "—":
        return '<p class="nl-empty-dash">—</p>'
    items = []
    for ln in md.split("\n"):
        ln = re.sub(r"^-\s*", "", ln.strip())
        if not ln:
            continue
        if highlight_mutations:
            li = _outline_line_to_li(ln, highlight_mutations=True)
            if li:
                items.append(li)
        else:
            items.append(f"<li>{html.escape(ln)}</li>")
    return f'<ul class="nl-ul">{"".join(items)}</ul>' if items else '<p class="nl-empty-dash">—</p>'


def _merge_fragment_to_html(
    fragment: str,
    *,
    highlight_mutations: bool = False,
    mutation_baseline: str = "",
) -> str:
    """多职能【分块】拼接稿：保留分块标题 + 分条要点。"""
    raw = (fragment or "").strip()
    if not raw:
        return '<p class="nl-empty-dash">—</p>'
    if "【" not in raw:
        return _fragment_to_ul_html(
            raw,
            highlight_mutations=highlight_mutations,
            mutation_baseline=mutation_baseline,
        )
    sections = parse_merge_role_sections(raw)
    if len(sections) <= 1 and sections and sections[0][0] == "【全文】":
        return _fragment_to_ul_html(
            sections[0][1],
            highlight_mutations=highlight_mutations,
            mutation_baseline=mutation_baseline,
        )
    parts: List[str] = []
    for title, body in sections:
        parts.append(f'<div class="nl-fn-merge-role">{html.escape(title)}</div>')
        parts.append(
            _fragment_to_ul_html(
                body or "—",
                highlight_mutations=highlight_mutations,
                mutation_baseline=mutation_baseline,
            )
        )
    return "".join(parts)


def _variant_fragment_at(variants: List[Dict[str, Any]], index: int) -> str:
    from narrativeloom.utils.display_utils import muffle_markdown_heading_lines
    from narrativeloom.service.llm_client import functional_slot_bundle_from_pack

    if index < 0 or not variants:
        return ""
    txt, _ = functional_slot_bundle_from_pack(variants, index)
    return muffle_markdown_heading_lines(txt or "")


def _variants_have_content(variants: List[Dict[str, Any]]) -> bool:
    from narrativeloom.service.llm_client import _looks_like_wrapped_variants_json, functional_fragment_display

    for v in variants or []:
        if isinstance(v, dict):
            raw = str(v.get("fragment") or "").strip()
        elif isinstance(v, str):
            raw = v.strip()
        else:
            continue
        if not raw:
            continue
        if _looks_like_wrapped_variants_json(raw):
            if functional_fragment_display(raw).strip():
                return True
        else:
            return True
    return False


def render_fn_variant_carousel(
    lg: str,
    beat_idx: int,
    role_name: str,
    variants: List[Dict[str, Any]],
    *,
    plan_labels: Optional[List[str]] = None,
    pick_label: Optional[str] = None,
    pick_applies_to_merge: bool = False,
    sync_merge_on_pick: bool = False,
    empty_hint: Optional[str] = None,
    show_upgrade_btn: bool = False,
    upgrade_pending_key: Optional[str] = None,
    merge_slot_display: bool = False,
) -> int:
    """职能方案卡：全宽卡片 + 底部一体导航（翻页 / 方案标签 / 选用）。"""
    labels = plan_labels or [T("plan_a", lg), T("plan_b", lg), T("plan_c", lg)]
    slug = fn_role_slug(role_name)
    page_key = fn_variant_page_key(beat_idx, role_name)
    sel_key = fn_variant_sel_key(beat_idx, role_name)
    has_content = _variants_have_content(variants)
    nvar = min(3, len(variants)) if has_content else 0
    pages = max(1, nvar) if has_content else 1
    pi = int(st.session_state.get(page_key, 0))
    pi = max(0, min(pi, pages - 1))
    st.session_state[page_key] = pi

    cur_sel = int(st.session_state.get(sel_key, 0))
    if cur_sel < 0 or cur_sel >= max(1, nvar):
        cur_sel = 0
        st.session_state[sel_key] = 0

    frag_raw = _variant_fragment_at(variants, pi) if has_content else ""
    if frag_raw and is_character_sculptor_role(role_name, lg):
        frag_raw = filter_character_sculptor_fragment(frag_raw)
    plan_lab = labels[pi] if has_content and pi < len(labels) else "—"
    plan_meta = f"{plan_lab} · {pi + 1}/{pages}" if has_content else "—"
    picked_cls = " is-picked" if has_content and pi == cur_sel else ""
    body_tall = " nl-fn-module-body-tall" if merge_slot_display else ""
    if has_content:
        body_inner = _merge_fragment_to_html(frag_raw) if merge_slot_display else _fragment_to_ul_html(frag_raw)
    elif empty_hint:
        body_inner = f'<p class="nl-fn-empty-hint">{html.escape(empty_hint)}</p>'
    else:
        body_inner = '<p class="nl-empty-dash">—</p>'

    st.markdown(f'<div class="nl-fn-stack-anchor" data-slug="{slug}"></div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="nl-fn-module nl-fn-module-instack{picked_cls}">'
        f'<div class="nl-fn-module-head">'
        f'<span class="nl-fn-module-role">{html.escape(role_name)}</span>'
        f'<span class="nl-fn-module-plan">{html.escape(plan_meta)}</span>'
        f"</div>"
        f'<div class="nl-fn-module-body{body_tall}">{body_inner}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown(f'<div class="nl-fn-nav-instack-anchor" data-slug="{slug}"></div>', unsafe_allow_html=True)
    if not has_content:
        if show_upgrade_btn and upgrade_pending_key:
            if st.button(
                T("antitrope_upgrade_btn", lg),
                key=f"fn_upgrade_{beat_idx}_{slug}",
                type="secondary",
                use_container_width=True,
            ):
                st.session_state[upgrade_pending_key] = True
                st.rerun()
        return 0

    nav_prev, nav_a, nav_b, nav_c, nav_next, nav_pick = st.columns(
        [0.38, 0.52, 0.52, 0.52, 0.38, 1.05],
        gap="small",
    )
    with nav_prev:
        if st.button("◀", key=f"fnv_prev_{beat_idx}_{slug}", disabled=pi <= 0, type="secondary"):
            st.session_state[page_key] = pi - 1
            st.rerun()
    plan_cols = [nav_a, nav_b, nav_c]
    for i in range(min(3, pages)):
        lab = labels[i] if i < len(labels) else str(i + 1)
        with plan_cols[i]:
            if st.button(
                lab,
                key=f"fnv_plan_{beat_idx}_{slug}_{i}",
                type="primary" if i == pi else "secondary",
                use_container_width=True,
            ):
                st.session_state[page_key] = i
                st.rerun()
    with nav_next:
        if st.button("▶", key=f"fnv_next_{beat_idx}_{slug}", disabled=pi >= pages - 1, type="secondary"):
            st.session_state[page_key] = pi + 1
            st.rerun()
    with nav_pick:
        pick_txt = pick_label or T("pick_this_variant", lg)
        if st.button(
            pick_txt,
            key=f"fnv_pick_{beat_idx}_{slug}_{pi}",
            type="primary" if pi == cur_sel else "secondary",
            use_container_width=True,
        ):
            st.session_state[sel_key] = pi
            st.session_state[page_key] = pi
            if pick_applies_to_merge and frag_raw.strip():
                st.session_state[f"_fn_merge_apply_text_{beat_idx}"] = frag_raw.strip()
            if sync_merge_on_pick:
                st.session_state[f"_fn_merge_sync_{beat_idx}"] = True
            st.rerun()
    return int(st.session_state.get(sel_key, pi))


def unified_plan_page_key(beat_idx: int) -> str:
    return f"unified_plan_page_{beat_idx}"


def unified_plan_pick_key(beat_idx: int) -> str:
    return f"unified_plan_pick_{beat_idx}"


def render_unified_plan_carousel(
    lg: str,
    beat_idx: int,
    variants: List[Dict[str, Any]],
    *,
    feedback_renderer: Optional[Callable[[str, Any, str], None]] = None,
    highlight_mutations: bool = False,
    plan_labels: Optional[List[str]] = None,
    role_names: Optional[List[str]] = None,
    locked_character_names: Optional[List[str]] = None,
    character_target_total: Optional[int] = None,
    role_layout: bool = True,
    renormalize_on_render: bool = False,
    cards_per_page: int = UNIFIED_PLANS_PER_PAGE,
    show_section_heading: bool = True,
    mutation_baseline: str = "",
    seed: str = "",
    beat_index: int = 0,
    prior_character_profiles: Optional[Dict[str, str]] = None,
) -> int:
    """功能化/反套路总体方案：横向翻页展示候选。"""
    from narrativeloom.utils.display_utils import normalize_single_unified_outline, outline_to_display_html

    per_page = max(1, int(cards_per_page))
    labels = plan_labels or [T("plan_a", lg), T("plan_b", lg), T("plan_c", lg), T("plan_d", lg)]
    page_key = unified_plan_page_key(beat_idx)
    pick_key = unified_plan_pick_key(beat_idx)
    n_var = len(variants)
    pages = max(1, (n_var + per_page - 1) // per_page)
    pi = int(st.session_state.get(page_key, 0))
    pi = max(0, min(pi, pages - 1))
    st.session_state[page_key] = pi

    picked = int(st.session_state.get(pick_key, 0))
    if picked < 0 or picked >= n_var:
        picked = 0
        st.session_state[pick_key] = 0

    if show_section_heading:
        section_heading(T("fn_unified_plans_title", lg))

    nav_l, nav_m, nav_r = st.columns([1, 3, 1])
    with nav_l:
        if st.button(
            "◀ " + T("carousel_prev", lg),
            key=f"unified_prev_{beat_idx}",
            disabled=pi <= 0,
            use_container_width=True,
            type="secondary",
        ):
            st.session_state[page_key] = pi - 1
            st.rerun()
    with nav_m:
        i0 = pi * per_page
        i1 = min(n_var - 1, i0 + per_page - 1)
        lab_a = labels[i0] if i0 < len(labels) else str(i0 + 1)
        lab_b = labels[i1] if i1 < len(labels) else str(i1 + 1)
        page_lbl = lab_a if i0 == i1 else f"{lab_a} · {lab_b}"
        st.markdown(
            f'<p class="nl-carousel-page">{html.escape(page_lbl)} · {pi + 1}/{pages}</p>',
            unsafe_allow_html=True,
        )
    with nav_r:
        if st.button(
            T("carousel_next", lg) + " ▶",
            key=f"unified_next_{beat_idx}",
            disabled=pi >= pages - 1,
            use_container_width=True,
            type="secondary",
        ):
            st.session_state[page_key] = pi + 1
            st.rerun()

    slice_start = pi * per_page
    slice_ = variants[slice_start : slice_start + per_page]
    cols = st.columns(per_page, gap="medium")
    body_cls = " nl-fn-module-body-dual" if per_page > 1 else " nl-fn-module-body-single"
    plan_cls = " nl-unified-plan-dual" if per_page > 1 else " nl-unified-plan-single"
    for col_i in range(per_page):
        with cols[col_i]:
            vi = slice_start + col_i
            if col_i >= len(slice_):
                st.markdown('<div class="nl-typ-card-spacer"></div>', unsafe_allow_html=True)
                continue
            item = slice_[col_i]
            lab = labels[vi] if vi < len(labels) else str(vi + 1)
            outline = str(item.get("outline") or "").strip()
            if renormalize_on_render and role_layout and outline and role_names:
                outline = normalize_single_unified_outline(
                    outline,
                    role_names=role_names,
                    lang=lg,
                    locked_names=locked_character_names,
                    character_target_total=character_target_total,
                    seed=seed,
                    beat_index=beat_index,
                    prior_character_profiles=prior_character_profiles,
                )
            picked_cls = " is-picked" if vi == picked else ""
            body_html = outline_to_display_html(
                outline,
                highlight_mutations=highlight_mutations,
                role_names=role_names if role_layout else None,
                outline_kind="roles" if role_layout else "story",
                mutation_baseline=mutation_baseline if highlight_mutations else "",
            )
            st.markdown(
                f'<div class="nl-fn-module nl-unified-plan{plan_cls}{picked_cls}">'
                f'<div class="nl-fn-module-head">'
                f'<span class="nl-fn-module-role">{html.escape(lab)}</span>'
                f"</div>"
                f'<div class="nl-fn-module-body nl-fn-module-body-tall{body_cls}">{body_html}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
            if feedback_renderer:
                feedback_renderer(lab, item.get("process_feedback"), lg)
            _pc1, _pc2, _pc3 = st.columns([1, 1.2, 1])
            with _pc2:
                if st.button(
                    T("pick_this_variant", lg),
                    key=f"unified_pick_{beat_idx}_{vi}",
                    type="primary" if vi == picked else "secondary",
                    use_container_width=True,
                ):
                    st.session_state[pick_key] = vi
                    st.session_state[page_key] = pi
                    st.rerun()
    return int(st.session_state.get(pick_key, picked))
