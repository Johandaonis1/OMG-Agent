"""
Screenshot capture utilities.

This module provides reliable screenshot capture from Android devices via ADB.
All screenshots are taken directly from the phone's screen buffer, NOT from
screen mirroring/casting, to avoid latency issues.

Key features:
- Direct ADB screencap (no screen mirroring)
- Multiple capture strategies with automatic fallback
- Configurable delays to ensure screen stability
- Retry mechanism for reliability
"""

import base64
import subprocess
import tempfile
import os
import time
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Callable

if TYPE_CHECKING:
    from PIL import Image


# ========== Screenshot Configuration ==========

@dataclass
class ScreenshotConfig:
    """Screenshot capture configuration."""

    # Delay before capturing (seconds) - helps with screen stability
    delay_before_capture: float = 0.0

    # Delay after action before capturing (seconds) - GeLab uses 2.0
    delay_after_action: float = 1.0

    # Timeout for screenshot operations (seconds)
    timeout: int = 10

    # Number of retries on failure
    max_retries: int = 3

    # Retry delay (seconds)
    retry_delay: float = 0.5

    # Preferred capture method: "pipe" (fast) or "file" (reliable)
    preferred_method: str = "pipe"


# Default configurations for different protocols
GELAB_SCREENSHOT_CONFIG = ScreenshotConfig(
    delay_before_capture=0.0,
    delay_after_action=2.0,  # GeLab official delay_after_capture
    timeout=10,
    max_retries=3,
    preferred_method="file"  # GeLab uses file-based
)

AUTOGLM_SCREENSHOT_CONFIG = ScreenshotConfig(
    delay_before_capture=0.0,
    delay_after_action=1.0,
    timeout=10,
    max_retries=3,
    preferred_method="file"  # AutoGLM uses file-based
)

UNIVERSAL_SCREENSHOT_CONFIG = ScreenshotConfig(
    delay_before_capture=0.0,
    delay_after_action=1.5,
    timeout=10,
    max_retries=3,
    preferred_method="pipe"  # Faster for general use
)


@dataclass
class ImagePreprocessConfig:
    """图像预处理配置 - 与 gelab-zero 对齐"""

    is_resize: bool = True
    target_size: tuple[int, int] = (728, 728)
    format: str = "jpeg"
    quality: int = 85
    keep_aspect_ratio: bool = False


class Screenshot:
    """Screenshot data container."""

    def __init__(
        self,
        base64_data: str,
        width: int,
        height: int,
        format: str = "png"
    ):
        """
        Initialize Screenshot.

        Args:
            base64_data: Base64 encoded image data
            width: Image width in pixels
            height: Image height in pixels
            format: Image format ('png' or 'jpeg')
        """
        self.base64_data = base64_data
        self.width = width
        self.height = height
        self.format = format

    def to_data_url(self) -> str:
        """Convert to data URL for embedding in HTML/messages."""
        return f"data:image/{self.format};base64,{self.base64_data}"

    def save(self, path: str | Path) -> None:
        """Save screenshot to file."""
        data = base64.b64decode(self.base64_data)
        with open(path, "wb") as f:
            f.write(data)

    @classmethod
    def from_file(cls, path: str | Path) -> "Screenshot":
        """Load screenshot from file."""
        from PIL import Image

        with open(path, "rb") as f:
            data = f.read()

        img = Image.open(path)
        width, height = img.size

        # Detect format
        fmt = "png"
        if data[:2] == b"\xff\xd8":
            fmt = "jpeg"

        return cls(
            base64_data=base64.b64encode(data).decode("utf-8"),
            width=width,
            height=height,
            format=fmt
        )

    def resize(self, max_size: int = 1024) -> "Screenshot":
        """
        Resize screenshot if larger than max_size (保持宽高比).

        Args:
            max_size: Maximum dimension (width or height)

        Returns:
            Resized screenshot (or self if no resize needed)
        """
        from PIL import Image
        import io

        if max(self.width, self.height) <= max_size:
            return self

        # Decode image
        data = base64.b64decode(self.base64_data)
        img = Image.open(io.BytesIO(data))

        # Calculate new size
        ratio = max_size / max(self.width, self.height)
        new_width = int(self.width * ratio)
        new_height = int(self.height * ratio)

        # Resize
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Encode back
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        new_data = buffer.getvalue()

        return Screenshot(
            base64_data=base64.b64encode(new_data).decode("utf-8"),
            width=new_width,
            height=new_height,
            format="jpeg"
        )

    def preprocess(self, config: Optional[ImagePreprocessConfig] = None) -> "Screenshot":
        """
        预处理截图 - 与 gelab-zero 完全对齐.

        Args:
            config: 图像预处理配置

        Returns:
            处理后的截图
        """
        from PIL import Image
        import io

        if config is None:
            config = ImagePreprocessConfig()

        if not config.is_resize:
            return self

        # Decode image
        data = base64.b64decode(self.base64_data)
        img = Image.open(io.BytesIO(data))

        target_w, target_h = config.target_size

        if config.keep_aspect_ratio:
            # 保持宽高比 resize
            ratio = min(target_w / img.width, target_h / img.height)
            new_w = int(img.width * ratio)
            new_h = int(img.height * ratio)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        else:
            # 强制 resize 到目标尺寸 (与 gelab-zero 一致)
            img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        # 转换为 RGB (JPEG 不支持透明通道)
        if config.format.lower() == "jpeg":
            img = img.convert("RGB")

        # Encode
        buffer = io.BytesIO()
        if config.format.lower() == "jpeg":
            img.save(buffer, format="JPEG", quality=config.quality)
            fmt = "jpeg"
        else:
            img.save(buffer, format="PNG")
            fmt = "png"

        new_data = buffer.getvalue()
        new_w, new_h = img.size

        return Screenshot(
            base64_data=base64.b64encode(new_data).decode("utf-8"),
            width=new_w,
            height=new_h,
            format=fmt
        )


