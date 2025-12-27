"""
Action Handler - Execute actions on Android device.

Supports multiple execution backends:
1. Direct ADB commands
2. MCP tools (if available)

Supports multiple input methods:
1. YADB (GeLab-Zero style) - requires yadb installed on device
2. ADB Keyboard (AutoGLM style) - requires ADB Keyboard app
3. Fallback to standard adb input text
"""

import time
import base64
import subprocess
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
from typing import Any, Callable, Protocol, Optional

from .space import Action, ActionType, Point, Direction


class InputMethod(Enum):
    """Text input method for Android devices."""
    YADB = "yadb"                    # GeLab-Zero style: YADB library
    ADB_KEYBOARD = "adb_keyboard"    # AutoGLM style: ADB Keyboard with Base64
    ADB_INPUT = "adb_input"          # Standard adb shell input text (ASCII only)
    AUTO = "auto"                    # Auto-detect best method


@dataclass
class ActionResult:
    """Result of action execution."""
    success: bool
    should_finish: bool
    message: str | None = None
    requires_user_input: bool = False
    user_prompt: str | None = None  # For INFO action


class DeviceExecutor(Protocol):
    """Protocol for device execution backends."""

    def tap(self, x: int, y: int) -> bool: ...
    def double_tap(self, x: int, y: int) -> bool: ...
    def long_press(self, x: int, y: int, duration_ms: int) -> bool: ...
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> bool: ...
    def type_text(self, text: str) -> bool: ...
    def press_back(self) -> bool: ...
    def press_home(self) -> bool: ...
    def launch_app(self, app_name: str) -> bool: ...
    def get_screen_size(self) -> tuple[int, int]: ...


