"""
History Manager - Manage conversation history with robust context and loop detection.

Key features:
- Generates multi-turn chat messages for LLM context (User -> Assistant -> User...)
- Detects and prevents action loops
- Handles image optimization (strips old screenshots)
- Supports task planning integration
"""

from dataclasses import dataclass, field
from typing import Any
from datetime import datetime
from collections import Counter

from .actions import Action, ActionType
from .planner import TaskPlan, TaskPlanner, TaskStatus, analyze_task_complexity


@dataclass
class HistoryEntry:
    """Single history entry."""
    step: int
    action: Action
    observation: str  # The screen info/text user saw
    screenshot_base64: str | None = None
    raw_thinking: str | None = None
    raw_action: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    user_reply: str | None = None  # Reply to INFO action
    sub_task_id: int | None = None  # Which sub-task this step belongs to


@dataclass
class ConversationHistory:
    """Full conversation history."""

    task: str
    entries: list[HistoryEntry] = field(default_factory=list)
    qa_history: list[tuple[str, str]] = field(default_factory=list)  # (question, answer) pairs
    task_plan: TaskPlan | None = None  # Task decomposition plan
    output_format: str = "autoglm"  # 'autoglm' or 'step' - for history formatting

    @property
    def step_count(self) -> int:
        """Get current step count."""
        return len(self.entries)

    def add_entry(
        self,
        action: Action,
        observation: str,
        screenshot_base64: str | None = None,
        user_reply: str | None = None,
        raw_thinking: str | None = None,
        raw_action: str | None = None,
    ) -> None:
        """Add new history entry."""
        sub_task_id = None
        if self.task_plan and self.task_plan.current_sub_task:
            sub_task_id = self.task_plan.current_sub_task.id

        entry = HistoryEntry(
            step=self.step_count + 1,
            action=action,
            observation=observation,
            screenshot_base64=screenshot_base64,
            user_reply=user_reply,
            raw_thinking=raw_thinking,
            raw_action=raw_action,
            sub_task_id=sub_task_id
        )
        self.entries.append(entry)

        # Track Q&A history
        if action.action_type == ActionType.INFO and user_reply:
            question = action.params.get("value", "")
            self.qa_history.append((question, user_reply))

    def get_recent_actions(self, n: int = 5) -> list[Action]:
        """Get last n actions."""
        return [e.action for e in self.entries[-n:]]

    def _format_action_for_history(self, action: Action) -> str:
        """Format action in the native model format for history replay."""
        if self.output_format == "step":
            # Tab-separated format for StepGUI
            return self._format_action_step(action)
        else:
            # Function call format for AutoGLM
            return self._format_action_autoglm(action)

    def _format_action_autoglm(self, action: Action) -> str:
        """Format action in AutoGLM function call style."""
        params = action.params.copy()

        # Handle finish/complete
        if action.action_type == ActionType.COMPLETE:
            msg = params.get("return", "任务已完成")
            return f'finish(message="{msg}")'

        if action.action_type == ActionType.ABORT:
            msg = params.get("value", "任务终止")
            return f'finish(message="终止: {msg}")'

        # Map action types to AutoGLM names
        action_name_map = {
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
            ActionType.NOTE: "Note",
        }

        action_name = action_name_map.get(action.action_type, action.action_type.value)
        param_parts = [f'action="{action_name}"']

        # Add parameters based on action type
        if "point" in params:
            param_parts.append(f'element={params["point"]}')
        if "point1" in params:
            param_parts.append(f'start={params["point1"]}')
        if "point2" in params:
            param_parts.append(f'end={params["point2"]}')
        if "value" in params:
            if action.action_type == ActionType.TYPE:
                param_parts.append(f'text="{params["value"]}"')
            elif action.action_type == ActionType.LAUNCH:
                param_parts.append(f'app="{params["value"]}"')
            elif action.action_type == ActionType.WAIT:
                param_parts.append(f'duration="{params["value"]} seconds"')
            else:
                param_parts.append(f'message="{params["value"]}"')

        return f'do({", ".join(param_parts)})'

    def _format_action_step(self, action: Action) -> str:
        """Format action in StepGUI tab-separated style."""
        params = action.params.copy()
        parts = []

        # Handle completion
        if action.action_type == ActionType.COMPLETE:
            return f"action:COMPLETE\treturn:{params.get('return', '任务已完成')}"

        if action.action_type == ActionType.ABORT:
            return f"action:ABORT\tvalue:{params.get('value', '任务终止')}"

        # Map action types
        action_name_map = {
            ActionType.CLICK: "CLICK",
            ActionType.SWIPE: "SLIDE",
            ActionType.TYPE: "TYPE",
            ActionType.BACK: "BACK",
            ActionType.HOME: "HOME",
            ActionType.LAUNCH: "AWAKE",
            ActionType.WAIT: "WAIT",
            ActionType.INFO: "INFO",
            ActionType.LONG_PRESS: "LONGPRESS",
        }

        action_name = action_name_map.get(action.action_type, action.action_type.value)
        parts.append(f"action:{action_name}")

        # Add parameters
        if "point" in params:
            p = params["point"]
            parts.append(f"point:{p[0]},{p[1]}")
        if "point1" in params and "point2" in params:
            p1, p2 = params["point1"], params["point2"]
            parts.append(f"point1:{p1[0]},{p1[1]}")
            parts.append(f"point2:{p2[0]},{p2[1]}")
        if "value" in params:
            parts.append(f"value:{params['value']}")

        return "\t".join(parts)

    def to_messages(self, max_history: int = 10) -> list[dict[str, Any]]:
        """
        Convert history to list of messages for LLM.

        Structure:
        User: Task + (Summary if truncated)
        User: Step 1 Observation (Image removed)
        Assistant: Step 1 Action (in native format)
        ...
        User: Step N Observation (Image removed)
        Assistant: Step N Action (in native format)
        """
        from .llm import MessageBuilder

        messages = []

        # Determine start index for history
        start_idx = max(0, len(self.entries) - max_history)

        for i, entry in enumerate(self.entries[start_idx:]):
            # User Message (Observation)
            content = entry.observation
            if i == 0 and start_idx > 0:
                content = f"Task: {self.task}\n\n[Previous steps truncated...]\n\n{content}"
            elif i == 0:
                content = f"Task: {self.task}\n\n{content}"

            messages.append(MessageBuilder.create_user_message(
                text=content,
                image_base64=None  # Old history has no image
            ))

            # Assistant Message (Action in native format)
            assistant_content = ""
            if entry.action.thinking:
                if self.output_format == "step":
                    assistant_content += f"<THINK>{entry.action.thinking}</THINK>\n"
                else:
                    assistant_content += f"<think>{entry.action.thinking}</think>\n"

            # Use native format instead of JSON
            if self.output_format == "step":
                # StepGUI format
                action_str = self._format_action_step(entry.action)
                if entry.action.explanation:
                    action_str = f"explain:{entry.action.explanation}\t{action_str}"
                if entry.action.summary:
                    action_str += f"\tsummary:{entry.action.summary}"
                assistant_content += action_str
            else:
                # AutoGLM format
                action_str = self._format_action_autoglm(entry.action)
                assistant_content += f"<answer>{action_str}</answer>"

            messages.append(MessageBuilder.create_assistant_message(assistant_content))

            # Add user reply if this step had one (After the action)
            if entry.user_reply:
                messages.append(MessageBuilder.create_user_message(
                    text=f"User Reply: {entry.user_reply}"
                ))

        return messages