def take_screenshot(
    device_id: str | None = None,
    timeout: int = 10,
    config: ScreenshotConfig | None = None,
    logger: Callable[[str], None] | None = None
) -> Screenshot:
    """
    Take screenshot using ADB (optimized version with retry mechanism).

    This function captures screenshots DIRECTLY from the phone's screen buffer
    via ADB, NOT from screen mirroring/casting. This avoids latency issues
    that would occur with screen casting software.

    Strategies:
    1. Windows: Use `adb shell "screencap -p | base64"` to avoid CRLF corruption.
    2. Others: Use `adb exec-out screencap -p` for speed.
    3. Fallback: File transfer (more reliable on some devices).

    Args:
        device_id: ADB device ID (optional)
        timeout: Timeout in seconds (default 10)
        config: Screenshot configuration (optional)
        logger: Logging callback (optional)

    Returns:
        Screenshot object
    """
    from PIL import Image
    import io

    if config is None:
        config = ScreenshotConfig()

    # Apply delay before capture if configured
    if config.delay_before_capture > 0:
        time.sleep(config.delay_before_capture)

    last_error = None

    # Retry loop
    for attempt in range(config.max_retries):
        try:
            # Choose capture method based on config
            if config.preferred_method == "file":
                result = _take_screenshot_file_based(device_id, config.timeout)
                if result:
                    if logger:
                        logger(f"[Screenshot] Captured via file transfer (attempt {attempt + 1})")
                    return result
            else:
                result = _take_screenshot_pipe(device_id, config.timeout)
                if result:
                    if logger:
                        logger(f"[Screenshot] Captured via pipe (attempt {attempt + 1})")
                    return result
                # Fallback to file-based on pipe failure
                result = _take_screenshot_file_based(device_id, config.timeout)
                if result:
                    if logger:
                        logger(f"[Screenshot] Captured via file transfer fallback (attempt {attempt + 1})")
                    return result

        except Exception as e:
            last_error = e
            if logger:
                logger(f"[Screenshot] Attempt {attempt + 1} failed: {e}")

        # Wait before retry
        if attempt < config.max_retries - 1:
            time.sleep(config.retry_delay)

    # All retries failed
    raise RuntimeError(f"Screenshot failed after {config.max_retries} attempts. Last error: {last_error}")


