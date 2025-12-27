"""
Protocol Adapter - 自动适配不同 VLM 模型的配置和协议。

支持三种协议：
1. autoglm - Open-AutoGLM 官方协议
2. gelab - gelab-zero 官方协议
3. universal - 通用协议（基于上述两个优化）

对标官方实现：
- gelab-zero: 728x728 resize, JPEG 85, 0-1000 坐标, <THINK>/<THINK> + TAB 格式
- Open-AutoGLM: 原始分辨率, PNG, 0-999 坐标, <think>/<answer> + do/finish 格式
"""

from dataclasses import dataclass, field
from typing import Any, Literal
from enum import Enum


class Protocol(str, Enum):
    """协议类型"""
    AUTOGLM = "autoglm"  # Open-AutoGLM 官方协议
    GELAB = "gelab"      # gelab-zero 官方协议
    UNIVERSAL = "universal"  # 通用优化协议


@dataclass
class ImageConfig:
    """图像预处理配置"""
    is_resize: bool = True
    target_size: tuple[int, int] = (728, 728)
    format: str = "jpeg"  # "png" or "jpeg"
    quality: int = 85


@dataclass
class ProtocolConfig:
    """协议完整配置"""

    # 协议标识
    protocol: Protocol = Protocol.UNIVERSAL

    # 坐标系配置
    coordinate_max: int = 1000  # 0-1000 (gelab) 或 0-999 (autoglm)

    # 图像配置
    image_config: ImageConfig = field(default_factory=ImageConfig)

    # LLM 参数
    temperature: float = 0.1
    top_p: float = 0.95
    max_tokens: int = 4096
    frequency_penalty: float = 0.0

    # 执行参数
    delay_after_action: float = 2.0  # gelab-zero 官方默认 2 秒
    max_steps: int = 400  # gelab-zero 官方默认 400 步


# =============================================================================
# 官方配置预设 (对标官方实现)
# =============================================================================

# gelab-zero 官方配置
GELAB_ZERO_CONFIG = ProtocolConfig(
    protocol=Protocol.GELAB,
    coordinate_max=1000,
    image_config=ImageConfig(
        is_resize=True,
        target_size=(728, 728),  # 官方默认
        format="jpeg",
        quality=85
    ),
    temperature=0.1,  # 官方默认
    top_p=0.95,
    max_tokens=4096,
    frequency_penalty=0.0,
    delay_after_action=2.0,  # 官方 delay_after_capture
    max_steps=400
)

# Open-AutoGLM 官方配置
AUTOGLM_CONFIG = ProtocolConfig(
    protocol=Protocol.AUTOGLM,
    coordinate_max=999,  # AutoGLM 使用 0-999
    image_config=ImageConfig(
        is_resize=False,  # AutoGLM 不 resize
        target_size=(1080, 2400),
        format="png",
        quality=100
    ),
    temperature=0.0,  # 官方默认
    top_p=0.85,
    max_tokens=3000,
    frequency_penalty=0.2,
    delay_after_action=1.0,
    max_steps=100
)

# 通用协议配置 (优化后的默认配置)
UNIVERSAL_CONFIG = ProtocolConfig(
    protocol=Protocol.UNIVERSAL,
    coordinate_max=1000,
    image_config=ImageConfig(
        is_resize=True,
        target_size=(728, 728),  # 使用 gelab-zero 的尺寸
        format="jpeg",
        quality=85
    ),
    temperature=0.1,
    top_p=0.95,
    max_tokens=4096,
    frequency_penalty=0.0,
    delay_after_action=1.5,
    max_steps=100
)


# =============================================================================
# 模型自动检测
# =============================================================================

# 模型名称到协议的映射
MODEL_PROTOCOL_MAP: dict[str, Protocol] = {
    # AutoGLM 系列
    "autoglm": Protocol.AUTOGLM,
    "autoglm-phone": Protocol.AUTOGLM,
    "autoglm-phone-9b": Protocol.AUTOGLM,
    "glm-4v": Protocol.AUTOGLM,
    "zhipuai/autoglm": Protocol.AUTOGLM,

    # gelab-zero 系列
    "gelab": Protocol.GELAB,
    "gelab-zero": Protocol.GELAB,
    "gelab-zero-4b": Protocol.GELAB,
    "gelab-zero-4b-preview": Protocol.GELAB,

    # Step 系列 (使用通用协议)
    # Step-GUI models follow GELab-Zero protocol (TAB action format + 2s delay)
    "step-gui": Protocol.GELAB,
    "step": Protocol.UNIVERSAL,

    # 通用 VLM (使用通用协议)
    "gpt-4o": Protocol.UNIVERSAL,
    "gpt-4-vision": Protocol.UNIVERSAL,
    "claude-3": Protocol.UNIVERSAL,
    "claude-3.5": Protocol.UNIVERSAL,
    "qwen-vl": Protocol.UNIVERSAL,
    "qwen2-vl": Protocol.UNIVERSAL,
    "internvl": Protocol.UNIVERSAL,
    "cogvlm": Protocol.UNIVERSAL,
    "llava": Protocol.UNIVERSAL,
}


