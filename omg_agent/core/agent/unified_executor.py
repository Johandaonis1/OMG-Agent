"""
Unified Executor - 统一执行器

提供对 AutoGLM 和 Gelab-Zero 协议的 100% 兼容执行。

对标实现：
- AutoGLM: phone_agent/agent.py
- Gelab-Zero: copilot_agent_client/mcp_agent_loop.py, copilot_agent_server/local_server.py

功能：
1. 协议切换 - 无缝切换 AutoGLM/Gelab-Zero 协议
2. 消息构建 - 完全按照原版格式构建消息
3. 步骤控制 - 与原版一致的迭代控制
4. 状态管理 - 兼容原版的状态保存与恢复
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from datetime import datetime
from enum import Enum

from .protocol_compat import (
    ProtocolType,
    ProtocolAdapter,
    AutoGLMMessageFormatter,
    GelabMessageFormatter,
    AutoGLMContextBuilder,
    GelabContextBuilder,
    AutoGLMStepController,
    GelabStepController,
    get_autoglm_system_prompt,
    get_gelab_system_prompt,
)


class StopReason(str, Enum):
    """停止原因"""
    NOT_STARTED = "NOT_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_ABORTED = "TASK_ABORTED"
    MAX_STEPS_REACHED = "MAX_STEPS_REACHED"
    INFO_NEEDS_REPLY = "INFO_ACTION_NEEDS_REPLY"
    SCREEN_OFF = "MANUAL_STOP_SCREEN_OFF"
    ERROR = "ERROR"


@dataclass
class ExecutionStep:
    """执行步骤信息"""
    step_num: int
    global_step_num: int
    timestamp: str
    action_type: str
    action_params: dict
    thinking: str
    explain: str
    summary: str
    screenshot_b64: str | None = None
    latency_ms: float = 0.0


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    stop_reason: str
    total_steps: int
    total_time: float
    steps: list[dict] = field(default_factory=list)
    session_id: str = ""
    error: str | None = None


class UnifiedExecutor:
    """
    统一执行器 - 支持 AutoGLM 和 Gelab-Zero 协议

    核心设计：
    1. 协议无关的外部接口
    2. 内部自动处理协议差异
    3. 完全对标原版的执行流程
    """

    def __init__(
        self,
        protocol: str | ProtocolType,
        task: str,
        model_config: dict | None = None,
        device_config: dict | None = None,
        callbacks: dict | None = None
    ):
        """
        初始化执行器

        Args:
            protocol: 协议类型 ("autoglm", "gelab", "universal")
            task: 任务描述
            model_config: 模型配置
            device_config: 设备配置
            callbacks: 回调函数
        """
        if isinstance(protocol, str):
            self.protocol = ProtocolType(protocol.lower())
        else:
            self.protocol = protocol

        self.task = task
        self.model_config = model_config or {}
        self.device_config = device_config or {}

        # 初始化协议适配器
        self.adapter = ProtocolAdapter(self.protocol)

        # 初始化上下文构建器
        if self.protocol == ProtocolType.AUTOGLM:
            self.context_builder = AutoGLMContextBuilder(task)
        else:
            self.context_builder = GelabContextBuilder(task, model_config)

        # 初始化步骤控制器
        self.step_controller = self.adapter.get_step_controller(
            max_steps=self.model_config.get("max_steps", self.adapter.max_steps),
            delay_after_action=self.model_config.get("delay_after_action", self.adapter.delay_after_action),
        )

        # 初始化消息格式化器
        self.message_formatter = self.adapter.get_message_formatter()

        # 回调函数
        self.on_action: Callable[[dict], None] = callbacks.get("on_action", lambda x: None)
        self.on_screenshot: Callable[[str], None] = callbacks.get("on_screenshot", lambda x: None)
        self.on_step: Callable[[ExecutionStep], None] = callbacks.get("on_step", lambda x: None)

        # 执行状态
        self._step_count = 0
        self._global_step_count = 0
        self._history = []
        self._session_id = ""

    def build_messages(
        self,
        screenshot_b64: str,
        current_app: str | None = None,
        history: list[dict] | None = None
    ) -> list[dict]:
        """
        构建 LLM 消息

        根据协议类型自动选择消息格式：
        - AutoGLM: System + User(task+app+img) + Assistant(action) + User(app+img)
        - Gelab-Zero: Task prompt + Image + History + Current Image
        """
        if self.protocol == ProtocolType.AUTOGLM:
            return self._build_autoglm_messages(screenshot_b64, current_app, history)
        else:
            return self._build_gelab_messages(screenshot_b64, current_app, history)

    def _build_autoglm_messages(
        self,
        screenshot_b64: str,
        current_app: str | None = None,
        history: list[dict] | None = None
    ) -> list[dict]:
        """构建 AutoGLM 格式的消息 - 对标 phone_agent/agent.py"""
        messages = []

        # System message
        system_prompt = self.adapter.get_system_prompt(date=self._get_date_string())
        messages.append({"role": "system", "content": system_prompt})

        # History
        if history:
            for entry in history:
                # User message (observation)
                obs = entry.get("observation", current_app or "unknown")
                messages.append({
                    "role": "user",
                    "content": [{"type": "text", "text": f"current_app: {obs}"}]
                })

                # Assistant message (action with thinking)
                think = entry.get("thinking", "")
                action = entry.get("action", "")
                messages.append({
                    "role": "assistant",
                    "content": f"\n{think}\n<answer>{action}</answer>"
                })

        # Current user message
        app_info = current_app or "unknown"
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": f"current_app: {app_info}"},
                {"type": "image_url", "image_url": {"url": screenshot_b64}}
            ]
        })

        return messages

    def _build_gelab_messages(
        self,
        screenshot_b64: str,
        current_app: str | None = None,
        history: list[dict] | None = None
    ) -> list[dict]:
        """构建 Gelab-Zero 格式的消息 - 对标 local_server.py + parser_0920_summary.py"""
        # 准备环境列表
        environments = []
        actions = []

        if history:
            for entry in history:
                env = {
                    "image": entry.get("screenshot_b64", ""),
                    "user_comment": entry.get("user_reply", "")
                }
                environments.append(env)

                action = {
                    "action": entry.get("action_type", ""),
                    "cot": entry.get("thinking", ""),
                    "explain": entry.get("explain", ""),
                    "summary": entry.get("summary", ""),
                    **{k: v for k, v in entry.get("params", {}).items()
                       if k not in ["action", "cot", "explain", "summary"]}
                }
                actions.append(action)

        # 当前环境
        current_env = {
            "image": screenshot_b64,
            "user_comment": ""
        }
        environments.append(current_env)

        # 使用 context builder 构建消息
        messages = self.context_builder.build_history_messages(
            environments=environments,
            actions=actions,
            current_screenshot_b64=None  # 이미 environments에 포함됨
        )

        return messages

    def parse_action(self, response: str) -> dict:
        """解析 LLM 响应为动作"""
        return self.message_formatter.parse_response(response)

    def format_action(self, action_type: str, **params) -> str:
        """格式化动作输出"""
        return self.message_formatter.format_action(action_type, **params)

    def create_action_response(self, thinking: str, action_type: str, **params) -> str:
        """创建完整的动作响应"""
        action_str = self.format_action(action_type, **params)
        return self.message_formatter.wrap_response(thinking, action_str)

    def get_stop_reason(self, action: dict, last_action_type: str | None = None) -> str:
        """获取停止原因"""
        action_type = action.get("action", "").upper()

        if action_type in ["COMPLETE", "FINISH"]:
            return StopReason.TASK_COMPLETED.value
        elif action_type == "ABORT":
            return StopReason.TASK_ABORTED.value
        elif action_type == "INFO":
            return StopReason.INFO_NEEDS_REPLY.value
        elif last_action_type:
            if last_action_type.upper() == "COMPLETE":
                return StopReason.TASK_COMPLETED.value
            elif last_action_type.upper() == "ABORT":
                return StopReason.TASK_ABORTED.value

        if self._step_count >= self.step_controller.max_steps:
            return StopReason.MAX_STEPS_REACHED.value

        return StopReason.NOT_STARTED.value

    def should_continue(self, action: dict | None = None) -> bool:
        """检查是否继续执行"""
        if action:
            action_type = action.get("action", "").upper()
            if action_type in ["COMPLETE", "FINISH", "ABORT"]:
                return False
            if action_type == "INFO" and self.step_controller.reply_mode != "auto_reply":
                return False
        return self._step_count < self.step_controller.max_steps

    def _get_date_string(self) -> str:
        """获取当前日期字符串 (AutoGLM 格式)"""
        today = datetime.today()
        weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekday = weekday_names[today.weekday()]
        return today.strftime("%Y年%m月%d日") + " " + weekday

    def create_step_info(
        self,
        action: dict,
        screenshot_b64: str | None,
        latency_ms: float = 0.0
    ) -> ExecutionStep:
        """创建步骤信息"""
        self._global_step_count += 1

        return ExecutionStep(
            step_num=self._step_count,
            global_step_num=self._global_step_count,
            timestamp=datetime.now().isoformat(),
            action_type=action.get("action", "UNKNOWN"),
            action_params={k: v for k, v in action.items()
                          if k != "action" and k not in ["cot", "thinking", "explain", "summary"]},
            thinking=action.get("cot", action.get("thinking", "")),
            explain=action.get("explain", ""),
            summary=action.get("summary", action.get("return", "")),
            screenshot_b64=screenshot_b64,
            latency_ms=latency_ms
        )

    def get_llm_params(self) -> dict[str, Any]:
        """获取 LLM 请求参数"""
        return {
            "temperature": self.model_config.get("temperature", self.adapter.temperature),
            "top_p": self.model_config.get("top_p", 0.95),
            "max_tokens": self.model_config.get("max_tokens", self.adapter.max_tokens),
            "frequency_penalty": self.model_config.get("frequency_penalty", 0.0),
        }

    def get_image_config(self) -> dict[str, Any]:
        """获取图像预处理配置"""
        return {
            "resize": self.adapter.resize_image,
            "target_size": getattr(self.adapter, "target_size", (728, 728)),
            "format": self.adapter.image_format,
            "quality": self.adapter.image_quality,
        }

    @property
    def delay_after_action(self) -> float:
        """获取动作后延迟时间"""
        return self.step_controller.delay_after_action


# =============================================================================
# 对比测试工具
# =============================================================================

class CompatibilityTester:
    """
    兼容性测试器 - 对比 OMGAgent 与原版的执行差异
    """

    def __init__(self):
        self.omg_results = []
        self.original_results = []

    def compare_responses(
        self,
        omg_response: str,
        original_response: str,
        protocol: ProtocolType
    ) -> dict:
        """对比两个响应"""
        adapter = ProtocolAdapter(protocol)
        omg_parsed = adapter.parse_action(omg_response)
        original_parsed = adapter.parse_action(original_response)

        return {
            "omg_parsed": omg_parsed,
            "original_parsed": original_parsed,
            "is_identical": omg_parsed == original_parsed,
            "differences": self._find_differences(omg_parsed, original_parsed)
        }

    def _find_differences(self, d1: dict, d2: dict, path: str = "") -> list[dict]:
        """找出两个字典的差异"""
        differences = []

        all_keys = set(d1.keys()) | set(d2.keys())

        for key in all_keys:
            current_path = f"{path}.{key}" if path else key

            if key not in d1:
                differences.append({
                    "path": current_path,
                    "omg": None,
                    "original": d2.get(key)
                })
            elif key not in d2:
                differences.append({
                    "path": current_path,
                    "omg": d1.get(key),
                    "original": None
                })
            elif d1.get(key) != d2.get(key):
                if isinstance(d1.get(key), dict) and isinstance(d2.get(key), dict):
                    differences.extend(self._find_differences(d1[key], d2[key], current_path))
                else:
                    differences.append({
                        "path": current_path,
                        "omg": d1.get(key),
                        "original": d2.get(key)
                    })

        return differences

    def test_message_format(
        self,
        protocol: ProtocolType,
        test_cases: list[dict]
    ) -> dict:
        """测试消息格式兼容性"""
        adapter = ProtocolAdapter(protocol)
        formatter = adapter.get_message_formatter()

        results = []

        for test_case in test_cases:
            action_type = test_case["action_type"]
            params = test_case.get("params", {})

            # 生成格式化的动作
            formatted = formatter.format_action(action_type, **params)

            # 解析回来
            parsed = formatter.parse_response(formatted)

            results.append({
                "input": test_case,
                "formatted": formatted,
                "parsed_back": parsed,
                "success": parsed.get("action", "").upper() == action_type.upper()
            })

        return {
            "protocol": protocol.value,
            "test_cases": len(test_cases),
            "passed": sum(1 for r in results if r["success"]),
            "failed": sum(1 for r in results if not r["success"]),
            "results": results
        }

    def generate_trace_report(
        self,
        steps: list[ExecutionStep],
        original_steps: list[dict] | None = None
    ) -> dict:
        """生成执行轨迹报告"""
        report = {
            "total_steps": len(steps),
            "action_types": {},
            "step_sequence": [],
            "compatibility_score": 100.0
        }

        for step in steps:
            action_type = step.action_type
            report["action_types"][action_type] = report["action_types"].get(action_type, 0) + 1
            report["step_sequence"].append({
                "step": step.step_num,
                "action": action_type,
                "thinking_length": len(step.thinking) if step.thinking else 0
            })

        # 与原版对比
        if original_steps:
            original_types = [s.get("action_type", "") for s in original_steps]
            omg_types = [s.action_type for s in steps]

            if original_types == omg_types:
                report["compatibility_score"] = 100.0
            else:
                # 计算序列相似度
                common = set(original_types) & set(omg_types)
                report["compatibility_score"] = len(common) / max(len(original_types), len(omg_types)) * 100

        return report


# =============================================================================
# 便捷函数
# =============================================================================

def create_executor(
    protocol: str,
    task: str,
    model_config: dict | None = None,
    **kwargs
) -> UnifiedExecutor:
    """创建执行器"""
    return UnifiedExecutor(
        protocol=protocol,
        task=task,
        model_config=model_config,
        **kwargs
    )


# 示例用法
if __name__ == "__main__":
    # 创建 AutoGLM 执行器
    executor = create_executor(
        protocol="autoglm",
        task="打开微信给张三发消息",
        model_config={"max_steps": 50, "temperature": 0.0}
    )

    print(f"Protocol: {executor.protocol.value}")
    print(f"Max steps: {executor.step_controller.max_steps}")
    print(f"Coordinate max: {executor.adapter.coordinate_max}")
    print(f"Image format: {executor.adapter.image_format}")

    # 测试动作格式化
    action_str = executor.format_action("CLICK", point=[500, 500], explain="点击发送按钮")
    print(f"\nFormatted action: {action_str}")

    # 测试兼容性
    tester = CompatibilityTester()
    result = tester.test_message_format(
        ProtocolType.GELAB_ZERO,
        [
            {"action_type": "CLICK", "params": {"point": [500, 500]}},
            {"action_type": "TYPE", "params": {"value": "Hello"}},
            {"action_type": "SWIPE", "params": {"point1": [500, 800], "point2": [500, 400]}},
        ]
    )
    print(f"\nCompatibility test: {result['passed']}/{result['test_cases']} passed")
