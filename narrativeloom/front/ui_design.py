# -*- coding: utf-8 -*-
"""NarrativeLoom-pro 设计系统：#657FEC + #EE8F95 · Streamlit 适配。"""

from __future__ import annotations

from typing import Literal

PageMode = Literal["landing", "workspace", "preview", "survey"]

# RGB(101,127,236) / RGB(238,143,149)
TOKENS = {
    "blue": "#657FEC",
    "pink": "#EE8F95",
    "gradient_main": "linear-gradient(120deg, #657FEC 0%, #8B9CF5 52%, #EE8F95 100%)",
    "gradient_soft": "linear-gradient(165deg, #EEF2FF 0%, #FDF4F5 48%, #F4F6FC 100%)",
    "gradient_sidebar": "linear-gradient(180deg, #657FEC 0%, #7A8FE8 55%, #8E9AE6 100%)",
    "primary": "#657FEC",
    "primary_hover": "#556EDC",
    "accent_pink": "#EE8F95",
    "text": "#2C3E66",
    "text_body": "#3D4F6F",
    "text_muted": "#6B7C9E",
    "border": "#C8D4F0",
    "surface": "#FFFFFF",
    "surface_tint": "#F3F6FD",
    "radius": "12px",
    "radius_lg": "16px",
    "shadow_card": "0 6px 22px rgba(101,127,236,0.14)",
    "font_serif": "'Lora', 'Noto Serif SC', 'Georgia', serif",
    "font_sans": "'Source Sans 3', 'Noto Sans SC', 'Microsoft YaHei', sans-serif",
    "transition": "0.22s ease",
}


def get_global_css(mode: PageMode = "landing") -> str:
    t = TOKENS
    g = t["gradient_main"]
    page_bg = t["gradient_soft"] if mode == "landing" else (
        "linear-gradient(180deg, #F0F4FF 0%, #FDF6F7 40%, #F4F6FC 100%)"
    )
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,500;0,600;0,700&family=Source+Sans+3:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;600;700&display=swap');

:root {{
    --nl-gradient: {g};
    --nl-primary: {t['blue']};
    --nl-pink: {t['pink']};
    --nl-bg: #F4F6FC;
    --nl-surface: {t['surface']};
    --nl-tint: {t['surface_tint']};
    --nl-border: {t['border']};
    --nl-text: {t['text']};
    --nl-body: {t['text_body']};
    --nl-muted: {t['text_muted']};
    --nl-serif: {t['font_serif']};
    --nl-sans: {t['font_sans']};
    --nl-radius: {t['radius']};
    --nl-shadow: {t['shadow_card']};
}}

html, body {{
    font-family: var(--nl-sans) !important;
    color: var(--nl-body);
}}
.stApp label, .stMarkdown, .stApp p, .stApp h1, .stApp h2, .stApp h3,
section.main input, section.main textarea, section.main button,
[data-testid="stSidebar"] .stMarkdown {{
    font-family: var(--nl-sans);
}}
/* Streamlit expander 等控件使用 Material Symbols，勿被全局 sans 覆盖 */
span[data-testid="stIconMaterial"],
.material-symbols-rounded,
.material-icons {{
    font-family: "Material Symbols Rounded", "Material Icons" !important;
    font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24 !important;
    font-feature-settings: "liga" !important;
}}
.stApp {{
    background: {page_bg} !important;
    background-attachment: fixed;
}}
[data-testid="stHeader"], [data-testid="stToolbar"] {{
    background: transparent !important;
}}
.block-container {{
    padding-top: 0.75rem;
    max-width: 1180px;
}}
section.main div[data-testid="stVerticalBlock"]:has(> div > div[data-testid="stMarkdownContainer"] style) {{
    margin: 0 !important;
    padding: 0 !important;
    min-height: 0 !important;
}}
section.main div[data-testid="stVerticalBlockBorderWrapper"]:has(style) {{
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
}}