class ADBExecutor:
    """
    ADB-based device executor.

    Supports multiple text input methods:
    - YADB: GeLab-Zero official method, requires yadb on device
    - ADB_KEYBOARD: AutoGLM official method, requires ADB Keyboard app
    - ADB_INPUT: Standard adb input (ASCII only)
    """

    # Timing configuration (seconds) - aligned with Open-AutoGLM defaults
    KEYBOARD_SWITCH_DELAY = 1.0
    TEXT_CLEAR_DELAY = 1.0
    TEXT_INPUT_DELAY = 1.0
    KEYBOARD_RESTORE_DELAY = 1.0

    # Device operation delays (seconds) - aligned with Open-AutoGLM `TIMING_CONFIG.device`
    DEFAULT_TAP_DELAY = 1.0
    DEFAULT_DOUBLE_TAP_DELAY = 1.0
    DOUBLE_TAP_INTERVAL = 0.1
    DEFAULT_LONG_PRESS_DELAY = 1.0
    DEFAULT_SWIPE_DELAY = 1.0
    DEFAULT_BACK_DELAY = 1.0
    DEFAULT_HOME_DELAY = 1.0
    DEFAULT_LAUNCH_DELAY = 1.0

    def __init__(
        self,
        device_id: str | None = None,
        logger: Callable[[str], None] | None = None,
        input_method: InputMethod = InputMethod.AUTO,
        protocol: str = "auto",
    ):
        self.device_id = device_id
        self.logger = logger
        self.input_method = input_method
        self.protocol = (protocol or "auto").lower()
        self._adb_prefix = f"adb -s {device_id}" if device_id else "adb"
        self._adb_prefix_list = ["adb", "-s", device_id] if device_id else ["adb"]
        self._cached_input_method: InputMethod | None = None

    def _should_sleep_after_device_action(self) -> bool:
        return self.protocol == "autoglm"

    def _run_command(self, cmd: str, timeout: int = 30) -> tuple[bool, str]:
        """Run ADB command (string) and return (success, output)."""
        if self.logger:
            self.logger(f"[CMD] {cmd}")
        try:
            import sys
            creationflags = 0
            if sys.platform == 'win32':
                creationflags = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=timeout,
                creationflags=creationflags
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)

    def _run_command_list(self, cmd_list: list, timeout: int = 30) -> tuple[bool, str]:
        """Run ADB command (list) and return (success, output)."""
        if self.logger:
            self.logger(f"[CMD] {' '.join(cmd_list)}")
        try:
            import sys
            creationflags = 0
            if sys.platform == 'win32':
                creationflags = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(
                cmd_list,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=timeout,
                creationflags=creationflags
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)

    # ========== Basic device operations ==========

    def _tap_raw(self, x: int, y: int) -> bool:
        cmd = f"{self._adb_prefix} shell input tap {x} {y}"
        success, _ = self._run_command(cmd)
        return success

    def tap(self, x: int, y: int) -> bool:
        success = self._tap_raw(x, y)
        if self._should_sleep_after_device_action():
            time.sleep(self.DEFAULT_TAP_DELAY)
        return success

    def double_tap(self, x: int, y: int) -> bool:
        # Two taps with short interval (Open-AutoGLM style)
        success1 = self._tap_raw(x, y)
        time.sleep(self.DOUBLE_TAP_INTERVAL)
        success2 = self._tap_raw(x, y)
        if self._should_sleep_after_device_action():
            time.sleep(self.DEFAULT_DOUBLE_TAP_DELAY)
        return bool(success1 and success2)

    def long_press(self, x: int, y: int, duration_ms: int = 2000) -> bool:
        # Use swipe with same start/end for long press (standard method)
        # Or use YADB for more reliable long press
        if self._check_yadb_available():
            cmd = f'{self._adb_prefix} shell app_process -Djava.class.path=/data/local/tmp/yadb /data/local/tmp com.ysbing.yadb.Main -touch {x} {y} {duration_ms}'
            success, _ = self._run_command(cmd)
            if self._should_sleep_after_device_action():
                time.sleep(self.DEFAULT_LONG_PRESS_DELAY)
            return success
        else:
            cmd = f"{self._adb_prefix} shell input swipe {x} {y} {x} {y} {duration_ms}"
            success, _ = self._run_command(cmd)
            if self._should_sleep_after_device_action():
                time.sleep(self.DEFAULT_LONG_PRESS_DELAY)
            return success

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 500) -> bool:
        cmd = f"{self._adb_prefix} shell input swipe {x1} {y1} {x2} {y2} {duration_ms}"
        success, _ = self._run_command(cmd)
        if self._should_sleep_after_device_action():
            time.sleep(self.DEFAULT_SWIPE_DELAY)
        return success

    def press_back(self) -> bool:
        cmd = f"{self._adb_prefix} shell input keyevent 4"
        success, _ = self._run_command(cmd)
        if self._should_sleep_after_device_action():
            time.sleep(self.DEFAULT_BACK_DELAY)
        return success

    def press_home(self) -> bool:
        cmd = f"{self._adb_prefix} shell input keyevent 3"
        success, _ = self._run_command(cmd)
        if self._should_sleep_after_device_action():
            time.sleep(self.DEFAULT_HOME_DELAY)
        return success

    def launch_app(self, app_name: str) -> bool:
        from ..device.apps import find_package_name
        package = find_package_name(app_name, protocol=self.protocol)
        if not package:
            return False

        # gelab-zero: reflush_app=True by default (force-stop before launching).
        if self.protocol == "gelab":
            cmd = f"{self._adb_prefix} shell am force-stop {package}"
            self._run_command(cmd)
            time.sleep(1.0)

        cmd = f"{self._adb_prefix} shell monkey -p {package} -c android.intent.category.LAUNCHER 1"
        success, _ = self._run_command(cmd)
        if self._should_sleep_after_device_action():
            time.sleep(self.DEFAULT_LAUNCH_DELAY)
        return success

    def get_screen_size(self) -> tuple[int, int]:
        cmd = f"{self._adb_prefix} shell wm size"
        success, output = self._run_command(cmd)
        if success:
            # Handle both "Physical size:" and "Override size:"
            if "Override size:" in output:
                size_str = output.split("Override size:")[-1].strip().split("\n")[0]
            elif "Physical size:" in output:
                size_str = output.split("Physical size:")[-1].strip().split("\n")[0]
            else:
                if self.logger:
                    self.logger(f"[ScreenSize] Failed to parse: {output}")
                return 1080, 1920
            try:
                w, h = size_str.split("x")
                w, h = int(w.strip()), int(h.strip())
                if self.logger:
                    self.logger(f"[ScreenSize] Detected: {w}x{h}")
                return w, h
            except:
                pass
        if self.logger:
            self.logger(f"[ScreenSize] Failed to detect, using default: 1080x1920")
        return 1080, 1920

    # ========== Text input methods ==========

    def type_text(self, text: str, method: InputMethod | None = None) -> bool:
        """
        Type text using the specified or auto-detected method.

        Args:
            text: Text to input
            method: Input method to use (None = use instance default or auto-detect)

        Returns:
            True if successful
        """
        if not text:
            return True

        method = method or self.input_method

        if method == InputMethod.AUTO:
            method = self._detect_best_input_method()

        if method == InputMethod.YADB:
            return self._type_text_yadb(text)
        elif method == InputMethod.ADB_KEYBOARD:
            return self._type_text_adb_keyboard(text)
        else:
            return self._type_text_adb_input(text)

    def _type_text_yadb(self, text: str) -> bool:
        """
        GeLab-Zero official method: Use YADB library.
        Requires yadb to be installed at /data/local/tmp/yadb on device.
        """
        # Ensure yadb exists (gelab-zero init_device behavior).
        if not self._check_yadb_available():
            self._install_yadb()

        if not self._check_yadb_available():
            # Fallback if we still don't have yadb.
            if self.logger:
                self.logger("[YADB] Not available, falling back to ADB keyboard/input")
            if self._check_adb_keyboard_available():
                return self._type_text_adb_keyboard(text)
            return self._type_text_adb_input(text)

        # Preprocess text for YADB (escape spaces, remove newlines/tabs)
        processed = self._preprocess_text_for_yadb(text)

        # Use YADB keyboard command
        cmd = f'{self._adb_prefix} shell app_process -Djava.class.path=/data/local/tmp/yadb /data/local/tmp com.ysbing.yadb.Main -keyboard "{processed}"'
        success, output = self._run_command(cmd)

        if self.logger:
            self.logger(f"[YADB] Input '{text[:20]}...' -> success={success}")

        return success

    def _type_text_adb_keyboard(self, text: str) -> bool:
        """
        AutoGLM official method: Use ADB Keyboard with Base64 encoding.
        Requires ADB Keyboard app to be installed and enabled.

        Full flow:
        1. Detect current keyboard and switch to ADB Keyboard
        2. Clear existing text
        3. Input new text (Base64 encoded)
        4. Restore original keyboard
        """
        # 1. Switch to ADB Keyboard
        original_ime = self._detect_and_set_adb_keyboard()
        time.sleep(self.KEYBOARD_SWITCH_DELAY)

        # 2. Clear existing text
        self._clear_text_adb_keyboard()
        time.sleep(self.TEXT_CLEAR_DELAY)

        # 3. Input text with Base64 encoding
        encoded = base64.b64encode(text.encode("utf-8")).decode("utf-8")
        cmd_list = self._adb_prefix_list + [
            "shell", "am", "broadcast",
            "-a", "ADB_INPUT_B64",
            "--es", "msg", encoded
        ]
        success, output = self._run_command_list(cmd_list)
        time.sleep(self.TEXT_INPUT_DELAY)

        if self.logger:
            self.logger(f"[ADB_KEYBOARD] Input '{text[:20]}...' -> success={success}")

        # 4. Restore original keyboard
        if original_ime and "adbkeyboard" not in original_ime.lower():
            self._restore_keyboard(original_ime)
            time.sleep(self.KEYBOARD_RESTORE_DELAY)

        return success

    def _type_text_adb_input(self, text: str) -> bool:
        """
        Standard ADB input method. Only works with ASCII characters.
        Falls back to this when YADB and ADB Keyboard are not available.
        """
        # Escape special characters for shell
        escaped = text.replace("'", "'\\''").replace(" ", "%s")
        cmd = f"{self._adb_prefix} shell input text '{escaped}'"
        success, _ = self._run_command(cmd)

        if self.logger:
            self.logger(f"[ADB_INPUT] Input '{text[:20]}...' -> success={success}")

        return success

    # ========== ADB Keyboard helper methods (AutoGLM style) ==========

    def _detect_and_set_adb_keyboard(self) -> str:
        """
        Detect current keyboard and switch to ADB Keyboard if needed.
        Returns the original IME identifier for later restoration.
        """
        # Get current IME
        cmd_list = self._adb_prefix_list + [
            "shell", "settings", "get", "secure", "default_input_method"
        ]
        success, output = self._run_command_list(cmd_list)
        current_ime = output.strip()

        # Switch to ADB Keyboard if not already set
        if "com.android.adbkeyboard/.AdbIME" not in current_ime:
            cmd_list = self._adb_prefix_list + [
                "shell", "ime", "set", "com.android.adbkeyboard/.AdbIME"
            ]
            self._run_command_list(cmd_list)

            # Warm up the keyboard with empty input
            warmup_cmd = self._adb_prefix_list + [
                "shell", "am", "broadcast",
                "-a", "ADB_INPUT_B64",
                "--es", "msg", ""
            ]
            self._run_command_list(warmup_cmd)

        return current_ime

    def _clear_text_adb_keyboard(self) -> bool:
        """Clear text in the currently focused input field using ADB Keyboard."""
        cmd_list = self._adb_prefix_list + [
            "shell", "am", "broadcast",
            "-a", "ADB_CLEAR_TEXT"
        ]
        success, _ = self._run_command_list(cmd_list)
        return success

    def _restore_keyboard(self, ime: str) -> bool:
        """Restore the original keyboard IME."""
        if not ime:
            return True
        cmd_list = self._adb_prefix_list + ["shell", "ime", "set", ime]
        success, _ = self._run_command_list(cmd_list)
        return success

    # ========== YADB helper methods (GeLab-Zero style) ==========

    def _preprocess_text_for_yadb(self, text: str) -> str:
        """
        Preprocess text for YADB input.
        - Replace newlines and tabs with spaces
        - Escape spaces with backslash
        """
        text = text.replace("\n", " ").replace("\t", " ").replace("\r", " ")
        text = text.replace(" ", "\\ ")
        return text

    def _check_yadb_available(self) -> bool:
        """Check if YADB is installed on the device."""
        cmd = f"{self._adb_prefix} shell ls /data/local/tmp/yadb"
        success, output = self._run_command(cmd)
        return success and "No such file" not in output

    def _install_yadb(self) -> bool:
        """Install YADB to the device (if yadb file exists locally)."""
        import os

        candidates: list[Path] = []

        # 1) Explicit override (most reliable)
        env_yadb = os.environ.get("YADB_PATH")
        if env_yadb:
            candidates.append(Path(env_yadb))

        # 2) Conventional env var used elsewhere in this repo for gelab-zero path
        gelab_zero_path = os.environ.get("GELAB_ZERO_PATH")
        if gelab_zero_path:
            candidates.append(Path(gelab_zero_path) / "yadb")

        # 3) Common relative locations (CWD-dependent)
        candidates.extend(
            [
                Path("yadb"),
                Path("./yadb"),
                Path("../yadb"),
                Path("../../yadb"),
                Path("../gelab-zero/yadb"),
                Path("../../gelab-zero/yadb"),
                Path("../../../gelab-zero/yadb"),
            ]
        )

        # 4) Repo layout heuristic: `OMG-Agent` and `gelab-zero` as siblings
        try:
            repo_root = Path(__file__).resolve().parents[4]
            candidates.append(repo_root / "yadb")
            candidates.append(repo_root.parent / "gelab-zero" / "yadb")
        except Exception:
            pass

        yadb_path: Path | None = next((p for p in candidates if p.is_file()), None)
        if not yadb_path:
            if self.logger:
                self.logger(
                    "[YADB] yadb file not found locally (set YADB_PATH or GELAB_ZERO_PATH to enable auto-install)"
                )
            return False

        cmd_list = self._adb_prefix_list + ["push", str(yadb_path), "/data/local/tmp/yadb"]
        success, _ = self._run_command_list(cmd_list)
        if self.logger:
            self.logger(f"[YADB] Install result: {success}")
        return success

    # ========== Auto-detection ==========

    def _detect_best_input_method(self) -> InputMethod:
        """Auto-detect the best available input method."""
        if self._cached_input_method:
            return self._cached_input_method

        # Priority 1: YADB (more reliable for Chinese)
        if self._check_yadb_available():
            self._cached_input_method = InputMethod.YADB
            if self.logger:
                self.logger("[InputMethod] Using YADB")
            return InputMethod.YADB

        # Priority 2: ADB Keyboard
        if self._check_adb_keyboard_available():
            self._cached_input_method = InputMethod.ADB_KEYBOARD
            if self.logger:
                self.logger("[InputMethod] Using ADB Keyboard")
            return InputMethod.ADB_KEYBOARD

        # Fallback: standard adb input
        self._cached_input_method = InputMethod.ADB_INPUT
        if self.logger:
            self.logger("[InputMethod] Using standard adb input (ASCII only)")
        return InputMethod.ADB_INPUT

    def _check_adb_keyboard_available(self) -> bool:
        """Check if ADB Keyboard is installed on the device."""
        # Avoid shell pipes for Windows compatibility; parse output in Python instead.
        cmd_list = self._adb_prefix_list + ["shell", "pm", "list", "packages"]
        success, output = self._run_command_list(cmd_list)
        return success and "adbkeyboard" in output.lower()

    def set_input_method(self, method: InputMethod) -> None:
        """Set the preferred input method."""
        self.input_method = method
        self._cached_input_method = None  # Clear cache to re-detect if AUTO


