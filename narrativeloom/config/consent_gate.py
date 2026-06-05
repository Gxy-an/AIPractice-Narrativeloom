# -*- coding: utf-8 -*-
"""知情同意书门禁：阅读全文并勾选声明后方可继续。"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Tuple

import streamlit as st

from narrativeloom.config.i18n import T
from narrativeloom.config.settings import PROJECT_ROOT
from narrativeloom.front.ui_components import inject_css, render_landing_lang_corner

_CONSENT_PATH = PROJECT_ROOT / "informed_consent_form.md"
_SECTION_EIGHT = "## 八、同意声明"


@lru_cache(maxsize=1)
def _load_consent_parts() -> Tuple[str, str, List[str]]:
    """返回 (正文 Markdown, 第八节标题行, 须勾选的声明条目)。"""
    if not _CONSENT_PATH.is_file():
        return ("（未找到知情同意书文件 informed_consent_form.md）", _SECTION_EIGHT, [])
    text = _CONSENT_PATH.read_text(encoding="utf-8")
    idx = text.find(_SECTION_EIGHT)
    if idx == -1:
        return (text.strip(), "", [])
    body = text[:idx].strip()
    items: List[str] = []
    for line in text[idx:].splitlines()[1:]:
        s = line.strip()
        if s.startswith("- "):
            items.append(s[2:].strip())
    return body, _SECTION_EIGHT, items


def _lang() -> str:
    return st.session_state.get("ui_lang") or "zh"


def _scroll_container():
    try:
        return st.container(border=True, height=480)
    except TypeError:
        return st.container(border=True)


def render_consent_gate() -> None:
    """展示知情同意书；全部勾选并确认后放行。"""
    if st.session_state.get("informed_consent_accepted"):
        return

    lg = _lang()
    body, section_header, items = _load_consent_parts()

    inject_css("landing")
    render_landing_lang_corner("consent_ui_lang")

    _sp, col, _sp2 = st.columns([0.35, 2.3, 0.35])
    with col:
        st.markdown(f"### {T('consent_page_title', lg)}")
        st.caption(T("consent_page_sub", lg))
        with _scroll_container():
            st.markdown(body)

        if section_header:
            st.markdown(f"**{section_header.lstrip('#').strip()}**")
        st.caption(T("consent_check_intro", lg))

        with st.container(border=True):
            all_checked = True
            for i, label in enumerate(items):
                key = f"consent_ck_{i}"
                if key not in st.session_state:
                    st.session_state[key] = False
                if not st.checkbox(label, key=key):
                    all_checked = False

        if st.button(T("consent_submit", lg), type="primary", use_container_width=True, key="consent_submit_btn"):
            if items and all_checked:
                st.session_state.informed_consent_accepted = True
                st.rerun()
            else:
                st.error(T("consent_error", lg))
    st.stop()