hr,
[data-testid="stDivider"],
div[data-testid="stDivider"],
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stHorizontalBlockBorderWrapper"],
[data-testid="stDecoration"] {{
    display: none !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    background: transparent !important;
}}
div[data-testid="stVerticalBlock"] > div[style*="border"] {{
    border: none !important;
}}
section.main [data-testid="column"] {{
    background: transparent !important;
}}

[data-testid="stSidebar"] {{
    background: {t['gradient_sidebar']} !important;
    border-right: none !important;
}}
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stMarkdown strong,
[data-testid="stSidebar"] label {{
    color: #F8FAFC !important;
}}
/* 侧栏导航：按钮前粉色圆点（替代 radio） */
.nl-side-nav div.stButton > button::before {{
    content: "";
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #EE8F95 !important;
    margin-right: 0.5rem;
    vertical-align: middle;
    position: relative;
    top: -1px;
    flex-shrink: 0;
}}
.nl-side-nav div.stButton > button[kind="primary"]::before {{
    box-shadow: 0 0 0 2px rgba(255,255,255,0.55);
}}
[data-testid="stSidebar"] [data-testid="stRadio"] svg circle,
[data-testid="stSidebar"] [data-testid="stRadio"] [data-baseweb="radio"] > div:first-child {{
    fill: {t['pink']} !important;
    background: {t['pink']} !important;
    border-color: {t['pink']} !important;
}}
[data-testid="stSidebar"] div.stButton > button,
[data-testid="stSidebar"] div.stButton > button[kind="secondary"],
[data-testid="stSidebar"] div.stButton > button[kind="primary"] {{
    background: rgba(255,255,255,0.18) !important;
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    border: 1px solid rgba(255,255,255,0.42) !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
}}
[data-testid="stSidebar"] div.stButton > button p,
[data-testid="stSidebar"] div.stButton > button span {{
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}}

.nl-sidebar-brand {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.25rem 0 1rem;
    margin-bottom: 0.35rem;
    border-bottom: 1px solid rgba(255,255,255,0.22);
}}
.nl-sidebar-brand .mark {{
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: {g};
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: #fff;
}}
.nl-sidebar-brand .name {{
    font-weight: 600;
    font-size: 1.05rem;
    color: #fff;
}}