class MCPExecutor:
    """MCP-based device executor (uses android-phone MCP tools)."""

    def __init__(self, mcp_client: Any = None):
        self.mcp_client = mcp_client
        self._screen_size: tuple[int, int] | None = None

    def _call_mcp(self, tool_name: str, **params) -> dict:
        """Call MCP tool."""
        if self.mcp_client is None:
            raise RuntimeError("MCP client not initialized")
        return self.mcp_client.call_tool(f"mcp__android-phone__{tool_name}", params)

    def tap(self, x: int, y: int) -> bool:
        try:
            self._call_mcp("phone_tap", x=x, y=y)
            return True
        except Exception:
            return False

    def double_tap(self, x: int, y: int) -> bool:
        try:
            self._call_mcp("phone_double_tap", x=x, y=y)
            return True
        except Exception:
            return False

    def long_press(self, x: int, y: int, duration_ms: int = 2000) -> bool:
        try:
            self._call_mcp("phone_long_press", x=x, y=y, duration_ms=duration_ms)
            return True
        except Exception:
            return False

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 500) -> bool:
        try:
            self._call_mcp("phone_swipe", start_x=x1, start_y=y1, end_x=x2, end_y=y2, duration_ms=duration_ms)
            return True
        except Exception:
            return False

    def type_text(self, text: str) -> bool:
        try:
            self._call_mcp("phone_type", text=text)
            return True
        except Exception:
            return False

    def press_back(self) -> bool:
        try:
            self._call_mcp("phone_back")
            return True
        except Exception:
            return False

    def press_home(self) -> bool:
        try:
            self._call_mcp("phone_home")
            return True
        except Exception:
            return False

    def launch_app(self, app_name: str) -> bool:
        try:
            self._call_mcp("phone_launch_app", app_name=app_name)
            return True
        except Exception:
            return False

    def get_screen_size(self) -> tuple[int, int]:
        if self._screen_size:
            return self._screen_size
        try:
            result = self._call_mcp("phone_device_info")
            # Parse screen size from result
            self._screen_size = (1080, 1920)  # Default
            return self._screen_size
        except Exception:
            return 1080, 1920


