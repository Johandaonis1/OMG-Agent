"""
Protocol Compatibility Layer - 协议兼容层

确保 OMGAgent 与 AutoGLM 和 Gelab-Zero 100% 协议兼容。

对标官方实现：
- AutoGLM: phone_agent/config/prompts_zh.py, phone_agent/agent.py
- Gelab-Zero: copilot_tools/parser_0920_summary.py, copilot_agent_server/local_server.py

核心对齐要素：
1. System Prompt - 严格提取原版 prompts
2. User Prompt - 消息格式 100% 一致
3. Action Format - 思考链和动作格式完全对齐
4. Step Control - 迭代次数、状态保存、中断机制
"""

import re
import json
from datetime import datetime
from typing import Any
from pathlib import Path
from enum import Enum


class ProtocolType(str, Enum):
    """协议类型"""
    AUTOGLM = "autoglm"      # Open-AutoGLM 官方协议
    GELAB_ZERO = "gelab"     # Gelab-Zero 官方协议
    UNIVERSAL = "universal"  # 通用优化协议


# =============================================================================
# AutoGLM 原版提示词提取 (对标 phone_agent/config/prompts_zh.py)
# =============================================================================

# 注意：此变量作为备用/参考。实际使用时可能会调用 prompts/autoglm.py
AUTOGLM_SYSTEM_PROMPT = """今天的日期是: {{date}}
你是一个智能体分析专家，可以根据操作历史和当前状态图执行一系列操作来完成任务。
你必须严格按照要求输出以下格式：
<think>{{think}}</think>
<answer>{{action}}</answer>

其中：
- <think>{{think}}</think> 是对你为什么选择这个操作的简短推理说明。
- <answer>{{action}}</answer> 是本次执行的具体操作指令，必须严格遵循下方定义的指令格式。

操作指令及其作用如下：
- do(action="Launch", app="xxx")
    Launch是启动目标app的操作，这比通过主屏幕导航更快。此操作完成后，您将自动收到结果状态的截图。
- do(action="Tap", element=[x,y])
    Tap是点击操作，点击屏幕上的特定点。可用此操作点击按钮、选择项目、从主屏幕打开应用程序，或与任何可点击的用户界面元素进行交互。坐标系统从左上角 (0,0) 开始到右下角（999,999)结束。此操作完成后，您将自动收到结果状态的截图。
- do(action="Tap", element=[x,y], message="重要操作")
    基本功能同Tap，点击涉及财产、支付、隐私等敏感按钮时触发。
- do(action="Type", text="xxx")
    Type是输入操作，在当前聚焦的输入框中输入文本。使用此操作前，请确保输入框已被聚焦（先点击它）。输入的文本将像使用键盘输入一样输入。重要提示：手机可能正在使用 ADB 键盘，该键盘不会像普通键盘那样占用屏幕空间。要确认键盘已激活，请查看屏幕底部是否显示 'ADB Keyboard {ON}' 类似的文本，或者检查输入框是否处于激活/高亮状态。不要仅仅依赖视觉上的键盘显示。自动清除文本：当你使用输入操作时，输入框中现有的任何文本（包括占位符文本和实际输入）都会在输入新文本前自动清除。你无需在输入前手动清除文本——直接使用输入操作输入所需文本即可。操作完成后，您将自动收到结果状态的截图。
- do(action="Type_Name", text="xxx")
    Type_Name是输入人名的操作，基本功能同Type。
- do(action="Interact")
    Interact是当有多个满足条件的选项时而触发的交互操作，询问用户如何选择。
- do(action="Swipe", start=[x1,y1], end=[x2,y2])
    Swipe是滑动操作，通过从起始坐标拖动到结束坐标来执行滑动手势。可用于滚动内容、在屏幕之间导航、下拉通知栏以及项目栏或进行基于手势的导航。坐标系统从左上角 (0,0) 开始到右下角（999,999)结束。滑动持续时间会自动调整以实现自然的移动。此操作完成后，您将自动收到结果状态的截图。
- do(action="Note", message="True")
    记录当前页面内容以便后续总结。
- do(action="Call_API", instruction="xxx")
    总结或评论当前页面或已记录的内容。
- do(action="Long Press", element=[x,y])
    Long Pres是长按操作，在屏幕上的特定点长按指定时间。可用于触发上下文菜单、选择文本或激活长按交互。坐标系统从左上角 (0,0) 开始到右下角（999,999)结束。此操作完成后，您将自动收到结果状态的屏幕截图。
- do(action="Double Tap", element=[x,y])
    Double Tap在屏幕上的特定点快速连续点按两次。使用此操作可以激活双击交互，如缩放、选择文本或打开项目。坐标系统从左上角 (0,0) 开始到右下角（999,999)结束。此操作完成后，您将自动收到结果状态的截图。
- do(action="Take_over", message="xxx")
    Take_over是接管操作，表示在登录和验证阶段需要用户协助。
- do(action="Back")
    导航返回到上一个屏幕或关闭当前对话框。相当于按下 Android 的返回按钮。使用此操作可以从更深的屏幕返回、关闭弹出窗口或退出当前上下文。此操作完成后，您将自动收到结果状态的截图。
- do(action="Home")
    Home是回到系统桌面的操作，相当于按下 Android 主屏幕按钮。使用此操作可退出当前应用并返回启动器，或从已知状态启动新任务。此操作完成后，您将自动收到结果状态的截图。
- do(action="Wait", duration="x seconds")
    等待页面加载，x为需要等待多少秒。
- finish(message="xxx")
    finish是结束任务的操作，表示准确完整完成任务，message是终止信息。

必须遵循的规则：
1. 在执行任何操作前，先检查当前app是否是目标app，如果不是，先执行 Launch。
2. 如果进入到了无关页面，先执行 Back。如果执行Back后页面没有变化，请点击页面左上角的返回键进行返回，或者右上角的X号关闭。
3. 如果页面未加载出内容，最多连续 Wait 三次，否则执行 Back重新进入。
4. 如果页面显示网络问题，需要重新加载，请点击重新加载。
5. 如果当前页面找不到目标联系人、商品、店铺等信息，可以尝试 Swipe 滑动查找。
6. 遇到价格区间、时间区间等筛选条件，如果没有完全符合的，可以放宽要求。
7. 在做小红书总结类任务时一定要筛选图文笔记。
8. 购物车全选后再点击全选可以把状态设为全不选，在做购物车任务时，如果购物车里已经有商品被选中时，你需要点击全选后再点击取消全选，再去找需要购买或者删除的商品。
9. 在做外卖任务时，如果相应店铺购物车里已经有其他商品你需要先把购物车清空再去购买用户指定的外卖。
10. 在做点外卖任务时，如果用户需要点多个外卖，请尽量在同一店铺进行购买，如果无法找到可以下单，并说明某个商品未找到。
11. 请严格遵循用户意图执行任务，用户的特殊要求可以执行多次搜索，滑动查找。比如（i）用户要求点一杯咖啡，要咸的，你可以直接搜索咸咖啡，或者搜索咖啡后滑动查找咸的咖啡，比如海盐咖啡。（ii）用户要找到XX群，发一条消息，你可以先搜索XX群，找不到结果后，将"群"字去掉，搜索XX重试。（iii）用户要找到宠物友好的餐厅，你可以搜索餐厅，找到筛选，找到设施，选择可带宠物，或者直接搜索可带宠物，必要时可以使用AI搜索。
12. 在选择日期时，如果原滑动方向与预期日期越来越远，请向反方向滑动查找。
13. 执行任务过程中如果有多个可选择的项目栏，请逐个查找每个项目栏，直到完成任务，一定不要在同一项目栏多次查找，从而陷入死循环。
14. 在执行下一步操作前请一定要检查上一步的操作是否生效，如果点击没生效，可能因为app反应较慢，请先稍微等待一下，如果还是不生效请调整一下点击位置重试，如果仍然不生效请跳过这一步继续任务，并在finish message说明点击不生效。
15. 在执行任务中如果遇到滑动不生效的情况，请调整一下起始点位置，增大滑动距离重试，如果还是不生效，有可能是已经滑到底了，请继续向反方向滑动，直到顶部或底部，如果仍然没有符合要求的结果，请跳过这一步继续任务，并在finish message说明但没找到要求的项目。
16. 在做游戏任务时如果在战斗页面如果有自动战斗一定要开启自动战斗，如果多轮历史状态相似要检查自动战斗是否开启。
17. 如果没有合适的搜索结果，可能是因为搜索页面不对，请返回到搜索页面的上一级尝试重新搜索，如果尝试三次返回上一级搜索后仍然没有符合要求的结果，执行 finish(message="原因")。
18. 在结束任务前请一定要仔细检查任务是否完整准确的完成，如果出现错选、漏选、多选的情况，请返回之前的步骤进行纠正。
"""


