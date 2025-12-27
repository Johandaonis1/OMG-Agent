"""
Action Parser - Parse LLM output to structured actions.

Supports multiple formats:
1. Tab-separated format (gelab-zero style):
   <THINK>...</THINK>
   explain:xxx  action:CLICK  point:x,y  summary:xxx

2. Function call format (AutoGLM style):
   do(action="Tap", element=[x, y])
   finish(message="...")
"""

import re
import ast
from typing import Any
from collections import OrderedDict

from .space import Action, ActionType


class ActionParser:
    """Parser for converting LLM output to structured actions."""

    # Map from various action names to standardized ActionType
    ACTION_NAME_MAP: dict[str, ActionType] = {
        # Standard names
        "CLICK": ActionType.CLICK,
        "DOUBLE_TAP": ActionType.DOUBLE_TAP,
        "DOUBLE_CLICK": ActionType.DOUBLE_TAP,
        "LONG_PRESS": ActionType.LONG_PRESS,
        "LONGPRESS": ActionType.LONG_PRESS,
        "SWIPE": ActionType.SWIPE,
        "SLIDE": ActionType.SWIPE,
        "SCROLL": ActionType.SWIPE,
        "TYPE": ActionType.TYPE,
        "BACK": ActionType.BACK,
        "HOME": ActionType.HOME,
        "LAUNCH": ActionType.LAUNCH,
        "AWAKE": ActionType.LAUNCH,
        "WAIT": ActionType.WAIT,
        "INFO": ActionType.INFO,
        "COMPLETE": ActionType.COMPLETE,
        "ABORT": ActionType.ABORT,
        "TAKE_OVER": ActionType.TAKE_OVER,
        "Take_over": ActionType.TAKE_OVER,
        "NOTE": ActionType.NOTE,
        # AutoGLM style names
        "Tap": ActionType.CLICK,
        "Double Tap": ActionType.DOUBLE_TAP,
        "Long Press": ActionType.LONG_PRESS,
        "Swipe": ActionType.SWIPE,
        "Type": ActionType.TYPE,
        "Type_Name": ActionType.TYPE,
        "Back": ActionType.BACK,
        "Home": ActionType.HOME,
        "Launch": ActionType.LAUNCH,
        "Wait": ActionType.WAIT,
        "Interact": ActionType.INFO,
        "Call_API": ActionType.NOTE,
    }

    # Legacy function-call style (non-official, kept for robustness / backward compatibility)
    _LEGACY_ACTION_NAMES: tuple[str, ...] = (
        "CLICK",
        "DOUBLE_TAP",
        "LONG_PRESS",
        "SWIPE",
        "TYPE",
        "BACK",
        "HOME",
        "LAUNCH",
        "WAIT",
        "INFO",
        "COMPLETE",
        "ABORT",
        "TAKE_OVER",
    )

    @classmethod
    def parse(cls, response: str) -> Action | None:
        """
        Parse LLM response to Action.

        Auto-detects format and delegates to appropriate parser.
        """
        response = response.strip()

        # Extract thinking from <think>/<THINK> tags first
        thinking = ""
        action_content = response

        # Handle <think>...</think> tags (AutoGLM format)
        import re
        think_match = re.search(r"<[Tt][Hh][Ii][Nn][Kk]>(.*?)</[Tt][Hh][Ii][Nn][Kk]>", response, re.DOTALL)
        if think_match:
            thinking = think_match.group(1).strip()

        # Extract content from <answer>...</answer> tags if present (AutoGLM format)
        answer_match = re.search(r"<[Aa][Nn][Ss][Ww][Ee][Rr]>(.*?)</[Aa][Nn][Ss][Ww][Ee][Rr]>", response, re.DOTALL)
        if answer_match:
            action_content = answer_match.group(1).strip()
        else:
            # Remove thinking tags from content
            action_content = re.sub(r"<[Tt][Hh][Ii][Nn][Kk]>.*?</[Tt][Hh][Ii][Nn][Kk]>", "", response, flags=re.DOTALL).strip()

        # Try AutoGLM function call format (scan for keywords)
        if "finish(message=" in action_content:
            full_call = cls._extract_balanced_call(action_content, "finish(message=")
            if full_call:
                action = cls._parse_function_call(full_call)
                if thinking:
                    action.thinking = thinking
                return action

        if "do(action=" in action_content:
            full_call = cls._extract_balanced_call(action_content, "do(action=")
            if full_call:
                action = cls._parse_function_call(full_call)
                if thinking:
                    action.thinking = thinking
                return action

        # Legacy format: CLICK(500,300), TYPE("text"), etc.
        legacy_call = cls._extract_legacy_call(action_content)
        if legacy_call:
            action = cls._parse_legacy_call(legacy_call)
            if action:
                if thinking:
                    action.thinking = thinking
                return action

        # Tab-separated format (gelab-zero / step-gui style)
        try:
            action = cls._parse_tab_format(action_content)
        except ValueError:
            return None

        if thinking and not action.thinking:
            action.thinking = thinking
        return action

    @staticmethod
    def _extract_balanced_call(text: str, start_marker: str) -> str | None:
        """Extract balanced function call starting with marker."""
        start = text.find(start_marker)
        if start == -1:
            return None
        
        count = 0
        in_string = False
        string_char = None
        escape = False
        
        for i, char in enumerate(text[start:], start):
            if in_string:
                if escape:
                    escape = False
                elif char == '\\':
                    escape = True
                elif char == string_char:
                    in_string = False
            else:
                if char in ('"', "'"):
                    in_string = True
                    string_char = char
                elif char == '(':
                    count += 1
                elif char == ')':
                    count -= 1
                    if count == 0:
                        return text[start:i+1]
        return None  # Malformed or incomplete

    @staticmethod
    def _extract_balanced_call_at(text: str, start: int) -> str | None:
        """Extract balanced function call starting at index `start`."""
        if start < 0 or start >= len(text):
            return None

        count = 0
        in_string = False
        string_char = None
        escape = False

        for i, char in enumerate(text[start:], start):
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == string_char:
                    in_string = False
            else:
                if char in ('"', "'"):
                    in_string = True
                    string_char = char
                elif char == "(":
                    count += 1
                elif char == ")":
                    count -= 1
                    if count == 0:
                        return text[start : i + 1]
        return None

    @classmethod
    def _extract_legacy_call(cls, text: str) -> str | None:
        """Extract legacy ACTION(...) call from text (returns last match)."""
        if not text:
            return None

        # Prefer the last action call in the text (often the actual output).
        pattern = r"\b(" + "|".join(map(re.escape, cls._LEGACY_ACTION_NAMES)) + r")\s*\("
        matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
        for m in reversed(matches):
            call = cls._extract_balanced_call_at(text, m.start())
            if call:
                return call.strip()
        return None

    @classmethod
    def _parse_legacy_call(cls, call: str) -> Action | None:
        """Parse legacy ACTION(...) syntax into an Action."""
        call = call.strip()
        m = re.match(r"^([A-Za-z_]+)\s*\((.*)\)\s*$", call, flags=re.DOTALL)
        if not m:
            return None

        name = m.group(1).strip()
        args_str = m.group(2).strip()

        # Parse args safely with AST.
        try:
            if args_str == "":
                args = ()
            else:
                parsed = ast.literal_eval(f"({args_str})")
                args = parsed if isinstance(parsed, tuple) else (parsed,)
        except Exception:
            return None

        action_name = name.upper()
        try:
            action_type = cls._normalize_action_type(action_name)
        except ValueError:
            return None

        params: dict[str, Any] = {}

        try:
            if action_type == ActionType.CLICK:
                x, y = int(args[0]), int(args[1])
                params["point"] = [x, y]
                if len(args) >= 3 and isinstance(args[2], str) and args[2].strip():
                    params["message"] = args[2]
            elif action_type == ActionType.DOUBLE_TAP:
                x, y = int(args[0]), int(args[1])
                params["point"] = [x, y]
            elif action_type == ActionType.LONG_PRESS:
                x, y = int(args[0]), int(args[1])
                params["point"] = [x, y]
                if len(args) >= 3:
                    params["duration"] = args[2]
            elif action_type == ActionType.SWIPE:
                x1, y1, x2, y2 = (int(args[0]), int(args[1]), int(args[2]), int(args[3]))
                params["point1"] = [x1, y1]
                params["point2"] = [x2, y2]
            elif action_type == ActionType.TYPE:
                params["value"] = str(args[0]) if args else ""
            elif action_type == ActionType.LAUNCH:
                params["value"] = str(args[0]) if args else ""
            elif action_type == ActionType.WAIT:
                params["value"] = args[0] if args else 1
            elif action_type == ActionType.INFO:
                params["value"] = str(args[0]) if args else ""
            elif action_type == ActionType.COMPLETE:
                if args:
                    params["return"] = str(args[0])
            elif action_type == ActionType.ABORT:
                if args:
                    params["value"] = str(args[0])
            elif action_type == ActionType.TAKE_OVER:
                if args:
                    params["message"] = str(args[0])
        except (IndexError, ValueError, TypeError):
            return None

        return Action(action_type=action_type, params=params)

    @classmethod
    def _parse_tab_format(cls, response: str) -> Action:
        """
        Parse tab-separated format:
        <THINK>...</THINK>
        explain:xxx  action:CLICK  point:x,y  summary:xxx
        """
        # Align with gelab-zero `Parser0920Summary.str2action` parsing behavior:
        # - Normalize THINK tags
        # - Split key/value pairs strictly by TAB
        response = cls._normalize_think_tags(response).strip()

        try:
            thinking = response.split("<THINK>")[1].split("</THINK>")[0].strip()
            kv_part = response.split("</THINK>")[1].strip()
        except IndexError:
            kv_part = response
            thinking = ""

        data = OrderedDict()
        data["thinking"] = thinking

        kvs = [kv.strip() for kv in kv_part.split("\t") if kv.strip()]
        for kv in kvs:
            if ":" not in kv:
                continue

            key = kv.split(":", 1)[0].strip()
            value = kv.split(":", 1)[1].strip()

            if key == "action":
                data["action_type"] = cls._normalize_action_type(value)
            elif key == "explain":
                data["explanation"] = value
            elif key == "summary":
                data["summary"] = value
            elif "point" in key:
                data[key] = cls._parse_point(value)
            else:
                # Keep other fields (e.g., value/return) as-is; ActionBuilder will map them.
                data[key] = value

        return cls._build_action(data)

    @classmethod
    def _parse_function_call(cls, response: str) -> Action:
        """
        Parse AutoGLM function call format:
        do(action="Tap", element=[x, y])
        finish(message="...")
        
        Note: response is expected to be a clean function call string.
        """
        response = response.strip()

        if response.startswith("finish("):
            # Handle finish action
            message = ""
            match = re.search(r'message\s*=\s*["\'](.+?)["\']', response)
            if match:
                message = match.group(1)
            return Action(
                action_type=ActionType.COMPLETE,
                params={"return": message}
            )

        # Handle Type action specially (may contain special characters in text)
        if 'action="Type"' in response or 'action="Type_Name"' in response:
            text_match = re.search(r'text\s*=\s*["\'](.+?)["\'](?:\s*\))?$', response)
            if text_match:
                text = text_match.group(1)
                return Action(
                    action_type=ActionType.TYPE,
                    params={"value": text}
                )

        # Use AST for safe parsing
        try:
            tree = ast.parse(response, mode="eval")
            if not isinstance(tree.body, ast.Call):
                raise ValueError("Expected function call")

            call = tree.body
            data: dict[str, Any] = {}
            duration_value: Any | None = None

            for keyword in call.keywords:
                key = keyword.arg
                value = ast.literal_eval(keyword.value)

                if key == "action":
                    data["action_type"] = cls._normalize_action_type(value)
                elif key == "element":
                    data["point"] = value
                elif key == "start":
                    data["point1"] = value
                elif key == "end":
                    data["point2"] = value
                elif key == "text":
                    data["value"] = value
                elif key == "app":
                    data["value"] = value
                elif key == "duration":
                    duration_value = value
                elif key == "message":
                    # AutoGLM: do(action="Tap", ..., message="...") uses `message` for sensitive confirmation.
                    data["message"] = value
                else:
                    data[key] = value

            if duration_value is not None:
                action_type = data.get("action_type")
                if action_type == ActionType.WAIT:
                    # AutoGLM uses duration="N seconds"; keep both for compatibility.
                    data["duration"] = duration_value
                    data["value"] = duration_value
                else:
                    data["duration"] = duration_value

            return cls._build_action(data)

        except (SyntaxError, ValueError) as e:
            raise ValueError(f"Failed to parse function call: {e}")

    @classmethod
    def _normalize_think_tags(cls, text: str) -> str:
        """Normalize various THINK tag formats."""
        # Fix common typos and case variations
        text = text.replace("<TINK>", "<THINK>").replace("</TINK>", "</THINK>")
        text = text.replace("<think>", "<THINK>").replace("</think>", "</THINK>")
        # Fix spacing issues
        text = re.sub(r"<\s*/?THINK\s*>", lambda m: "<THINK>" if "/" not in m.group() else "</THINK>", text, flags=re.IGNORECASE)
        return text

    @classmethod
    def _normalize_action_type(cls, action_name: str) -> ActionType:
        """Convert action name string to ActionType enum."""
        action_name = action_name.strip()

        # Direct lookup
        if action_name in cls.ACTION_NAME_MAP:
            return cls.ACTION_NAME_MAP[action_name]

        # Case-insensitive lookup
        upper_name = action_name.upper()
        for key, value in cls.ACTION_NAME_MAP.items():
            if key.upper() == upper_name:
                return value

        # Try to match ActionType directly
        try:
            return ActionType(upper_name)
        except ValueError:
            raise ValueError(f"Unknown action type: {action_name}")

    @classmethod
    def _parse_point(cls, value: str) -> list[int]:
        """Parse point from string 'x,y' or 'x y'."""
        coords = value.replace(",", " ").split()
        if len(coords) < 2:
            raise ValueError(f"Invalid point format: {value}")
        return [int(coords[0]), int(coords[1])]

    @classmethod
    def _build_action(cls, data: dict[str, Any]) -> Action:
        """Build Action object from parsed data."""
        raw_action_type = data.pop("action_type", None)
        if raw_action_type is None:
            raw_action_type = data.pop("action", None)

        if raw_action_type is None:
            raise ValueError("Missing action type")

        action_type = (
            raw_action_type
            if isinstance(raw_action_type, ActionType)
            else cls._normalize_action_type(str(raw_action_type))
        )
        thinking = data.pop("thinking", data.pop("think", data.pop("cot", "")))
        explanation = data.pop("explanation", data.pop("explain", ""))
        summary = data.pop("summary", "")

        return Action(
            action_type=action_type,
            thinking=thinking,
            explanation=explanation,
            summary=summary,
            params=data
        )

    @classmethod
    def to_string(cls, action: Action, format: str = "tab") -> str:
        """
        Convert Action to string format.

        Args:
            action: Action object
            format: "tab" for tab-separated, "function" for function call

        Returns:
            Formatted action string
        """
        if format == "function":
            return cls._to_function_string(action)
        return cls._to_tab_string(action)

    @classmethod
    def _to_tab_string(cls, action: Action) -> str:
        """Convert to tab-separated format."""
        parts = []

        if action.thinking:
            parts.append(f"<THINK>{action.thinking}</THINK>")

        kv_parts = []
        if action.explanation:
            kv_parts.append(f"explain:{action.explanation}")

        kv_parts.append(f"action:{action.action_type.value}")

        # Add params
        for key, value in action.params.items():
            if isinstance(value, list):
                value = ",".join(str(v) for v in value)
            kv_parts.append(f"{key}:{value}")

        if action.summary:
            kv_parts.append(f"summary:{action.summary}")

        parts.append("\t".join(kv_parts))
        return "\n".join(parts)

    @classmethod
    def _to_function_string(cls, action: Action) -> str:
        """Convert to function call format."""
        params = action.params.copy()

        # Map action type back
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
            ActionType.COMPLETE: None,  # Special case
            ActionType.ABORT: None,
        }

        if action.action_type == ActionType.COMPLETE:
            msg = params.get("return", "Task completed")
            return f'finish(message="{msg}")'

        action_name = action_name_map.get(action.action_type, action.action_type.value)

        # Build parameter string
        param_parts = [f'action="{action_name}"']

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
            else:
                param_parts.append(f'value="{params["value"]}"')

        return f'do({", ".join(param_parts)})'