class ActionHandler:
    """
    Executes actions on Android device.

    Supports:
    - Callback for sensitive operation confirmation
    - Callback for human takeover requests
    - Multiple execution backends (ADB, MCP)
    - Configurable coordinate system (0-1000 or 0-999)
    - Protocol-aware text input (GeLab/AutoGLM/Universal)
    """

    # Default swipe distance as fraction of screen
    DEFAULT_SWIPE_FRACTION = 0.3
    DEFAULT_SWIPE_DURATION_MS = 500
    DEFAULT_LONG_PRESS_MS = 2000

    def __init__(
        self,
        executor: DeviceExecutor | None = None,
        device_id: str | None = None,
        confirmation_callback: Callable[[str], bool] | None = None,
        takeover_callback: Callable[[str], None] | None = None,
        info_callback: Callable[[str], str] | None = None,
        logger: Callable[[str], None] | None = None,
        coordinate_max: int = 1000,  # 坐标系最大值：1000 (gelab) 或 999 (autoglm)
        input_method: InputMethod = InputMethod.AUTO,  # 文本输入方式
        protocol: str = "auto",  # 协议: "gelab", "autoglm", "universal", "auto"
    ):
        """
        Initialize action handler.

        Args:
            executor: Device executor instance (ADB or MCP)
            device_id: ADB device ID (used if executor not provided)
            confirmation_callback: Called for sensitive operations, returns True to proceed
            takeover_callback: Called when agent requests human takeover
            info_callback: Called when agent needs information from user
            logger: Callback for logging execution details
            coordinate_max: Maximum coordinate value (1000 for gelab, 999 for autoglm)
            input_method: Text input method (YADB, ADB_KEYBOARD, ADB_INPUT, AUTO)
            protocol: Protocol to use ("gelab", "autoglm", "universal", "auto")
        """
        self.logger = logger
        self.protocol = protocol.lower()
        self.device_id = device_id

        # Determine input method based on protocol if not explicitly set
        if input_method == InputMethod.AUTO:
            input_method = self._get_default_input_method_for_protocol(protocol)

        # Create executor with appropriate input method
        if executor:
            self.executor = executor
        else:
            self.executor = ADBExecutor(
                device_id=device_id,
                logger=logger,
                input_method=input_method,
                protocol=self.protocol,
            )

        self.confirmation_callback = confirmation_callback or self._default_confirmation
        self.takeover_callback = takeover_callback or self._default_takeover
        self.info_callback = info_callback or self._default_info
        self.coordinate_max = coordinate_max
        self.input_method = input_method

        self._screen_size: tuple[int, int] | None = None

    def _get_default_input_method_for_protocol(self, protocol: str) -> InputMethod:
        """Get the default input method for a protocol."""
        protocol = protocol.lower()
        if protocol == "gelab":
            return InputMethod.YADB  # GeLab uses YADB
        elif protocol == "autoglm":
            return InputMethod.ADB_KEYBOARD  # AutoGLM uses ADB Keyboard
        else:
            return InputMethod.AUTO  # Auto-detect for universal/auto

    @property
    def screen_size(self) -> tuple[int, int]:
        """Get screen size, caching the result."""
        if self._screen_size is None:
            self._screen_size = self.executor.get_screen_size()
        return self._screen_size

    def execute(self, action: Action) -> ActionResult:
        """
        Execute an action.

        Args:
            action: Action to execute

        Returns:
            ActionResult with execution status
        """
        action_type = action.action_type
        params = action.params

        # Control flow actions
        if action_type == ActionType.COMPLETE:
            return ActionResult(
                success=True,
                should_finish=True,
                message=params.get("return", "Task completed")
            )

        if action_type == ActionType.ABORT:
            return ActionResult(
                success=True,
                should_finish=True,
                message=params.get("value", params.get("reason", "Task aborted"))

            )

        if action_type == ActionType.INFO:
            # Open-AutoGLM: "Interact" is surfaced to the client but does not block the loop.
            if self.protocol == "autoglm":
                return ActionResult(
                    success=True,
                    should_finish=False,
                    message="User interaction required",
                    requires_user_input=False,
                )

            prompt = (
                params.get("value")
                or action.explanation
                or params.get("message")
                or "Please provide more information"
            )
            return ActionResult(
                success=True,
                should_finish=False,
                requires_user_input=True,
                user_prompt=prompt,
            )

        if action_type == ActionType.TAKE_OVER:
            message = params.get("message", "Human intervention required")
            self.takeover_callback(message)
            return ActionResult(success=True, should_finish=False)

        # Get handler method
        handler = self._get_handler(action_type)
        if handler is None:
            return ActionResult(
                success=False,
                should_finish=False,
                message=f"Unknown action type: {action_type.value}"
            )

        try:
            return handler(action)
        except Exception as e:
            return ActionResult(
                success=False,
                should_finish=False,
                message=f"Action failed: {e}"
            )

    def _get_handler(self, action_type: ActionType) -> Callable[[Action], ActionResult] | None:
        """Get handler method for action type."""
        handlers = {
            ActionType.CLICK: self._handle_click,
            ActionType.DOUBLE_TAP: self._handle_double_tap,
            ActionType.LONG_PRESS: self._handle_long_press,
            ActionType.SWIPE: self._handle_swipe,
            ActionType.TYPE: self._handle_type,
            ActionType.BACK: self._handle_back,
            ActionType.HOME: self._handle_home,
            ActionType.LAUNCH: self._handle_launch,
            ActionType.WAIT: self._handle_wait,
            ActionType.NOTE: self._handle_note,
        }
        return handlers.get(action_type)

    def _to_absolute(self, point: list[int] | tuple[int, int]) -> tuple[int, int]:
        """Convert normalized coordinates to absolute pixels.

        Supports both 0-1000 (gelab-zero) and 0-999 (AutoGLM) coordinate systems.
        """
        width, height = self.screen_size
        # Open-AutoGLM converts coordinates using a fixed 1000 denominator
        # (`int(x / 1000 * width)`), even though the prompt says 0-999.
        # Gelab-Zero also uses 0-1000 normalization.
        denom = 1000 if self.coordinate_max in (999, 1000) else self.coordinate_max
        return (
            int(point[0] * width / denom),
            int(point[1] * height / denom)
        )

    def _handle_click(self, action: Action) -> ActionResult:
        point = action.params.get("point")
        if not point:
            return ActionResult(False, False, "Missing point parameter")

        # Check for sensitive operation
        if "message" in action.params:
            if not self.confirmation_callback(action.params["message"]):
                return ActionResult(False, True, "User cancelled sensitive operation")

        x, y = self._to_absolute(point)
        success = self.executor.tap(x, y)
        return ActionResult(success, False)

    def _handle_double_tap(self, action: Action) -> ActionResult:
        point = action.params.get("point")
        if not point:
            return ActionResult(False, False, "Missing point parameter")

        x, y = self._to_absolute(point)
        success = self.executor.double_tap(x, y)
        return ActionResult(success, False)

    def _handle_long_press(self, action: Action) -> ActionResult:
        point = action.params.get("point")
        if not point:
            return ActionResult(False, False, "Missing point parameter")

        if self.protocol == "autoglm":
            default_seconds = 3.0
        elif self.protocol == "gelab":
            # gelab-zero default_duration=1.5s (see pu_frontend_executor.py)
            default_seconds = 1.5
        else:
            default_seconds = 2.0

        raw_duration = action.params.get("duration", default_seconds)
        try:
            if isinstance(raw_duration, str):
                normalized = raw_duration.replace("seconds", "").replace("second", "").strip()
                duration_seconds = float(normalized)
            else:
                duration_seconds = float(raw_duration)
        except (ValueError, TypeError):
            duration_seconds = default_seconds

        duration_ms = int(duration_seconds * 1000)
        x, y = self._to_absolute(point)
        success = self.executor.long_press(x, y, duration_ms)
        return ActionResult(success, False)

    def _handle_swipe(self, action: Action) -> ActionResult:
        params = action.params
        is_direction_swipe = False

        # Two-point swipe
        if "point1" in params and "point2" in params:
            x1, y1 = self._to_absolute(params["point1"])
            x2, y2 = self._to_absolute(params["point2"])
        # Point + direction swipe
        elif "point" in params and "direction" in params:
            is_direction_swipe = True
            x, y = self._to_absolute(params["point"])
            direction = params["direction"].upper()
            width, height = self.screen_size
            delta_x = int(self.DEFAULT_SWIPE_FRACTION * width)
            delta_y = int(self.DEFAULT_SWIPE_FRACTION * height)

            if self.protocol == "gelab":
                # gelab-zero pu_frontend_executor SCROLL direction mapping (vertical inverted).
                direction_map = {
                    "UP": (x, y, x, y + delta_y),
                    "DOWN": (x, y, x, y - delta_y),
                    "LEFT": (x, y, x - delta_x, y),
                    "RIGHT": (x, y, x + delta_x, y),
                }
            else:
                direction_map = {
                    "UP": (x, y, x, y - delta_y),
                    "DOWN": (x, y, x, y + delta_y),
                    "LEFT": (x, y, x - delta_x, y),
                    "RIGHT": (x, y, x + delta_x, y),
                }

            if direction not in direction_map:
                return ActionResult(False, False, f"Invalid direction: {direction}")

            x1, y1, x2, y2 = direction_map[direction]
        else:
            return ActionResult(False, False, "Missing swipe parameters")

        if self.protocol == "autoglm":
            # Open-AutoGLM: duration_ms is auto-calculated from distance and clamped to [1000, 2000].
            dist_sq = (x1 - x2) ** 2 + (y1 - y2) ** 2
            duration_ms = int(dist_sq / 1000)
            duration_ms = max(1000, min(duration_ms, 2000))
        elif self.protocol == "gelab":
            # gelab-zero: SCROLL uses fixed 1200ms; SLIDE defaults to 1.5s if not provided.
            if is_direction_swipe:
                duration_ms = 1200
            else:
                raw_duration = params.get("duration", 1.5)
                try:
                    duration_ms = int(float(raw_duration) * 1000)
                except (ValueError, TypeError):
                    duration_ms = 1500
        else:
            raw_duration = params.get("duration", 0.5)
            try:
                duration_ms = int(float(raw_duration) * 1000)
            except (ValueError, TypeError):
                duration_ms = 500

        success = self.executor.swipe(x1, y1, x2, y2, duration_ms)
        return ActionResult(success, False)

    def _handle_type(self, action: Action) -> ActionResult:
        """
        Handle text input action.

        Supports both GeLab and AutoGLM style parameters:
        - GeLab: value, point, keyboard_exists (or is_keyboard)
        - AutoGLM: text (mapped to value)

        Logic:
        1. If keyboard_exists is False and point is provided, tap the input field first
        2. If keyboard_exists is True (or not specified), assume keyboard is already open
        3. Use the configured input method (YADB/ADB_KEYBOARD/AUTO)
        """
        # Get text value (support both 'value' and 'text' keys)
        text = action.params.get("value", action.params.get("text", ""))

        if not text:
            return ActionResult(True, False, "Empty text, nothing to type")

        # Check keyboard_exists parameter (GeLab style)
        # Default to True (assume keyboard is open)
        keyboard_exists = action.params.get(
            "keyboard_exists",
            action.params.get("is_keyboard", True)
        )

        # Handle string values for keyboard_exists
        if isinstance(keyboard_exists, str):
            keyboard_exists = keyboard_exists.lower() in ("true", "1", "yes")

        # If keyboard doesn't exist and we have a point, tap the input field first
        if not keyboard_exists and "point" in action.params:
            point = action.params["point"]
            x, y = self._to_absolute(point)
            if self.logger:
                self.logger(f"[TYPE] Keyboard not exists, tapping input field at ({x}, {y})")
            self.executor.tap(x, y)
            time.sleep(1.0)  # Wait for keyboard to appear

        # Perform text input
        if self.logger:
            self.logger(f"[TYPE] Inputting text: '{text[:30]}...' using {self.input_method.value}")

        success = self.executor.type_text(text)

        if not success:
            return ActionResult(False, False, f"Failed to type text: {text[:30]}...")

        return ActionResult(True, False)

    def _handle_back(self, action: Action) -> ActionResult:
        success = self.executor.press_back()
        return ActionResult(success, False)

    def _handle_home(self, action: Action) -> ActionResult:
        success = self.executor.press_home()
        return ActionResult(success, False)

    def _handle_launch(self, action: Action) -> ActionResult:
        app_name = action.params.get("value")
        if not app_name:
            return ActionResult(False, False, "Missing app name")

        success = self.executor.launch_app(app_name)
        if not success:
            return ActionResult(False, False, f"Failed to launch app: {app_name}")
        return ActionResult(True, False)

    def _handle_wait(self, action: Action) -> ActionResult:
        raw = action.params.get("value", action.params.get("duration", 1))
        try:
            if isinstance(raw, str):
                # Open-AutoGLM uses e.g. "5 seconds"
                normalized = raw.replace("seconds", "").replace("second", "").strip()
                duration = float(normalized)
            else:
                duration = float(raw)
        except (ValueError, TypeError):
            duration = 1.0

        time.sleep(duration)
        return ActionResult(True, False)

    def _handle_note(self, action: Action) -> ActionResult:
        # Note action is for internal recording, no device action needed
        return ActionResult(True, False)

    @staticmethod
    def _default_confirmation(message: str) -> bool:
        """Default confirmation using console input."""
        response = input(f"Sensitive operation: {message}\nConfirm? (Y/N): ")
        return response.upper() == "Y"

    @staticmethod
    def _default_takeover(message: str) -> None:
        """Default takeover using console input."""
        input(f"{message}\nPress Enter after completing manual operation...")

    @staticmethod
    def _default_info(prompt: str) -> str:
        """Default info callback using console input."""
        return input(f"Agent asks: {prompt}\nYour response: ")