def detect_protocol(model_name: str) -> Protocol:
    """
    根据模型名称自动检测协议类型。

    Args:
        model_name: 模型名称

    Returns:
        检测到的协议类型
    """
    model_lower = model_name.lower()

    # 精确匹配
    if model_lower in MODEL_PROTOCOL_MAP:
        return MODEL_PROTOCOL_MAP[model_lower]

    # 模糊匹配
    for key, protocol in MODEL_PROTOCOL_MAP.items():
        if key in model_lower:
            return protocol

    # 默认使用通用协议
    return Protocol.UNIVERSAL


def get_protocol_config(
    model_name: str | None = None,
    protocol: Protocol | str | None = None
) -> ProtocolConfig:
    """
    获取协议配置。

    优先级：
    1. 显式指定的 protocol
    2. 根据 model_name 自动检测
    3. 默认使用 universal

    Args:
        model_name: 模型名称（用于自动检测）
        protocol: 显式指定的协议

    Returns:
        协议配置
    """
    # 确定协议
    if protocol is not None:
        if isinstance(protocol, str):
            protocol = Protocol(protocol.lower())
    elif model_name is not None:
        protocol = detect_protocol(model_name)
    else:
        protocol = Protocol.UNIVERSAL

    # 返回对应配置的副本
    if protocol == Protocol.AUTOGLM:
        return ProtocolConfig(
            protocol=AUTOGLM_CONFIG.protocol,
            coordinate_max=AUTOGLM_CONFIG.coordinate_max,
            image_config=ImageConfig(
                is_resize=AUTOGLM_CONFIG.image_config.is_resize,
                target_size=AUTOGLM_CONFIG.image_config.target_size,
                format=AUTOGLM_CONFIG.image_config.format,
                quality=AUTOGLM_CONFIG.image_config.quality
            ),
            temperature=AUTOGLM_CONFIG.temperature,
            top_p=AUTOGLM_CONFIG.top_p,
            max_tokens=AUTOGLM_CONFIG.max_tokens,
            frequency_penalty=AUTOGLM_CONFIG.frequency_penalty,
            delay_after_action=AUTOGLM_CONFIG.delay_after_action,
            max_steps=AUTOGLM_CONFIG.max_steps
        )
    elif protocol == Protocol.GELAB:
        return ProtocolConfig(
            protocol=GELAB_ZERO_CONFIG.protocol,
            coordinate_max=GELAB_ZERO_CONFIG.coordinate_max,
            image_config=ImageConfig(
                is_resize=GELAB_ZERO_CONFIG.image_config.is_resize,
                target_size=GELAB_ZERO_CONFIG.image_config.target_size,
                format=GELAB_ZERO_CONFIG.image_config.format,
                quality=GELAB_ZERO_CONFIG.image_config.quality
            ),
            temperature=GELAB_ZERO_CONFIG.temperature,
            top_p=GELAB_ZERO_CONFIG.top_p,
            max_tokens=GELAB_ZERO_CONFIG.max_tokens,
            frequency_penalty=GELAB_ZERO_CONFIG.frequency_penalty,
            delay_after_action=GELAB_ZERO_CONFIG.delay_after_action,
            max_steps=GELAB_ZERO_CONFIG.max_steps
        )
    else:
        return ProtocolConfig(
            protocol=UNIVERSAL_CONFIG.protocol,
            coordinate_max=UNIVERSAL_CONFIG.coordinate_max,
            image_config=ImageConfig(
                is_resize=UNIVERSAL_CONFIG.image_config.is_resize,
                target_size=UNIVERSAL_CONFIG.image_config.target_size,
                format=UNIVERSAL_CONFIG.image_config.format,
                quality=UNIVERSAL_CONFIG.image_config.quality
            ),
            temperature=UNIVERSAL_CONFIG.temperature,
            top_p=UNIVERSAL_CONFIG.top_p,
            max_tokens=UNIVERSAL_CONFIG.max_tokens,
            frequency_penalty=UNIVERSAL_CONFIG.frequency_penalty,
            delay_after_action=UNIVERSAL_CONFIG.delay_after_action,
            max_steps=UNIVERSAL_CONFIG.max_steps
        )


# =============================================================================
# 协议适配器
# =============================================================================