# =============================================================================
# Gelab-Zero 原版提示词提取 (对标 copilot_tools/parser_0920_summary.py)
# =============================================================================

GELAB_TASK_DEFINE_PROMPT = """你是一个手机 GUI-Agent 操作专家，你需要根据用户下发的任务、手机屏幕截图和交互操作的历史记录，借助既定的动作空间与手机进行交互，从而完成用户的任务。
请牢记，手机屏幕坐标系以左上角为原点，x轴向右，y轴向下，取值范围均为 0-1000。

# 行动原则：

1. 你需要明确记录自己上一次的action，如果是滑动，不能超过5次。
2. 你需要严格遵循用户的指令，如果你和用户进行过对话，需要更遵守最后一轮的指令

# Action Space:

在 Android 手机的场景下，你的动作空间包含以下9类操作，所有输出都必须遵守对应的参数要求：
1. CLICK：点击手机屏幕坐标，需包含点击的坐标位置 point。
例如：action:CLICK\tpoint:x,y
2. TYPE：在手机输入框中输入文字，需包含输入内容 value、输入框的位置 point。
例如：action:TYPE\tvalue:输入内容\tpoint:x,y
3. COMPLETE：任务完成后向用户报告结果，需包含报告的内容 value。
例如：action:COMPLETE\treturn:完成任务后向用户报告的内容
4. WAIT：等待指定时长，需包含等待时间 value（秒）。
例如：action:WAIT\tvalue:等待时间
5. AWAKE：唤醒指定应用，需包含唤醒的应用名称 value。
例如：action:AWAKE\tvalue:应用名称
6. INFO：询问用户问题或详细信息，需包含提问内容 value。
例如：action:INFO\tvalue:提问内容
7. ABORT：终止当前任务，仅在当前任务无法继续执行时使用，需包含 value 说明原因。
例如：action:ABORT\tvalue:终止任务的原因
8. SLIDE：在手机屏幕上滑动，滑动的方向不限，需包含起点 point1 和终点 point2。
例如：action:SLIDE\tpoint1:x1,y1\tpoint2:x2,y2
9. LONGPRESS：长按手机屏幕坐标，需包含长按的坐标位置 point。
例如：action:LONGPRESS\tpoint:x,y
"""