class LoopDetector:
    """Detects and prevents repetitive action loops."""

    def __init__(
        self,
        max_consecutive_same: int = 5,  # 放宽阈值
        max_consecutive_swipes: int = 15,  # 官方允许更多滑动
        max_click_same_point: int = 5,  # 放宽阈值
        point_tolerance: int = 50  # Tolerance for "same" point (in 0-1000 coords)
    ):
        self.max_consecutive_same = max_consecutive_same
        self.max_consecutive_swipes = max_consecutive_swipes
        self.max_click_same_point = max_click_same_point
        self.point_tolerance = point_tolerance

    def check_loop(self, entries: list[HistoryEntry]) -> tuple[bool, str]:
        """
        Check if we're in a loop pattern.

        Returns:
            Tuple of (is_looping, warning_message)
        """
        if len(entries) < 3:
            return False, ""

        # 只检测严重的循环（完全相同的操作重复多次）
        # 滑动操作不算循环，因为滑动查找是正常行为

        # Check: Exact same action repeated (including params) - 但排除滑动
        if len(entries) >= 3:
            last_action = entries[-1].action

            # 滑动是正常行为，不检测
            if last_action.action_type == ActionType.SWIPE:
                return False, ""

            prev_action = entries[-2].action
            if self._actions_identical(last_action, prev_action):
                # Check how many times this exact action was repeated
                repeat_count = 1
                for i in range(len(entries) - 2, -1, -1):
                    if self._actions_identical(entries[i].action, last_action):
                        repeat_count += 1
                    else:
                        break
                if repeat_count >= self.max_consecutive_same:
                    return True, f"完全相同的操作重复了 {repeat_count} 次"

        return False, ""
    
    def _are_points_similar(self, points: list) -> bool:
        """Check if all points are within tolerance of each other."""
        if not points:
            return False
        
        base = points[0]
        if not isinstance(base, (list, tuple)) or len(base) < 2:
            return False
            
        for point in points[1:]:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                return False
            if abs(point[0] - base[0]) > self.point_tolerance or abs(point[1] - base[1]) > self.point_tolerance:
                return False
        return True
    
    def _actions_identical(self, a1: Action, a2: Action) -> bool:
        """Check if two actions are functionally identical."""
        if a1.action_type != a2.action_type:
            return False
        
        # Compare key params based on action type
        if a1.action_type == ActionType.CLICK:
            p1 = a1.params.get("point")
            p2 = a2.params.get("point")
            if p1 and p2:
                return (abs(p1[0] - p2[0]) <= self.point_tolerance and 
                        abs(p1[1] - p2[1]) <= self.point_tolerance)
        elif a1.action_type == ActionType.TYPE:
            return a1.params.get("value") == a2.params.get("value")
        elif a1.action_type == ActionType.SWIPE:
            p1_start = a1.params.get("point1")
            p1_end = a1.params.get("point2")
            p2_start = a2.params.get("point1")
            p2_end = a2.params.get("point2")
            if p1_start and p1_end and p2_start and p2_end:
                return (self._are_points_similar([p1_start, p2_start]) and
                        self._are_points_similar([p1_end, p2_end]))
        elif a1.action_type in (ActionType.BACK, ActionType.HOME, ActionType.WAIT):
            return True  # These are always "same"
        
        return a1.params == a2.params


