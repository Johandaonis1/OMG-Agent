"""
OMGAgent Modern GUI - ChatGPT Style Interface

参考设计实现:
- 左侧边栏: 会话历史 (可折叠)
- 顶部菜单栏: 文件、设备、视图、帮助 (与经典版一致)
- 中间聊天区: GPT 风格消息气泡
- 底部输入区: 设备/模型选择器 + 输入框
- 右侧面板: 手机屏幕投屏区域 (可调整大小)

Author: OMGAgent Team
Version: 5.2.0
"""

from __future__ import annotations

import sys
import json
import subprocess
import threading
from datetime import datetime
from typing import Optional, List, Any, Literal
from dataclasses import dataclass, field

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QComboBox,
    QFrame, QScrollArea, QSizePolicy, QGraphicsDropShadowEffect,
    QSplitter, QFileDialog, QInputDialog, QMessageBox, QDialog,
    QProgressBar, QGroupBox, QToolButton, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal, QThread, QByteArray, QBuffer, QIODevice, QPoint, QEvent
from PyQt6.QtGui import (
    QPixmap, QColor, QFont, QAction, QIcon, QCursor, QImage, QPainter, QPainterPath, QKeySequence, QMouseEvent
)


# =============================================================================
# Theme System (主题系统)
# =============================================================================

ThemeMode = Literal["dark", "light"]

@dataclass
class ThemeColors:
    """主题配色"""
    # 背景色
    bg_main: str
    bg_sidebar: str
    bg_chat: str
    bg_input: str
    bg_bubble_agent: str
    bg_bubble_user: str
    bg_hover: str
    bg_active: str
    bg_screen: str
    bg_secondary: str
    
    # 文本色
    text_primary: str
    text_secondary: str
    text_muted: str
    text_on_accent: str
    
    # 强调色
    accent: str
    accent_hover: str
    success: str
    warning: str
    error: str
    
    # 边框色
    border: str
    border_light: str
    
    # 滚动条
    scrollbar_bg: str
    scrollbar_handle: str


# 深色主题
DARK_THEME = ThemeColors(
    bg_main="#1a1a1a",
    bg_sidebar="#141414",
    bg_chat="#1e1e1e",
    bg_input="#2a2a2a",
    bg_bubble_agent="#2d2d2d",
    bg_bubble_user="#4f46e5",
    bg_hover="#2a2a2a",
    bg_active="#3b82f6",
    bg_screen="#0d0d0d",
    bg_secondary="#252525",
    text_primary="#e5e5e5",
    text_secondary="#a3a3a3",
    text_muted="#737373",
    text_on_accent="#ffffff",
    accent="#3b82f6",
    accent_hover="#2563eb",
    success="#22c55e",
    warning="#f59e0b",
    error="#ef4444",
    border="#333333",
    border_light="#404040",
    scrollbar_bg="transparent",
    scrollbar_handle="#404040",
)

# 浅色主题
LIGHT_THEME = ThemeColors(
    bg_main="#ffffff",
    bg_sidebar="#f8f9fa",
    bg_chat="#ffffff",
    bg_input="#f1f3f5",
    bg_bubble_agent="#e9ecef",
    bg_bubble_user="#228be6",
    bg_hover="#e9ecef",
    bg_active="#228be6",
    bg_screen="#212529",
    bg_secondary="#f1f3f5",
    text_primary="#212529",
    text_secondary="#495057",
    text_muted="#868e96",
    text_on_accent="#ffffff",
    accent="#228be6",
    accent_hover="#1c7ed6",
    success="#40c057",
    warning="#fab005",
    error="#fa5252",
    border="#dee2e6",
    border_light="#ced4da",
    scrollbar_bg="#f1f3f5",
    scrollbar_handle="#ced4da",
)


def get_theme(mode: ThemeMode) -> ThemeColors:
    return LIGHT_THEME if mode == "light" else DARK_THEME


# 当前主题 (默认深色)
_current_theme: ThemeColors = DARK_THEME
_current_mode: ThemeMode = "dark"


def set_theme(mode: ThemeMode):
    global _current_theme, _current_mode
    _current_mode = mode
    _current_theme = get_theme(mode)


def theme() -> ThemeColors:
    return _current_theme


def current_mode() -> ThemeMode:
    return _current_mode


# =============================================================================
# Session Item Widget (会话项组件)
# =============================================================================