def get_autoglm_system_prompt(date: str | None = None) -> str:
    """获取 AutoGLM 风格的系统提示词"""
    # Prefer the prompt text aligned with Open-AutoGLM.
    from .prompts.autoglm import AUTOGLM_PROMPT_ZH

    if date is None:
        return AUTOGLM_PROMPT_ZH

    # Keep the body text identical; only override the date on the first line.
    return re.sub(
        r"^今天的日期是: .*?\n",
        f"今天的日期是: {date}\n",
        AUTOGLM_PROMPT_ZH,
        count=1,
    )


def get_gelab_system_prompt(task: str) -> str:
    """获取 Gelab-Zero 风格的系统提示词"""
    # Gelab-Zero 的 system prompt 不特定于任务，任务在 User Message 中
    return GELAB_TASK_DEFINE_PROMPT


# =============================================================================
# 消息格式转换器 (对标各协议的消息格式)
# =============================================================================

class AutoGLMMessageFormatter:
    """AutoGLM 消息格式器 - 对标 phone_agent/agent.py"""

    @staticmethod
    def format_thinking(think: str) -> str:
        """格式化思考内容"""
        return f"\n{think}\n"

    @staticmethod
    def format_action(action_type: str, **params) -> str:
        """格式化动作输出 - AutoGLM 风格 do(action="...", ...)"""
        if action_type == "COMPLETE":
            message = params.get("return", "Task completed")
            return f'finish(message="{message}")'
        elif action_type == "ABORT":
             message = params.get("value", "Task aborted")
             return f'finish(message="{message}")'

        action_name_map = {
            "CLICK": "Tap",
            "DOUBLE_TAP": "Double Tap",
            "LONG_PRESS": "Long Press",
            "SWIPE": "Swipe",
            "TYPE": "Type",
            "BACK": "Back",
            "HOME": "Home",
            "LAUNCH": "Launch",
            "WAIT": "Wait",
            "INFO": "Interact",
            "AWAKE": "Launch" # Gelab compatibility
        }

        action_name = action_name_map.get(action_type, action_type)

        parts = [f'action="{action_name}"']

        if action_type == "WAIT":
            dur = params.get("duration", params.get("value", "1"))
            if isinstance(dur, (int, float)):
                dur_str = f"{dur} seconds"
            else:
                dur_str = str(dur).strip()
                if "second" not in dur_str:
                    dur_str = f"{dur_str} seconds"
            parts.append(f'duration="{dur_str}"')
            return f'do({", ".join(parts)})'

        if "point" in params:
            parts.append(f"element={params['point']}")
        if "point1" in params:
            parts.append(f"start={params['point1']}")
        if "point2" in params:
            parts.append(f"end={params['point2']}")
        if "value" in params:
            if action_type == "TYPE":
                parts.append(f'text="{params["value"]}"')
            elif action_type == "LAUNCH" or action_type == "AWAKE":
                parts.append(f'app="{params["value"]}"')
            else:
                parts.append(f'value="{params["value"]}"')
        if "direction" in params:
            parts.append(f"direction={params['direction']}")
        if "duration" in params:
            dur = params["duration"]
            # For gesture/touch durations, keep numeric when possible.
            if isinstance(dur, (int, float)):
                parts.append(f"duration={dur}")
            else:
                parts.append(f'duration="{str(dur)}"')

        return f'do({", ".join(parts)})'

    @staticmethod
    def wrap_response(think: str, action_str: str) -> str:
        """包装完整的响应"""
        return f"\n{think}\n<answer>{action_str}</answer>"

    @staticmethod
    def parse_response(response: str) -> dict:
        """解析 AutoGLM 响应格式 - 对标 ModelClient.parse_response"""
        result = {}

        # 优先尝试 <think>/<answer> 解析 (Prompt 要求)
        think_match = re.search(r"<[Tt][Hh][Ii][Nn][Kk]>(.*?)</[Tt][Hh][Ii][Nn][Kk]>", response, re.DOTALL)
        answer_match = re.search(r"<[Aa][Nn][Ss][Ww][Ee][Rr]>(.*?)</[Aa][Nn][Ss][Ww][Ee][Rr]>", response, re.DOTALL)

        if think_match and answer_match:
            result["think"] = think_match.group(1).strip()
            result["action_content"] = answer_match.group(1).strip()
            return result

        # Fallback: 对标 ModelClient._parse_response (Marker based)
        # Rule 1: Check for finish(message=
        if "finish(message=" in response:
            parts = response.split("finish(message=", 1)
            result["think"] = parts[0].strip()
            result["action_content"] = "finish(message=" + parts[1]
            return result

        # Rule 2: Check for do(action=
        if "do(action=" in response:
            parts = response.split("do(action=", 1)
            result["think"] = parts[0].strip()
            result["action_content"] = "do(action=" + parts[1]
            return result
            
        # Rule 3: <answer> without <think>
        if answer_match:
             result["action_content"] = answer_match.group(1).strip()
             result["think"] = re.sub(r"<[Aa][Nn][Ss][Ww][Ee][Rr]>(.*?)</[Aa][Nn][Ss][Ww][Ee][Rr]>", "", response, flags=re.DOTALL).strip()
             return result

        # Rule 4: Return plain content (ActionParser will likely fail but original implementation does this)
        result["action_content"] = response
        return result


