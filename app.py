# -*- coding: utf-8 -*-
"""NarrativeLoom Streamlit 入口。"""

from narrativeloom.config.env_bootstrap import bootstrap_env
from narrativeloom.controller.main import main

bootstrap_env()
main()
