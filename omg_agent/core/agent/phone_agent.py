"""
PhoneAgent - Main agent class for phone automation.

Combines the best features from Open-AutoGLM and gelab-zero:
- Clean architecture with dataclass configs
- Session management for task resumption
- History summary compression
- Multiple reply modes for INFO action
- Callback mechanisms for human intervention

Auto-adaptation:
- 自动检测模型类型并加载对应协议配置
- 支持 AutoGLM、gelab-zero、通用 VLM 三种协议
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal
from enum import Enum

from .actions import ActionHandler, ActionParser, ActionResult, ActionSpace
from .actions.space import Action, ActionType
from .device.screenshot import (
    take_screenshot, get_current_app, is_screen_on, wake_screen,
    ImagePreprocessConfig
)
from .device.apps import autoglm_app_name_from_package
from .history import HistoryManager, HistoryEntry
from .llm import LLMClient, LLMConfig, MessageBuilder
from .prompts import get_system_prompt
from .session import SessionManager
from .protocol_adapter import (
    Protocol,
    detect_protocol,
    get_protocol_config,
)
from .protocol_compat import ProtocolAdapter as CompatProtocolAdapter, create_adapter
from .context_builder import ContextBuilder, ContextConfig, get_context_builder

# 配置模块级日志器
logger = logging.getLogger(__name__)


class ReplyMode(str, Enum):
    """How to handle INFO actions."""
    AUTO = "auto"  # Auto-reply using LLM
    MANUAL = "manual"  # Wait for user input
    CALLBACK = "callback"  # Use callback function
    PAUSE = "pause"  # Pause session, return to caller


@dataclass
class AgentConfig:
    """Configuration for PhoneAgent."""

    # Device settings
    device_id: str | None = None

    # Execution limits
    max_steps: int = 100
    step_delay: float = 1.0  # Delay between steps

    # Language
    lang: str = "zh"

    # 自动适配：设为 True 时根据 model_name 自动检测协议
    auto_adapt: bool = True

    # Prompt protocol: "universal" | "autoglm" | "gelab" | None (auto)
    prompt_protocol: str | None = None

    # System prompt (auto-loaded if None)
    system_prompt: str | None = None

    # Reply mode for INFO actions
    reply_mode: ReplyMode = ReplyMode.CALLBACK

    # Session storage
    session_dir: str | None = None

    # Auto wake screen
    auto_wake_screen: bool = True

    # Auto press home before task
    reset_to_home: bool = True

    # 图像预处理配置 (None = 使用协议默认配置)
    image_preprocess: ImagePreprocessConfig | None = None

    # 坐标系范围 (None = 使用协议默认: 1000 或 999)
    coordinate_max: int | None = None

    # Loop avoidance (prompt-level mitigation; does not auto-abort)
    loop_guard_enabled: bool = True
    # Start injecting anti-loop prompt after this many consecutive identical actions (excluding SWIPE by default).
    loop_guard_repeat_threshold: int = 3
    # Whether to ignore swipe repeats (swiping can be a normal search behavior).
    loop_guard_ignore_swipe: bool = True

    # Verbose output (deprecated, use logging instead)
    verbose: bool = False

    # 内部使用：协议适配器
    _protocol_adapter: CompatProtocolAdapter | None = field(default=None, repr=False)

    def apply_protocol(self, model_name: str | None = None) -> None:
        """
        应用协议配置。

        根据模型名称自动检测协议，或使用显式指定的协议。
        对标官方实现加载对应配置。
        """
        # 确定协议
        if self.prompt_protocol is not None:
            protocol = Protocol(self.prompt_protocol)
        elif model_name is not None and self.auto_adapt:
            protocol = detect_protocol(model_name)
        else:
            protocol = Protocol.UNIVERSAL

        # 获取协议配置
        protocol_config = get_protocol_config(protocol=protocol)
        # Use protocol_compat adapter for official-aligned parsing/formatting
        self._protocol_adapter = create_adapter(protocol.value)

        # 应用协议配置（如果未显式设置）
        if self.prompt_protocol is None:
            self.prompt_protocol = protocol.value

        if self.coordinate_max is None:
            self.coordinate_max = protocol_config.coordinate_max

        if self.image_preprocess is None:
            self.image_preprocess = ImagePreprocessConfig(
                is_resize=protocol_config.image_config.is_resize,
                target_size=protocol_config.image_config.target_size,
                format=protocol_config.image_config.format,
                quality=protocol_config.image_config.quality
            )

        # 应用执行参数（如果是默认值）
        if self.step_delay == 1.0:  # 默认值
            self.step_delay = protocol_config.delay_after_action

        if self.max_steps == 100:  # 默认值
            self.max_steps = protocol_config.max_steps

        # 加载系统提示词
        if self.system_prompt is None:
            self.system_prompt = get_system_prompt(self.lang, self.prompt_protocol)

    def __post_init__(self):
        # Defer protocol-dependent defaults when auto-adapting (PhoneAgent will call apply_protocol()).
        if self.prompt_protocol is None and self.auto_adapt:
            return

        if self.prompt_protocol is None:
            self.prompt_protocol = "universal"

        # 设置默认坐标系（根据协议）
        if self.coordinate_max is None:
            if self.prompt_protocol == "autoglm":
                self.coordinate_max = 999
            else:
                # Gelab & Universal default to 1000
                self.coordinate_max = 1000

        # 设置默认图像配置（根据协议）
        if self.image_preprocess is None:
            if self.prompt_protocol == "autoglm":
                # AutoGLM: Use original resolution for best performance
                self.image_preprocess = ImagePreprocessConfig(
                    is_resize=False,
                    target_size=(1080, 2400),
                    format="png",
                    quality=100
                )
            elif self.prompt_protocol == "gelab":
                # Gelab: Resize to 728x728 JPEG (Standard)
                self.image_preprocess = ImagePreprocessConfig(
                    is_resize=True,
                    target_size=(728, 728),
                    format="jpeg",
                    quality=85
                )
            else:
                # Universal: resize to 728x728, JPEG
                self.image_preprocess = ImagePreprocessConfig(
                    is_resize=True,
                    target_size=(728, 728),
                    format="jpeg",
                    quality=85
                )

        # 加载系统提示词
        if self.system_prompt is None:
            self.system_prompt = get_system_prompt(self.lang, self.prompt_protocol)


@dataclass
class StepResult:
    """Result of a single agent step."""

    success: bool
    finished: bool
    action: Action | None
    action_result: ActionResult | None = None
    message: str | None = None

    # For INFO action handling
    needs_user_input: bool = False
    user_prompt: str | None = None

    # Session info
    session_id: str | None = None
    step_count: int = 0

    @property
    def thinking(self) -> str:
        """Get thinking content from action (backward compatibility)."""
        if self.action:
            return self.action.thinking
        return ""


@dataclass
class RunResult:
    """Result of running a complete task."""

    success: bool
    message: str
    step_count: int
    session_id: str | None = None
    final_action: Action | None = None

    # Stop reason
    stop_reason: Literal[
        "completed",
        "aborted",
        "max_steps",
        "error",
        "paused",
        "screen_off"
    ] = "completed"


class PhoneAgent:
    """
    AI-powered agent for automating Android phone interactions.

    The agent uses a vision-language model to understand screen content
    and decide on actions to complete user tasks.

    Features:
    - Session management for task resumption
    - History summary compression for efficient context
    - Multiple reply modes for user interaction
    - Callback mechanisms for sensitive operations

    Example:
        >>> from omg_agent.core.agent import PhoneAgent, AgentConfig
        >>> from omg_agent.core.agent.llm import LLMConfig
        >>>
        >>> llm_config = LLMConfig(provider="openai", model="gpt-4o")
        >>> agent_config = AgentConfig(device_id="emulator-5554")
        >>> agent = PhoneAgent(llm_config, agent_config)
        >>>
        >>> result = agent.run("Open WeChat and send 'Hello' to John")
        >>> print(result.message)
    """

    def __init__(
        self,
        llm_config: LLMConfig | None = None,
        agent_config: AgentConfig | None = None,
        # Callbacks
        confirmation_callback: Callable[[str], bool] | None = None,
        takeover_callback: Callable[[str], None] | None = None,
        info_callback: Callable[[str], str] | None = None,
        # Progress callback
        on_step: Callable[[StepResult], None] | None = None,
        # Logging callback
        log_callback: Callable[[str], None] | None = None,
        # Screenshot provider (for GUI integration)
        screenshot_provider: Callable[[], Any] | None = None,
        # Backward compatibility aliases
        model_config: LLMConfig | None = None,
        logger: Callable[[str], None] | None = None,  # Alias for log_callback
    ):
        """
        Initialize PhoneAgent.

        Args:
            llm_config: Configuration for LLM client
            agent_config: Agent behavior configuration
            confirmation_callback: Called for sensitive operation confirmation
            takeover_callback: Called when agent requests human takeover
            info_callback: Called when agent needs information from user
            on_step: Called after each step with results
            log_callback: Callback for logging (deprecated)
            screenshot_provider: Optional callable that returns Screenshot object
            model_config: Alias for llm_config (backward compatibility)
        """
        # Handle backward compatibility
        if model_config is not None and llm_config is None:
            llm_config = model_config
        
        # Handle logger alias
        if logger is not None and log_callback is None:
            log_callback = logger

        self.llm_config = llm_config or LLMConfig()
        self.config = agent_config or AgentConfig()

        # Log callback (for GUI integration)
        self._log_callback = log_callback

        # =================================================================
        # 自动适配：根据模型名称检测协议并加载对应配置
        # 对标官方 gelab-zero 和 Open-AutoGLM 实现
        # =================================================================
        model_name = self.llm_config.model.lower()

        # 应用协议配置（自动检测或使用显式指定）
        if self.config.auto_adapt:
            self.config.apply_protocol(model_name)
            self._log(f"🔧 Auto-adapted to protocol: {self.config.prompt_protocol}", "debug")
            self._log(f"   - Coordinate max: {self.config.coordinate_max}", "debug")
            self._log(f"   - Image resize: {self.config.image_preprocess.is_resize}", "debug")
            if self.config.image_preprocess.is_resize:
                self._log(f"   - Target size: {self.config.image_preprocess.target_size}", "debug")

        # 确定历史输出格式
        protocol = self.config.prompt_protocol
        if protocol == "autoglm":
            self._output_format = "autoglm"
        elif protocol == "gelab":
            self._output_format = "step"  # Gelab strictly uses STEP format
        else:
            # 通用协议：根据模型名称决定
            if any(k in model_name for k in ["step", "gelab"]):
                self._output_format = "step"
            else:
                self._output_format = "autoglm"

        # Screenshot provider for GUI integration
        self._screenshot_provider = screenshot_provider

        # Initialize components
        self.llm_client = LLMClient(self.llm_config)
        self.action_handler = ActionHandler(
            device_id=self.config.device_id,
            confirmation_callback=confirmation_callback,
            takeover_callback=takeover_callback,
            info_callback=info_callback,
            logger=log_callback,
            coordinate_max=self.config.coordinate_max,  # 传递坐标系配置
            protocol=self.config.prompt_protocol or "auto",
        )
        self.history_manager = HistoryManager(output_format=self._output_format)
        self.session_manager = SessionManager(self.config.session_dir)

        # Callbacks
        self._on_step = on_step

        # Current session
        self._current_session_id: str | None = None

        # Error recovery tracking
        self._parse_error_count: int = 0
        self._max_parse_errors: int = 3  # Max consecutive parse errors before aborting
        self._llm_error_count: int = 0
        self._max_llm_errors: int = 2  # Max consecutive LLM errors before aborting (after retries)

        # 协议适配器（用于高级功能）
        self._protocol_adapter = self.config._protocol_adapter

        # 上下文构建器 - 根据协议创建
        self._context_builder = get_context_builder(
            protocol=self.config.prompt_protocol,
            max_history_steps=8,
            use_summary=True,
            lang=self.config.lang
        )

        # 追踪上一步的 summary（用于 gelab 模式）
        self._last_summary: str = ""

    def _log(self, message: str, level: str = "info") -> None:
        """Internal logging method."""
        if level == "debug":
            logger.debug(message)
        elif level == "warning":
            logger.warning(message)
        elif level == "error":
            logger.error(message)
        else:
            logger.info(message)
        
        # Also call log callback if provided (for GUI)
        if self._log_callback:
            self._log_callback(message)

    def _ensure_screen_on(self, protocol: str) -> bool:
        """
        Ensure screen is on before task starts.
        Returns True if screen is on (or waked), False if failed.
        """
        if not self.config.auto_wake_screen:
            return True

        if is_screen_on(self.config.device_id):
            return True

        self._log(f"[Screen] Screen is off, attempting to wake...")
        wake_screen(self.config.device_id)
        time.sleep(1.5)  # Wait for wake up

        if is_screen_on(self.config.device_id):
            return True

        # Retry logic
        if protocol == "gelab":
            # Gelab: strict check (stop if failed) is handled by caller
            return False
        else:
            # AutoGLM/Universal: Retry once more
            wake_screen(self.config.device_id)
            time.sleep(1)
            return is_screen_on(self.config.device_id)

    def run(
        self,
        task: str,
        session_id: str | None = None,
        user_reply: str | None = None
    ) -> RunResult:
        """
        Run the agent to complete a task.

        Args:
            task: Natural language description of the task
            session_id: Resume existing session (for INFO action handling)
            user_reply: User's reply when resuming paused session

        Returns:
            RunResult with completion status and message
        """
        # Initialize or resume session
        if session_id:
            session = self.session_manager.resume_session(session_id)
            if session is None:
                return RunResult(
                    success=False,
                    message=f"Session not found: {session_id}",
                    step_count=0,
                    stop_reason="error"
                )
            self._current_session_id = session_id
        else:
            # New task
            self._current_session_id = self.session_manager.create_session(
                task=task,
                device_id=self.config.device_id
            )
            
            # Start task with planning (uses LLM for complex tasks)
            task_plan = self.history_manager.start_task(task, llm_client=self.llm_client)
            if task_plan:
                self._log(f"Task Plan: {len(task_plan.sub_tasks)} steps identified")

            # gelab-zero: reset environment (home) before starting a new task
            if self.config.reset_to_home and (self.config.prompt_protocol or "").lower() == "gelab":
                self.action_handler.executor.press_home()
                time.sleep(0.5)

        self._log(f"Session: {self._current_session_id}")
        self._log(f"Task: {task}")

        # Run loop
        last_result = None
        protocol = (self.config.prompt_protocol or "universal").lower()
        stop_reason: str = "max_steps"
        pending_user_reply = user_reply

        # 优化：仅在任务开始前检查并唤醒屏幕，避免每一轮都检查导致延迟
        # Optimize: Check and wake screen only at start, not every step
        if self.config.auto_wake_screen:
            if not self._ensure_screen_on(protocol):
                self._log(f"[Screen] Screen is off and failed to wake. Task may fail.", "warning")
                if protocol == "gelab":
                    return RunResult(
                        success=False,
                        message="Screen off (Manual Stop)",
                        step_count=0,
                        stop_reason="MANUAL_STOP_SCREEN_OFF"
                    )

        for step in range(self.config.max_steps):
            # 移除循环内的每步息屏检测以提升效率
            # Remove per-step screen check for efficiency

            # Execute step (consume any pending user reply once, like gelab-zero reply_info)
            result = self._execute_step(pending_user_reply)
            last_result = result
            pending_user_reply = None

            # Update session
            self.session_manager.update_session(
                self._current_session_id,
                step_count=result.step_count,
                history_summary=self.history_manager.get_summary()
            )

            # Callback
            if self._on_step:
                self._on_step(result)

            # Check termination conditions
            if result.finished:
                if result.action and result.action.action_type == ActionType.COMPLETE:
                    stop_reason = "TASK_COMPLETED_SUCCESSFULLY" if protocol == "gelab" else "completed"
                    self.session_manager.complete_session(
                        self._current_session_id,
                        result.message
                    )
                elif result.action and result.action.action_type == ActionType.ABORT:
                    stop_reason = "TASK_ABORTED_BY_AGENT" if protocol == "gelab" else "aborted"
                    self.session_manager.abort_session(
                        self._current_session_id,
                        result.message
                    )
                break

            # Handle INFO action
            if result.needs_user_input:
                if self.config.reply_mode == ReplyMode.PAUSE:
                    self.session_manager.pause_session(
                        self._current_session_id,
                        result.user_prompt or ""
                    )
                    stop_reason = "INFO_ACTION_NEEDS_REPLY" if protocol == "gelab" else "paused"
                    break
                elif self.config.reply_mode == ReplyMode.AUTO:
                    pending_user_reply = self._auto_reply(task, result.user_prompt or "")
                elif self.config.reply_mode == ReplyMode.CALLBACK:
                    pending_user_reply = self.action_handler.info_callback(result.user_prompt or "")
                elif self.config.reply_mode == ReplyMode.MANUAL:
                    pending_user_reply = input(f"Agent asks: {result.user_prompt}\nYour response: ")

            # Delay between steps
            if protocol != "autoglm":
                time.sleep(self.config.step_delay)

        if stop_reason == "max_steps" and protocol == "gelab":
            stop_reason = "MAX_STEPS_REACHED"

        # Build result
        return RunResult(
            success=stop_reason in ("completed", "TASK_COMPLETED_SUCCESSFULLY"),
            message=last_result.message if last_result else "No steps executed",
            step_count=self.history_manager.step_count,
            session_id=self._current_session_id,
            final_action=last_result.action if last_result else None,
            stop_reason=stop_reason
        )

    def step(self, task: str | None = None, user_reply: str | None = None) -> StepResult:
        """
        Execute a single step.

        Useful for manual control or integration with external systems.

        Args:
            task: Task description (required for first step)
            user_reply: User's reply to previous INFO action

        Returns:
            StepResult with step details
        """
        is_first = self.history_manager.step_count == 0

        if is_first:
            if not task:
                raise ValueError("Task is required for the first step")
            task_plan = self.history_manager.start_task(task, llm_client=self.llm_client)
            if task_plan:
                self._log(f"Task Plan: {len(task_plan.sub_tasks)} steps")

        return self._execute_step(user_reply)

    def _execute_step(self, user_reply: str | None = None) -> StepResult:
        """Execute a single step of the agent loop."""

        step_num = self.history_manager.step_count + 1
        self._log(f"Step {step_num}")

        # Capture current screen state
        try:
            self._log(f"[Vision] Capturing screenshot...")
            if self._screenshot_provider:
                screenshot = self._screenshot_provider()
                if screenshot is None:
                    screenshot = take_screenshot(self.config.device_id)
            else:
                screenshot = take_screenshot(self.config.device_id)

            self._log(f"[Vision] Screenshot captured: {screenshot.width}x{screenshot.height}")

            # 应用图像预处理 (与 gelab-zero 对齐)
            if self.config.image_preprocess and self.config.image_preprocess.is_resize:
                self._log(f"[Vision] Preprocessing image to {self.config.image_preprocess.target_size}...")
                screenshot = screenshot.preprocess(self.config.image_preprocess)

            current_app = get_current_app(self.config.device_id)
            if current_app:
                self._log(f"[Device] Current app: {current_app.get('package', 'unknown')}")
        except Exception as e:
            self._log(f"[Vision] Failed to capture screen: {e}", "error")
            import traceback
            self._log(f"[Vision] Traceback: {traceback.format_exc()}", "error")
            return StepResult(
                success=False,
                finished=True,
                action=None,
                message=f"Failed to capture screen: {e}",
                step_count=step_num
            )

        # Build screen info for observation (align with official protocols)
        current_app_pkg = current_app.get("package", "unknown") if current_app else "unknown"
        prompt_app = (
            autoglm_app_name_from_package(current_app_pkg)
            if (self.config.prompt_protocol or "").lower() == "autoglm"
            else current_app_pkg
        )
        screen_info = MessageBuilder.build_screen_info(prompt_app)

        # [Dynamic Plan Update] Analyze screen state and adjust plan
        self._update_plan_from_screen(screen_info)

        # 获取历史记录（用于上下文构建）
        history_entries = None
        qa_history = None
        if self.history_manager._history:
            history_entries = self.history_manager._history.entries
            qa_history = self.history_manager._history.qa_history

        # Consume reply-from-client BEFORE building messages (gelab-zero reply_info semantics)
        if user_reply and self.history_manager._history:
            history = self.history_manager._history
            question = "指令是："
            if history.entries:
                last_entry = history.entries[-1]
                last_entry.user_reply = user_reply
                if last_entry.action.action_type == ActionType.INFO:
                    question = last_entry.action.params.get("value", "") or ""
            if not history.qa_history or history.qa_history[-1] != (question, user_reply):
                history.qa_history.append((question, user_reply))
            qa_history = history.qa_history

        # Dynamic anti-loop prompt injection (prompt-level mitigation; never auto-abort)
        system_prompt = self.config.system_prompt or ""
        if (
            self.config.loop_guard_enabled
            and self.history_manager._history
            and self.history_manager._history.entries
        ):
            entries = self.history_manager._history.entries
            last_action = entries[-1].action

            # Swiping can be a normal search behavior; ignore unless explicitly enabled.
            if not (self.config.loop_guard_ignore_swipe and last_action.action_type == ActionType.SWIPE):
                repeat_count = 1
                for i in range(len(entries) - 2, -1, -1):
                    if self.history_manager.loop_detector._actions_identical(entries[i].action, last_action):
                        repeat_count += 1
                    else:
                        break

                if repeat_count >= max(2, int(self.config.loop_guard_repeat_threshold)):
                    recent_summary = self.history_manager.get_action_summary_for_prompt(lang=self.config.lang)
                    if (self.config.lang or "zh").lower().startswith("zh"):
                        loop_prompt = (
                            "【循环纠正】检测到你最近连续执行了相同/等价操作多次，但可能没有产生有效进展。\n"
                            f"连续重复次数: {repeat_count}\n"
                            "要求：下一步必须改变策略，避免再次输出与最近操作等价的动作（例如重复点击同一位置/重复返回/重复主页）。\n"
                            "建议：\n"
                            "1) 重新观察当前屏幕是否有弹窗/权限/加载/焦点等导致操作无效；\n"
                            "2) 如果在列表/聊天中查找目标，请滚动到不同区域或换入口，不要在同一位置反复尝试；\n"
                            "3) 尝试返回/主页/重新打开目标 App，或换一条更稳妥的路径；\n"
                            "4) 如果仍无法判断，请用 INFO/Interact 请求用户澄清或选择。\n"
                            "注意：仍需严格按协议要求输出动作格式，不要输出额外文本。\n\n"
                            f"{recent_summary}"
                        )
                    else:
                        loop_prompt = (
                            "[Anti-loop] Detected repeated identical/equivalent actions with no progress.\n"
                            f"Consecutive repeats: {repeat_count}\n"
                            "Requirement: The next step MUST change strategy; do NOT output an action equivalent to the recent ones.\n"
                            "Suggestions:\n"
                            "1) Re-check the current screen for dialogs/permissions/loading/focus issues;\n"
                            "2) If searching in a list/chat, scroll to a different region or use a different entry point;\n"
                            "3) Try Back/Home/relaunch the target app, or take an alternative path;\n"
                            "4) If still uncertain, ask the user via INFO/Interact.\n"
                            "Note: You must still follow the required action output format.\n\n"
                            f"{recent_summary}"
                        )

                    self._log(f"[LoopGuard] Detected repeated action ×{repeat_count}; injecting anti-loop prompt", "warning")
                    system_prompt = f"{system_prompt}\n\n{loop_prompt}".strip()

        # Build context messages - Unified via ContextBuilder -> ProtocolAdapter (ensures 100% official compliance)
        messages = self._context_builder.build_messages(
            system_prompt=system_prompt,
            task=self.history_manager.task or "",
            current_screenshot_b64=screenshot.to_data_url(),
            current_app=current_app,
            history_entries=history_entries,
            last_summary=self._last_summary,
            qa_history=qa_history
        )

        # Get LLM response
        try:
            self._log(f"[LLM] Requesting completion from {self.llm_config.model}...")
            response = self.llm_client.request(messages)
            self._log(f"[LLM] Response received ({response.latency_ms}ms)")

            raw_thinking = response.thinking or ""
            raw_action = response.action or response.content or ""

            # DEBUG: 记录 LLM 响应
            self._log(f"[DEBUG] LLM response.action: {response.action[:100] if response.action else 'None'}...", "debug")
            self._log(f"[DEBUG] LLM response.thinking: {response.thinking[:100] if response.thinking else 'None'}...", "debug")

            if response.thinking:
                self._log(f"Thinking: {response.thinking[:200]}..." if len(response.thinking) > 200 else f"Thinking: {response.thinking}", "debug")

            # Reset LLM error count on success
            self._llm_error_count = 0

        except Exception as e:
            self._llm_error_count += 1
            error_msg = str(e)

            # Check if this is a connection error (already retried by LLMClient)
            is_connection_error = any(keyword in error_msg.lower() for keyword in [
                "connect", "connection", "timeout", "ssl", "refused", "unreachable"
            ])

            if is_connection_error and self._llm_error_count < self._max_llm_errors:
                self._log(
                    f"LLM connection error ({self._llm_error_count}/{self._max_llm_errors}): {e}. "
                    f"Will retry after wait.",
                    "warning"
                )
                # Return a WAIT action to retry next step
                return StepResult(
                    success=True,
                    finished=False,
                    action=Action(
                        action_type=ActionType.WAIT,
                        params={"value": "5"},
                        thinking=f"LLM service temporarily unavailable. Waiting to retry..."
                    ),
                    message=f"LLM connection error, waiting to retry ({self._llm_error_count}/{self._max_llm_errors})",
                    step_count=step_num
                )
            else:
                self._log(f"LLM error: {e}", "error")
                return StepResult(
                    success=False,
                    finished=True,
                    action=None,
                    message=f"LLM error: {e}",
                    step_count=step_num
                )

        # Parse action
        # Parse action using ProtocolAdapter (Ensures 100% official compliance)
        try:
            self._log(f"[Parser] Parsing action from response...")
            parsed_result = self._protocol_adapter.parse_action(response.action or response.content)
            self._log(f"[DEBUG] Protocol parsed result keys: {list(parsed_result.keys())}", "debug")

            if self.config.prompt_protocol == "autoglm":
                # AutoGLM: ProtocolAdapter returns raw 'action_content' string (e.g. "do(...)")
                # We need to parse this string into an Action object
                action_str = parsed_result.get("action_content", "")
                if not action_str:
                    # Fallback if no action content found
                    self._log(f"[Parser] No action content found in response", "warning")
                    action = Action(ActionType.ABORT, params={"value": "No action content found"})
                else:
                    try:
                        action = ActionParser._parse_function_call(action_str)
                        self._log(f"[Parser] Parsed function call: {action.action_type}")
                    except ValueError as e:
                        # If simple call parsing fails, try passing the raw content (might be free text)
                        self._log(f"[Parser] Function call parse failed: {e}, treating as raw response", "warning")
                        if "finish" in action_str:
                             # Try to salvage a finish action
                             action = Action(ActionType.COMPLETE, params={"return": action_str})
                        else:
                             raise e

                # Attach thinking from protocol parser
                action.thinking = parsed_result.get("think", "")

            else:
                # Gelab/Universal: ProtocolAdapter returns fully parsed fields (action, point, etc.)
                action = ActionParser._build_action(parsed_result)
                self._log(f"[Parser] Built action: {action.action_type}")

            self._log(f"[DEBUG] Parsed action: type={action.action_type}, thinking={action.thinking[:50] if action.thinking else 'None'}...", "debug")

            if not action.thinking and response.thinking:
                action.thinking = response.thinking
            
            # Reset error count on successful parse
            self._parse_error_count = 0
                
        except ValueError as e:
            self._parse_error_count += 1
            self._log(f"Failed to parse action ({self._parse_error_count}/{self._max_parse_errors}): {e}", "warning")
            self._log(f"Raw response: {(response.action or response.content)[:200]}", "debug")

            # Open-AutoGLM behavior: parsing failure -> finish with raw output
            if self.config.prompt_protocol == "autoglm":
                action = Action(
                    action_type=ActionType.COMPLETE,
                    params={"return": raw_action},
                    thinking=raw_thinking,
                )
                self._parse_error_count = 0
            else:
                # Check if we've exceeded max parse errors
                if self._parse_error_count >= self._max_parse_errors:
                    self._log(f"❌ Too many parse errors, aborting task", "error")
                    return StepResult(
                        success=False,
                        finished=True,
                        action=Action(
                            action_type=ActionType.ABORT,
                            params={"value": f"LLM response parsing failed {self._parse_error_count} times"},
                            thinking="LLM is not returning parseable actions."
                        ),
                        message=f"Task aborted: LLM response parsing failed repeatedly",
                        step_count=step_num
                    )

                # Use WAIT to give the model another chance
                action = Action(
                    action_type=ActionType.WAIT,
                    params={"value": "1"},
                    thinking=f"Action parsing failed: {e}. Waiting to retry."
                )

        self._log(f"Action: {action.action_type.value}")
        if action.explanation:
            self._log(f"Explanation: {action.explanation}", "debug")

        # Validate action
        is_valid, error = ActionSpace.validate(action)
        if not is_valid:
            self._log(f"Invalid action: {error}", "warning")

        # Check for action loop BEFORE executing (只警告，不中止)
        if self.history_manager._history and self.history_manager._history.entries:
            from datetime import datetime
            temp_entries = self.history_manager._history.entries.copy()
            temp_entries.append(HistoryEntry(
                step=len(temp_entries) + 1,
                action=action,
                observation=screen_info
            ))
            is_loop, loop_msg = self.history_manager.loop_detector.check_loop(temp_entries)
            if is_loop:
                self._log(f"⚠️ Loop detected: {loop_msg}", "warning")

                same_action_count = 0
                for entry in reversed(self.history_manager._history.entries):
                    if self.history_manager.loop_detector._actions_identical(entry.action, action):
                        same_action_count += 1
                    else:
                        break
                # Do not auto-abort on loop detection. We rely on the dynamic anti-loop prompt injection
                # (see above) to steer the model away from repetition, and allow the user to stop manually.
                if same_action_count >= max(3, int(self.config.loop_guard_repeat_threshold)):
                    self._log(
                        f"[LoopGuard] Same action already repeated {same_action_count} times; "
                        f"next action should change strategy (or ask user via INFO/Interact).",
                        "warning",
                    )

        # Execute action
        self._log(f"[Executor] Executing action: {action.action_type.value}")
        try:
            action_result = self.action_handler.execute(action)
            if action_result.success:
                self._log(f"[Executor] Action completed successfully")
            else:
                self._log(f"[Executor] Action failed: {action_result.message}", "warning")
        except Exception as e:
            self._log(f"[Executor] Action execution error: {e}", "error")
            import traceback
            self._log(f"[Executor] Traceback: {traceback.format_exc()}", "error")
            # Create a failed action result
            from omg_agent.core.agent.actions import ActionResult
            action_result = ActionResult(
                success=False,
                message=f"Action execution error: {e}"
            )

        # Record in history
        self.history_manager.add_action(
            action=action,
            observation=prompt_app,
            screenshot_base64=screenshot.base64_data,
            user_reply=None,
            raw_thinking=raw_thinking,
            raw_action=raw_action,
        )

        # 更新 summary（用于 gelab 模式的历史压缩）
        if action.summary:
            self._last_summary = action.summary

        # Auto-advance sub-task progress based on action success
        if action_result.success and self.history_manager.task_plan:
            self._try_advance_subtask(action, current_app)

        # Check if finished
        finished = action.action_type in (ActionType.COMPLETE, ActionType.ABORT) or action_result.should_finish

        if finished:
            self._log(f"Task finished: {action_result.message or action.params.get('return', 'Done')}")

        return StepResult(
            success=action_result.success,
            finished=finished,
            action=action,
            action_result=action_result,
            message=action_result.message or action.params.get("return"),
            needs_user_input=action_result.requires_user_input,
            user_prompt=action_result.user_prompt,
            session_id=self._current_session_id,
            step_count=step_num
        )

    def _try_advance_subtask(self, action: Action, current_app: dict[str, str] | None) -> None:
        """
        Try to advance to the next sub-task based on action result.
        
        Uses heuristics to determine if current sub-task is likely complete:
        - LAUNCH action completed and app changed to target
        - Navigation actions (CLICK, SWIPE) that likely achieved goal
        - After several successful actions on same sub-task
        """
        task_plan = self.history_manager.task_plan
        if not task_plan or not task_plan.current_sub_task:
            return
        
        current_sub = task_plan.current_sub_task
        should_advance = False
        
        # Check if this action is likely to complete the current sub-task
        if action.action_type == ActionType.LAUNCH:
            # Check if we launched the target app
            if current_sub.app_target and current_app:
                package_name = current_app.get("packageName", "")
                if current_sub.app_target in package_name or package_name in current_sub.app_target:
                    should_advance = True
                    self._log(f"✓ Sub-task {current_sub.id} completed: {current_sub.description}", "debug")
        
        elif action.action_type in (ActionType.CLICK, ActionType.TYPE):
            # For click/type actions, check if description mentions keywords
            desc_lower = current_sub.description.lower()
            action_keywords = {
                "点击": ActionType.CLICK,
                "输入": ActionType.TYPE,
                "搜索": ActionType.TYPE,
                "发送": ActionType.CLICK,
            }
            for keyword, expected_type in action_keywords.items():
                if keyword in desc_lower and action.action_type == expected_type:
                    # Likely completed this sub-task
                    should_advance = True
                    self._log(f"✓ Sub-task {current_sub.id} likely completed: {current_sub.description}", "debug")
                    break
        
        elif action.action_type == ActionType.BACK or action.action_type == ActionType.HOME:
            # Check if sub-task description mentions returning
            desc_lower = current_sub.description.lower()
            if "返回" in desc_lower or "桌面" in desc_lower:
                should_advance = True
                self._log(f"✓ Sub-task {current_sub.id} completed: {current_sub.description}", "debug")
        
        # Also advance if we've done 3+ actions on the same sub-task (heuristic)
        if not should_advance and self.history_manager._history:
            same_subtask_actions = sum(
                1 for e in self.history_manager._history.entries[-5:]
                if e.sub_task_id == current_sub.id
            )
            if same_subtask_actions >= 3:
                # Consider moving to next sub-task after multiple actions
                should_advance = True
                self._log(f"→ Moving to next sub-task after {same_subtask_actions} actions", "debug")
        
        if should_advance:
            self.history_manager.advance_sub_task()
            if task_plan.current_sub_task:
                self._log(f"📍 Current sub-task: {task_plan.current_sub_task.description}")
                # 提醒剩余步骤
                remaining = len(task_plan.remaining_steps)
                if remaining > 0:
                    self._log(f"⚠️ Remaining {remaining} steps", "info")
    
    def _update_plan_from_screen(self, screen_info: str) -> None:
        """
        根据屏幕状态动态更新任务计划。
        
        检测意外情况并调整计划，如：
        - 需要登录
        - 出现弹窗
        - 页面加载中
        """
        task_plan = self.history_manager.task_plan
        if not task_plan:
            return
        
        # 使用 TaskPlan 的 update_from_observation 方法
        suggestion = task_plan.update_from_observation(screen_info, "")
        if suggestion:
            self._log(f"💡 Plan adjustment: {suggestion}", "info")

    def _auto_reply(self, task: str, question: str) -> str:
        """Auto-generate reply to agent's question using LLM."""
        messages = [
            {
                "role": "user",
                "content": f"""你正在帮助用户完成手机上的任务。
任务是：{task}

手机自动化 Agent 询问：{question}

请提供简短、直接的回答来帮助 Agent 继续执行。
只输出答案，不要解释。"""
            }
        ]

        try:
            response = self.llm_client.request(messages, max_tokens=256, temperature=0.5)
            return response.content.strip()
        except Exception:
            return "请继续执行任务。"

    def reset(self) -> None:
        """Reset agent state for a new task."""
        self.history_manager.reset()
        self._current_session_id = None

    @property
    def context(self) -> list[dict[str, Any]]:
        """Get current conversation history as list of dicts."""
        if self.history_manager._history is None:
            return []
        return [
            {
                "step": e.step,
                "action": e.action.to_dict(),
                "observation": e.observation,
                "user_reply": e.user_reply,
            }
            for e in self.history_manager._history.entries
        ]

    @property
    def step_count(self) -> int:
        """Get current step count."""
        return self.history_manager.step_count

    @property
    def current_session(self) -> str | None:
        """Get current session ID."""
        return self._current_session_id