class GelabMessageFormatter:
    """Gelab-Zero 消息格式器 - 对标 copilot_tools/parser_0920_summary.py"""

    @staticmethod
    def format_thinking(think: str) -> str:
        """格式化思考内容"""
        return f"<THINK>{think}</THINK>"

    @staticmethod
    def format_action(action_type: str, **params) -> str:
        """格式化动作输出 - Gelab-Zero 风格 action:xxx\tpoint:xxx"""
        parts = []

        if "explain" in params:
            parts.append(f"explain:{params['explain']}")

        parts.append(f"action:{action_type}")

        if "point" in params:
            x, y = params["point"]
            parts.append(f"point:{x},{y}")
        if "point1" in params:
            x, y = params["point1"]
            parts.append(f"point1:{x},{y}")
        if "point2" in params:
            x, y = params["point2"]
            parts.append(f"point2:{x},{y}")
        if "value" in params:
            parts.append(f"value:{params['value']}")
        if "direction" in params:
            parts.append(f"direction:{params['direction']}")
        if "duration" in params:
            parts.append(f"duration:{params['duration']}")
        if "summary" in params:
            parts.append(f"summary:{params['summary']}")
        if "return" in params:
            parts.append(f"return:{params['return']}")

        return "\t".join(parts)

    @staticmethod
    def wrap_response(think: str, action_str: str) -> str:
        """包装完整的响应"""
        return f"\n{think}\n{action_str}\n"

    @staticmethod
    def parse_response(response: str) -> dict:
        """解析 Gelab-Zero 响应格式"""
        result = {}

        # 提取 thinking
        think_match = re.search(r"<[Tt][Hh][Ii][Nn][Kk]>(.*?)</[Tt][Hh][Ii][Nn][Kk]>", response, re.DOTALL)
        if think_match:
            result["cot"] = think_match.group(1).strip()

        # 提取 key-value pairs
        action_str = re.sub(r"<[Tt][Hh][Ii][Nn][Kk]>.*?</[Tt][Hh][Ii][Nn][Kk]>", "", response, flags=re.DOTALL).strip()
        
        # 移除可能的 XML 闭合标签残留 (issue workaround)
        action_str = action_str.replace("</THINK>", "").strip()

        # 分割并解析 - 严格对标 parser_0920_summary.py
        kvs = [kv.strip() for kv in action_str.split("\t") if kv.strip()]
        for kv in kvs:
            if ":" not in kv:
                continue
            key, value = kv.split(":", 1)
            key = key.strip().lower()
            value = value.strip()

            if key == "action":
                result["action"] = value
            elif "point" in key:
                 # Parse point format: "x,y" or "x y"
                try:
                    coords = value.replace(",", " ").split()
                    if len(coords) >= 2:
                        result[key] = [int(coords[0]), int(coords[1])]
                except:
                    pass
            elif key == "value":
                result["value"] = value
            elif key == "explain":
                result["explain"] = value
            elif key == "summary":
                result["summary"] = value
            elif key == "return":
                result["return"] = value
            else:
                result[key] = value

        return result


# =============================================================================
# Universal 协议支持 (V2 JSON)
# =============================================================================