class SessionItem(QFrame):
    """侧边栏会话历史项 - 支持点击和删除"""
    
    clicked = pyqtSignal(str)
    delete_clicked = pyqtSignal(str)
    
    def __init__(self, session_id: str, title: str, status: str = "", parent=None):
        super().__init__(parent)
        self._id = session_id
        self._title = title
        self._status = status  # completed, failed, running, etc.
        self._active = False
        self._build()
        
    def _build(self):
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # Avoid text overlap on high-DPI / large-font systems.
        self.setMinimumHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(10)
        
        # 状态图标
        self._icon = QLabel(self._get_status_icon())
        self._icon.setFixedSize(28, 28)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 标题和状态
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)
        
        self._title_label = QLabel(self._title)
        self._title_label.setWordWrap(False)
        # Allow shrinking inside the fixed-width sidebar and show full title on hover.
        self._title_label.setMinimumWidth(0)
        self._title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._title_label.setToolTip(self._title)
         
        self._status_label = QLabel(self._get_status_text())
        self._status_label.setMinimumWidth(0)
        self._status_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
         
        text_col.addWidget(self._title_label)
        text_col.addWidget(self._status_label)
         
        # 删除按钮
        self._delete_btn = QPushButton("×")
        self._delete_btn.setObjectName("deleteBtn")
        self._delete_btn.setFixedSize(20, 20)
        self._delete_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self._id))
        self._delete_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        layout.addWidget(self._icon)
        layout.addLayout(text_col, stretch=1)
        layout.addWidget(self._delete_btn)
         
        self._update_style()
        QTimer.singleShot(0, self._update_elided_text)
        
    def _get_status_icon(self) -> str:
        icons = {
            "completed": "OK",
            "failed": "X",
            "aborted": "-",
            "running": "...",
        }
        return icons.get(self._status, "C")
        
    def _get_status_text(self) -> str:
        texts = {
            "completed": "Completed",
            "failed": "Failed",
            "aborted": "Aborted",
            "running": "Running",
        }
        return texts.get(self._status, "")
        
    def _update_style(self):
        t = theme()
        if self._active:
            bg = t.bg_active
            hover_bg = t.bg_active
            text_color = t.text_on_accent
            status_color = "rgba(255,255,255,0.7)"
            icon_bg = "rgba(255,255,255,0.2)"
            icon_color = t.text_on_accent
            delete_color = "rgba(255,255,255,0.6)"
        else:
            bg = "transparent"
            hover_bg = t.bg_hover
            text_color = t.text_primary
            status_color = t.text_muted
            icon_bg = t.bg_input
            icon_color = self._get_icon_color()
            delete_color = t.text_muted
        
        self.setStyleSheet(f"""
            SessionItem {{
                background-color: {bg};
                border-radius: 10px;
            }}
            SessionItem:hover {{
                background-color: {hover_bg};
            }}
            SessionItem QPushButton#deleteBtn {{
                background-color: transparent;
                border: none;
                font-size: 14px;
                font-weight: bold;
                color: {delete_color};
            }}
            SessionItem:hover QPushButton#deleteBtn {{
                color: {delete_color};
            }}
            SessionItem QPushButton#deleteBtn:hover {{
                color: {t.error};
            }}
        """)
        self._title_label.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 500;
            color: {text_color};
        """)
        self._status_label.setStyleSheet(f"""
            font-size: 11px;
            color: {status_color};
        """)
        self._icon.setStyleSheet(f"""
            background-color: {icon_bg};
            border-radius: 14px;
            font-size: 10px;
            font-weight: bold;
            color: {icon_color};
        """)
        
    def _get_icon_color(self) -> str:
        t = theme()
        colors = {
            "completed": t.success,
            "failed": t.error,
            "aborted": t.warning,
            "running": t.accent,
        }
        return colors.get(self._status, t.accent)
        
    def set_active(self, active: bool):
        self._active = active
        self._update_style()
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._id)
        super().mousePressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        layout = self.layout()
        if layout is None:
            return
        margins = layout.contentsMargins()
        spacing = layout.spacing()
        available = (
            self.width()
            - margins.left()
            - margins.right()
            - self._icon.width()
            - self._delete_btn.width()
            - (2 * spacing)
        )
        if available < 0:
            available = 0
        fm = self._title_label.fontMetrics()
        self._title_label.setText(fm.elidedText(self._title, Qt.TextElideMode.ElideRight, available))
        
    def refresh_theme(self):
        self._update_style()


# =============================================================================
# Chat Message Components (聊天消息组件)
# =============================================================================

class AgentMessage(QFrame):
    """Agent 消息 - Enhanced Style"""
    
    def __init__(self, content: str, thinking: str = "", action: str = "", msg_type: str = "normal", parent=None):
        super().__init__(parent)
        self._content = content
        self._thinking = thinking
        self._action = action
        self._msg_type = msg_type
        self._thinking_expanded = False
        self._build()
        
    def _build(self):
        t = theme()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        # 头像 (Bot)
        avatar = QLabel("AI")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(f"""
            background-color: {t.accent};
            border-radius: 8px;
            font-size: 13px;
            font-weight: bold;
            color: {t.text_on_accent};
        """)
        
        # 内容列
        content_col = QVBoxLayout()
        content_col.setSpacing(8)
        
        # 思考过程 (如果存在)
        if self._thinking:
            thinking_container = QFrame()
            thinking_layout = QVBoxLayout(thinking_container)
            thinking_layout.setContentsMargins(0, 0, 0, 0)
            thinking_layout.setSpacing(4)
            
            # 切换按钮
            from omg_agent.core.i18n import I18n
            s = I18n.get_strings()
            self._toggle_btn = QPushButton(f"▶ 💭 {s.thinking_process}")
            self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {t.text_muted};
                    border: none;
                    font-size: 12px;
                    text-align: left;
                    font-style: italic;
                    padding: 4px 8px;
                    background-color: {t.bg_input};
                    border-radius: 12px;
                }}
                QPushButton:hover {{
                    color: {t.text_primary};
                    background-color: {t.bg_hover};
                }}
            """)
            self._toggle_btn.clicked.connect(self._toggle_thinking)
            
            # 思考内容区域
            self._thinking_frame = QFrame()
            self._thinking_frame.setStyleSheet(f"""
                background-color: {t.bg_input};
                border-left: 3px solid {t.border};
                border-radius: 4px;
                margin-top: 4px;
            """)
            thinking_text_layout = QVBoxLayout(self._thinking_frame)
            thinking_text_layout.setContentsMargins(12, 12, 12, 12)
            
            thinking_label = QLabel(self._format_text(self._thinking, is_thinking=True))
            thinking_label.setWordWrap(True)
            thinking_label.setTextFormat(Qt.TextFormat.RichText)
            thinking_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            thinking_label.setStyleSheet(f"""
                font-size: 12px;
                color: {t.text_secondary};
                font-family: 'Cascadia Code', 'Consolas', monospace;
                line-height: 1.4;
            """)
            thinking_text_layout.addWidget(thinking_label)
            
            self._thinking_frame.hide()
            
            thinking_layout.addWidget(self._toggle_btn, alignment=Qt.AlignmentFlag.AlignLeft)
            thinking_layout.addWidget(self._thinking_frame)
            content_col.addWidget(thinking_container)
        
        # 执行动作状态条
        if self._action:
            import json
            action_text = self._action
            # 尝试美化 JSON 显示
            try:
                if self._action.strip().startswith("{"):
                    data = json.loads(self._action)
                    # 提取关键信息
                    action_type = data.get("action_type", data.get("action", "ACTION"))
                    params = {k: v for k, v in data.items() if k not in ["action_type", "action"]}
                    param_str = ", ".join([f"{k}={v}" for k, v in params.items()])
                    action_text = f"▶ {action_type} <span style='color:{t.text_muted}'>({param_str})</span>"
                else:
                    action_text = f"▶ {self._action}"
            except:
                pass

            action_bar = QLabel(action_text)
            action_bar.setTextFormat(Qt.TextFormat.RichText)
            action_bar.setWordWrap(True)
            action_bar.setStyleSheet(f"""
                background-color: {t.bg_secondary};
                color: {t.accent};
                padding: 6px 12px;
                border-radius: 6px;
                font-size: 11px;
                font-weight: bold;
                border: 1px solid {t.border};
            """)
            content_col.addWidget(action_bar)

        # 主消息
        if self._content:
            msg = QLabel(self._format_text(self._content))
            msg.setWordWrap(True)
            msg.setTextFormat(Qt.TextFormat.RichText)
            msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            msg.setOpenExternalLinks(True)
            # Determine style based on msg_type
            if self._msg_type == "error":
                bg_color = "rgba(255, 60, 60, 0.15)"
                border_color = t.error
                text_color = t.error
            elif self._msg_type == "success":
                bg_color = "rgba(60, 255, 60, 0.15)"
                border_color = t.success
                text_color = t.success
            else:
                bg_color = t.bg_bubble_agent
                border_color = "transparent"
                text_color = t.text_primary

            msg.setStyleSheet(f"""
                font-size: 14px;
                color: {text_color};
                line-height: 1.5;
            """)
            # Wrap in bubble if standalone
            msg_container = QFrame()
            msg_container.setStyleSheet(f"""
                background-color: {bg_color};
                padding: 12px 16px;
                border-radius: 12px;
                border-top-left-radius: 2px;
                border: 1px solid {border_color};
            """)
            msg_layout = QVBoxLayout(msg_container)
            msg_layout.setContentsMargins(0, 0, 0, 0)
            msg_layout.addWidget(msg)
            
            content_col.addWidget(msg_container)
        
        layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(content_col, stretch=1)
        layout.addStretch()
        
    def _format_text(self, text: str, is_thinking: bool = False) -> str:
        """Simple Text Formatting (Markdown-like)"""
        import html
        import re
        
        # HTML Escape
        text = html.escape(text)
        
        if not is_thinking:
            # Bold **text**
            text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
            # Code `text`
            text = re.sub(r'`(.*?)`', r'<code style="font-family:monospace; background-color:rgba(127,127,127,0.15); padding:2px 4px; border-radius:3px;">\1</code>', text)
        
        # Convert newlines to breaks
        text = text.replace('\n', '<br>')
        return text

    def _toggle_thinking(self):
        from omg_agent.core.i18n import I18n
        s = I18n.get_strings()
        self._thinking_expanded = not self._thinking_expanded
        self._thinking_frame.setVisible(self._thinking_expanded)
        arrow = "▼" if self._thinking_expanded else "▶"
        self._toggle_btn.setText(f"{arrow} 💭 {s.thinking_process}")


class UserMessage(QFrame):
    """用户消息"""
    
    def __init__(self, content: str, parent=None):
        super().__init__(parent)
        self._content = content
        self._build()
        
    def _build(self):
        t = theme()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        # 消息气泡
        msg_container = QFrame()
        msg_container.setStyleSheet(f"""
            background-color: {t.bg_bubble_user};
            border-radius: 12px;
            border-top-right-radius: 2px;
        """)
        
        container_layout = QVBoxLayout(msg_container)
        container_layout.setContentsMargins(16, 12, 16, 12)
        
        msg = QLabel(self._format_text(self._content))
        msg.setWordWrap(True)
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        msg.setAlignment(Qt.AlignmentFlag.AlignLeft)
        msg.setStyleSheet(f"""
            font-size: 14px;
            color: {t.text_on_accent};
            border: none;
            background: transparent;
            line-height: 1.5;
        """)
        container_layout.addWidget(msg)
        
        # 头像
        avatar = QLabel("U")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(f"""
            background-color: {t.bg_secondary};
            color: {t.text_primary};
            border-radius: 16px;
            font-size: 13px;
            font-weight: bold;
        """)
        
        layout.addStretch()
        layout.addWidget(msg_container, stretch=0) # 气泡不且拉伸
        layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)

    def _format_text(self, text: str) -> str:
        """Simple Text Formatting (Markdown-like)"""
        import html
        import re
        
        # HTML Escape
        text = html.escape(text)
        
        # Bold **text**
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        # Code `text`
        text = re.sub(r'`(.*?)`', r'<code style="font-family:monospace; background-color:rgba(255,255,255,0.2); padding:2px 4px; border-radius:3px;">\1</code>', text)
        
        # Convert newlines to breaks
        text = text.replace('\n', '<br>')
        return text


