# -*- coding: utf-8 -*-
"""项目路径与数据目录配置。"""

from __future__ import annotations

from pathlib import Path

# narrativeloom/config/settings.py -> 仓库根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DRAFT_DIR = DATA_DIR / "drafts"
LOG_PATH = DATA_DIR / "experiment_log.csv"