class UniversalMessageFormatter:
    """Universal (JSON) 消息格式器"""

    @staticmethod
    def format_thinking(think: str) -> str:
        return think

    @staticmethod
    def format_action(action_type: str, **params) -> str:
        """格式化动作输出为 JSON - 用于历史记录"""
        action_dict = {"type": action_type}
        
        # 参数映射
        for k, v in params.items():
            if k == "duration" and action_type.lower() == "wait":
                action_dict["time"] = v
            elif k == "value":
                # 根据类型猜测 value 含义
                 if action_type.lower() == "type":
                     action_dict["text"] = v
                 elif action_type.lower() in ["launch", "open"]:
                     action_dict["app"] = v
                 else:
                     action_dict["value"] = v
            else:
                action_dict[k] = v
                
        return json.dumps(action_dict, ensure_ascii=False)

    @staticmethod
    def wrap_response(think: str, action_str: str) -> str:
        """包装完整响应"""
        # action_str 应该是一个 JSON 对象字符串
        try:
            # 尝试构造完整 JSON
            # 假设 action_str 已经是 {"action": {...}} 或者 {"type": ...}
            # 如果是旧版字符串，尝试转换为 JSON
            if action_str.strip().startswith("{"):
                return action_str
            else:
                return f'{{"thought": "{think}", "action": {{ "type": "Legacy", "value": "{action_str}" }}}}'
        except:
             return f'{{"thought": "{think}", "response": "{action_str}"}}'

    @staticmethod
    def parse_response(response: str) -> dict:
        """解析 JSON 响应 (支持 V2.1 增强字段)"""
        result = {}
        try:
            # 1. 清理 Markdown 代码块
            clean_resp = re.sub(r"^```json\s*", "", response.strip())
            clean_resp = re.sub(r"\s*```$", "", clean_resp)
            
            # 2. 尝试解析 JSON
            data = json.loads(clean_resp)
            
            # 3. 提取所有 V2.1 字段
            # AutoGLM 通用字段映射
            result["think"] = data.get("thought", data.get("thinking", ""))
            
            # 保存增强字段，供 UniversalContextBuilder 使用
            result["observation"] = data.get("observation", "")
            result["reflection"] = data.get("reflection", "")
            result["progress"] = data.get("progress", {}) # {completed: [], pending: []}
            result["summary"] = data.get("summary", "")
            
            action_data = data.get("action", {})
            if not action_data and "type" in data:
                 action_data = data
            
            # 4. 映射动作类型 (Action Map)
            raw_type = action_data.get("type", "unknown").lower()
            
            type_map = {
                "tap": "Tap", "click": "Tap",
                "type": "Type", "input": "Type",
                "swipe": "Swipe", "scroll": "Swipe",
                "back": "Back",
                "home": "Home",
                "wait": "Wait", "sleep": "Wait",
                "launch": "Launch", "open": "Launch",
                "finish": "COMPLETE", "complete": "COMPLETE", "success": "COMPLETE",
                "abort": "ABORT", "stop": "ABORT"
            }
            
            internal_type = type_map.get(raw_type, raw_type.capitalize())
            result["action"] = internal_type
            
            # 5. 映射参数
            for k, v in action_data.items():
                if k == "type": continue
                
                # 标准化
                if k == "time" and internal_type == "Wait":
                    result["duration"] = v
                elif k == "text" and internal_type == "Type":
                    result["value"] = v 
                elif k == "app" and internal_type == "Launch":
                    result["value"] = v
                else:
                    result[k] = v
            
            return result
            
        except json.JSONDecodeError:
            # 容错：如果 JSON 解析失败，尝试从文本中寻找特征
            if "finish" in response.lower() or "complete" in response.lower():
                return {"action": "COMPLETE", "value": response}
            return {"action": "ABORT", "value": f"JSON Parse Error: {response[:100]}"}


class AutoGLMContextBuilder:
    """
    AutoGLM 上下文构建器 - 100% 对标 phone_agent/agent.py

    官方 Open-AutoGLM 的消息格式：
    1. 系统消息: {"role": "system", "content": system_prompt}
    2. 首次用户消息: {"role": "user", "content": [image, text(task + screen_info)]}
    3. 首次助手消息: {"role": "assistant", "content": "<think>...</think><answer>...</answer>"}
    4. 后续用户消息: {"role": "user", "content": [text("** Screen Info **\\n\\n{screen_info}")]}
       (官方会移除旧消息中的图片，所以历史用户消息不包含图片)
    5. 后续助手消息: {"role": "assistant", "content": "<think>...</think><answer>...</answer>"}
    ...
    N. 当前用户消息: {"role": "user", "content": [image, text("** Screen Info **\\n\\n{screen_info}")]}
    """

    def __init__(self, task: str, system_prompt: str | None = None):
        self.task = task
        self.system_prompt = system_prompt or get_autoglm_system_prompt()
        self.history = []

    def build_initial_messages(self, screenshot_b64: str, current_app: str) -> list[dict]:
        """
        构建初始消息 - 对标 Open-AutoGLM agent.py 首次步骤
        """
        messages = []

        # System message
        messages.append({"role": "system", "content": self.system_prompt})

        # Current app info
        screen_info_json = json.dumps({"current_app": current_app}, ensure_ascii=False)
        text_content = f"{self.task}\n\n{screen_info_json}"

        # First user message with task and screenshot
        image_url = (
            screenshot_b64
            if screenshot_b64.startswith("data:image/")
            else f"data:image/png;base64,{screenshot_b64}"
        )
        messages.append({
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": text_content},
            ]
        })

        return messages

    def build_step_messages(
        self,
        history_entries: list[dict],
        screenshot_b64: str,
        current_app: str
    ) -> list[dict]:
        """
        构建步骤消息 (包含历史) - 100% 对标 Open-AutoGLM agent.py 后续步骤
        """
        messages = []

        # System message
        messages.append({"role": "system", "content": self.system_prompt})

        # 重建历史对话
        for idx, entry in enumerate(history_entries):
            app_name = entry.get('app', current_app)
            screen_info_json = json.dumps({"current_app": app_name}, ensure_ascii=False)

            if idx == 0:
                text_content = f"{self.task}\n\n{screen_info_json}"
            else:
                text_content = f"** Screen Info **\n\n{screen_info_json}"

            # User message
            messages.append({
                "role": "user",
                "content": [{"type": "text", "text": text_content}]
            })

            # Assistant message (action)
            think = entry.get("think", "")
            action = entry.get("action", "")
            messages.append({
                "role": "assistant",
                "content": f"<think>{think}</think><answer>{action}</answer>"
            })

        # Current user message
        screen_info_json = json.dumps({"current_app": current_app}, ensure_ascii=False)
        text_content = f"** Screen Info **\n\n{screen_info_json}"

        image_url = (
            screenshot_b64
            if screenshot_b64.startswith("data:image/")
            else f"data:image/png;base64,{screenshot_b64}"
        )
        messages.append({
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": text_content},
            ]
        })

        return messages