def _take_screenshot_pipe(device_id: str | None = None, timeout: int = 10) -> Screenshot | None:
    """
    Take screenshot using pipe method (fast but may fail on some devices).

    This method captures directly from the phone's screen buffer via ADB pipe.
    NOT from screen mirroring - this is direct device capture.
    """
    from PIL import Image
    import io

    use_base64_pipe = (sys.platform == 'win32')

    cmd = ["adb"]
    if device_id:
        cmd.extend(["-s", device_id])

    if use_base64_pipe:
        # Windows: Pipe base64 to avoid binary corruption
        cmd.extend(["shell", "screencap -p | base64"])
    else:
        # Linux/Mac: Direct binary pipe
        cmd.extend(["exec-out", "screencap", "-p"])

    try:
        creationflags = 0
        if sys.platform == 'win32':
            creationflags = subprocess.CREATE_NO_WINDOW

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            creationflags=creationflags
        )

        if result.returncode != 0 or not result.stdout:
            return None

        if use_base64_pipe:
            # Decode base64 output
            try:
                # Remove newlines before decoding
                b64_str = result.stdout.replace(b'\r', b'').replace(b'\n', b'')
                png_data = base64.b64decode(b64_str)
            except Exception:
                return None
        else:
            png_data = result.stdout

        # Verify PNG header
        if not png_data.startswith(b'\x89PNG'):
            return None

        # Get image dimensions
        img = Image.open(io.BytesIO(png_data))
        width, height = img.size

        # Helper: ensure we have base64 string for the Screenshot object
        if use_base64_pipe:
            base64_data = b64_str.decode('utf-8')
        else:
            base64_data = base64.b64encode(png_data).decode("utf-8")

        return Screenshot(
            base64_data=base64_data,
            width=width,
            height=height,
            format="png"
        )

    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None