# =============================================================================
# Screen Panel (投屏面板)
# =============================================================================

class ScreenPanel(QFrame):
    """投屏面板 - 支持点击/滑动/长按操作"""
    
    # 信号
    clicked = pyqtSignal(int, int)           # 单击 (x, y)
    swiped = pyqtSignal(int, int, int, int)  # 滑动 (x1, y1, x2, y2)
    long_pressed = pyqtSignal(int, int)      # 长按 (x, y)
    
    # 常量
    LONG_PRESS_DURATION = 800  # 毫秒
    SWIPE_THRESHOLD = 30       # 像素
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_frame = None
        self._screen_size = (1080, 2400)
        self._current_pixmap = None
        self._press_pos = None
        self._is_long_press = False
        self._position = "right"  # Default position
        self._build()
        self._setup_long_press_timer()
        
    def _build(self):
        t = theme()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(300)
        # Remove constrained max width to allow full resizing functionality like original GUI
        # self.setMaximumWidth(600)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # 状态栏
        status_row = QHBoxLayout()
        
        self._status_dot = QFrame()
        self._status_dot.setFixedSize(8, 8)
        
        self._status_label = QLabel("Connected")
        
        status_row.addWidget(self._status_dot)
        status_row.addWidget(self._status_label)
        status_row.addStretch()
        
        layout.addLayout(status_row)
        
        # 屏幕显示
        self._screen = QLabel()
        self._screen.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._screen.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._screen.setMinimumSize(276, 476)
        self._screen.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        
        # 占位符
        self._placeholder = QLabel("Click 'Start Cast' to begin")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        placeholder_layout = QVBoxLayout(self._screen)
        placeholder_layout.addStretch()
        placeholder_layout.addWidget(self._placeholder)
        placeholder_layout.addStretch()
        
        layout.addWidget(self._screen, stretch=1)
        
        self._apply_theme()
        
    def _setup_long_press_timer(self):
        self._long_press_timer = QTimer()
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.timeout.connect(self._on_long_press_timeout)
        
    def set_position(self, position: str):
        """Set panel position ('left' or 'right') to adjust border"""
        self._position = position
        self.refresh_theme()

    def _apply_theme(self):
        t = theme()
        border_style = f"border-left: 1px solid {t.border};" if self._position == "right" else f"border-right: 1px solid {t.border};"
        self.setStyleSheet(f"background-color: {t.bg_sidebar}; {border_style}")
        self._screen.setStyleSheet(f"""
            background-color: {t.bg_screen};
            border-radius: 8px;
        """)
        self._placeholder.setStyleSheet(f"color: {t.text_muted}; font-size: 13px;")
        self._status_dot.setStyleSheet(f"background-color: {t.success}; border-radius: 4px;")
        self._status_label.setStyleSheet(f"color: {t.success}; font-size: 12px;")
            
    def update_frame(self, data):
        try:
            if data is None:
                return
                
            pixmap = None
            if isinstance(data, QPixmap):
                pixmap = data
            elif isinstance(data, bytes):
                img = QImage.fromData(data)
                if not img.isNull():
                    pixmap = QPixmap.fromImage(img)
            elif isinstance(data, QImage):
                pixmap = QPixmap.fromImage(data)
                
            if pixmap and not pixmap.isNull():
                self._current_frame = data
                self._screen_size = (pixmap.width(), pixmap.height())
                scaled = pixmap.scaled(
                    self._screen.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self._current_pixmap = scaled
                self._screen.setPixmap(scaled)
                self._placeholder.hide()
        except Exception as e:
            print(f"Update frame error: {e}")
            
    def set_status(self, connected: bool, text: str = ""):
        t = theme()
        color = t.success if connected else t.text_muted
        self._status_dot.setStyleSheet(f"background-color: {color}; border-radius: 4px;")
        self._status_label.setText(text or ("Connected" if connected else "Disconnected"))
        self._status_label.setStyleSheet(f"color: {color}; font-size: 12px;")
        
    def show_placeholder(self):
        self._screen.clear()
        self._current_pixmap = None
        self._placeholder.show()
        
    def set_screen_size(self, width: int, height: int):
        self._screen_size = (width, height)
        
    def get_screen_size(self):
        return self._screen_size
        
    def refresh_theme(self):
        self._apply_theme()
        
    # === 触摸事件处理 ===
    
    def _to_screen_coords(self, pos: QPoint):
        """将组件坐标转换为手机屏幕坐标"""
        if not self._current_pixmap:
            return None
            
        # 计算屏幕区域的位置
        screen_rect = self._screen.geometry()
        pixmap_rect = self._current_pixmap.rect()
        
        # 计算图像在 screen 中的居中偏移
        x_offset = (screen_rect.width() - pixmap_rect.width()) // 2
        y_offset = (screen_rect.height() - pixmap_rect.height()) // 2
        
        # 转换为相对于 _screen 的坐标
        local_pos = self._screen.mapFromParent(pos)
        click_x = local_pos.x() - x_offset
        click_y = local_pos.y() - y_offset
        
        # 检查是否在图片范围内
        if 0 <= click_x <= pixmap_rect.width() and 0 <= click_y <= pixmap_rect.height():
            real_x = int(click_x * self._screen_size[0] / pixmap_rect.width())
            real_y = int(click_y * self._screen_size[1] / pixmap_rect.height())
            return (real_x, real_y)
        return None
        
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.pos()
            self._is_long_press = False
            self._long_press_timer.start(self.LONG_PRESS_DURATION)
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event: QMouseEvent):
        self._long_press_timer.stop()
        
        if event.button() == Qt.MouseButton.LeftButton and self._press_pos:
            release_pos = event.pos()
            dx = abs(release_pos.x() - self._press_pos.x())
            dy = abs(release_pos.y() - self._press_pos.y())
            
            if self._is_long_press:
                pass  # 已处理
            elif dx > self.SWIPE_THRESHOLD or dy > self.SWIPE_THRESHOLD:
                # 滑动
                start = self._to_screen_coords(self._press_pos)
                end = self._to_screen_coords(release_pos)
                if start and end:
                    self.swiped.emit(start[0], start[1], end[0], end[1])
            else:
                # 点击
                coords = self._to_screen_coords(release_pos)
                if coords:
                    self.clicked.emit(coords[0], coords[1])
                    
            self._press_pos = None
        super().mouseReleaseEvent(event)
        
    def _on_long_press_timeout(self):
        if self._press_pos:
            self._is_long_press = True
            coords = self._to_screen_coords(self._press_pos)
            if coords:
                self.long_pressed.emit(coords[0], coords[1])


# =============================================================================
# Collapsible Sidebar (可折叠侧边栏)
# =============================================================================

