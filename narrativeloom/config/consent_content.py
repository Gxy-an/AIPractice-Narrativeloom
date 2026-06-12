# -*- coding: utf-8 -*-
"""知情同意书结构化内容（供 UI 渲染，非 Markdown）。"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple, TypedDict


class ConsentMeta(TypedDict):
    title: str
    chips: List[str]


CONSENT_META: ConsentMeta = {
    "title": "人机协同叙事创作实验知情同意书",
    "chips": ["约 40 分钟", "招募 25 人", "北京大学", "CHI 2026 研究"],
}

CONSENT_SECTIONS: List[Dict[str, Any]] = [
    {
        "title": "一、研究基本信息",
        "kind": "kv",
        "rows": [
            ("项目名称", "人格功能分化对人机协同讲故事创意多样性与叙事连贯性的影响"),
            ("负责人", "顾馨月"),
            ("所属机构", "北京大学化学与分子工程学院"),
            ("联系邮箱", "2400011707@stu.pku.edu.cn"),
            ("预计招募", "25 人"),
            ("实验时长", "约 40 分钟"),
        ],
    },
    {
        "title": "二、研究目的与背景",
        "kind": "text",
        "paragraphs": [
            "本研究基于国际顶级人机交互会议 CHI 2026 论文"
            "《NarrativeLoom: Enhancing Creative Storytelling through Multi-Persona Collaborative Improvisation》"
            "（arXiv:2603.07155v1），旨在比较类型化人格与功能化人格两种 AI 协作模式"
            "对人类叙事创作体验与故事质量的影响。",
            "您的参与将帮助我们理解如何设计更高效、更具创意的 AI 写作辅助工具，"
            "为未来人机协同创作系统的优化提供科学依据。",
        ],
    },
    {
        "title": "三、实验流程",
        "kind": "steps",
        "steps": [
            {"label": "知情同意与基础信息", "time": "约 3 分钟", "desc": "阅读本同意书，填写匿名基本信息。"},
            {"label": "系统熟悉与任务说明", "time": "约 2 分钟", "desc": "观看系统操作演示，了解实验任务要求。"},
            {
                "label": "人机协同故事创作",
                "time": "约 30 分钟",
                "desc": "体验两种 AI 协作模式，基于给定灵感与 AI 协作完成至少 2 个故事节拍；可自由选择、编辑 AI 生成内容。",
            },
            {"label": "实验问卷填写", "time": "约 5 分钟", "desc": "回答关于创作体验、创意感知、系统易用性的问题。"},
            {"label": "实验结束", "time": "", "desc": "提交问卷后即可获得实验报酬。"},
        ],
    },
    {
        "title": "四、潜在风险",
        "kind": "bullets",
        "intro": "本研究属于最低风险实验，不存在任何身体伤害风险：",
        "items": [
            "可能存在轻微的认知疲劳（类似日常写作）；",
            "不会收集任何敏感个人信息；",
            "您创作的故事内容将被完全匿名处理，不会与您的身份关联。",
        ],
    },
    {
        "title": "五、潜在收益",
        "kind": "bullets",
        "items": [
            "个人收益：完成全部实验后，您将获得0元现金报酬（实验结束后 24 小时内发放）。",
            "科学收益：您的参与将推动人机协同创作领域的科学研究，帮助开发更智能、更人性化的 AI 创意工具。",
            "体验收益：您将率先体验基于前沿研究的 AI 故事创作系统。",
        ],
    },
    {
        "title": "六、数据隐私与保密",
        "kind": "bullets",
        "intro": "我们严格遵守学术研究伦理规范，采取最高标准保护您的隐私：",
        "items": [
            "完全匿名：所有实验数据将使用随机生成的 ID 标识，不会收集可识别个人身份的信息。",
            "数据加密存储：所有数据将存储在加密服务器中，仅研究团队成员有权访问。",
            "数据使用范围：数据仅用于本研究的学术分析，不会用于任何商业用途。",
            "数据保存期限：原始数据将保存至研究论文发表后 1 年，到期后将永久删除。",
            "数据共享：学术发表时仅会使用聚合的统计数据，不会展示任何个人的具体创作内容或回答。",
        ],
    },
    {
        "title": "七、您的权利",
        "kind": "bullets",
        "items": [
            "自愿参与权：您的参与完全自愿，可在实验开始前拒绝参与，无需任何理由。",
            "随时退出权：可在实验过程中任何时间退出，无需说明理由，且不会影响已完成部分的报酬。",
            "数据控制权：实验结束后 7 天内，可通过联系邮箱要求删除您的所有实验数据。",
            "知情权：有权在实验前、中、后询问任何与本研究相关的问题，我们将及时为您解答。",
            "获得报酬权：只要您参与了实验，都将获得上述相应的报酬。",
        ],
    },
]

CONSENT_STATEMENTS: List[str] = [
    "我已阅读并完全理解本知情同意书的所有内容。",
    "我确认自己年满 18 周岁，具有完全民事行为能力。",
    "我自愿参与本研究，了解自己的权利和义务。",
    "我同意研究团队收集和使用我的匿名实验数据用于学术研究。",
    "我了解我可以随时退出实验，且不会受到任何不利影响。",
]

CONSENT_META_EN: ConsentMeta = {
    "title": "Informed Consent — Human–AI Collaborative Storytelling Study",
    "chips": ["~40 minutes", "25 participants", "Peking University", "CHI 2026 research"],
}

CONSENT_SECTIONS_EN: List[Dict[str, Any]] = [
    {
        "title": "1. Study information",
        "kind": "kv",
        "rows": [
            (
                "Project title",
                "Effects of persona functional differentiation on creative diversity and narrative coherence in human–AI collaborative storytelling",
            ),
            ("Principal investigator", "Xinyue Gu"),
            ("Institution", "College of Chemistry and Molecular Engineering, Peking University"),
            ("Contact email", "2400011707@stu.pku.edu.cn"),
            ("Target enrollment", "25 participants"),
            ("Session length", "About 40 minutes"),
        ],
    },
    {
        "title": "2. Purpose and background",
        "kind": "text",
        "paragraphs": [
            "This study is based on the CHI 2026 paper "
            "“NarrativeLoom: Enhancing Creative Storytelling through Multi-Persona Collaborative Improvisation” "
            "(arXiv:2603.07155v1). We compare typified-persona and functional-persona AI collaboration modes "
            "and how they affect human storytelling experience and story quality.",
            "Your participation will help us design more effective and creative AI writing assistants "
            "and inform future human–AI co-creation systems.",
        ],
    },
    {
        "title": "3. Procedure",
        "kind": "steps",
        "steps": [
            {
                "label": "Consent & demographics",
                "time": "~3 min",
                "desc": "Read this form and provide anonymous background information.",
            },
            {
                "label": "Tutorial & task briefing",
                "time": "~2 min",
                "desc": "Review a short system walkthrough and the storytelling task.",
            },
            {
                "label": "Human–AI story creation",
                "time": "~30 min",
                "desc": "Try both AI collaboration modes and complete at least two story beats from a sparkles prompt; you may select and edit AI output freely.",
            },
            {
                "label": "Post-task questionnaire",
                "time": "~5 min",
                "desc": "Answer questions about creativity, experience, and usability.",
            },
            {"label": "End of session", "time": "", "desc": "Submit the questionnaire to receive compensation."},
        ],
    },
    {
        "title": "4. Potential risks",
        "kind": "bullets",
        "intro": "This is a minimal-risk study with no physical harm:",
        "items": [
            "You may experience mild cognitive fatigue similar to everyday writing;",
            "No sensitive personal information will be collected;",
            "Story content you create will be fully anonymized and not linked to your identity.",
        ],
    },
    {
        "title": "5. Potential benefits",
        "kind": "bullets",
        "items": [
            "Personal: CNY 0 cash compensation after completing the full session (paid within 24 hours).",
            "Scientific: Your data supports research on human–AI creative collaboration.",
            "Experiential: You will try an AI storytelling system based on recent HCI research.",
        ],
    },
    {
        "title": "6. Privacy and confidentiality",
        "kind": "bullets",
        "intro": "We follow academic ethics standards and protect your privacy:",
        "items": [
            "Full anonymity: data are labeled with random IDs; no directly identifying information is collected.",
            "Encrypted storage: data are stored on encrypted servers accessible only to the research team.",
            "Use: data are used only for academic analysis, not for commercial purposes.",
            "Retention: raw data are kept for one year after publication, then permanently deleted.",
            "Sharing: publications will report aggregated statistics only, never individual drafts or answers.",
        ],
    },
    {
        "title": "7. Your rights",
        "kind": "bullets",
        "items": [
            "Voluntary participation: you may decline before starting, without giving a reason.",
            "Withdraw anytime: you may stop during the session without penalty for completed portions.",
            "Data control: within 7 days after the session you may request deletion via the contact email.",
            "Information: you may ask questions before, during, or after the study.",
            "Compensation: participants who take part receive the compensation described above.",
        ],
    },
]

CONSENT_STATEMENTS_EN: List[str] = [
    "I have read and fully understand this informed consent form.",
    "I confirm that I am at least 18 years old and legally competent to consent.",
    "I voluntarily participate in this study and understand my rights and obligations.",
    "I agree that the research team may collect and use my anonymized experimental data for academic research.",
    "I understand that I may withdraw at any time without adverse consequences.",
]


def get_consent_bundle(lang: str) -> Tuple[ConsentMeta, List[Dict[str, Any]], List[str]]:
    """Return consent meta, sections, and checkbox statements for the UI language."""
    if (lang or "zh") == "en":
        return CONSENT_META_EN, CONSENT_SECTIONS_EN, CONSENT_STATEMENTS_EN
    return CONSENT_META, CONSENT_SECTIONS, CONSENT_STATEMENTS
