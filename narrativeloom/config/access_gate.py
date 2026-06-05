# -*- coding: utf-8 -*-
"""网页访问密码门禁（可选，由 APP_ACCESS_PASSWORD 控制）。"""

from __future__ import annotations

import os
import secrets

import streamlit as st

from narrativeloom.config.i18n import T
from narrativeloom.front.ui_components import inject_css, render_landing_lang_corner


def _configured_password() -> str:
    return (os.getenv("APP_ACCESS_PASSWORD") or "").strip()


def _lang() -> str:
    return st.session_state.get("ui_lang") or "zh"


def render_access_gate() -> None:
    """若配置了 APP_ACCESS_PASSWORD，则先校验访问密码；未配置则直接放行。"""
    expected = _configured_password()
    if not expected:
        st.session_state.app_access_granted = True
        return
    if st.session_state.get("app_access_granted"):
        return

    lg = _lang()
    inject_css("landing")
    render_landing_lang_corner("gate_ui_lang")

    _sp, col, _sp2 = st.columns([1, 1.05, 1])
    with col:
        st.markdown(f"### {T('gate_title', lg)}")
        st.caption(T("gate_sub", lg))
        pwd = st.text_input(
            T("gate_password_label", lg),
            type="password",
            placeholder=T("gate_password_ph", lg),
            key="gate_password_input",
        )
        if st.button(T("gate_submit", lg), type="primary", use_container_width=True, key="gate_submit_btn"):
            if secrets.compare_digest(pwd.strip(), expected):
                st.session_state.app_access_granted = True
                st.rerun()
            else:
                st.error(T("gate_error", lg))
    st.stop()