class CollapsibleSidebar(QFrame):
    """可折叠侧边栏"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = True
        self._sessions: List[dict] = []
        self._position = "left"  # Default position
        self._build()
        
    def _build(self):
        t = theme()
        self.setFixedWidth(220)
        
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)
        
        # 内容区
        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(12, 14, 12, 14)
        content_layout.setSpacing(8)
        
        # 标题行
        title_row = QHBoxLayout()
        self._title = QLabel("OMGAgent")
        self._title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {t.text_primary};")
        
        self._collapse_btn = QPushButton("<")
        self._collapse_btn.setFixedSize(24, 24)
        self._collapse_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._collapse_btn.clicked.connect(self.toggle)
        self._collapse_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.text_secondary};
                border: none;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {t.text_primary};
            }}
        """)
        
        title_row.addWidget(self._title)
        title_row.addStretch()
        title_row.addWidget(self._collapse_btn)
        content_layout.addLayout(title_row)
        
        content_layout.addSpacing(12)
        
        # 新建会话按钮
        from omg_agent.core.i18n import I18n
        s = I18n.get_strings()
        self._new_btn = QPushButton(f"+ {s.new_session}")
        self._new_btn.setFixedHeight(36)
        self._new_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._new_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.text_primary};
                border: 1px dashed {t.border};
                border-radius: 8px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {t.bg_hover};
                border-style: solid;
            }}
        """)
        content_layout.addWidget(self._new_btn)
        
        content_layout.addSpacing(14)
        
        # 会话列表（可滚动）
        self._session_scroll = QScrollArea()
        self._session_scroll.setWidgetResizable(True)
        self._session_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._session_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._session_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._session_list_widget = QWidget()
        self._session_list_widget.setStyleSheet("background: transparent;")
        self._session_list_widget.setMinimumWidth(0)
        self._session_list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self._session_container = QVBoxLayout(self._session_list_widget)
        # Keep a small right padding so the last column (delete) never gets clipped.
        self._session_container.setContentsMargins(0, 0, 8, 0)
        self._session_container.setSpacing(6)
        self._session_container.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._session_scroll.setWidget(self._session_list_widget)
        content_layout.addWidget(self._session_scroll, stretch=1)
        self._session_scroll.viewport().installEventFilter(self)
        QTimer.singleShot(0, self._sync_session_list_width)
        
        self._main_layout.addWidget(self._content)
        
        # 折叠状态的展开按钮
        self._expand_btn = QPushButton(">")
        self._expand_btn.setFixedSize(32, 32)
        self._expand_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._expand_btn.clicked.connect(self.toggle)
        self._expand_btn.hide()
        
        self._apply_theme()
        
    def set_position(self, position: str):
        """Set sidebar position ('left' or 'right')"""
        self._position = position
        # Update collapse button arrow if needed? 
        # When expanded, button is "<". If on Right, to collapse rightward it should be ">"?
        # Actually standard: Collapses into a thin strip.
        # If Right: Width 220 -> 40. Content hides. Button < becomes >?
        # Let's keep valid arrows simple.
        # If Left: Collapse (<) makes it small. Expand (>) makes it big.
        # If Right: Collapse (>) makes it small? 
        # Let's just update border for now.
        if self._expanded:
             self._collapse_btn.setText(">" if self._position == "right" else "<")
        else:
             self._expand_btn.setText("<" if self._position == "right" else ">")
        
        self.refresh_theme()

    def _apply_theme(self):
        t = theme()
        border_style = f"border-right: 1px solid {t.border};" if self._position == "left" else f"border-left: 1px solid {t.border};"
        self.setStyleSheet(f"background-color: {t.bg_sidebar}; {border_style}")
        self._title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {t.text_primary};")
        self._collapse_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.text_secondary};
                border: none;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {t.text_primary};
            }}
        """)
        self._new_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.text_primary};
                border: 1px dashed {t.border};
                border-radius: 8px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {t.bg_hover};
                border-style: solid;
            }}
        """)
        self._expand_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.bg_sidebar};
                color: {t.text_secondary};
                border: 1px solid {t.border};
                border-radius: 4px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {t.bg_hover};
                color: {t.text_primary};
            }}
        """)

    def toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.setFixedWidth(220)
            self._content.show()
            self._expand_btn.hide()
            # Update arrow
            arrow = ">" if self._position == "right" else "<"
            self._collapse_btn.setText(arrow)
        else:
            self.setFixedWidth(40)
            self._content.hide()
            self._expand_btn.show()
            # Update arrow
            arrow = "<" if self._position == "right" else ">"
            self._expand_btn.setText(arrow)
            # 显示展开按钮在中心
            self._main_layout.addWidget(self._expand_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _sync_session_list_width(self) -> None:
        if not hasattr(self, "_session_scroll") or not hasattr(self, "_session_list_widget"):
            return
        viewport_w = self._session_scroll.viewport().width()
        # Force the list widget to follow the viewport width, preventing horizontal overflow.
        self._session_list_widget.setFixedWidth(max(0, viewport_w))
        for s in self._sessions:
            widget = s.get("widget")
            if widget is not None and hasattr(widget, "_update_elided_text"):
                widget._update_elided_text()

    def eventFilter(self, obj, event):
        if hasattr(self, "_session_scroll") and obj is self._session_scroll.viewport():
            if event.type() == QEvent.Type.Resize:
                self._sync_session_list_width()
        return super().eventFilter(obj, event)
        
    def toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.setFixedWidth(220)
            self._content.show()
            self._expand_btn.hide()
            self._collapse_btn.setText("<")
        else:
            self.setFixedWidth(40)
            self._content.hide()
            self._expand_btn.show()
            # 显示展开按钮在中心
            self._main_layout.addWidget(self._expand_btn, alignment=Qt.AlignmentFlag.AlignCenter)
            
    def add_session(self, session_id: str, title: str, status: str, on_click, on_delete):
        item = SessionItem(session_id, title, status)
        item.clicked.connect(on_click)
        item.delete_clicked.connect(on_delete)
        # 插入到顶部（最新的会话在上面）
        self._session_container.insertWidget(0, item)
        self._sessions.insert(0, {"id": session_id, "title": title, "status": status, "widget": item})
        # Ensure the newest session stays visible.
        QTimer.singleShot(0, lambda: self._session_scroll.verticalScrollBar().setValue(0))
        return item
        
    def remove_session(self, session_id: str):
        for i, s in enumerate(self._sessions):
            if s["id"] == session_id:
                widget = s["widget"]
                self._session_container.removeWidget(widget)
                widget.deleteLater()
                self._sessions.pop(i)
                break
        
    def select_session(self, session_id: str):
        self.clear_active()
        for s in self._sessions:
            if s["id"] == session_id:
                s["widget"].set_active(True)
                break
        
    def get_sessions(self):
        return self._sessions
        
    def clear_active(self):
        for s in self._sessions:
            s["widget"].set_active(False)
            
    def clear_all(self):
        for s in self._sessions:
            self._session_container.removeWidget(s["widget"])
            s["widget"].deleteLater()
        self._sessions.clear()
            
    def refresh_theme(self):
        self._apply_theme()
        for s in self._sessions:
            s["widget"].refresh_theme()


# =============================================================================
# Main Window (主窗口)
# =============================================================================

class ModernMainWindow(QMainWindow):
    """OMGAgent 主窗口 - ChatGPT 风格界面"""
    
    switch_to_classic = pyqtSignal()
    
    def __init__(self, theme_mode: ThemeMode = "dark"):
        super().__init__()
        
        # 设置主题
        set_theme(theme_mode)
        self._theme_mode = theme_mode
        self._layout_mode = "standard"  # standard: Sidebar Left, Screen Right
        
        # 状态
        self._current_session = None
        self._agent_thread = None
        self._screen_thread = None
        self._is_casting = False
        self._is_running = False
        self._is_paused = False
        self._current_device = None
        
        # 加载配置
        from omg_agent.core.config import load_config
        from omg_agent.core.i18n import I18n
        self._config = load_config()
        
        # 模型配置
        current_model = self._config.model
        self._model_config = {
            "profile_name": self._config.current_profile,
            "api_url": current_model.base_url,
            "api_key": current_model.api_key,
            "model_name": current_model.model_name,
            "agent_type": current_model.agent_type,
            "max_steps": current_model.max_steps,
            "temperature": current_model.temperature,
            "top_p": current_model.top_p,
            "max_tokens": current_model.max_tokens,
            "frequency_penalty": current_model.frequency_penalty,
            "step_delay": current_model.step_delay,
            "coordinate_max": current_model.coordinate_max,
            "auto_wake": current_model.auto_wake,
            "reset_home": current_model.reset_home,
            "image_preprocess": {
                "is_resize": current_model.image_preprocess.is_resize,
                "target_size": list(current_model.image_preprocess.target_size),
                "format": current_model.image_preprocess.format,
                "quality": current_model.image_preprocess.quality,
            } if current_model.image_preprocess else None,
        }
        
        self._setup_window()
        self._create_menu()
        self._create_ui()
        self._apply_styles()
        
        # 连接投屏点击信号
        self._screen_panel.clicked.connect(self._on_screen_tap)
        self._screen_panel.swiped.connect(self._on_screen_swipe)
        self._screen_panel.long_pressed.connect(self._on_screen_long_press)
        
        self._refresh_devices()
        self._load_history()
        self._add_welcome_message()
        
    def _s(self):
        """获取当前语言字符串"""
        from omg_agent.core.i18n import I18n
        return I18n.get_strings()
        
    def _setup_window(self):
        self.setWindowTitle("OMGAgent")
        self.setMinimumSize(1200, 750)
        self.resize(1400, 850)
        
    def _create_menu(self):
        """创建菜单栏 - 与经典版一致"""
        from omg_agent.core.i18n import I18n
        s = I18n.get_strings()
        
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu(s.file)
        
        model_action = QAction(s.model_config, self)
        model_action.setShortcut(QKeySequence("Ctrl+M"))
        model_action.triggered.connect(self._show_model_config)
        file_menu.addAction(model_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction(s.exit, self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 设备菜单
        device_menu = menubar.addMenu(s.device)
        
        refresh_action = QAction(s.refresh_devices, self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self._refresh_devices)
        device_menu.addAction(refresh_action)
        
        wireless_action = QAction(s.wireless_connect, self)
        wireless_action.triggered.connect(self._connect_wifi)
        device_menu.addAction(wireless_action)
        
        disconnect_action = QAction(s.disconnect_all, self)
        disconnect_action.triggered.connect(self._disconnect_all)
        device_menu.addAction(disconnect_action)
        
        # 视图菜单
        view_menu = menubar.addMenu(s.view)
        
        classic_action = QAction(s.switch_to_classic_ui, self)
        classic_action.triggered.connect(self.switch_to_classic.emit)
        view_menu.addAction(classic_action)
        
        layout_action = QAction(s.switch_layout_direction, self)
        layout_action.setShortcut(QKeySequence("Ctrl+L"))
        layout_action.triggered.connect(self._toggle_layout)
        view_menu.addAction(layout_action)
        
        view_menu.addSeparator()
        
        # 主题子菜单
        theme_menu = view_menu.addMenu(s.theme)
        
        self._dark_action = QAction(s.dark_theme, self)
        self._dark_action.setCheckable(True)
        self._dark_action.setChecked(self._theme_mode == "dark")
        self._dark_action.triggered.connect(lambda: self._set_theme("dark"))
        theme_menu.addAction(self._dark_action)
        
        self._light_action = QAction(s.light_theme, self)
        self._light_action.setCheckable(True)
        self._light_action.setChecked(self._theme_mode == "light")
        self._light_action.triggered.connect(lambda: self._set_theme("light"))
        theme_menu.addAction(self._light_action)
        
        # 语言子菜单
        lang_menu = view_menu.addMenu(s.language)
        
        zh_action = QAction("中文", self)
        zh_action.setCheckable(True)
        zh_action.triggered.connect(lambda: self._set_language("zh"))
        lang_menu.addAction(zh_action)
        
        en_action = QAction("English", self)
        en_action.setCheckable(True)
        en_action.triggered.connect(lambda: self._set_language("en"))
        lang_menu.addAction(en_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu(s.help)
        
        about_action = QAction(s.about, self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        
    def _create_ui(self):
        """创建主 UI"""
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 左侧边栏 (可折叠)
        self._sidebar = CollapsibleSidebar()
        self._sidebar._new_btn.clicked.connect(self._new_session)
        layout.addWidget(self._sidebar)
        
        # 中间和右侧使用 Splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(3)
        self._splitter.setChildrenCollapsible(False)
        
        # 中间聊天区
        self._center = self._create_center()
        self._splitter.addWidget(self._center)
        
        # 右侧投屏
        self._screen_panel = ScreenPanel()
        self._splitter.addWidget(self._screen_panel)
        
        # 设置初始比例
        self._splitter.setSizes([460, 720])
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 2)
        
        layout.addWidget(self._splitter, stretch=1)
        
    def _toggle_layout(self):
        """Toggle layout direction (Standard vs Inverted)"""
        # Save current splitter sizes to try restore proportion
        sizes = self._splitter.sizes()
        total_width = sum(sizes) if sizes else 1000
        
        # Determine new mode
        self._layout_mode = "inverted" if self._layout_mode == "standard" else "standard"
        
        # Get main layout (HBox)
        central = self.centralWidget()
        main_layout = central.layout()
        
        # Detach widgets (setParent(None) removes them from layout)
        # Note: We must be careful not to delete them. setParent(None) removes from layout but keeps python ref if we have it in self.
        
        # Remove from Splitter first
        # Chat and Screen are in Splitter
        self._center.setParent(None)
        self._screen_panel.setParent(None)
        
        # Remove Splitter and Sidebar from Main Layout
        self._splitter.setParent(None)
        self._sidebar.setParent(None)
        
        # Rebuild based on mode
        if self._layout_mode == "standard":
            # Left: Sidebar | Middle: Chat | Right: Screen
            # Main: [Sidebar, Splitter]
            # Splitter: [Chat, Screen]
            
            # 1. Update positions/styles
            self._sidebar.set_position("left")
            self._screen_panel.set_position("right")
            
            # 2. Add to Main Layout
            main_layout.addWidget(self._sidebar)
            main_layout.addWidget(self._splitter)
            
            # 3. Add to Splitter
            self._splitter.addWidget(self._center)
            self._splitter.addWidget(self._screen_panel)
            
            # 4. Restore Splitter Sizes
            # Standard: Chat (0), Screen (1)
            # If coming from Inverted: Screen (0), Chat (1)
            # We want to swap the sizes if switching modes to keep relative sizes natural?
            # Or just set default/proportional.
            # Let's set proportional based on previous total.
            # Standard: Chat ~460, Screen ~720 (Ratio 1:1.5)
            self._splitter.setSizes([460, 720])
            self._splitter.setStretchFactor(0, 1) # Chat
            self._splitter.setStretchFactor(1, 2) # Screen
            
        else:
            # Left: Screen | Middle: Chat | Right: Sidebar
            # Main: [Splitter, Sidebar]
            # Splitter: [Screen, Chat]
            
            # 1. Update positions/styles
            self._sidebar.set_position("right")
            self._screen_panel.set_position("left")
            
            # 2. Add to Main Layout
            main_layout.addWidget(self._splitter)
            main_layout.addWidget(self._sidebar)
            
            # 3. Add to Splitter
            self._splitter.addWidget(self._screen_panel)
            self._splitter.addWidget(self._center)
            
            # 4. Restore Splitter Sizes
            # Inverted: Screen (0), Chat (1)
            self._splitter.setSizes([720, 460])
            self._splitter.setStretchFactor(0, 2) # Screen
            self._splitter.setStretchFactor(1, 1) # Chat
            
        # Refresh theme to ensure borders are correct
        self._sidebar.refresh_theme()
        self._screen_panel.refresh_theme()
    def _create_center(self) -> QFrame:
        t = theme()
        center = QFrame()
        
        layout = QVBoxLayout(center)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 聊天滚动区
        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self._chat_container = QWidget()
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setContentsMargins(0, 20, 0, 20)
        self._chat_layout.setSpacing(0)
        self._chat_layout.addStretch()
        
        self._chat_scroll.setWidget(self._chat_container)
        layout.addWidget(self._chat_scroll, stretch=1)
        
        # 输入区
        input_area = self._create_input_area()
        layout.addWidget(input_area)
        
        return center
        
    def _create_input_area(self) -> QFrame:
        t = theme()
        s = self._s()
        area = QFrame()
        area.setFixedHeight(130)
        
        layout = QVBoxLayout(area)
        layout.setContentsMargins(20, 0, 20, 16)
        layout.setSpacing(8)
        
        # 第一行：设备 + 模型 + Agent + 投屏按钮
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        
        self._device_label = QLabel(s.device + ":")
        self._device_combo = QComboBox()
        self._device_combo.setMinimumWidth(60)
        self._device_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._device_combo.currentTextChanged.connect(self._on_device_change)
        
        self._model_label = QLabel(s.model_name.replace(":", "") + ":")
        self._model_combo = QComboBox()
        self._model_combo.setMinimumWidth(60)
        self._model_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for name in self._config.get_profile_names():
            self._model_combo.addItem(name)
        self._model_combo.setCurrentText(self._config.current_profile)
        self._model_combo.currentTextChanged.connect(self._on_model_change)
        
        self._agent_label = QLabel("Agent:")
        self._agent_combo = QComboBox()
        self._agent_combo.setMinimumWidth(60)
        self._agent_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Agent 类型
        # 动态 populate Agent 类型
        from omg_agent.core.config import AGENT_TYPE_INFO
        for agent_id, info in AGENT_TYPE_INFO.items():
            # 使用图标+名称
            label = f"{info.get('icon', '')} {info['name']}"
            self._agent_combo.addItem(label, agent_id)
        # 根据当前配置设置
        agent_type = self._model_config.get("agent_type", "universal")
        for i in range(self._agent_combo.count()):
            if self._agent_combo.itemData(i) == agent_type:
                self._agent_combo.setCurrentIndex(i)
                break
        self._agent_combo.currentIndexChanged.connect(self._on_agent_change)
        
        # 暂停按钮
        self._pause_btn = QPushButton(s.pause)
        self._pause_btn.setMinimumWidth(60)
        self._pause_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._pause_btn.clicked.connect(self._toggle_pause)
        self._pause_btn.setEnabled(False)
        
        row1.addWidget(self._device_label)
        row1.addWidget(self._device_combo)
        row1.addWidget(self._model_label)
        row1.addWidget(self._model_combo)
        row1.addWidget(self._agent_label)
        row1.addWidget(self._agent_combo)
        row1.addWidget(self._pause_btn)
        row1.addStretch()
        
        self._cast_btn = QPushButton(s.start_screen)
        self._cast_btn.setMinimumWidth(70)
        self._cast_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._cast_btn.clicked.connect(self._toggle_cast)
        row1.addWidget(self._cast_btn)
        
        layout.addLayout(row1)
        
        # 第二行：输入框 + 发送/停止按钮
        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        
        self._input_frame = QFrame()
        input_layout = QHBoxLayout(self._input_frame)
        input_layout.setContentsMargins(14, 0, 8, 0)
        
        self._input = QLineEdit()
        self._input.setPlaceholderText(s.input_task)
        self._input.setFixedHeight(44)
        self._input.returnPressed.connect(self._on_send_or_stop)
        
        self._send_btn = QPushButton(s.execute)
        self._send_btn.setFixedSize(70, 36)
        self._send_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._send_btn.clicked.connect(self._on_send_or_stop)
        
        input_layout.addWidget(self._input)
        input_layout.addWidget(self._send_btn)
        
        input_row.addWidget(self._input_frame)
        layout.addLayout(input_row)
        
        return area
        
    def _apply_styles(self):
        t = theme()
        
        splitter_handle = t.border if current_mode() == "dark" else t.border_light
        
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {t.bg_main};
            }}
            
            QMenuBar {{
                background-color: {t.bg_sidebar};
                color: {t.text_primary};
                border-bottom: 1px solid {t.border};
                padding: 4px 8px;
            }}
            QMenuBar::item {{
                padding: 6px 12px;
                border-radius: 4px;
            }}
            QMenuBar::item:selected {{
                background-color: {t.bg_hover};
            }}
            
            QMenu {{
                background-color: {t.bg_main};
                border: 1px solid {t.border};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 20px;
                color: {t.text_primary};
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {t.bg_hover};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {t.border};
                margin: 4px 8px;
            }}
            
            QComboBox {{
                background-color: {t.bg_input};
                color: {t.text_primary};
                border: 1px solid {t.border};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
            }}
            QComboBox:hover {{
                border-color: {t.accent};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 18px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {t.bg_main};
                border: 1px solid {t.border};
                selection-background-color: {t.bg_hover};
                color: {t.text_primary};
            }}
            
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: {t.scrollbar_bg};
                width: 8px;
            }}
            QScrollBar::handle:vertical {{
                background: {t.scrollbar_handle};
                border-radius: 4px;
                min-height: 40px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            
            QSplitter::handle {{
                background-color: {splitter_handle};
            }}
            QSplitter::handle:hover {{
                background-color: {t.accent};
            }}
            
            QLabel {{
                color: {t.text_secondary};
                font-size: 12px;
            }}
        """)
        
        # 中间区域
        self._center.setStyleSheet(f"background-color: {t.bg_chat};")
        
        # 输入框样式
        self._input_frame.setStyleSheet(f"""
            background-color: {t.bg_input};
            border: 1px solid {t.border};
            border-radius: 10px;
        """)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                color: {t.text_primary};
                font-size: 14px;
            }}
            QLineEdit::placeholder {{
                color: {t.text_muted};
            }}
        """)
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.accent};
                color: {t.text_on_accent};
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {t.accent_hover};
            }}
        """)
        self._cast_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.accent};
                color: {t.text_on_accent};
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {t.accent_hover};
            }}
        """)
        
        # 暂停按钮样式
        self._pause_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.bg_input};
                color: {t.text_primary};
                border: 1px solid {t.border};
                border-radius: 6px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {t.bg_hover};
            }}
            QPushButton:disabled {{
                color: {t.text_muted};
                background-color: {t.bg_input};
            }}
        """)
        
    def _apply_send_btn_style(self, stop_mode: bool = False):
        """应用发送按钮样式"""
        t = theme()
        if stop_mode:
            self._send_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t.error};
                    color: {t.text_on_accent};
                    border: none;
                    border-radius: 6px;
                    font-size: 13px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: #dc2626;
                }}
            """)
        else:
            self._send_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t.accent};
                    color: {t.text_on_accent};
                    border: none;
                    border-radius: 6px;
                    font-size: 13px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: {t.accent_hover};
                }}
            """)
        
    def _set_theme(self, mode: ThemeMode):
        if mode == self._theme_mode:
            return
            
        self._theme_mode = mode
        set_theme(mode)
        
        self._dark_action.setChecked(mode == "dark")
        self._light_action.setChecked(mode == "light")
        
        self._apply_styles()
        self._sidebar.refresh_theme()
        self._screen_panel.refresh_theme()
        
    def _set_language(self, lang: str):
        from omg_agent.core.i18n import I18n
        I18n.set_language(lang)
        # 重建菜单
        self.menuBar().clear()
        self._create_menu()
        # 更新输入区域文本
        self._update_ui_text()
        
    def _update_ui_text(self):
        """更新 UI 文本"""
        s = self._s()
        self._device_label.setText(s.device + ":")
        self._model_label.setText(s.model_name.replace(":", "") + ":")
        self._input.setPlaceholderText(s.input_task)
        if not self._is_running:
            self._send_btn.setText(s.execute)
            self._pause_btn.setText(s.pause)
        else:
            self._send_btn.setText(s.stop)
            self._pause_btn.setText(s.pause if not self._is_paused else s.resume)
        if not self._is_casting:
            self._cast_btn.setText(s.start_screen)
        else:
            self._cast_btn.setText(s.stop)
        # 更新侧边栏按钮
        self._sidebar._new_btn.setText(f"+ {s.new_session}")
        
    # === 会话管理 ===
    
    def _add_welcome_message(self):
        s = self._s()
        welcome = AgentMessage(s.ready + " - " + s.input_task)
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, welcome)
        
    def _load_history(self):
        """加载历史记录"""
        try:
            from omg_agent.core.task_history import get_history_manager
            history_mgr = get_history_manager()
            tasks = history_mgr.list_tasks(limit=30)
            
            for task in tasks:
                # Keep full title; SessionItem will elide visually and show full text in tooltip.
                title = task.task_name
                self._sidebar.add_session(
                    task.task_id, 
                    title, 
                    task.status,
                    self._on_session_clicked,
                    self._on_session_delete
                )
        except Exception as e:
            print(f"Load history error: {e}")
            
    def _on_session_clicked(self, session_id: str):
        self._sidebar.select_session(session_id)
        self._current_session = session_id
        self._load_session_detail(session_id)
        
    def _on_session_delete(self, session_id: str):
        """删除会话"""
        s = self._s()
        reply = QMessageBox.question(
            self, 
            s.confirm_clear,
            f"Delete this session?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from omg_agent.core.task_history import get_history_manager
                history_mgr = get_history_manager()
                history_mgr.delete_task(session_id)
                self._sidebar.remove_session(session_id)
                
                # 如果删除的是当前会话，清空聊天区
                if self._current_session == session_id:
                    self._current_session = None
                    self._new_session()
            except Exception as e:
                print(f"Delete session error: {e}")
        
    def _load_session_detail(self, session_id: str):
        """加载会话详情 - 完整显示历史记录"""
        try:
            from omg_agent.core.task_history import get_history_manager
            history_mgr = get_history_manager()
            task = history_mgr.load_task(session_id)
            
            # 清空当前聊天
            while self._chat_layout.count() > 1:
                item = self._chat_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            if not task:
                self._chat_layout.insertWidget(
                    self._chat_layout.count() - 1,
                    AgentMessage("No history found for this session.", msg_type="error"),
                )
                self._scroll_to_bottom()
                return

            # 添加任务内容
            self._chat_layout.insertWidget(
                self._chat_layout.count() - 1,
                UserMessage(task.task_name),
            )

            # 任务元信息
            start_time = task.get_display_time()
            meta_lines = [f"Task started at {start_time}"]
            if task.device_id:
                meta_lines.append(f"Device: {task.device_id}")
            self._chat_layout.insertWidget(
                self._chat_layout.count() - 1,
                AgentMessage("\n".join(meta_lines)),
            )

            # 添加每个步骤（task_history 存的是 dict）
            steps = task.steps or []
            if not steps:
                self._chat_layout.insertWidget(
                    self._chat_layout.count() - 1,
                    AgentMessage("No steps recorded for this session."),
                )
            else:
                for step in steps:
                    step_num = step.get("step_num", "?")
                    action_type = step.get("action_type", "UNKNOWN")
                    params = step.get("action_params", {}) or {}
                    thinking = step.get("thinking", "") or ""
                    result = step.get("result", "") or ""
                    success = bool(step.get("success", True))

                    ts = step.get("timestamp", "") or ""
                    ts_disp = ""
                    if ts:
                        try:
                            ts_disp = datetime.fromisoformat(ts).strftime("%H:%M:%S")
                        except Exception:
                            ts_disp = ts

                    header = f"Step {step_num} · {action_type}"
                    if ts_disp:
                        header += f" · {ts_disp}"

                    content = header
                    if result:
                        content += f"\n{result}"

                    # AgentMessage action bar supports JSON: {"action_type": "...", ...params}
                    try:
                        action_json = json.dumps({"action_type": action_type, **params}, ensure_ascii=False)
                    except Exception:
                        action_json = str({"action_type": action_type, "params": params})

                    self._chat_layout.insertWidget(
                        self._chat_layout.count() - 1,
                        AgentMessage(
                            content,
                            thinking=thinking,
                            action=action_json,
                            msg_type="success" if success else "error",
                        ),
                    )

            # 结果汇总
            status_icon = {
                "completed": "✅",
                "failed": "❌",
                "aborted": "⏹",
                "running": "…",
            }.get(task.status, "❔")

            summary_lines = [f"{status_icon} Status: {task.status}"]
            if task.result_summary:
                summary_lines.append(f"Result: {task.result_summary}")
            if task.end_time:
                try:
                    end_disp = datetime.fromisoformat(task.end_time).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    end_disp = task.end_time
                summary_lines.append(f"Ended at {end_disp}")
            duration = task.get_duration()
            if duration:
                summary_lines.append(f"Duration: {duration}")

            self._chat_layout.insertWidget(
                self._chat_layout.count() - 1,
                AgentMessage("\n".join(summary_lines)),
            )
            self._scroll_to_bottom()
        except Exception as e:
            print(f"Load session detail error: {e}")
        
    def _new_session(self):
        while self._chat_layout.count() > 1:
            item = self._chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._add_welcome_message()
        
    # === 设备管理 ===
    
    def _refresh_devices(self):
        self._device_combo.clear()
        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            )
            lines = result.stdout.strip().split("\n")[1:]
            devices = [line.split("\t")[0] for line in lines if "\tdevice" in line]
            
            if devices:
                self._device_combo.addItems(devices)
                self._current_device = devices[0]
                self._screen_panel.set_status(True, "Connected")
            else:
                self._device_combo.addItem("No device")
                self._screen_panel.set_status(False, "No device")
        except Exception as e:
            self._device_combo.addItem("Error")
            self._screen_panel.set_status(False, "Error")
            
    def _on_device_change(self, device: str):
        if device and "No device" not in device and "Error" not in device:
            self._current_device = device
            self._screen_panel.set_status(True, "Connected")
            
    def _on_model_change(self, profile_name: str):
        profile = self._config.model_profiles.get(profile_name)
        if profile:
            self._model_config.update({
                "profile_name": profile_name,
                "api_url": profile.get("base_url"),
                "api_key": profile.get("api_key"),
                "model_name": profile.get("model_name"),
                "agent_type": profile.get("agent_type"),
            })
            # 同步 Agent 下拉框
            for i in range(self._agent_combo.count()):
                if self._agent_combo.itemData(i) == profile.get("agent_type"):
                    self._agent_combo.blockSignals(True)
                    self._agent_combo.setCurrentIndex(i)
                    self._agent_combo.blockSignals(False)
                    break
                    
    def _on_agent_change(self, index: int):
        agent_type = self._agent_combo.currentData()
        if agent_type:
            self._model_config["agent_type"] = agent_type
            
    def _toggle_pause(self):
        s = self._s()
        if not self._agent_thread or not self._is_running:
            return
            
        if self._is_paused:
            self._agent_thread.resume()
            self._is_paused = False
            self._pause_btn.setText(s.pause)
            self._add_agent_message(s.log_task_resumed)
        else:
            self._agent_thread.pause()
            self._is_paused = True
            self._pause_btn.setText(s.resume)
            self._add_agent_message(s.log_task_paused)
            
    def _connect_wifi(self):
        """显示无线连接对话框"""
        from omg_agent.gui.main_window import WirelessConnectDialog
        
        dialog = WirelessConnectDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            address = dialog.get_address()
            if address:
                self._connect_wireless_action(address)
                
    def _connect_wireless_action(self, address: str):
        """执行连接"""
        s = self._s()
        try:
            result = subprocess.run(
                ["adb", "connect", address],
                capture_output=True, text=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            )
            if "connected" in result.stdout.lower():
                QMessageBox.information(self, "Success", f"Connected to {address}")
                self._refresh_devices()
            else:
                QMessageBox.warning(self, "Failed", result.stdout or result.stderr)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            
    def _disconnect_all(self):
        try:
            subprocess.run(["adb", "disconnect"], timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            self._refresh_devices()
        except:
            pass
            
    # === 投屏 ===
    
    def _toggle_cast(self):
        if self._is_casting:
            self._stop_cast()
        else:
            self._start_cast()
            
    def _start_cast(self):
        s = self._s()
        if not self._current_device:
            QMessageBox.warning(self, s.notice, s.please_connect_device)
            return
        
        # 确保之前的线程已停止
        if self._screen_thread:
            self._screen_thread.stop()
            self._screen_thread.wait(500)
            self._screen_thread = None
            
        try:
            from omg_agent.gui.main_window import ScreenCaptureThread
            
            self._screen_thread = ScreenCaptureThread(self._current_device, fps=10)
            self._screen_thread.frame_ready.connect(self._on_frame)
            self._screen_thread.error.connect(self._on_cast_error)
            self._screen_thread.start()
            
            self._is_casting = True
            self._cast_btn.setText(s.stop)
            self._screen_panel.set_status(True, s.status_screening)
        except Exception as e:
            print(f"Start cast error: {e}")
            QMessageBox.warning(self, s.error, f"{s.log_screen_error.format(str(e))}")
        
    def _stop_cast(self):
        s = self._s()
        if self._screen_thread:
            self._screen_thread.stop()
            self._screen_thread.wait(500)
            self._screen_thread = None
            
        self._is_casting = False
        self._cast_btn.setText(s.start_screen)
        self._screen_panel.show_placeholder()
        self._screen_panel.set_status(True, s.status_screen_stopped)
        
    def _on_frame(self, data: bytes):
        try:
            self._screen_panel.update_frame(data)
        except Exception as e:
            print(f"Frame update error: {e}")
            
    def _on_cast_error(self, error: str):
        print(f"Cast error: {error}")
        self._stop_cast()
        self._screen_panel.set_status(False, "Error")
        
    # === 投屏点击操作 ===
    
    def _on_screen_tap(self, x: int, y: int):
        """处理投屏区域点击"""
        if not self._current_device:
            return
        self._adb_input("tap", str(x), str(y))
        self._add_agent_message(f"Tap at ({x}, {y})")
        
    def _on_screen_swipe(self, x1: int, y1: int, x2: int, y2: int):
        """处理投屏区域滑动"""
        if not self._current_device:
            return
        self._adb_input("swipe", str(x1), str(y1), str(x2), str(y2), "300")
        self._add_agent_message(f"Swipe from ({x1}, {y1}) to ({x2}, {y2})")
        
    def _on_screen_long_press(self, x: int, y: int):
        """处理投屏区域长按"""
        if not self._current_device:
            return
        self._adb_input("swipe", str(x), str(y), str(x), str(y), "1000")
        self._add_agent_message(f"Long press at ({x}, {y})")
        
    def _adb_input(self, *args):
        """执行 ADB input 命令"""
        try:
            cmd = ["adb"]
            if self._current_device:
                cmd.extend(["-s", self._current_device])
            cmd.extend(["shell", "input", *args])
            subprocess.run(
                cmd,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
        except Exception as e:
            print(f"ADB input error: {e}")
            
    # === 消息发送 ===
    
    def _on_send_or_stop(self):
        """发送或停止按钮的统一处理"""
        if self._is_running:
            self._stop_task()
        else:
            self._on_send()
            
    def _on_send(self):
        text = self._input.text().strip()
        if not text:
            return
            
        self._input.clear()
        
        user_msg = UserMessage(text)
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, user_msg)
        
        # 添加会话到侧边栏
        sessions = self._sidebar.get_sessions()
        display = text[:22] + "..." if len(text) > 22 else text
        self._sidebar.add_session(
            f"s_{len(sessions)}", 
            display, 
            "running",
            self._on_session_clicked,
            self._on_session_delete
        )
        self._sidebar.select_session(f"s_{len(sessions)}")
        
        self._run_task(text)
        self._scroll_to_bottom()
        
    def _stop_task(self):
        """停止当前任务"""
        s = self._s()
        if self._agent_thread and self._agent_thread.isRunning():
            self._agent_thread.stop()
            self._add_agent_message(s.log_task_stopped)
        self._reset_task_ui()
        
    def _reset_task_ui(self):
        """重置任务相关 UI"""
        s = self._s()
        self._is_running = False
        self._is_paused = False
        self._send_btn.setText(s.execute)
        self._pause_btn.setText(s.pause)
        self._pause_btn.setEnabled(False)
        self._input.setEnabled(True)
        self._apply_send_btn_style()
        
    def _run_task(self, task: str):
        from omg_agent.gui.main_window import AgentThread
        s = self._s()
        
        if not self._current_device:
            self._add_agent_message(s.please_connect_device)
            return
            
        if self._agent_thread and self._agent_thread.isRunning():
            self._agent_thread.stop()
            self._agent_thread.wait()
            
        config = {**self._model_config, "device_id": self._current_device}
        
        # 定义直连设备截屏函数，绕过 GUI 投屏流
        def get_screenshot():
            if self._agent_thread:
                 self._agent_thread.log.emit("[Vision] Capturing fresh device screenshot (Direct ADB)...")
            try:
                from omg_agent.core.agent.device import get_screenshot
                return get_screenshot(self._current_device)
            except Exception as e:
                if self._agent_thread:
                    self._agent_thread.log.emit(f"[Vision] Capture failed: {e}")
                return None

        self._agent_thread = AgentThread(task, config, get_screenshot)
        self._agent_thread.thinking.connect(self._on_thinking)
        self._agent_thread.action.connect(self._on_action)
        self._agent_thread.task_finished.connect(self._on_finished)
        self._agent_thread.error.connect(self._on_error)
        self._agent_thread.finished.connect(self._on_thread_finished)
        self._agent_thread.log.connect(self._on_log)
        self._agent_thread.user_input_requested.connect(self._on_agent_user_input_requested)
        self._agent_thread.confirmation_requested.connect(self._on_agent_confirmation_requested)
        self._agent_thread.takeover_requested.connect(self._on_agent_takeover_requested)
        self._agent_thread.start()
        
        # 更新 UI 状态
        self._is_running = True
        self._is_paused = False
        self._send_btn.setText(s.stop)
        self._pause_btn.setEnabled(True)
        self._input.setEnabled(False)
        self._apply_send_btn_style(stop_mode=True)
        
        self._add_agent_message(s.log_start_task.format(task))
        
    def _on_log(self, msg: str):
        """Handle agent logs"""
        print(f"[Agent] {msg}")

    def _on_agent_user_input_requested(self, context):
        """Handle Agent INFO request (runs on UI thread)."""
        try:
            prompt, result_container, event = context
        except Exception:
            return

        s = self._s()
        try:
            text, ok = QInputDialog.getText(self, s.notice, prompt)
            result_container["text"] = text if ok else ""
        except Exception:
            result_container["text"] = ""
        finally:
            try:
                event.set()
            except Exception:
                pass

    def _on_agent_confirmation_requested(self, context):
        """Handle sensitive operation confirmation (runs on UI thread)."""
        try:
            message, result_container, event = context
        except Exception:
            return

        s = self._s()
        try:
            reply = QMessageBox.question(
                self,
                s.notice,
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            result_container["ok"] = reply == QMessageBox.StandardButton.Yes
        except Exception:
            result_container["ok"] = False
        finally:
            try:
                event.set()
            except Exception:
                pass

    def _on_agent_takeover_requested(self, context):
        """Handle human takeover request (runs on UI thread)."""
        try:
            message, event = context
        except Exception:
            return

        s = self._s()
        try:
            QMessageBox.information(self, s.notice, message)
        except Exception:
            pass
        finally:
            try:
                event.set()
            except Exception:
                pass
        
    def _on_thread_finished(self):
        """Agent 线程完成"""
        self._reset_task_ui()
        
    def _on_thinking(self, text: str):
        display = text[:180] + "..." if len(text) > 180 else text
        self._add_agent_message(display, thinking=text)
        self._scroll_to_bottom()
        
    def _on_action(self, text: str):
        try:
            data = json.loads(text)
            action_type = data.get("action_type", "UNKNOWN")
            self._add_agent_message(f"Action: {action_type}", action=action_type)
        except:
            self._add_agent_message(f"Executing: {text[:80]}")
        self._scroll_to_bottom()
        
    def _on_finished(self, msg: str):
        s = self._s()
        self._add_agent_message(f"{s.task_done}: {msg}", msg_type="success")
        self._scroll_to_bottom()
        self._reset_task_ui()
        
    def _on_error(self, error: str):
        s = self._s()
        self._add_agent_message(f"{s.error}: {error}", msg_type="error")
        self._scroll_to_bottom()
        self._reset_task_ui()
        
    def _add_agent_message(self, content: str, thinking: str = "", action: str = "", msg_type: str = "normal"):
        msg = AgentMessage(content, thinking=thinking, action=action, msg_type=msg_type)
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, msg)
        
    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda:
            self._chat_scroll.verticalScrollBar().setValue(
                self._chat_scroll.verticalScrollBar().maximum()
            )
        )
        
    # === 其他 ===
    
    def _show_model_config(self):
        from omg_agent.gui.main_window import ModelConfigDialog
        
        dialog = ModelConfigDialog(self._model_config, self, saved_profiles=self._config.model_profiles)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._model_config = dialog.get_config()
            self._config.model_profiles = dialog.get_saved_profiles()
            self._add_agent_message("Model configuration updated")
            
    def _show_about(self):
        from omg_agent.core.i18n import I18n
        s = I18n.get_strings()
        QMessageBox.about(self, s.about, s.about_text)
        
    def closeEvent(self, event):
        if self._screen_thread:
            self._screen_thread.stop()
        if self._agent_thread:
            try:
                self._agent_thread.stop()
                self._agent_thread.wait(1000)
            except:
                pass
        event.accept()


# =============================================================================
# Entry Point
# =============================================================================

def run_gui():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = ModernMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_gui()
