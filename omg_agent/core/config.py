"""
配置管理模块

提供应用配置的加载、保存和管理功能
支持多模型配置、Agent 类型切换、参数自动适配

对标官方实现:
- AutoGLM: 0-999 坐标，原始分辨率，temperature=0.0
- gelab-zero: 0-1000 坐标，728x728，temperature=0.1
- 通用: 0-1000 坐标，728x728，temperature=0.1 (兼容优化)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Literal

# 默认配置目录
CONFIG_DIR = Path.home() / ".omg-agent" / "configs"
CONFIG_FILE = CONFIG_DIR / "config.json"

# 历史记录目录
HISTORY_DIR = Path.home() / ".omg-agent" / "history"


# =============================================================================
# Agent 类型定义
# =============================================================================
AgentType = Literal["universal", "autoglm", "gelab"]


@dataclass
class ImagePreprocessConfig:
    """图像预处理配置"""

    is_resize: bool = True  # 是否 resize 截图
    target_size: tuple[int, int] = (728, 728)  # 目标尺寸
    format: str = "jpeg"  # 输出格式: png 或 jpeg
    quality: int = 85  # JPEG 质量 (1-100)
    keep_aspect_ratio: bool = False  # 是否保持宽高比


@dataclass
class ModelProfile:
    """模型配置档案 - 包含完整的默认参数"""

    # 基本信息
    name: str = "自定义"
    base_url: str = "http://localhost:8000/v1"
    api_key: str = "EMPTY"
    model_name: str = "autoglm-phone-9b"

    # Agent 类型 (决定提示词和解析方式)
    agent_type: AgentType = "universal"

    # 执行参数 (根据 agent_type 自动适配默认值)
    max_steps: int = 100
    temperature: float = 0.1
    top_p: float = 0.95
    max_tokens: int = 4096
    frequency_penalty: float = 0.0
    step_delay: float = 1.5

    # 设备控制
    auto_wake: bool = True
    reset_home: bool = True

    # 图像预处理配置
    image_preprocess: ImagePreprocessConfig = None

    # 坐标系范围: 1000 (gelab/universal) 或 999 (autoglm)
    coordinate_max: int = 1000

    # 对比测试路径 (开发用)
    open_autoglm_path: str = ""
    gelab_zero_path: str = ""

    def __post_init__(self):
        # 根据 agent_type 设置正确的图像预处理默认值
        if self.image_preprocess is None:
            if self.agent_type == "autoglm":
                # AutoGLM: 不做 resize，保持原始尺寸，PNG 格式
                self.image_preprocess = ImagePreprocessConfig(
                    is_resize=False,
                    target_size=(1080, 2400),
                    format="png",
                    quality=100
                )
            else:
                # gelab 和 universal: resize 到 728x728，JPEG 格式
                self.image_preprocess = ImagePreprocessConfig(
                    is_resize=True,
                    target_size=(728, 728),
                    format="jpeg",
                    quality=85
                )

    def apply_agent_defaults(self) -> None:
        """根据 agent_type 应用官方默认参数"""
        if self.agent_type == "autoglm":
            # AutoGLM 官方配置
            self.coordinate_max = 999
            self.temperature = 0.0
            self.top_p = 0.85
            self.max_tokens = 3000
            self.frequency_penalty = 0.2
            self.step_delay = 1.0
            self.max_steps = 100
            self.image_preprocess = ImagePreprocessConfig(
                is_resize=False,
                target_size=(1080, 2400),
                format="png",
                quality=100
            )
        elif self.agent_type == "gelab":
            # gelab-zero 官方配置
            self.coordinate_max = 1000
            self.temperature = 0.1
            self.top_p = 0.95
            self.max_tokens = 4096
            self.frequency_penalty = 0.0
            self.step_delay = 2.0
            self.max_steps = 400
            self.image_preprocess = ImagePreprocessConfig(
                is_resize=True,
                target_size=(728, 728),
                format="jpeg",
                quality=85
            )
        else:  # universal
            # 通用优化配置 (结合两者)
            self.coordinate_max = 1000
            self.temperature = 0.1
            self.top_p = 0.95
            self.max_tokens = 4096
            self.frequency_penalty = 0.0
            self.step_delay = 1.5
            self.max_steps = 100
            self.image_preprocess = ImagePreprocessConfig(
                is_resize=True,
                target_size=(728, 728),
                format="jpeg",
                quality=85
            )


# 兼容旧版本
ModelConfig = ModelProfile


@dataclass
class UIConfig:
    """界面配置"""

    theme: str = "dark"
    language: str = "zh"
    window_width: int = 1280
    window_height: int = 800
    modern_ui_intro_shown: bool = False  # 是否已显示Modern UI引导


@dataclass
class Config:
    """应用配置"""

    # 当前使用的模型配置
    current_profile: str = "自定义"

    # 所有保存的模型配置 (name -> ModelProfile)
    model_profiles: dict = field(default_factory=dict)

    # UI 配置
    ui: UIConfig = field(default_factory=UIConfig)

    # 上次使用的设备
    last_device: Optional[str] = None

    def __post_init__(self):
        """确保当前配置存在"""
        if not self.model_profiles:
            self.model_profiles = {"自定义": asdict(ModelProfile())}
        if self.current_profile not in self.model_profiles:
            self.current_profile = list(self.model_profiles.keys())[0]

    @property
    def model(self) -> ModelProfile:
        """获取当前模型配置"""
        profile_dict = self.model_profiles.get(self.current_profile, {})
        fields = {f.name for f in ModelProfile.__dataclass_fields__.values()}
        filtered = {k: v for k, v in profile_dict.items() if k in fields}

        # 处理嵌套的 image_preprocess
        if "image_preprocess" in filtered and isinstance(filtered["image_preprocess"], dict):
            img_fields = {f.name for f in ImagePreprocessConfig.__dataclass_fields__.values()}
            img_data = {k: v for k, v in filtered["image_preprocess"].items() if k in img_fields}
            # 处理 tuple
            if "target_size" in img_data and isinstance(img_data["target_size"], list):
                img_data["target_size"] = tuple(img_data["target_size"])
            filtered["image_preprocess"] = ImagePreprocessConfig(**img_data)

        return ModelProfile(**filtered)

    def set_model(self, profile: ModelProfile) -> None:
        """设置当前模型配置"""
        self.model_profiles[profile.name] = asdict(profile)
        self.current_profile = profile.name

    def get_profile_names(self) -> list[str]:
        """获取所有配置档案名称"""
        return list(self.model_profiles.keys())

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "current_profile": self.current_profile,
            "model_profiles": self.model_profiles,
            "ui": asdict(self.ui),
            "last_device": self.last_device,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Config:
        """从字典创建配置"""
        ui_data = data.get("ui", {})
        ui_fields = {f.name for f in UIConfig.__dataclass_fields__.values()}

        # 兼容旧版本配置（只有单个 model 字段）
        model_profiles = data.get("model_profiles", {})
        if not model_profiles and "model" in data:
            old_model = data["model"]
            old_model["name"] = "自定义"
            model_profiles = {"自定义": old_model}

        return cls(
            current_profile=data.get("current_profile", "自定义"),
            model_profiles=model_profiles,
            ui=UIConfig(**{k: v for k, v in ui_data.items() if k in ui_fields}),
            last_device=data.get("last_device"),
        )


def load_config() -> Config:
    """加载配置文件"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return Config.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Warning: Failed to load config: {e}")
    return Config()