def _take_screenshot_file_based(device_id: str | None = None, timeout: int = 5) -> Screenshot | None:
    """
    File-based screenshot method (more reliable on some devices).

    This method captures directly from the phone's screen buffer via ADB file transfer.
    NOT from screen mirroring - this is direct device capture.

    This is the method used by both GeLab-Zero and AutoGLM official implementations.
    """
    adb_cmd = ["adb"]
    if device_id:
        adb_cmd.extend(["-s", device_id])

    creationflags = 0
    if sys.platform == 'win32':
        creationflags = subprocess.CREATE_NO_WINDOW

    # Create temp file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        temp_path = f.name

    # Use UUID to avoid conflicts with multiple devices
    import uuid
    remote_path = f"/sdcard/screenshot_{uuid.uuid4().hex[:8]}.png"

    try:
        # Step 1: Capture screenshot on device
        result = subprocess.run(
            adb_cmd + ["shell", "screencap", "-p", remote_path],
            timeout=timeout,
            capture_output=True,
            creationflags=creationflags
        )

        if result.returncode != 0:
            return None

        # Step 2: Pull screenshot to local
        result = subprocess.run(
            adb_cmd + ["pull", remote_path, temp_path],
            timeout=timeout,
            capture_output=True,
            creationflags=creationflags
        )

        if result.returncode != 0:
            return None

        # Step 3: Cleanup remote file (don't wait)
        subprocess.Popen(
            adb_cmd + ["shell", "rm", remote_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags
        )

        # Verify file exists and has content
        if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
            return None

        # Load and return
        return Screenshot.from_file(temp_path)

    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None
    finally:
        # Cleanup temp file
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass



def get_current_app(device_id: str | None = None) -> dict[str, str]:
    """
    Get current foreground app info.

    Returns:
        Dict with 'package' and 'activity' keys
    """
    adb_cmd = ["adb"]
    if device_id:
        adb_cmd.extend(["-s", device_id])
    adb_cmd.extend(["shell", "dumpsys", "activity", "activities"])

    try:
        # Use simple subprocess call without shell=True for better compatibility
        creationflags = 0
        if sys.platform == 'win32':
            creationflags = subprocess.CREATE_NO_WINDOW
            
        result = subprocess.run(
            adb_cmd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8', 
            errors='ignore',
            creationflags=creationflags
        )
        output = result.stdout

        # Parse output in Python instead of grep
        for line in output.splitlines():
            if "mResumedActivity" in line:
                # Parse output like: mResumedActivity: ActivityRecord{xxx com.example.app/.MainActivity ...}
                line = line.strip()
                if "ActivityRecord" in line and "/" in line:
                    parts = line.split()
                    for part in parts:
                        if "/" in part and "." in part and "{" not in part:
                            # Found component name
                            component = part.rstrip("}")
                            if "/" in component:
                                package, activity = component.split("/", 1)
                                return {"package": package, "activity": activity}
                
        return {"package": "unknown", "activity": "unknown"}

    except Exception:
        return {"package": "unknown", "activity": "unknown"}


def get_screen_orientation(device_id: str | None = None) -> int:
    """
    Get screen orientation.

    Returns:
        0: Portrait
        1: Landscape (rotated left)
        2: Portrait (upside down)
        3: Landscape (rotated right)
    """
    adb_cmd = ["adb"]
    if device_id:
        adb_cmd.extend(["-s", device_id])
    adb_cmd.extend(["shell", "dumpsys", "input"])

    try:
        creationflags = 0
        if sys.platform == 'win32':
            creationflags = subprocess.CREATE_NO_WINDOW

        result = subprocess.run(
            adb_cmd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8', 
            errors='ignore',
            creationflags=creationflags
        )
        output = result.stdout

        # Parse orientation in Python
        import re
        # Look for "orientation=0" etc.
        match = re.search(r"orientation=(\d)", output)
        if match:
            return int(match.group(1))

    except Exception:
        pass

    return 0


def is_screen_on(device_id: str | None = None) -> bool:
    """Check if screen is on."""
    adb_cmd = ["adb"]
    if device_id:
        adb_cmd.extend(["-s", device_id])
    adb_cmd.extend(["shell", "dumpsys", "power"])

    try:
        creationflags = 0
        if sys.platform == 'win32':
            creationflags = subprocess.CREATE_NO_WINDOW

        result = subprocess.run(
            adb_cmd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8', 
            errors='ignore',
            creationflags=creationflags
        )
        # Check for multiple indicators of screen ON state
        output = result.stdout
        # mWakefulness=Awake is the most reliable indicator on modern Android
        # state=ON is used in some older versions or specific displays
        return ("mWakefulness=Awake" in output or 
                "state=ON" in output or 
                "Display Power: state=ON" in output)
    except Exception:
        return True  # Assume on if can't detect


def wake_screen(device_id: str | None = None) -> None:
    """Wake up screen if off."""
    # Always try to wake using KEYCODE_WAKEUP (224) which is safe (doesn't toggle off)
    adb_cmd = ["adb"]
    if device_id:
        adb_cmd.extend(["-s", device_id])
    
    creationflags = 0
    if sys.platform == 'win32':
        creationflags = subprocess.CREATE_NO_WINDOW
        
    # Use KEYCODE_WAKEUP (224) instead of POWER (26) to avoid toggling screen off
    subprocess.run(
        adb_cmd + ["shell", "input", "keyevent", "224"],
        capture_output=True,
        creationflags=creationflags
    )
    
    # Swipe up to unlock (if needed) - standard behavior
    subprocess.run(
        adb_cmd + ["shell", "input", "swipe", "500", "1000", "500", "300"],
        capture_output=True,
        creationflags=creationflags
    )


# Alias for backward compatibility with phone_agent.adb.screenshot
get_screenshot = take_screenshot


def get_screenshot_config_for_protocol(protocol: str) -> ScreenshotConfig:
    """
    Get the appropriate screenshot configuration for a protocol.

    Args:
        protocol: Protocol name ("gelab", "autoglm", "universal", or "auto")

    Returns:
        ScreenshotConfig appropriate for the protocol
    """
    protocol = protocol.lower()
    if protocol == "gelab":
        return GELAB_SCREENSHOT_CONFIG
    elif protocol == "autoglm":
        return AUTOGLM_SCREENSHOT_CONFIG
    else:
        return UNIVERSAL_SCREENSHOT_CONFIG


def take_screenshot_for_protocol(
    device_id: str | None = None,
    protocol: str = "auto",
    logger: Callable[[str], None] | None = None
) -> Screenshot:
    """
    Take screenshot using protocol-specific configuration.

    This is a convenience function that combines protocol detection
    with screenshot capture.

    Args:
        device_id: ADB device ID (optional)
        protocol: Protocol name ("gelab", "autoglm", "universal", or "auto")
        logger: Logging callback (optional)

    Returns:
        Screenshot object
    """
    config = get_screenshot_config_for_protocol(protocol)
    return take_screenshot(device_id=device_id, config=config, logger=logger)
