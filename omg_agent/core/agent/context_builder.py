"""
Context Builder - 上下文构建器

Delegates to `protocol_compat.py` to ensure 100% alignment with official implementations.
"""

from typing import Any

from .device.apps import autoglm_app_name_from_package
from .protocol_compat import ProtocolType, create_adapter

class ContextConfig:
    """上下文构建配置"""

    def __init__(
        self,
        protocol: str = "universal",
        max_history_steps: int = 8,
        use_summary: bool = True,
        lang: str = "zh",
    ):
        self.protocol = protocol
        self.max_history_steps = max_history_steps
        self.use_summary = use_summary
        self.lang = lang


class ContextBuilder:
    """
    上下文构建器 - 代理到 protocol_compat.py
    """

    def __init__(self, config: ContextConfig | None = None):
        self.config = config or ContextConfig()
        # Create adapter based on protocol string
        self.adapter = create_adapter(self.config.protocol)

    def build_messages(
        self,
        system_prompt: str,
        task: str,
        current_screenshot_b64: str,
        current_app: dict[str, str] | None = None,
        history_entries: list[Any] | None = None,
        last_summary: str = "",
        qa_history: list[tuple[str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        构建消息
        """
        # Obtain the specific builder from adapter
        # Note: We pass task here because AutoGLM builder needs it in __init__
        # But Gelab builder needs it in build_messages (sometimes)
        builder = self.adapter.get_context_builder(task=task, system_prompt=system_prompt)

        if self.config.protocol == "autoglm":
            # AutoGLM: Adapter returns AutoGLMContextBuilder
            # We need to adapt the arguments to build_step_messages OR build_initial_messages
            
            # Map history entries
            # Expecting history_entries to be list of HistoryEntry objects from history.py
            # AutoGLMContextBuilder expects list of dicts: {'app': str, 'think': str, 'action': str}
            
            mapped_history = []
            if history_entries:
                formatter = self.adapter.get_message_formatter()
                for entry in history_entries:
                    # 获取 thinking (prioritize raw)
                    think = entry.raw_thinking or (entry.action.thinking if entry.action else "")
                    
                    # 获取 action string (prioritize raw)
                    if entry.raw_action:
                        action_str = entry.raw_action
                    else:
                        # Reconstruct action string using format_action
                        # This requires unpacking Action params.
                        # Ideally HistoryEntry should strictly store raw_action for AutoGLM.
                        # If not, we try to format it.
                        action_obj = entry.action
                        if action_obj:
                            # format_action expects type string and kwargs
                            # ActionType value is e.g. "CLICK", "TYPE"...
                            # But formatter.format_action maps "CLICK" -> "Tap" etc.
                            # We pass the enum value string "CLICK"
                            action_str = formatter.format_action(
                                action_obj.action_type.name, # Use name like "CLICK"
                                **action_obj.params
                            )
                            # Remove "do()" wrapper if raw_action usually contains it?
                            # AutoGLMMessageFormatter.format_action returns "do(...)" or "finish(...)"
                            # AutoGLMContextBuilder expects raw action string to put inside <answer>
                            # Yes, it expects "do(...)"
                        else:
                            action_str = "pass"

                    mapped_history.append({
                        "app": entry.observation, # Observation in history is app name/package
                        "think": think,
                        "action": action_str
                    })

            pkg = current_app.get("package", "unknown") if current_app else "unknown"
            app_str = autoglm_app_name_from_package(pkg)

            if not mapped_history:
                return builder.build_initial_messages(current_screenshot_b64, app_str)
            else:
                return builder.build_step_messages(mapped_history, current_screenshot_b64, app_str)

        elif self.config.protocol == "gelab":
            # Gelab: Adapter returns GelabContextBuilder
            # build_messages(self, system_prompt, task, current_screenshot_b64, current_app, history_entries, last_summary, qa_history)
            
            # GelabContextBuilder.build_messages args from protocol_compat.py:
            # (system_prompt, task, current_screenshot_b64, current_app, history_entries, last_summary, qa_history)
            # Note: history_entries for GelabContextBuilder are expected to be?
            # protocol_compat: "history_entries: list[dict]" -> used in history_display logic? 
            # Wait, my logic in GelabContextBuilder.build_messages (protocol_compat.py) 
            # DOES NOT USE history_entries directly! 
            # It uses `last_summary` and `qa_history`.
            # Original Gelab `env2messages4ask` only uses summary for history.
            # So passing history_entries is actually not needed for Gelab logic as per my implementation in Step 37.
            
            return builder.build_messages(
                system_prompt=system_prompt,
                task=task,
                current_screenshot_b64=current_screenshot_b64,
                current_app=current_app.get("package", "unknown") if current_app else "unknown",
                history_entries=[], # Ignored by GelabContextBuilder in compat
                last_summary=last_summary,
                qa_history=qa_history
            )

        elif self.config.protocol == "universal":
            # Universal: Use UniversalContextBuilder (JSON-enhanced, AutoGLM-like multi-turn context).
            # Unlike gelab, UniversalContextBuilder expects history_entries to reconstruct context.
            mapped_history: list[dict[str, Any]] = []
            if history_entries:
                formatter = self.adapter.get_message_formatter()

                # Respect configured history limit to avoid runaway context.
                recent_entries = history_entries[-self.config.max_history_steps :]
                for entry in recent_entries:
                    think = entry.raw_thinking or (entry.action.thinking if entry.action else "")

                    if entry.raw_action:
                        action_str = entry.raw_action
                    else:
                        action_obj = entry.action
                        if action_obj:
                            action_str = formatter.format_action(
                                action_obj.action_type.name,
                                **action_obj.params,
                            )
                        else:
                            action_str = ""

                    # Pull any structured fields from the Action params (universal JSON protocol).
                    params = entry.action.params if entry.action else {}
                    mapped_history.append(
                        {
                            "app": entry.observation,
                            "think": think,
                            "action": entry.action.to_dict() if entry.action else action_str,
                            "summary": getattr(entry.action, "summary", "") if entry.action else "",
                            "observation": params.get("observation", ""),
                            "reflection": params.get("reflection", ""),
                            "progress": params.get("progress", {}),
                        }
                    )

            app_str = current_app.get("package", "unknown") if current_app else "unknown"
            if not mapped_history:
                return builder.build_initial_messages(current_screenshot_b64, app_str)
            return builder.build_step_messages(mapped_history, current_screenshot_b64, app_str)

        else:
            # Fallback to Universal (defaults to Gelab logic in ProtocolAdapter universal)
            # But let's check what protocol_compat says about universal
            # ProtocolAdapter(ProtocolType.UNIVERSAL) -> GelabContextBuilder
            
            return builder.build_messages(
                system_prompt=system_prompt,
                task=task,
                current_screenshot_b64=current_screenshot_b64,
                current_app=current_app.get("package", "unknown") if current_app else "unknown",
                history_entries=[],
                last_summary=last_summary,
                qa_history=qa_history
            )


def get_context_builder(protocol: str = "universal", **kwargs) -> ContextBuilder:
    """获取上下文构建器"""
    config = ContextConfig(protocol=protocol, **kwargs)
    return ContextBuilder(config)
