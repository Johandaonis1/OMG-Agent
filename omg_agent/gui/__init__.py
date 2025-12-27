"""
OMG-Agent GUI 模块

提供图形用户界面组件
"""

# 原有组件
from omg_agent.gui.main_window import EnhancedMainWindow, run_app

# 新增现代 UI 组件
from omg_agent.gui.modern_window import (
    ModernMainWindow,
    run_gui,
)

__all__ = [
    # 原有组件
    "EnhancedMainWindow",
    "run_app",
    # 新增现代 UI 组件
    "ModernMainWindow",
    "run_gui",
]