class UniversalContextBuilder(AutoGLMContextBuilder):
    """Universal 上下文构建器 (继承自 AutoGLM 但适配 JSON 格式)"""
    
    def __init__(self, task: str, system_prompt: str | None = None):
         from .prompts.system import get_system_prompt
         # 获取 Universal V2 Prompt
         sp = system_prompt or get_system_prompt("zh", "universal")
         super().__init__(task, sp)

    def build_step_messages(
        self,
        history_entries: list[dict],
        screenshot_b64: str,
        current_app: str
    ) -> list[dict]:
        """构建步骤消息 - V2.1: 注入任务进度和反思"""
        messages = []

        # System message
        messages.append({"role": "system", "content": self.system_prompt})

        # --- 获取上一轮的任务状态，用于注入到当前提示中 ---
        last_progress = None
        
        # 重建历史对话
        for idx, entry in enumerate(history_entries):
            app_name = entry.get('app', current_app)
            screen_info_json = json.dumps({"current_app": app_name}, ensure_ascii=False)

            # 构造 User 消息 (Observation)
            if idx == 0:
                text_content = f"{self.task}\n\n{screen_info_json}"
            else:
                text_content = f"** Screen Info **\n\n{screen_info_json}"

            messages.append({
                "role": "user",
                "content": [{"type": "text", "text": text_content}]
            })

            # 构造 Assistant 消息 (History - JSON)
            # 我们需要保存当时的所有思考过程，以便模型"回忆"起当时的状态
            hist_json = {
                "observation": entry.get("observation", ""),
                "reflection": entry.get("reflection", ""),
                "progress": entry.get("progress", {}),
                "thought": entry.get("think", ""),
                "action": {"type": "HistoryAction", "description": str(entry.get("action"))},
                "summary": entry.get("summary", "")
            }
            
            # 保存到变量中供下文使用
            if entry.get("progress"):
                last_progress = entry.get("progress")
            
            messages.append({
                "role": "assistant",
                "content": json.dumps(hist_json, ensure_ascii=False)
            })

        # --- 构造当前轮 User 消息 (包含 Context 增强) ---
        
        # Base Screen Info
        screen_data = {"current_app": current_app}
        context_parts = []
        
        # 1. 注入任务状态 (Task Status Payload)
        if last_progress:
            # 将上一轮的模型认为的进度，显式告知它自己，保持连贯性
            # 并提示它核实进度
            status_str = json.dumps(last_progress, ensure_ascii=False)
            context_parts.append(f"** Last Analysis of Task Progress **\n{status_str}\n(Please verify this progress based on the new screen.)")
            
        # 2. 注入屏幕信息
        context_parts.append(f"** Screen Info **\n{json.dumps(screen_data, ensure_ascii=False)}")
        
        final_text = "\n\n".join(context_parts)

        image_url = (
            screenshot_b64
            if screenshot_b64.startswith("data:image/")
            else f"data:image/png;base64,{screenshot_b64}"
        )
        messages.append({
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": final_text},
            ]
        })

        return messages


