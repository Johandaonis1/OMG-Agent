"""
GUI Log Adapter - GUI 日志适配器

增强 GUI 日志显示，确保与原版 AutoGLM/Gelab-Zero 一致。

功能：
1. 思考显示 - 完整显示 <THINK> 内容
2. 动作显示 - 显示格式化后的动作指令
3. 坐标显示 - 显示点击/滑动的坐标
4. 状态显示 - 显示当前步骤、成功/失败状态
5. 对齐原版输出格式
"""

import json
from datetime import datetime
from typing import Any

from .actions.space import Action, ActionType


class LogLevel:
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class GUILogger:
    """
    GUI 日志适配器 - 对标各协议的日志输出格式

    AutoGLM 输出格式（phone_agent/agent.py）:
        =================
        💭 Thinking:
        -----
        {thinking}
        -----
        🎯 Action:
        {action}

    Gelab-Zero 输出格式（copilot_agent_server/local_server.py）:
        Step {step_num}: {action_type}
        COT: {cot}
        Explain: {explain}
        Point: {x}, {y}
    """

    def __init__(
        self,
        log_callback=None,
        show_thinking: bool = True,
        show_coordinates: bool = True,
        protocol: str = "autoglm"
    ):
        """
        初始化 GUI 日志适配器

        Args:
            log_callback: 日志回调函数 (message: str, level: str) -> None
            show_thinking: 是否显示思考内容
            show_coordinates: 是否显示坐标
            protocol: 协议类型 ("autoglm", "gelab", "universal")
        """
        self.log_callback = log_callback
        self.show_thinking = show_thinking
        self.show_coordinates = show_coordinates
        self.protocol = protocol

        # 统计
        self.step_count = 0
        self.action_counts = {}

    def log_step_start(self, step_num: int, task: str | None = None) -> str:
        """记录步骤开始"""
        self.step_count = step_num
        self._log(f"\n{'=' * 50}", LogLevel.INFO)
        self._log(f"Step {step_num}", LogLevel.INFO)
        self._log(f"{'=' * 50}", LogLevel.INFO)

        if task and step_num == 1:
            self._log(f"Task: {task}", LogLevel.INFO)

        return f"Step {step_num}"

    def log_thinking(self, thinking: str) -> str:
        """记录思考内容 - 对标 AutoGLM 的 💭 Thinking 输出"""
        if not thinking:
            return ""

        display = ""
        if self.protocol == "autoglm":
            display = f"\n💭 Thinking:\n{'-' * 50}\n{thinking}\n{'-' * 50}"
        else:
            display = f"\n<THINK>{thinking}</THINK>"

        if self.show_thinking:
            self._log(display, LogLevel.DEBUG)

        return thinking

    def log_action(self, action: Action) -> str:
        """
        记录动作 - 对标 AutoGLM 的 🎯 Action 输出

        AutoGLM 格式:
            🎯 Action:
            do(action="Tap", element=[500, 800])

        Gelab-Zero 格式:
            action:CLICK	point:500,800
        """
        action_type = action.action_type
        params = action.params or {}

        # 更新统计
        self.action_counts[action_type] = self.action_counts.get(action_type, 0) + 1

        # 格式化动作输出
        if self.protocol == "autoglm":
            formatted = self._format_autoglm_action(action)
        elif self.protocol == "gelab":
            formatted = self._format_gelab_action(action)
        else:
            formatted = self._format_universal_action(action)

        # 显示
        if self.protocol == "autoglm":
            display = f"\n🎯 Action:\n{formatted}"
        else:
            display = f"\n{formatted}"

        self._log(display, LogLevel.INFO)

        return formatted

    def log_result(self, success: bool, message: str | None = None) -> str:
        """记录执行结果"""
        status = "✅ SUCCESS" if success else "❌ FAILED"
        if message:
            display = f"\n{status}: {message}"
        else:
            display = f"\n{status}"

        self._log(display, LogLevel.INFO if success else LogLevel.ERROR)

        return display

    def log_coordinates(self, x: int, y: int) -> str:
        """记录坐标"""
        if not self.show_coordinates:
            return ""

        display = f"📍 Coordinates: ({x}, {y})"
        self._log(display, LogLevel.DEBUG)

        return display

    def log_screen_info(self, app_name: str | None = None) -> str:
        """记录屏幕信息"""
        info = {"current_app": app_name or "unknown"}
        display = f"\n📱 Screen: {json.dumps(info, ensure_ascii=False)}"

        self._log(display, LogLevel.INFO)

        return display

    def log_summary(self, summary: str) -> str:
        """记录步骤摘要 - Gelab-Zero 格式"""
        if not summary:
            return ""

        display = f"\n📝 Summary: {summary}"
        self._log(display, LogLevel.INFO)

        return summary

    def log_info_request(self, prompt: str) -> str:
        """记录 INFO 请求"""
        display = f"\n❓ Info Request: {prompt}"
        self._log(display, LogLevel.WARNING)

        return prompt

    def log_error(self, error: str) -> str:
        """记录错误"""
        display = f"\n🚨 Error: {error}"
        self._log(display, LogLevel.ERROR)

        return error

    def log_finished(self, stop_reason: str, total_steps: int) -> str:
        """记录任务完成"""
        self._log(f"\n{'=' * 50}", LogLevel.INFO)
        self._log(f"Task Finished: {stop_reason}", LogLevel.INFO)
        self._log(f"Total Steps: {total_steps}", LogLevel.INFO)
        self._log(f"{'=' * 50}\n", LogLevel.INFO)

        # 动作统计
        if self.action_counts:
            stats = ", ".join(f"{k.value}: {v}" for k, v in self.action_counts.items())
            self._log(f"Action Stats: {stats}\n", LogLevel.INFO)

        return f"{stop_reason} (steps: {total_steps})"

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "total_steps": self.step_count,
            "action_counts": {k.value: v for k, v in self.action_counts.items()},
            "protocol": self.protocol,
        }

    def _log(self, message: str, level: str = LogLevel.INFO) -> None:
        """内部日志方法"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] [{level}] {message}"

        if self.log_callback:
            self.log_callback(formatted, level)
        else:
            print(formatted)

    def _format_autoglm_action(self, action: Action) -> str:
        """格式化 AutoGLM 动作"""
        action_type = action.action_type
        params = action.params or {}

        if action_type == ActionType.COMPLETE:
            msg = params.get("return", "Task completed")
            return f'finish(message="{msg}")'

        if action_type == ActionType.ABORT:
            msg = params.get("value", "Task aborted")
            return f'finish(message="Abort: {msg}")'

        # 动作名称映射
        name_map = {
            ActionType.CLICK: "Tap",
            ActionType.DOUBLE_TAP: "Double Tap",
            ActionType.LONG_PRESS: "Long Press",
            ActionType.SWIPE: "Swipe",
            ActionType.TYPE: "Type",
            ActionType.BACK: "Back",
            ActionType.HOME: "Home",
            ActionType.LAUNCH: "Launch",
            ActionType.WAIT: "Wait",
            ActionType.INFO: "Interact",
            ActionType.TAKE_OVER: "Take_over",
        }

        action_name = name_map.get(action_type, action_type.value)
        parts = [f'action="{action_name}"']

        if "point" in params:
            p = params["point"]
            parts.append(f"element=[{p[0]}, {p[1]}]")
        if "point1" in params and "point2" in params:
            p1, p2 = params["point1"], params["point2"]
            parts.append(f"start=[{p1[0]}, {p1[1]}]")
            parts.append(f"end=[{p2[0]}, {p2[1]}]")
        if "value" in params:
            val = params["value"]
            if action_type == ActionType.TYPE:
                parts.append(f'text="{val}"')
            elif action_type == ActionType.LAUNCH:
                parts.append(f'app="{val}"')
            else:
                parts.append(f'value="{val}"')

        return f"do({', '.join(parts)})"

    def _format_gelab_action(self, action: Action) -> str:
        """格式化 Gelab-Zero 动作"""
        action_type = action.action_type
        params = action.params or {}

        parts = []

        if action.explanation:
            parts.append(f"explain:{action.explanation}")

        # 动作名称映射
        name_map = {
            ActionType.CLICK: "CLICK",
            ActionType.SWIPE: "SLIDE",
            ActionType.TYPE: "TYPE",
            ActionType.BACK: "BACK",
            ActionType.HOME: "HOME",
            ActionType.LAUNCH: "AWAKE",
            ActionType.WAIT: "WAIT",
            ActionType.INFO: "INFO",
            ActionType.LONG_PRESS: "LONGPRESS",
            ActionType.COMPLETE: "COMPLETE",
            ActionType.ABORT: "ABORT",
        }

        action_name = name_map.get(action_type, action_type.value)
        parts.append(f"action:{action_name}")

        if "point" in params:
            p = params["point"]
            parts.append(f"point:{p[0]},{p[1]}")
        if "point1" in params and "point2" in params:
            p1, p2 = params["point1"], params["point2"]
            parts.append(f"point1:{p1[0]},{p1[1]}")
            parts.append(f"point2:{p2[0]},{p2[1]}")
        if "value" in params:
            parts.append(f"value:{params['value']}")
        if "return" in params:
            parts.append(f"return:{params['return']}")

        if action.summary:
            parts.append(f"summary:{action.summary}")

        return "\t".join(parts)

    def _format_universal_action(self, action: Action) -> str:
        """格式化通用动作"""
        action_type = action.action_type.value
        params = action.params or {}

        info = [f"action={action_type}"]

        if "point" in params:
            p = params["point"]
            info.append(f"point=({p[0]}, {p[1]})")
        if "value" in params:
            val = str(params["value"])[:30]
            info.append(f"value={val}")

        if action.explanation:
            info.append(f"explain={action.explanation}")

        return f"[{' | '.join(info)}]"


# 便捷函数
def create_gui_logger(
    protocol: str = "autoglm",
    log_callback=None,
    **kwargs
) -> GUILogger:
    """创建 GUI 日志适配器"""
    return GUILogger(
        log_callback=log_callback,
        protocol=protocol,
        **kwargs
    )