.nl-landing-lang-anchor {{
    display: none;
}}
div.nl-landing-lang-anchor + div[data-testid="stSelectbox"] {{
    position: fixed !important;
    top: 0.65rem !important;
    right: 1rem !important;
    z-index: 999 !important;
    width: 5.5rem !important;
    max-width: 5.5rem !important;
    margin: 0 !important;
    background: rgba(255,255,255,0.92) !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 8px rgba(101,127,236,0.12) !important;
}}
div.nl-landing-lang-anchor + div[data-testid="stSelectbox"] > div {{
    font-size: 0.78rem !important;
}}
div.nl-landing-lang-anchor + div[data-testid="stSelectbox"] label {{
    display: none !important;
}}
.nl-landing-wrap {{ text-align: center; padding: 3.5rem 1rem 1.5rem; max-width: 720px; margin: 0 auto; }}
.nl-landing-title {{
    font-size: clamp(3rem, 8.5vw, 4.35rem);
    font-weight: 700;
    background: {g};
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 0.75rem;
    letter-spacing: 0.02em;
}}
.nl-landing-tag {{ font-family: var(--nl-serif); font-size: 1.12rem; color: var(--nl-text); }}
.nl-landing-tag2 {{ font-family: var(--nl-serif); font-size: 1rem; color: #5A6F94; margin-bottom: 1.25rem; }}
.nl-lang-bar {{ display: flex; justify-content: flex-end; padding: 0.35rem 0 0.5rem; }}

.nl-serif-h1 {{ font-family: var(--nl-serif); font-size: 1.65rem; font-weight: 600; color: var(--nl-text); margin: 0 0 0.5rem; }}
.nl-serif-h2 {{ font-family: var(--nl-serif); font-size: 1.15rem; font-weight: 600; color: var(--nl-text); margin: 0 0 0.35rem; }}
.nl-muted-line {{ font-size: 0.88rem; color: var(--nl-muted); margin: 0 0 0.75rem; line-height: 1.5; }}
.nl-modal-card {{
    background: var(--nl-surface);
    border-radius: {t['radius_lg']};
    box-shadow: var(--nl-shadow);
    border: 1px solid var(--nl-border);
    padding: 1.5rem 1.65rem 1.25rem;
    max-width: 640px;
    margin: 1rem auto 1.5rem;
}}
.nl-sparkle-box {{
    background: linear-gradient(135deg, #F3F6FD 0%, #FDF4F5 100%);
    border: 1px solid var(--nl-border);
    border-radius: var(--nl-radius);
    padding: 0.85rem 1rem;
    margin: 0.5rem 0 1rem;
    line-height: 1.55;
}}

.nl-carousel-page {{
    font-size: 0.88rem;
    font-weight: 600;
    color: var(--nl-muted);
    text-align: center;
    margin: 0;
}}
.nl-recommend-box {{
    background: linear-gradient(135deg, #F3F6FD, #FDF4F5);
    border: 1px solid var(--nl-border);
    border-radius: var(--nl-radius);
    padding: 0.75rem 1rem;
    margin: 0.35rem 0 0.75rem;
    font-size: 0.9rem;
    line-height: 1.55;
}}
.nl-recommend-box strong {{ color: var(--nl-primary); }}

[data-testid="column"] > div > .nl-typ-col-wrap {{
    min-width: 0;
    width: 100%;
}}
.nl-typ-col-wrap {{
    width: 100%;
    min-width: 16rem;
    max-width: 100%;
}}
/* —— 类型化候选卡片（等高 + 内滚） —— */
.nl-typ-card {{
    border: 1px solid var(--nl-border);
    border-radius: var(--nl-radius);
    background: var(--nl-surface);
    box-shadow: 0 2px 10px rgba(101,127,236,0.08);
    display: flex;
    flex-direction: column;
    height: 36.75rem;
    width: 100%;
    box-sizing: border-box;
    margin: 0 0 0.4rem;
    overflow: hidden;
}}
.nl-typ-card.is-picked {{
    border-color: {t['blue']};
    box-shadow: 0 0 0 2px rgba(101,127,236,0.2);
}}
.nl-typ-card-title {{
    flex-shrink: 0;
    padding: 0.5rem 0.72rem;
    font-size: 0.98rem;
    font-weight: 700;
    color: var(--nl-text);
    border-bottom: 1px solid #E6EBF5;
    background: linear-gradient(90deg, rgba(101,127,236,0.12), rgba(238,143,149,0.1));
}}
.nl-typ-card-scroll {{
    flex: 1;
    min-height: 0;
    overflow-x: hidden;
    overflow-y: auto;
    padding: 0.5rem 0.72rem 0.55rem;
    -webkit-overflow-scrolling: touch;
}}
.nl-typ-field {{
    margin-bottom: 0.45rem;
}}
.nl-typ-lbl {{
    display: block;
    font-size: 0.78rem;
    font-weight: 600;
    color: {t['blue']};
    margin-bottom: 0.15rem;
}}
.nl-typ-txt {{
    margin: 0;
    font-size: 0.86rem;
    line-height: 1.45;
    color: var(--nl-body);
    white-space: normal;
    word-break: normal;
    overflow-wrap: break-word;
}}
.nl-ul {{
    margin: 0.12rem 0 0.2rem 1.05rem;
    padding: 0;
    font-size: 0.86rem;
    line-height: 1.46;
    color: var(--nl-body);
}}
.nl-ul li {{
    margin-bottom: 0.22rem;
    word-break: break-word;
}}
.nl-empty-dash {{
    margin: 0;
    color: var(--nl-muted);
    font-size: 0.86rem;
}}
.nl-beat-heading {{
    font-family: var(--nl-serif);
    font-size: 1.45rem;
    font-weight: 700;
    color: var(--nl-text);
    margin: 0.5rem 0 0.85rem;
    letter-spacing: 0.02em;
}}
/* —— 功能化职能模块 —— */
.nl-fn-module {{
    width: 100%;
    box-sizing: border-box;
    border: 1px solid var(--nl-border);
    border-radius: {t['radius_lg']};
    background: var(--nl-surface);
    margin: 0 0 0.25rem;
    overflow: hidden;
    box-shadow: 0 2px 10px rgba(101,127,236,0.06);
}}
.nl-fn-module.is-picked {{
    border-color: {t['blue']};
    box-shadow: 0 0 0 1px rgba(101,127,236,0.25);
}}
.nl-fn-module-head {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.42rem 0.68rem;
    background: linear-gradient(90deg, #F3F6FD, #FDF4F5);
    border-bottom: 1px solid var(--nl-border);
}}
.nl-fn-module-role {{
    font-weight: 700;
    font-size: 0.92rem;
    color: var(--nl-text);
}}
.nl-fn-module-plan {{
    font-size: 0.8rem;
    color: var(--nl-muted);
    white-space: nowrap;
}}
.nl-fn-module-body {{
    padding: 0.5rem 0.75rem 0.55rem;
    max-height: 9rem;
    overflow-y: auto;
    font-size: 0.86rem;
    line-height: 1.48;
    color: var(--nl-body);
}}
.nl-consent-scroll .nl-fn-module-body {{
    max-height: none;
    overflow: visible;
}}
.nl-typ-as-fn .nl-fn-module-body,
.nl-typ-as-fn .nl-typ-fn-body {{
    max-height: 15.75rem;
    min-height: 10.5rem;
}}
.nl-fn-module-body-tall {{
    max-height: 30rem;
    min-height: 16rem;
}}
.nl-unified-plan .nl-fn-module-body-tall {{
    max-height: 42rem;
    min-height: 18rem;
}}
.nl-unified-plan-dual .nl-fn-module-body-dual {{
    max-height: 32rem;
    min-height: 12rem;
}}
.nl-unified-plan-single .nl-fn-module-body-single {{
    max-height: 40rem;
    min-height: 18rem;
}}
.nl-unified-plan-dual.is-picked {{
    box-shadow: 0 0 0 2px rgba(101,127,236,0.45);
}}
.nl-fn-role-sep {{
    height: 0;
    margin: 0.15rem 0 0.95rem;
    border: none;
    border-top: 1px solid rgba(101,127,236,0.14);
}}
.nl-fn-empty-hint {{
    margin: 0;
    font-size: 0.86rem;
    line-height: 1.5;
    color: var(--nl-muted);
}}
/* 功能化：卡片 + 底栏合为一体（避免方案键“悬空”在两个人格之间） */
.nl-fn-stack-anchor,
.nl-fn-nav-instack-anchor {{
    display: none;
}}
div.nl-fn-stack-anchor + div.nl-fn-module-instack {{
    margin: 0 !important;
    border-radius: {t['radius_lg']} {t['radius_lg']} 0 0 !important;
    border-bottom: none !important;
    box-shadow: none !important;
}}
div.nl-fn-nav-instack-anchor + div[data-testid="stHorizontalBlock"] {{
    align-items: center !important;
    justify-content: center !important;
    margin: 0 0 1.1rem !important;
    padding: 0.42rem 0.55rem !important;
    gap: 0.28rem !important;
    background: linear-gradient(180deg, #F8FAFE 0%, #F5F6FA 100%);
    border: 1px solid var(--nl-border);
    border-top: 1px dashed rgba(101,127,236,0.35);
    border-radius: 0 0 {t['radius_lg']} {t['radius_lg']};
    box-shadow: 0 4px 14px rgba(101,127,236,0.08);
}}
div.nl-fn-nav-instack-anchor + div[data-testid="stHorizontalBlock"] > div:nth-child(2),
div.nl-fn-nav-instack-anchor + div[data-testid="stHorizontalBlock"] > div:nth-child(3),
div.nl-fn-nav-instack-anchor + div[data-testid="stHorizontalBlock"] > div:nth-child(4) {{
    flex: 0 1 4.2rem !important;
    max-width: 4.2rem !important;
}}
div.nl-fn-nav-instack-anchor + div[data-testid="stHorizontalBlock"] div.stButton > button {{
    min-height: 2rem !important;
    font-size: 0.8rem !important;
    padding: 0.28rem 0.5rem !important;
    border-radius: 8px !important;
    width: 100%;
}}
div.nl-fn-nav-instack-anchor + div[data-testid="stHorizontalBlock"] div.stButton > button[kind="secondary"] {{
    background: #fff !important;
    color: var(--nl-text) !important;
    -webkit-text-fill-color: var(--nl-text) !important;
    border: 1px solid var(--nl-border) !important;
    box-shadow: none !important;
}}
div.nl-fn-nav-instack-anchor + div[data-testid="stHorizontalBlock"] div.stButton > button[kind="primary"] {{
    background: {t['blue']} !important;
    color: #fff !important;
    -webkit-text-fill-color: #fff !important;
    border: none !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 8px rgba(101,127,236,0.28) !important;
}}
div.nl-fn-nav-instack-anchor + div[data-testid="stHorizontalBlock"] > div:first-child div.stButton > button,
div.nl-fn-nav-instack-anchor + div[data-testid="stHorizontalBlock"] > div:nth-child(5) div.stButton > button {{
    font-size: 0.72rem !important;
    padding: 0.28rem 0.2rem !important;
}}
div.nl-fn-nav-instack-anchor + div[data-testid="stHorizontalBlock"] > div:first-child,
div.nl-fn-nav-instack-anchor + div[data-testid="stHorizontalBlock"] > div:nth-child(5) {{
    flex: 0 0 2rem !important;
    max-width: 2rem !important;
    min-width: 2rem !important;
}}
div.nl-fn-nav-instack-anchor + div[data-testid="stHorizontalBlock"] > div:last-child {{
    flex: 1 1 auto !important;
    max-width: 9rem !important;
    margin-left: auto !important;
}}
.nl-fn-merge-role {{
    font-weight: 700;
    font-size: 0.84rem;
    color: var(--nl-text);
    margin: 0.35rem 0 0.15rem;
}}
.nl-fn-merge-role:first-child {{
    margin-top: 0;
}}
.nl-fn-toolbar {{
    margin: 0.15rem 0 0.85rem;
}}
.nl-fn-toolbar div.stButton > button {{
    min-height: 1.75rem !important;
    font-size: 0.78rem !important;
    padding: 0.2rem 0.55rem !important;
    border-radius: 8px !important;
    width: 100%;
}}
.nl-fn-toolbar div.stButton > button[kind="secondary"] {{
    background: #fff !important;
    color: var(--nl-text) !important;
    -webkit-text-fill-color: var(--nl-text) !important;
    border: 1px solid var(--nl-border) !important;
    box-shadow: none !important;
}}
.nl-fn-toolbar div.stButton > button[kind="primary"] {{
    background: {t['blue']} !important;
    color: #fff !important;
    font-size: 0.78rem !important;
    box-shadow: none !important;
}}
.nl-confirm-wrap div.stButton > button {{
    background: {t['blue']} !important;
    border: none !important;
    color: #fff !important;
    -webkit-text-fill-color: #fff !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    border-radius: 10px !important;
    box-shadow: 0 6px 18px rgba(101,127,236,0.35) !important;
    min-height: 2.75rem !important;
}}
.nl-confirm-wrap div.stButton > button:hover {{
    filter: brightness(1.06);
}}

.nl-mut-highlight {{
    background: linear-gradient(120deg, #FFE0EA 0%, #FFD1E3 45%, #E6E4FF 100%);
    color: #8B1E3F;
    padding: 0.12em 0.38em;
    border-radius: 5px;
    font-weight: 600;
    box-shadow: 0 0 0 1px rgba(255, 105, 140, 0.42);
}}
.nl-mut-li {{
    background: linear-gradient(90deg, rgba(255, 224, 234, 0.55) 0%, rgba(255, 255, 255, 0) 100%);
    border-left: 3px solid #FF6B9A;
    padding-left: 0.45rem;
    margin-left: -0.45rem;
    border-radius: 4px;
}}
.nl-outline-pre {{
    white-space: pre-wrap;
    word-break: break-word;
    font-family: inherit;
    font-size: 0.95rem;
    line-height: 1.65;
    margin: 0;
    background: transparent;
    border: none;
    padding: 0;
}}
.nl-fn-outline {{
    background: linear-gradient(135deg, #FAFCFF 0%, #FDF6F7 100%);
    border: 1px solid var(--nl-border);
    border-radius: var(--nl-radius);
    padding: 0.9rem 1rem;
    font-size: 0.95rem;
    line-height: 1.65;
}}
.nl-prose-full {{
    background: var(--nl-surface);
    border: 1px solid var(--nl-border);
    border-radius: var(--nl-radius-lg);
    padding: 1.25rem 1.4rem;
    line-height: 1.8;
    font-family: var(--nl-serif);
}}
.nl-prose-p {{
    margin: 0 0 1em 0;
}}
.nl-prose-p:last-child {{
    margin-bottom: 0;
}}
.nl-beat-pill {{
    min-width: 2rem;
    height: 2rem;
    border-radius: 8px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.82rem;
    font-weight: 600;
    border: 1px solid var(--nl-border);
    background: var(--nl-surface);
    color: var(--nl-muted);
}}
.nl-beat-pill.nl-done {{
    background: var(--nl-gradient);
    color: #fff;
    border: none;
}}
.nl-beat-pill.nl-current {{
    border-color: {t['pink']};
    color: #B85C68;
    background: #FFF5F6;
}}
.nl-fn-slots-preview {{
    background: linear-gradient(135deg, #EEF2FF, #FDF4F5);
    border-radius: var(--nl-radius);
    padding: 0.85rem 1rem;
    margin-bottom: 1rem;
    border: 1px solid var(--nl-border);
}}

section.main div.stButton > button[kind="primary"] {{
    background: {t['blue']} !important;
    border: none !important;
    color: #fff !important;
    -webkit-text-fill-color: #fff !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    min-height: 2rem !important;
    font-size: 0.84rem !important;
    padding: 0.32rem 0.9rem !important;
    box-shadow: 0 2px 8px rgba(101,127,236,0.22) !important;
}}
section.main div.stButton > button[kind="secondary"] {{
    border-radius: 10px !important;
    border: 1px solid var(--nl-border) !important;
    background: #fff !important;
    color: var(--nl-text) !important;
    -webkit-text-fill-color: var(--nl-text) !important;
}}
section.main div[data-testid="stTextInput"] input,
section.main div[data-testid="stTextArea"] textarea {{
    border: 1px solid var(--nl-border) !important;
    border-radius: 10px !important;
    background: #FAFCFF !important;
}}
[data-testid="stRadio"] svg circle {{ fill: {t['blue']} !important; }}
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {{
    background: {t['blue']} !important;
}}
button[role="switch"][aria-checked="true"] {{
    background: {t['blue']} !important;
}}

/* —— 知情同意页 —— */
.nl-consent-page {{
    max-width: 920px;
    margin: 0 auto;
    padding: 0 0.5rem 2rem;
}}
.nl-consent-steps {{
    display: flex;
    justify-content: center;
    gap: 0.35rem;
    flex-wrap: wrap;
    margin: 0.5rem 0 1.25rem;
}}
.nl-consent-step {{
    font-size: 0.78rem;
    font-weight: 600;
    padding: 0.28rem 0.72rem;
    border-radius: 999px;
    border: 1px solid var(--nl-border);
    color: var(--nl-muted);
    background: rgba(255,255,255,0.72);
}}
.nl-consent-step.is-active {{
    background: var(--nl-gradient);
    color: #fff;
    border-color: transparent;
    box-shadow: 0 2px 8px rgba(101,127,236,0.22);
}}
.nl-consent-hero {{
    text-align: center;
    padding: 1.5rem 0.5rem 0.75rem;
}}
.nl-consent-hero h1 {{
    font-family: var(--nl-serif);
    font-size: clamp(1.45rem, 3.5vw, 1.85rem);
    font-weight: 700;
    color: var(--nl-text);
    margin: 0 0 0.45rem;
    line-height: 1.35;
}}
.nl-consent-hero p {{
    font-size: 0.9rem;
    color: var(--nl-muted);
    margin: 0;
    line-height: 1.55;
}}
.nl-consent-chips {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    justify-content: center;
    margin: 0.85rem 0 1.1rem;
}}
.nl-consent-chip {{
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--nl-text);
    padding: 0.32rem 0.78rem;
    border-radius: 999px;
    border: 1px solid var(--nl-border);
    background: linear-gradient(135deg, #EEF2FF 0%, #FDF4F5 100%);
}}
.nl-consent-scroll {{
    max-height: min(46vh, 440px);
    overflow-y: auto;
    padding-right: 0.35rem;
    margin-bottom: 1rem;
}}
.nl-consent-scroll::-webkit-scrollbar {{ width: 6px; }}
.nl-consent-scroll::-webkit-scrollbar-thumb {{
    background: #C8D4F0;
    border-radius: 999px;
}}
.nl-consent-kv {{
    display: grid;
    grid-template-columns: minmax(5.5rem, 7rem) 1fr;
    gap: 0.35rem 0.75rem;
    margin: 0;
    font-size: 0.86rem;
    line-height: 1.5;
}}
.nl-consent-kv dt {{
    margin: 0;
    font-weight: 600;
    color: var(--nl-primary);
}}
.nl-consent-kv dd {{
    margin: 0;
    color: var(--nl-body);
}}
.nl-consent-steps-list {{
    margin: 0;
    padding: 0;
    list-style: none;
}}
.nl-consent-steps-list li {{
    display: flex;
    gap: 0.65rem;
    margin-bottom: 0.65rem;
    align-items: flex-start;
}}
.nl-consent-step-num {{
    flex-shrink: 0;
    width: 1.45rem;
    height: 1.45rem;
    border-radius: 50%;
    background: var(--nl-gradient);
    color: #fff;
    font-size: 0.72rem;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    margin-top: 0.05rem;
}}
.nl-consent-step-body strong {{
    display: block;
    color: var(--nl-text);
    font-size: 0.88rem;
    margin-bottom: 0.12rem;
}}
.nl-consent-step-body span {{
    font-size: 0.78rem;
    color: var(--nl-muted);
}}
.nl-consent-step-body p {{
    margin: 0.15rem 0 0;
    font-size: 0.84rem;
    line-height: 1.48;
    color: var(--nl-body);
}}
.nl-consent-agree {{
    background: var(--nl-surface);
    border: 1px solid var(--nl-border);
    border-radius: {t['radius_lg']};
    box-shadow: var(--nl-shadow);
    padding: 1rem 1.1rem 0.65rem;
    margin-bottom: 0.85rem;
}}
.nl-consent-agree-head {{
    font-family: var(--nl-serif);
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--nl-text);
    margin: 0 0 0.25rem;
}}
.nl-consent-agree-sub {{
    font-size: 0.82rem;
    color: var(--nl-muted);
    margin: 0 0 0.65rem;
    line-height: 1.45;
}}
div[data-testid="stVerticalBlock"]:has(.nl-consent-agree) div[data-testid="stCheckbox"] label span {{
    font-size: 0.86rem !important;
    line-height: 1.45 !important;
    color: var(--nl-body) !important;
}}
.nl-consent-check-all {{
    border-top: 1px dashed var(--nl-border);
    margin-top: 0.35rem;
    padding-top: 0.55rem;
    margin-bottom: 0.15rem;
}}
div[data-testid="stVerticalBlock"]:has(.nl-consent-check-all) div[data-testid="stCheckbox"] label span {{
    font-size: 0.88rem !important;
    font-weight: 600 !important;
    color: var(--nl-primary) !important;
}}
</style>
"""