class GelabContextBuilder:
    """
    Gelab-Zero 上下文构建器 - 100% 对标 copilot_tools/parser_0920_summary.py
    """

    def __init__(self, task: str, model_config: dict | None = None):
        self.task = task
        self.model_config = model_config or {}
        # Gelab prompt is constant
        self.system_prompt = GELAB_TASK_DEFINE_PROMPT

    def build_messages(
        self,
        system_prompt: str,
        task: str,
        current_screenshot_b64: str,
        current_app: str,
        history_entries: list[dict],
        last_summary: str = "",
        qa_history: list[tuple] | None = None
    ) -> list[dict]:
        """
        构建消息 - 100% 对标 parser_0920_summary.py 中的 env2messages4ask
        """

        # 1. Prepare history summary
        summary_history = last_summary.strip() if last_summary else ""

        # 2. Prepare QA history
        qa_prompt = ""
        if qa_history and len(qa_history) > 0:
            qa_str_list = [f"你曾经提出的问题：{q}\n\n用户对你的指示：{a}" for q, a in qa_history]
            qa_prompt = "这是你和用户的对话历史： " + "\n" + "\n".join(qa_str_list) + "\n\n 你需要更加注意用户最后的指示。 "

        # 3. Construct 'history_display'
        if qa_prompt == "":
            history_display = summary_history if summary_history else "暂无历史操作"
        else:
            history_display = (summary_history + qa_prompt) if summary_history else "暂无历史操作"

        # 4. Construct task with user instruction
        user_instruction = f'\n\n{qa_prompt}\n\n' if qa_prompt != "" else ""
        full_task = task + user_instruction + "指令结束\n\n"

        # 5. Construct status prompt text
        status_text_part1 = f'''
已知用户指令为：{full_task}
已知已经执行过的历史动作如下：{history_display}
当前手机屏幕截图如下：
'''
        status_text_part2 = f'''

在执行操作之前，请务必回顾你的历史操作记录和限定的动作空间，先进行思考和解释然后输出动作空间和对应的参数：
1. 思考（THINK）：在 <THINK> 和 </THINK> 标签之间。
2. 解释（explain）：在动作格式中，使用 explain: 开头，简要说明当前动作的目的和执行方式。
在执行完操作后，请输出执行完当前步骤后的新历史总结。
输出格式示例：
<THINK> 思考的内容 </THINK>
explain:解释的内容\taction:动作空间和对应的参数\tsummary:执行完当前步骤后的新历史总结
'''

        # 6. Prepare image URL
        image_url = (
            current_screenshot_b64
            if current_screenshot_b64.startswith("data:image/")
            else f"data:image/jpeg;base64,{current_screenshot_b64}"
        )

        # 7. Construct final conversation
        conversations = [
            {
                "type": "text",
                "text": self.system_prompt
            },
            {
                "type": "text",
                "text": status_text_part1
            },
            {
                "type": "image_url",
                "image_url": {"url": image_url}
            },
            {
                "type": "text",
                "text": status_text_part2
            }
        ]

        messages = [{
            "role": "user",
            "content": conversations
        }]

        return messages


# =============================================================================
# 步骤控制 (对标各协议的 step management)
# =============================================================================

class AutoGLMStepController:
    """AutoGLM 步骤控制器 - 对标 phone_agent/agent.py"""

    def __init__(self, max_steps: int = 100):
        self.max_steps = max_steps
        self.step_count = 0

    def should_continue(self) -> bool:
        """检查是否继续"""
        return self.step_count < self.max_steps

    def increment_step(self):
        """增加步数"""
        self.step_count += 1

    def get_finish_reason(self, action: dict) -> str:
        """获取完成原因"""
        action_type = action.get("action", "").lower()

        if action_type == "finish":
            return "TASK_COMPLETED"
        elif action_type == "take_over":
            return "TAKE_OVER"
        elif self.step_count >= self.max_steps:
            return "MAX_STEPS_REACHED"
        else:
            return "UNKNOWN"


class GelabStepController:
    """Gelab-Zero 步骤控制器 - 对标 copilot_agent_client/mcp_agent_loop.py"""

    def __init__(
        self,
        max_steps: int = 400,
        delay_after_capture: float = 2.0,
        reply_mode: str = "pass_to_client"
    ):
        self.max_steps = max_steps
        self.delay_after_capture = delay_after_capture
        self.reply_mode = reply_mode  # "auto_reply", "pass_to_client", "manual_reply"
        self.step_count = 0
        self.local_step_count = 0

    def should_continue(self, action: dict | None = None) -> bool:
        """检查是否继续"""
        if action:
            action_type = action.get("action", "").upper()
            if action_type in ["COMPLETE", "ABORT"]:
                return False

        return self.local_step_count < self.max_steps

    def increment_step(self):
        """增加步数"""
        self.step_count += 1
        self.local_step_count += 1

    def get_stop_reason(self, action: dict | None = None, last_action_type: str | None = None) -> str:
        """获取停止原因 - 对标 mcp_agent_loop.py"""
        if action:
            action_type = action.get("action", "").upper()
            if action_type == "COMPLETE":
                return "TASK_COMPLETED_SUCCESSFULLY"
            elif action_type == "ABORT":
                return "TASK_ABORTED_BY_AGENT"
            elif action_type == "INFO":
                return "INFO_ACTION_NEEDS_REPLY"

        if last_action_type:
            if last_action_type.upper() == "COMPLETE":
                return "TASK_COMPLETED_SUCCESSFULLY"
            elif last_action_type.upper() == "ABORT":
                return "TASK_ABORTED_BY_AGENT"

        if self.local_step_count >= self.max_steps:
            return "MAX_STEPS_REACHED"

        return "UNKNOWN"


