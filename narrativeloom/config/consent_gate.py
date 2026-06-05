# -*- coding: utf-8 -*-
"""知情同意书门禁：阅读全文并勾选声明后方可继续。"""

from __future__ import annotations

import html
from typing import Any, Dict, List

import streamlit as st

from narrativeloom.config.consent_content import CONSENT_META, CONSENT_SECTIONS, CONSENT_STATEMENTS
from narrativeloom.config.i18n import T
from narrativeloom.front.ui_components import inject_css, render_landing_lang_corner


def _lang() -> str:
    return st.session_state.get("ui_lang") or "zh"


def _render_steps(lg: str) -> str:
    labels = (
        (T("consent_step_access", lg), False),
        (T("consent_step_consent", lg), True),
        (T("consent_step_login", lg), False),
    )
    parts = []
    for text, active in labels:
        cls = "nl-consent-step is-active" if active else "nl-consent-step"
        parts.append(f'<span class="{cls}">{html.escape(text)}</span>')
    return f'<div class="nl-consent-steps">{"".join(parts)}</div>'


def _render_hero(lg: str) -> str:
    title = CONSENT_META["title"]
    chips = "".join(f'<span class="nl-consent-chip">{html.escape(c)}</span>' for c in CONSENT_META["chips"])
    return f"""
<div class="nl-consent-hero">
  <h1>{html.escape(title)}</h1>
  <p>{html.escape(T("consent_page_sub", lg))}</p>
</div>
<div class="nl-consent-chips">{chips}</div>
"""


def _render_section(section: Dict[str, Any]) -> str:
    title = html.escape(section["title"])
    kind = section.get("kind", "text")
    body = ""

    if kind == "kv":
        rows = "".join(
            f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>"
            for k, v in section.get("rows", [])
        )
        body = f'<dl class="nl-consent-kv">{rows}</dl>'
    elif kind == "text":
        body = "".join(f"<p>{html.escape(p)}</p>" for p in section.get("paragraphs", []))
    elif kind == "steps":
        items = []
        for i, step in enumerate(section.get("steps", []), 1):
            time_badge = (
                f'<span>{html.escape(step["time"])}</span>'
                if step.get("time")
                else ""
            )
            items.append(
                f'<li><span class="nl-consent-step-num">{i}</span>'
                f'<div class="nl-consent-step-body">'
                f'<strong>{html.escape(step["label"])}</strong>{time_badge}'
                f'<p>{html.escape(step["desc"])}</p></div></li>'
            )
        body = f'<ol class="nl-consent-steps-list">{"".join(items)}</ol>'
    elif kind == "bullets":
        intro = section.get("intro")
        intro_html = f"<p>{html.escape(intro)}</p>" if intro else ""
        lis = "".join(f"<li>{html.escape(item)}</li>" for item in section.get("items", []))
        body = f'{intro_html}<ul class="nl-ul">{lis}</ul>'

    return f"""
<div class="nl-fn-module">
  <div class="nl-fn-module-head">
    <span class="nl-fn-module-role">{title}</span>
  </div>
  <div class="nl-fn-module-body">{body}</div>
</div>
"""


def _render_sections_html(sections: List[Dict[str, Any]]) -> str:
    inner = "".join(_render_section(sec) for sec in sections)
    return f'<div class="nl-consent-scroll">{inner}</div>'


def render_consent_gate() -> None:
    """展示知情同意书；全部勾选并确认后放行。"""
    if st.session_state.get("informed_consent_accepted"):
        return

    lg = _lang()
    inject_css("landing")
    render_landing_lang_corner("consent_ui_lang")

    _sp, col, _sp2 = st.columns([0.4, 2.2, 0.4])
    with col:
        st.markdown('<div class="nl-consent-page">', unsafe_allow_html=True)
        st.markdown(_render_steps(lg), unsafe_allow_html=True)
        st.markdown(_render_hero(lg), unsafe_allow_html=True)
        st.markdown(_render_sections_html(CONSENT_SECTIONS), unsafe_allow_html=True)

        st.markdown(
            f"""
<div class="nl-consent-agree">
  <p class="nl-consent-agree-head">{html.escape(T("consent_agree_head", lg))}</p>
  <p class="nl-consent-agree-sub">{html.escape(T("consent_check_intro", lg))}</p>
</div>
""",
            unsafe_allow_html=True,
        )

        all_checked = True
        for i, label in enumerate(CONSENT_STATEMENTS):
            key = f"consent_ck_{i}"
            if key not in st.session_state:
                st.session_state[key] = False
            if not st.checkbox(label, key=key):
                all_checked = False

        if st.button(T("consent_submit", lg), type="primary", use_container_width=True, key="consent_submit_btn"):
            if CONSENT_STATEMENTS and all_checked:
                st.session_state.informed_consent_accepted = True
                st.rerun()
            else:
                st.error(T("consent_error", lg))

        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()
