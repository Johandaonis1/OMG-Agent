"""
Agent - A unified phone automation agent framework.

Combines the best features from Open-AutoGLM and gelab-zero:
- Clean architecture with clear separation of concerns
- Rich action space with INFO, ABORT, COMPLETE support
- Session management for task resumption
- History summary compression for efficient context management
- Task planning for complex multi-step tasks
- Callback mechanisms for human intervention
- Multi-model LLM support

Auto-adaptation:
- 自动检测模型类型并加载对应协议配置
- 支持 AutoGLM、gelab-zero、通用 VLM 三种协议
- 对标官方实现的截图尺寸、坐标系、提示词
"""

from .phone_agent import PhoneAgent, AgentConfig, StepResult, RunResult, ReplyMode
from .actions import ActionSpace, ActionHandler, ActionResult, ActionParser
from .actions.space import Action, ActionType, Point
from .history import HistoryManager, ConversationHistory
from .session import SessionManager, SessionState
from .planner import TaskPlanner, TaskPlan, SubTask, TaskStatus, analyze_task_complexity
from .llm import LLMConfig, ModelConfig, LLMClient
from .device import Screenshot, get_screenshot, take_screenshot
from .protocol_adapter import (
    Protocol,
    ProtocolConfig,
    ProtocolAdapter,
    ImageConfig,
    get_protocol_config,
    detect_protocol,
    auto_adapt,
    AUTOGLM_CONFIG,
    GELAB_ZERO_CONFIG,
    UNIVERSAL_CONFIG,
)
from .protocol_compat import (
    ProtocolType,
    ProtocolAdapter as UnifiedProtocolAdapter,
    AutoGLMMessageFormatter,
    GelabMessageFormatter,
    AutoGLMContextBuilder,
    GelabContextBuilder,
    AutoGLMStepController,
    GelabStepController,
    get_autoglm_system_prompt,
    get_gelab_system_prompt,
    create_adapter,
)
from .unified_executor import (
    UnifiedExecutor,
    ExecutionResult,
    ExecutionStep,
    StopReason,
    CompatibilityTester,
    create_executor,
)
from .gui_log_adapter import GUILogger, LogLevel, create_gui_logger
from .context_builder import ContextBuilder, ContextConfig, get_context_builder

__version__ = "0.3.0"
__all__ = [
    # Main agent
    "PhoneAgent",
    "AgentConfig",
    "StepResult",
    "RunResult",
    "ReplyMode",
    # Protocol adapter
    "Protocol",
    "ProtocolConfig",
    "ProtocolAdapter",
    "ImageConfig",
    "get_protocol_config",
    "detect_protocol",
    "auto_adapt",
    "AUTOGLM_CONFIG",
    "GELAB_ZERO_CONFIG",
    "UNIVERSAL_CONFIG",
    # Protocol compatibility layer (new in 0.3.0)
    "ProtocolType",
    "UnifiedProtocolAdapter",
    "AutoGLMMessageFormatter",
    "GelabMessageFormatter",
    "AutoGLMContextBuilder",
    "GelabContextBuilder",
    "AutoGLMStepController",
    "GelabStepController",
    "get_autoglm_system_prompt",
    "get_gelab_system_prompt",
    "create_adapter",
    # Unified executor (new in 0.3.0)
    "UnifiedExecutor",
    "ExecutionResult",
    "ExecutionStep",
    "StopReason",
    "CompatibilityTester",
    "create_executor",
    # GUI logger (new in 0.3.0)
    "GUILogger",
    "LogLevel",
    "create_gui_logger",
    # Context builder
    "ContextBuilder",
    "ContextConfig",
    "get_context_builder",
    # LLM
    "LLMConfig",
    "ModelConfig",  # Alias for backward compatibility
    "LLMClient",
    # Actions
    "ActionSpace",
    "ActionHandler",
    "ActionResult",
    "ActionParser",
    "Action",
    "ActionType",
    "Point",
    # Device
    "Screenshot",
    "get_screenshot",
    "take_screenshot",
    # History
    "HistoryManager",
    "ConversationHistory",
    # Session
    "SessionManager",
    "SessionState",
    # Planner
    "TaskPlanner",
    "TaskPlan",
    "SubTask",
    "TaskStatus",
    "analyze_task_complexity",
]