# =============================================================================
# 统一协议适配器
# =============================================================================

class ProtocolAdapter:
    """统一协议适配器 - 提供 100% 协议兼容"""

    def __init__(self, protocol: ProtocolType):
        self.protocol = protocol

        # 设置协议特定的配置
        if protocol == ProtocolType.AUTOGLM:
            self.coordinate_max = 999
            self.max_steps = 100
            self.delay_after_action = 1.0
            self.temperature = 0.0
            self.image_format = "png"
            self.image_quality = 100
            self.resize_image = False
        elif protocol == ProtocolType.GELAB_ZERO:
            self.coordinate_max = 1000
            self.max_steps = 400
            self.delay_after_action = 2.0
            self.temperature = 0.1
            self.image_format = "jpeg"
            self.image_quality = 85
            self.resize_image = True
            self.target_size = (728, 728)
        else:  # UNIVERSAL
            self.coordinate_max = 1000
            self.max_steps = 100
            self.delay_after_action = 1.5
            self.temperature = 0.1
            self.image_format = "jpeg"
            self.image_quality = 85
            self.resize_image = True
            self.target_size = (728, 728)

    def get_system_prompt(self, task: str | None = None, date: str | None = None) -> str:
        """获取系统提示词"""
        if self.protocol == ProtocolType.AUTOGLM:
            return get_autoglm_system_prompt(date)
        elif self.protocol == ProtocolType.GELAB_ZERO:
            return get_gelab_system_prompt(task or "")
        else:
            # Universal V2 Prompt
            from .prompts.system import get_system_prompt
            return get_system_prompt("zh", "universal")

    def get_message_formatter(self):
        """获取消息格式化器"""
        if self.protocol == ProtocolType.AUTOGLM:
            return AutoGLMMessageFormatter()
        elif self.protocol == ProtocolType.UNIVERSAL:
            try:
                # 检查是否已定义 UniversalMessageFormatter (避免循环引用或未定义错误)
                return UniversalMessageFormatter()
            except NameError:
                # Fallback to Gelab if UniversalMessageFormatter is not ready
                return GelabMessageFormatter()
        else:
            return GelabMessageFormatter()

    def get_context_builder(self, task: str, **kwargs):
        """获取上下文构建器"""
        if self.protocol == ProtocolType.AUTOGLM:
            return AutoGLMContextBuilder(task, kwargs.get("system_prompt"))
        elif self.protocol == ProtocolType.UNIVERSAL:
            try:
                return UniversalContextBuilder(task, kwargs.get("system_prompt"))
            except NameError:
                return AutoGLMContextBuilder(task, kwargs.get("system_prompt"))
        else:
            return GelabContextBuilder(task, kwargs.get("model_config"))

    def get_step_controller(self, **kwargs) -> GelabStepController | AutoGLMStepController:
        """获取步骤控制器"""
        max_steps = kwargs.get("max_steps", self.max_steps)
        delay = kwargs.get("delay_after_action", self.delay_after_action)

        if self.protocol == ProtocolType.AUTOGLM:
            return AutoGLMStepController(max_steps)
        else:
            reply_mode = kwargs.get("reply_mode", "pass_to_client")
            return GelabStepController(max_steps, delay, reply_mode)

    def normalize_coordinates(self, x: int, y: int, from_max: int = 1000) -> tuple[int, int]:
        """归一化坐标"""
        if from_max == self.coordinate_max:
            return x, y
        scale = self.coordinate_max / from_max
        return int(x * scale), int(y * scale)

    def parse_action(self, response: str) -> dict:
        """解析动作响应"""
        formatter = self.get_message_formatter()
        return formatter.parse_response(response)

    def format_action(self, action_type: str, **params) -> str:
        """格式化动作"""
        formatter = self.get_message_formatter()
        return formatter.format_action(action_type, **params)


# =============================================================================
# 便捷函数
# =============================================================================

def create_adapter(protocol: str | ProtocolType) -> ProtocolAdapter:
    """创建协议适配器"""
    if isinstance(protocol, str):
        protocol = ProtocolType(protocol.lower())
    return ProtocolAdapter(protocol)


def get_original_prompt(protocol: str, task: str | None = None) -> str:
    """获取原版提示词"""
    adapter = create_adapter(protocol)
    return adapter.get_system_prompt(task)


# 示例用法
if __name__ == "__main__":
    # AutoGLM 协议
    adapter = create_adapter("autoglm")
    print("AutoGLM System Prompt:")
    print(adapter.get_system_prompt()[:200] + "...")

    # Gelab-Zero 协议
    adapter = create_adapter("gelab")
    print("\nGelab-Zero System Prompt:")
    print(adapter.get_system_prompt("打开微信给张三发消息")[:200] + "...")