class HistoryManager:
    """
    Manages conversation history with robust context handling and loop detection.

    Includes:
    - Chat-based history for multi-turn context
    - Loop detection and prevention
    - Task planning integration
    - Efficient context compression
    """

    def __init__(
        self,
        max_history_steps: int = 8,  # Reduced for efficiency
        use_task_planning: bool = False,  # Default to False for official protocol compatibility
        output_format: str = "autoglm"  # 'autoglm' or 'step'
    ):
        """
        Initialize history manager.

        Args:
            max_history_steps: Max number of past steps to include in context
            use_task_planning: Whether to use task planning for complex tasks
                NOTE: Set to False when using official AutoGLM/gelab-zero protocols
                to ensure 100% compatibility with official implementation.
            output_format: Format for history messages ('autoglm' or 'step')
        """
        self.max_history_steps = max_history_steps
        self.use_task_planning = use_task_planning
        self.output_format = output_format
        self._history: ConversationHistory | None = None
        self.loop_detector = LoopDetector()

    def start_task(self, task: str, llm_client: Any = None, output_format: str | None = None) -> TaskPlan | None:
        """
        Start tracking a new task.

        Args:
            task: The task description
            llm_client: Optional LLM client for complex task planning
            output_format: Override output format ('autoglm' or 'step')

        Returns:
            TaskPlan if planning was used, None otherwise
        """
        # Use provided format or default
        fmt = output_format or self.output_format
        self._history = ConversationHistory(task=task, output_format=fmt)

        # Analyze task complexity and create plan if needed
        if self.use_task_planning:
            complexity = analyze_task_complexity(task)
            if complexity["is_complex"]:
                # Use LLM for complex tasks if available
                plan = TaskPlanner.create_plan(
                    task,
                    use_llm=(llm_client is not None),
                    llm_client=llm_client
                )
                self._history.task_plan = plan
                # Mark first task as in progress
                if plan.sub_tasks:
                    plan.sub_tasks[0].status = TaskStatus.IN_PROGRESS
                return plan

        return None

    def set_output_format(self, fmt: str) -> None:
        """Set output format for history formatting."""
        self.output_format = fmt
        if self._history:
            self._history.output_format = fmt

    def add_action(
        self,
        action: Action,
        observation: str,
        screenshot_base64: str | None = None,
        user_reply: str | None = None,
        raw_thinking: str | None = None,
        raw_action: str | None = None,
    ) -> None:
        """Record an action."""
        if self._history is None:
            raise RuntimeError("No task started. Call start_task() first.")
        self._history.add_entry(
            action=action,
            observation=observation,
            screenshot_base64=screenshot_base64,
            user_reply=user_reply,
            raw_thinking=raw_thinking,
            raw_action=raw_action,
        )
    
    def advance_sub_task(self) -> bool:
        """
        Mark current sub-task as complete and move to next.
        
        Returns:
            True if there are more sub-tasks, False if all done
        """
        if self._history and self._history.task_plan:
            self._history.task_plan.mark_current_complete()
            # Mark next as in progress
            if self._history.task_plan.current_sub_task:
                self._history.task_plan.current_sub_task.status = TaskStatus.IN_PROGRESS
                return True
            return False
        return True  # No plan, assume not complete

    def check_loop(self) -> tuple[bool, str]:
        """Check if we're stuck in a loop."""
        if self._history is None or not self._history.entries:
            return False, ""
        return self.loop_detector.check_loop(self._history.entries)

    def get_summary(self) -> str:
        """Get text summary of recent actions (backward compatibility/logging)."""
        if self._history is None or not self._history.entries:
            return ""
        
        lines = []
        for entry in self._history.entries[-5:]:
            lines.append(f"Step {entry.step}: {entry.action.action_type.value}")
        return "\n".join(lines)

    def get_recent_actions(self, n: int = 5) -> list[Action]:
        """Get recent actions."""
        if self._history is None:
            return []
        return self._history.get_recent_actions(n)
    
    def get_last_action(self) -> Action | None:
        """Get the very last action."""
        actions = self.get_recent_actions(1)
        return actions[0] if actions else None

    def get_action_summary_for_prompt(self, lang: str = "zh") -> str:
        """Generate a summary of recent actions for inclusion in the prompt."""
        if self._history is None or not self._history.entries:
            return ""
        
        recent = self._history.entries[-self.max_history_steps:]
        
        if lang == "zh":
            lines = ["### 已执行的操作："]
            for entry in recent:
                action = entry.action
                action_str = f"步骤 {entry.step}: {action.action_type.value}"
                if action.params:
                    if "point" in action.params:
                        action_str += f" @ {action.params['point']}"
                    if "value" in action.params:
                        val = str(action.params['value'])[:30]
                        action_str += f" [{val}]"
                lines.append(action_str)
            
            # Add loop warning if detected
            is_loop, loop_msg = self.check_loop()
            if is_loop:
                lines.append(f"\n⚠️ **警告**：{loop_msg}")
        else:
            lines = ["### Executed Actions:"]
            for entry in recent:
                action = entry.action
                action_str = f"Step {entry.step}: {action.action_type.value}"
                if action.params:
                    if "point" in action.params:
                        action_str += f" @ {action.params['point']}"
                    if "value" in action.params:
                        val = str(action.params['value'])[:30]
                        action_str += f" [{val}]"
                lines.append(action_str)
            
            is_loop, loop_msg = self.check_loop()
            if is_loop:
                lines.append(f"\n⚠️ **Warning**: {loop_msg}")
        
        return "\n".join(lines)

    @property
    def step_count(self) -> int:
        """Get current step count."""
        if self._history is None:
            return 0
        return self._history.step_count
        
    @property
    def task(self) -> str | None:
        """Get current task."""
        if self._history is None:
            return None
        return self._history.task
    
    @property
    def task_plan(self) -> TaskPlan | None:
        """Get current task plan."""
        if self._history is None:
            return None
        return self._history.task_plan

    def reset(self) -> None:
        """Reset history."""
        self._history = None

    def build_context_messages(
        self,
        system_prompt: str,
        current_screenshot_b64: str,
        current_app: dict[str, str] | None = None,
        lang: str = "zh"
    ) -> list[dict[str, Any]]:
        """
        Build messages for LLM context.
        与官方Open-AutoGLM 100%一致的消息格式。

        Structure:
        1. System Message (prompt)
        2. [First Step] User: task + screen_info + screenshot
        3. [First Step] Assistant: <think>...</think><answer>...</answer>
        4. [Step N] User: screen_info + screenshot (image removed after response)
        5. [Step N] Assistant: <think>...</think><answer>...</answer>
        6. [Current] User: screen_info + screenshot
        """
        import json
        from .llm import MessageBuilder

        # Special handling for Gelab/Step Protocol (Single Turn with Summary)
        if self.output_format == "step":
            # Gelab-Zero logic: Everything is in one User message
            user_content = []
            
            # 1. Task Definition (System Prompt)
            # Gelab includes the definition in the user message
            user_content.append({"type": "text", "text": system_prompt})
            
            # 2. Status & History Summary
            summary_history = "暂无历史操作"
            if self._history and self._history.entries:
                last_entry = self._history.entries[-1]
                if last_entry.action.summary:
                    summary_history = last_entry.action.summary
            
            status_text = f"已知用户指令为：{self.task}\n已知已经执行过的历史动作如下：{summary_history}\n当前手机屏幕截图如下：\n"
            user_content.append({"type": "text", "text": status_text})
            
            # 3. Current Screenshot
            user_content.append({"type": "image_url", "image_url": {"url": current_screenshot_b64}})
            
            # 4. Post-Image Instruction
            post_text = """
在执行操作之前，请务必回顾你的历史操作记录和限定的动作空间，先进行思考和解释然后输出动作空间和对应的参数：
1. 思考（THINK）：在 <THINK> 和 </THINK> 标签之间。
2. 解释（explain）：在动作格式中，使用 explain: 开头，简要说明当前动作的目的和执行方式。
3. 总结（summary）：在动作格式中，使用 summary: 开头，更新当前步骤后的历史总结。
在执行完操作后，请输出执行完当前步骤后的新历史总结。
输出格式示例：
<THINK> 思考的内容 </THINK>
explain:解释的内容\taction:动作空间和对应的参数\tsummary:执行完当前步骤后的新历史总结
"""
            user_content.append({"type": "text", "text": post_text})
            
            return [{"role": "user", "content": user_content}]

        # Standard AutoGLM Logic (Multi-turn Chat)
        messages = []

        # 1. System Message
        messages.append(MessageBuilder.create_system_message(system_prompt))

        # 2. 历史消息 - 与官方格式一致
        if self._history and self._history.entries:
            for i, entry in enumerate(self._history.entries):
                # User Message (Observation) - 图片已移除
                if i == 0:
                    # 第一步包含任务
                    screen_info = json.dumps({"current_app": entry.observation}, ensure_ascii=False)
                    text_content = f"{self.task}\n\n{screen_info}"
                else:
                    # 后续步骤
                    screen_info = json.dumps({"current_app": entry.observation}, ensure_ascii=False)
                    text_content = f"** Screen Info **\n\n{screen_info}"

                # 历史消息不包含图片（已移除）
                messages.append({"role": "user", "content": [{"type": "text", "text": text_content}]})

                # Assistant Message - 与官方 Open-AutoGLM 格式一致
                thinking = entry.raw_thinking if entry.raw_thinking is not None else (entry.action.thinking or "")
                
                if self.output_format == "step":
                    # Fallback if step used in chat mode (shouldn't happen with above if)
                    action_str = self._history._format_action_step(entry.action)
                    if thinking:
                        assistant_content = f"<THINK>{thinking}</THINK>\n{action_str}"
                    else:
                        assistant_content = action_str
                else:
                    # AutoGLM: always include <think> and no extra newline (matches phone_agent/agent.py)
                    action_str = entry.raw_action if entry.raw_action is not None else self._history._format_action_autoglm(entry.action)
                    assistant_content = f"<think>{thinking}</think><answer>{action_str}</answer>"

                messages.append(MessageBuilder.create_assistant_message(assistant_content))

        # 3. 当前步骤的User消息（包含截图）
        if current_app:
            screen_info = json.dumps({"current_app": current_app.get("package", "unknown")}, ensure_ascii=False)
        else:
            screen_info = json.dumps({"current_app": "unknown"}, ensure_ascii=False)

        if not self._history or not self._history.entries:
            # 第一步
            text_content = f"{self.task}\n\n{screen_info}"
        else:
            # 后续步骤
            text_content = f"** Screen Info **\n\n{screen_info}"

        messages.append(MessageBuilder.create_user_message(
            text=text_content,
            image_base64=current_screenshot_b64
        ))

        return messages
