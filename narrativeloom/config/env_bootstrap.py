# -*- coding: utf-8 -*-
"""本地 .env 与 Streamlit Cloud secrets 统一注入环境变量。"""

from __future__ import annotations

import os

from narrativeloom.config.settings import PROJECT_ROOT

_SECRET_KEYS = (
    "MIMO_API_KEY",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "LLM_MODEL",
    "DEEPSEEK_API_KEY",
    "APP_ACCESS_PASSWORD",
)


def bootstrap_env() -> None:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
    try:
        import streamlit as st
    except Exception:
        return
    try:
        secrets = st.secrets
    except Exception:
        return
    for key in _SECRET_KEYS:
        if os.getenv(key):
            continue
        try:
            val = secrets.get(key)
        except Exception:
            val = None
        if val:
            os.environ[key] = str(val).strip()