def save_config(config: Config) -> None:
    """保存配置文件"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)


# =============================================================================
# 模型预设 (内置模板，对标官方配置)
# =============================================================================
MODEL_PRESETS = {
    # === AutoGLM 系列 (使用官方 autoglm 配置) ===
    "BigModel (智谱 AutoGLM)": ModelProfile(
        name="BigModel (智谱 AutoGLM)",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        api_key="",
        model_name="autoglm-phone",  # BigModel 使用此模型名
        agent_type="autoglm",
        coordinate_max=999,
        temperature=0.0,
        top_p=0.85,
        max_tokens=3000,
        frequency_penalty=0.2,
        step_delay=1.0,
        max_steps=100,
        image_preprocess=ImagePreprocessConfig(is_resize=False, format="png"),
    ),
    "魔搭 AutoGLM": ModelProfile(
        name="魔搭 AutoGLM",
        base_url="https://api-inference.modelscope.cn/v1",
        api_key="",
        model_name="ZhipuAI/AutoGLM-Phone-9B",  # 魔搭使用此模型名
        agent_type="autoglm",
        coordinate_max=999,
        temperature=0.0,
        top_p=0.85,
        max_tokens=3000,
        frequency_penalty=0.2,
        step_delay=1.0,
        max_steps=100,
        image_preprocess=ImagePreprocessConfig(is_resize=False, format="png"),
    ),

    # === Step-GUI 系列 (使用 gelab 协议) ===
    "Step-GUI (阶跃星辰)": ModelProfile(
        name="Step-GUI (阶跃星辰)",
        base_url="https://api.stepfun.com/v1",
        api_key="",
        model_name="step-gui",
        agent_type="gelab",  # Step-GUI 使用 gelab 协议
        coordinate_max=1000,
        temperature=0.1,
        top_p=0.95,
        max_tokens=4096,
        step_delay=2.0,
        max_steps=400,
        image_preprocess=ImagePreprocessConfig(is_resize=True, target_size=(728, 728)),
    ),

    # === 本地部署 (Ollama / vLLM) ===
    "Ollama (本地)": ModelProfile(
        name="Ollama (本地)",
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        model_name="llava:latest",  # 可替换为其他视觉模型
        agent_type="universal",
        coordinate_max=1000,
        temperature=0.1,
        top_p=0.95,
        max_tokens=4096,
        step_delay=1.5,
        max_steps=100,
        image_preprocess=ImagePreprocessConfig(is_resize=True, target_size=(728, 728)),
    ),
    "vLLM (本地)": ModelProfile(
        name="vLLM (本地)",
        base_url="http://localhost:8000/v1",
        api_key="EMPTY",
        model_name="Qwen/Qwen2-VL-7B-Instruct",  # 可替换
        agent_type="universal",
        coordinate_max=1000,
        temperature=0.1,
        top_p=0.95,
        max_tokens=4096,
        step_delay=1.5,
        max_steps=100,
        image_preprocess=ImagePreprocessConfig(is_resize=True, target_size=(728, 728)),
    ),

    # === 自定义 ===
    "自定义": ModelProfile(name="自定义"),
}


# Agent 类型描述
AGENT_TYPE_INFO = {
    "universal": {
        "name": "通用 (Universal)",
        "description": "兼容大多数 VLM，结合 AutoGLM 和 gelab-zero 优化",
        "icon": "🌐",
    },
    "autoglm": {
        "name": "AutoGLM",
        "description": "对标 Open-AutoGLM 官方实现，适用于 AutoGLM 系列模型",
        "icon": "🤖",
    },
    "gelab": {
        "name": "gelab-zero",
        "description": "对标 gelab-zero 官方实现，适用于 gelab 系列模型",
        "icon": "🔬",
    },
}


# 快捷任务预设
QUICK_TASKS = [
    "打开微信",
    "打开设置",
    "截图并保存",
    "返回主屏幕",
    "查看最近通知",
    "打开相机拍照",
    "打开浏览器搜索今天天气",
]

# 滑动手势预设
SWIPE_GESTURES = {
    "上滑": {"start": (500, 800), "end": (500, 200)},
    "下滑": {"start": (500, 200), "end": (500, 800)},
    "左滑": {"start": (800, 500), "end": (200, 500)},
    "右滑": {"start": (200, 500), "end": (800, 500)},
}


def get_default_config_for_model(model_name: str) -> dict:
    """根据模型名称获取默认配置"""
    model_lower = model_name.lower()

    # AutoGLM 系列
    if any(k in model_lower for k in ["autoglm", "glm-4v"]):
        return {
            "agent_type": "autoglm",
            "coordinate_max": 999,
            "temperature": 0.0,
            "top_p": 0.85,
            "max_tokens": 3000,
            "step_delay": 1.0,
            "max_steps": 100,
        }

    # gelab-zero 系列
    if any(k in model_lower for k in ["gelab"]):
        return {
            "agent_type": "gelab",
            "coordinate_max": 1000,
            "temperature": 0.1,
            "top_p": 0.95,
            "max_tokens": 4096,
            "step_delay": 2.0,
            "max_steps": 400,
        }

    # Step-GUI 和其他通用 VLM
    return {
        "agent_type": "universal",
        "coordinate_max": 1000,
        "temperature": 0.1,
        "top_p": 0.95,
        "max_tokens": 4096,
        "step_delay": 1.5,
        "max_steps": 100,
    }