class ProtocolAdapter:
    """
    协议适配器 - 统一处理不同协议的差异。
    """

    def __init__(self, config: ProtocolConfig):
        self.config = config

    @classmethod
    def from_model(cls, model_name: str) -> "ProtocolAdapter":
        """从模型名称创建适配器"""
        config = get_protocol_config(model_name=model_name)
        return cls(config)

    @classmethod
    def from_protocol(cls, protocol: Protocol | str) -> "ProtocolAdapter":
        """从协议类型创建适配器"""
        config = get_protocol_config(protocol=protocol)
        return cls(config)

    def get_system_prompt(self, lang: str = "zh") -> str:
        """获取对应协议的系统提示词"""
        from .prompts.system import get_system_prompt
        return get_system_prompt(lang, self.config.protocol.value)

    def preprocess_image(self, screenshot: Any) -> Any:
        """
        预处理截图。

        Args:
            screenshot: Screenshot 对象

        Returns:
            处理后的 Screenshot 对象
        """
        if not self.config.image_config.is_resize:
            return screenshot

        from .device.screenshot import ImagePreprocessConfig

        preprocess_config = ImagePreprocessConfig(
            is_resize=self.config.image_config.is_resize,
            target_size=self.config.image_config.target_size,
            format=self.config.image_config.format,
            quality=self.config.image_config.quality,
            keep_aspect_ratio=False
        )

        return screenshot.preprocess(preprocess_config)

    def normalize_coordinates(
        self,
        x: int,
        y: int,
        from_max: int = 1000
    ) -> tuple[int, int]:
        """
        归一化坐标到协议的坐标系。

        Args:
            x, y: 输入坐标
            from_max: 输入坐标的最大值

        Returns:
            归一化后的坐标
        """
        to_max = self.config.coordinate_max
        if from_max == to_max:
            return x, y

        scale = to_max / from_max
        return int(x * scale), int(y * scale)

    def denormalize_coordinates(
        self,
        x: int,
        y: int,
        screen_width: int,
        screen_height: int
    ) -> tuple[int, int]:
        """
        将协议坐标转换为实际像素坐标。

        Args:
            x, y: 协议坐标 (0 到 coordinate_max)
            screen_width, screen_height: 屏幕尺寸

        Returns:
            实际像素坐标
        """
        max_coord = self.config.coordinate_max
        actual_x = int(x * screen_width / max_coord)
        actual_y = int(y * screen_height / max_coord)
        return actual_x, actual_y

    def get_llm_params(self) -> dict[str, Any]:
        """获取 LLM 请求参数"""
        return {
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "max_tokens": self.config.max_tokens,
            "frequency_penalty": self.config.frequency_penalty,
        }

    def parse_response(self, response: str) -> dict[str, Any]:
        """
        解析 LLM 响应。

        根据协议类型选择不同的解析方式。
        """
        from .actions.parser import ActionParser
        action = ActionParser.parse(response)
        if action is None:
            raise ValueError("Failed to parse action from response")
        return action.to_dict()

    def format_action_output(self, action: Any) -> str:
        """
        将动作格式化为协议格式的字符串。
        """
        from .actions.parser import ActionParser

        if self.config.protocol == Protocol.AUTOGLM:
            return ActionParser.to_string(action, format="function")
        else:
            return ActionParser.to_string(action, format="tab")

    @property
    def delay_after_action(self) -> float:
        """获取动作后的延迟时间"""
        return self.config.delay_after_action

    @property
    def max_steps(self) -> int:
        """获取最大步数"""
        return self.config.max_steps


# =============================================================================
# 便捷函数
# =============================================================================

def auto_adapt(model_name: str) -> tuple[ProtocolConfig, ProtocolAdapter]:
    """
    自动适配模型。

    Args:
        model_name: 模型名称

    Returns:
        (协议配置, 协议适配器) 元组
    """
    config = get_protocol_config(model_name=model_name)
    adapter = ProtocolAdapter(config)
    return config, adapter


def get_config_summary(config: ProtocolConfig) -> str:
    """获取配置摘要"""
    return f"""协议配置:
  - 协议: {config.protocol.value}
  - 坐标范围: 0-{config.coordinate_max}
  - 图像 resize: {config.image_config.is_resize}
  - 目标尺寸: {config.image_config.target_size}
  - 图像格式: {config.image_config.format}
  - Temperature: {config.temperature}
  - Max tokens: {config.max_tokens}
  - 动作延迟: {config.delay_after_action}s
  - 最大步数: {config.max_steps}"""


# Backward-compatible re-exports for legacy imports.
from .protocol_compat import ProtocolType, create_adapter  # noqa: E402
