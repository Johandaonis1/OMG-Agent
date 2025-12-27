"""
主题定义模块

提供深色和浅色主题的颜色定义
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal

ThemeName = Literal["dark", "light"]


@dataclass
class ThemeColors:
    """主题颜色定义"""
    
    # 背景色
    main_bg: str
    panel_bg: str
    input_bg: str
    
    # 边框和分隔线
    border: str
    
    # 文字颜色
    text: str
    text_secondary: str
    
    # 强调色
    accent: str
    success: str
    danger: str
    warning: str
    
    # 按钮颜色
    button_bg: str
    button_hover: str


# 主题定义
THEMES: Dict[ThemeName, ThemeColors] = {
    # === Premium Themes ===
    "nebula": ThemeColors(
        main_bg="#0F172A",      # Slate 900 (Deep Blue/Black)
        panel_bg="#1E293B",     # Slate 800
        input_bg="#0F172A",
        border="#334155",       # Slate 700
        text="#F1F5F9",         # Slate 100
        text_secondary="#94A3B8", # Slate 400
        accent="#818CF8",       # Indigo 400
        success="#34D399",      # Emerald 400
        danger="#F87171",       # Red 400
        warning="#FBBF24",      # Amber 400
        button_bg="#334155",
        button_hover="#475569",
    ),
    "ceramic": ThemeColors(
        main_bg="#FAFAFA",      # Zinc 50
        panel_bg="#FFFFFF",     # White
        input_bg="#F4F4F5",     # Zinc 100
        border="#E4E4E7",       # Zinc 200
        text="#18181B",         # Zinc 900
        text_secondary="#71717A", # Zinc 500
        accent="#2563EB",       # Blue 600
        success="#059669",      # Emerald 600
        danger="#DC2626",       # Red 600
        warning="#D97706",      # Amber 600
        button_bg="#F4F4F5",
        button_hover="#E4E4E7",
    ),
    "sunset": ThemeColors(
        main_bg="#2a1b2e",      # Deep Purple/Brown
        panel_bg="#462a42",     
        input_bg="#2a1b2e",
        border="#663e5b",
        text="#ffd6e0",
        text_secondary="#d4a3b1",
        accent="#ff7b9c",       # Pink
        success="#98c379",
        danger="#e06c75",
        warning="#e5c07b",
        button_bg="#462a42",
        button_hover="#663e5b",
    ),
    # Keep legacy for compatibility but map them to new ones if needed, or refine them
    "dark": ThemeColors(
        main_bg="#121212",
        panel_bg="#1E1E1E",
        input_bg="#252525",
        border="#333333",
        text="#E0E0E0",
        text_secondary="#A0A0A0",
        accent="#BB86FC",
        success="#03DAC6",
        danger="#CF6679",
        warning="#FFB74D",
        button_bg="#2C2C2C",
        button_hover="#3D3D3D",
    ),
    "light": ThemeColors(
        main_bg="#FFFFFF",
        panel_bg="#F3F4F6",
        input_bg="#FFFFFF",
        border="#E5E7EB",
        text="#111827",
        text_secondary="#6B7280",
        accent="#3B82F6",
        success="#10B981",
        danger="#EF4444",
        warning="#F59E0B",
        button_bg="#F3F4F6",
        button_hover="#E5E7EB",
    ),
}


def get_theme(name: ThemeName) -> ThemeColors:
    """获取主题颜色"""
    return THEMES.get(name, THEMES["dark"])


def generate_stylesheet(theme: ThemeColors) -> str:
    """生成 Qt 样式表"""
    return f"""
        QMainWindow {{
            background-color: {theme.main_bg};
        }}
        
        QGroupBox {{
            font-weight: 600;
            font-size: 13px;
            color: {theme.text};
            border: 1px solid {theme.border};
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 8px;
            background-color: {theme.panel_bg};
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 8px;
            background-color: {theme.panel_bg};
        }}
        
        QPushButton {{
            background-color: {theme.button_bg};
            color: {theme.text};
            border: 1px solid {theme.border};
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 500;
            min-height: 20px;
        }}
        
        QPushButton:hover {{
            background-color: {theme.button_hover};
            border-color: {theme.accent};
        }}
        
        QPushButton:pressed {{
            background-color: {theme.main_bg};
            border-color: {theme.accent};
        }}
        
        QPushButton:disabled {{
            background-color: {theme.main_bg};
            color: {theme.text_secondary};
            border-color: {theme.border};
        }}
        
        QPushButton#primary {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #60a5fa, stop:1 #3b82f6);
            border: none;
            border-radius: 6px;
            color: #ffffff;
            font-weight: 500;
            padding: 8px 18px;
        }}

        QPushButton#primary:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #93c5fd, stop:1 #60a5fa);
        }}

        QPushButton#primary:pressed {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #2563eb, stop:1 #1d4ed8);
        }}

        QPushButton#danger {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #9ca3af, stop:1 #6b7280);
            border: none;
            border-radius: 6px;
            color: #ffffff;
            font-weight: 500;
            padding: 8px 18px;
        }}

        QPushButton#danger:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #f87171, stop:1 #ef4444);
        }}

        QPushButton#danger:pressed {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #dc2626, stop:1 #b91c1c);
        }}

        QPushButton#primary:disabled, QPushButton#danger:disabled {{
            background: #374151;
            color: #6b7280;
        }}

        QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background-color: {theme.input_bg};
            color: {theme.text};
            border: 1px solid {theme.border};
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 13px;
            selection-background-color: {theme.accent};
        }}
        
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
            border-color: {theme.accent};
        }}
        
        QComboBox::drop-down {{
            border: none;
            width: 28px;
        }}
        
        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid {theme.text_secondary};
            margin-right: 8px;
        }}
        
        QComboBox QAbstractItemView {{
            background-color: {theme.panel_bg};
            color: {theme.text};
            selection-background-color: {theme.accent};
            border: 1px solid {theme.border};
            border-radius: 6px;
        }}
        
        QLabel {{
            color: {theme.text};
        }}
        
        QTabWidget::pane {{
            border: 1px solid {theme.border};
            border-radius: 6px;
            background-color: {theme.main_bg};
            top: -1px;
        }}
        
        QTabBar::tab {{
            background-color: transparent;
            color: {theme.text_secondary};
            padding: 8px 16px;
            border: 1px solid transparent;
            border-bottom: none;
            margin-right: 2px;
        }}
        
        QTabBar::tab:selected {{
            background-color: {theme.main_bg};
            color: {theme.text};
            border: 1px solid {theme.border};
            border-bottom: 1px solid {theme.main_bg};
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
        }}
        
        QScrollBar:vertical {{
            background-color: {theme.main_bg};
            width: 8px;
            border-radius: 4px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {theme.border};
            border-radius: 4px;
            min-height: 24px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {theme.text_secondary};
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        
        QProgressBar {{
            background-color: {theme.button_bg};
            border: none;
            border-radius: 3px;
        }}
        
        QProgressBar::chunk {{
            background-color: {theme.accent};
            border-radius: 3px;
        }}
        
        QDialog {{
            background-color: {theme.main_bg};
        }}
        
        QStatusBar {{
            background-color: {theme.panel_bg};
            color: {theme.text_secondary};
            border-top: 1px solid {theme.border};
        }}
        
        QMenuBar {{
            background-color: {theme.panel_bg};
            color: {theme.text};
            border-bottom: 1px solid {theme.border};
        }}
        
        QMenuBar::item:selected {{
            background-color: {theme.button_hover};
        }}
        
        QMenu {{
            background-color: {theme.panel_bg};
            color: {theme.text};
            border: 1px solid {theme.border};
        }}
        
        QMenu::item:selected {{
            background-color: {theme.accent};
        }}
    """
