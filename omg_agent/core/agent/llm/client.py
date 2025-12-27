"""
LLM Client - OpenAI compatible LLM interface.

Supports:
- OpenAI official API
- Local models (Ollama, vLLM, LocalAI, etc.)
- Any OpenAI-compatible API
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM configuration (OpenAI compatible) - 与官方AutoGLM一致的默认参数."""

    # Model
    model: str = "autoglm-phone-9b"

    # API settings
    api_key: str | None = None
    api_base: str | None = None

    # Generation parameters - 与官方Open-AutoGLM一致
    max_tokens: int = 3000
    temperature: float = 0.0  # 官方默认
    top_p: float = 0.85  # 官方默认
    frequency_penalty: float = 0.2  # 官方默认

    # Image handling
    resize_images: bool = True
    max_image_size: int = 1024

    # Timeout
    timeout: int = 120

    # Streaming (some OpenAI-compatible servers don't support it reliably)
    stream: bool = False

    # Retry settings (for connection errors)
    max_retries: int = 3  # 最大重试次数
    retry_delay: float = 2.0  # 初始重试延迟（秒）
    retry_backoff: float = 2.0  # 重试延迟倍增因子

    # Language (for prompts)
    lang: str = "zh"

    def __post_init__(self):
        # Load from environment if not set
        if self.api_key is None:
            self.api_key = os.environ.get("OPENAI_API_KEY", "EMPTY")

        if self.api_base is None:
            self.api_base = os.environ.get("OPENAI_API_BASE", "http://localhost:8000/v1")

    # Aliases for backward compatibility with phone_agent.model.ModelConfig
    @property
    def base_url(self) -> str | None:
        return self.api_base

    @base_url.setter
    def base_url(self, value: str | None):
        self.api_base = value

    @property
    def model_name(self) -> str:
        return self.model

    @model_name.setter
    def model_name(self, value: str):
        self.model = value


# Alias for backward compatibility
ModelConfig = LLMConfig


@dataclass
class LLMResponse:
    """LLM response container."""

    content: str
    thinking: str = ""
    action: str = ""
    raw_response: dict = field(default_factory=dict)

    # Token usage
    prompt_tokens: int = 0
    completion_tokens: int = 0

    # Timing
    latency_ms: int = 0

    def parse_thinking_and_action(self) -> None:
        """
        Parse thinking and action from content.

        Match Open-AutoGLM parsing rules (`phone_agent/model/client.py`):
        1. If content contains 'finish(message=', everything before is thinking,
           everything from 'finish(message=' onwards is action.
        2. Else if content contains 'do(action=', everything before is thinking,
           everything from 'do(action=' onwards is action.
        3. Fallback: If content contains '<answer>', use legacy parsing with XML tags.
        4. Otherwise, return empty thinking and full content as action.
        """
        import re

        content = self.content or ""

        # Robust handling: if the model follows the prompt and wraps output in
        # <think>/<answer> tags, extract the inner content first. (Some models
        # will otherwise trip rule 2 because "do(action=" appears inside <answer>.)
        answer_match = re.search(
            r"<[Aa][Nn][Ss][Ww][Ee][Rr]>(.*?)</[Aa][Nn][Ss][Ww][Ee][Rr]>",
            content,
            flags=re.DOTALL,
        )
        if answer_match:
            action_part = answer_match.group(1).strip()
            think_match = re.search(
                r"<[Tt][Hh][Ii][Nn][Kk]>(.*?)</[Tt][Hh][Ii][Nn][Kk]>",
                content,
                flags=re.DOTALL,
            )
            if think_match:
                thinking_part = think_match.group(1).strip()
            else:
                thinking_part = content[: answer_match.start()]
                thinking_part = re.sub(r"</?think>", "", thinking_part, flags=re.IGNORECASE).strip()

            self.thinking = thinking_part
            self.action = action_part
            return

        if "finish(message=" in content:
            parts = content.split("finish(message=", 1)
            thinking = parts[0].strip()
            action = "finish(message=" + parts[1]

            thinking = re.sub(r"</?think>", "", thinking, flags=re.IGNORECASE).strip()
            thinking = re.sub(r"</?answer>", "", thinking, flags=re.IGNORECASE).strip()
            action = re.sub(r"</?answer>", "", action, flags=re.IGNORECASE).strip()

            self.thinking = thinking
            self.action = action
            return

        if "do(action=" in content:
            parts = content.split("do(action=", 1)
            thinking = parts[0].strip()
            action = "do(action=" + parts[1]

            thinking = re.sub(r"</?think>", "", thinking, flags=re.IGNORECASE).strip()
            thinking = re.sub(r"</?answer>", "", thinking, flags=re.IGNORECASE).strip()
            action = re.sub(r"</?answer>", "", action, flags=re.IGNORECASE).strip()

            self.thinking = thinking
            self.action = action
            return

        if re.search(r"<answer>", content, re.IGNORECASE):
            parts = re.split(r"<answer>", content, maxsplit=1, flags=re.IGNORECASE)
            thinking_part = parts[0]
            action_part = parts[1] if len(parts) > 1 else ""
            thinking_part = re.sub(r"</?think>", "", thinking_part, flags=re.IGNORECASE).strip()
            action_part = re.sub(r"</answer>", "", action_part, flags=re.IGNORECASE).strip()
            self.thinking = thinking_part
            self.action = action_part
            return

        self.thinking = ""
        self.action = content


class LLMClient:
    """
    Multi-provider LLM client.

    Supports vision models for screenshot understanding.
    """

    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig()
        self._client = None
        self._use_legacy_api = False

    def _get_openai_client(self):
        """Get OpenAI client (lazy init)."""
        if self._client is None:
            try:
                import openai
                # Check if using new API (1.0+) or legacy API
                if hasattr(openai, 'OpenAI'):
                    # New API (openai >= 1.0)
                    self._client = openai.OpenAI(
                        api_key=self.config.api_key,
                        base_url=self.config.api_base,
                        timeout=self.config.timeout
                    )
                    self._use_legacy_api = False
                else:
                    # Legacy API (openai < 1.0)
                    openai.api_key = self.config.api_key
                    if self.config.api_base:
                        openai.api_base = self.config.api_base
                    self._client = openai
                    self._use_legacy_api = True
                    logger.info("Using legacy OpenAI API (< 1.0)")
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        return self._client

    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is retryable (connection errors, timeouts, 5xx errors)."""
        error_str = str(error).lower()

        # Connection errors
        if any(keyword in error_str for keyword in [
            "connect", "connection", "timeout", "timed out",
            "ssl", "eof", "reset", "refused", "unreachable",
            "network", "host", "socket"
        ]):
            return True

        # HTTP 5xx errors (server errors)
        if any(code in error_str for code in ["500", "502", "503", "504"]):
            return True

        # Rate limiting
        if "429" in error_str or "rate" in error_str:
            return True

        return False

    def request(self, messages: list[dict[str, Any]], **kwargs) -> LLMResponse:
        """
        Send request to LLM with automatic retry on connection errors.

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Override config parameters

        Returns:
            LLMResponse with parsed content

        Raises:
            Exception: If all retries are exhausted
        """
        start_time = time.time()

        # Initialize client first to detect API version
        self._get_openai_client()

        # Merge config with kwargs
        stream = bool(kwargs.get("stream", self.config.stream))
        params = {
            "model": kwargs.get("model", self.config.model),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "top_p": kwargs.get("top_p", self.config.top_p),
            "frequency_penalty": kwargs.get("frequency_penalty", self.config.frequency_penalty),
            "stream": stream,
        }

        # Preprocess messages (handle images)
        processed_messages = self._preprocess_messages(messages)

        # Retry logic with exponential backoff
        max_retries = self.config.max_retries
        retry_delay = self.config.retry_delay
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # Use appropriate API based on version
                if self._use_legacy_api:
                    response = self._request_openai_legacy(processed_messages, params)
                else:
                    response = self._request_openai(processed_messages, params)

                # Some OpenAI-compatible servers misbehave in stream mode and return empty deltas.
                if params.get("stream") and not (response.content or "").strip():
                    logger.warning("[LLM] Empty content in stream mode; retrying once with stream disabled")
                    params_no_stream = params.copy()
                    params_no_stream["stream"] = False
                    if self._use_legacy_api:
                        response = self._request_openai_legacy(processed_messages, params_no_stream)
                    else:
                        response = self._request_openai(processed_messages, params_no_stream)

                # Calculate latency
                response.latency_ms = int((time.time() - start_time) * 1000)

                # Parse thinking and action
                response.parse_thinking_and_action()

                # Log if we recovered from a previous error
                if attempt > 0:
                    logger.info(f"LLM request succeeded after {attempt} retries")

                return response

            except Exception as e:
                last_error = e

                # Check if this error is retryable
                if not self._is_retryable_error(e):
                    logger.error(f"Non-retryable LLM error: {e}")
                    raise

                # Check if we have retries left
                if attempt < max_retries:
                    wait_time = retry_delay * (self.config.retry_backoff ** attempt)
                    logger.warning(
                        f"LLM connection error (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    time.sleep(wait_time)

                    # Reset client to force reconnection
                    self._client = None
                else:
                    logger.error(
                        f"LLM request failed after {max_retries + 1} attempts. Last error: {e}"
                    )

        # All retries exhausted
        raise last_error

    def _preprocess_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Preprocess messages, handling image encoding."""
        import base64

        processed = []
        for msg in messages:
            new_msg = {"role": msg["role"]}

            content = msg.get("content")
            if isinstance(content, str):
                new_msg["content"] = content
            elif isinstance(content, list):
                # Multi-modal content
                new_content = []
                for item in content:
                    if item.get("type") == "text":
                        new_content.append(item)
                    elif item.get("type") == "image_url":
                        url = item.get("image_url", {}).get("url", "")
                        if url.startswith("data:image/"):
                            # Already base64 encoded
                            new_content.append(item)
                        elif url.startswith(("http://", "https://")):
                            # Remote URL, keep as is
                            new_content.append(item)
                        else:
                            # Local file path, encode
                            try:
                                with open(url, "rb") as f:
                                    data = f.read()
                                b64 = base64.b64encode(data).decode("utf-8")
                                # Detect format
                                fmt = "png"
                                if data[:2] == b"\xff\xd8":
                                    fmt = "jpeg"
                                new_content.append({
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/{fmt};base64,{b64}"}
                                })
                            except Exception as e:
                                # Skip failed images
                                logger.warning(f"Failed to load image {url}: {e}")
                    elif item.get("type") == "image_base64":
                        # Convert to standard format
                        b64 = item.get("image_base64", {}).get("data", "")
                        new_content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"}
                        })

                new_msg["content"] = new_content
            else:
                new_msg["content"] = content

            processed.append(new_msg)

        return processed

    def _request_openai(self, messages: list[dict], params: dict) -> LLMResponse:
        """Send request using OpenAI API."""
        client = self._get_openai_client()

        recovered_json = None
        response_obj = None
        stream = bool(params.get("stream"))

        try:
            logger.debug(f"Requesting with params: {params}")
            response_obj = client.chat.completions.create(
                messages=messages,
                **params
            )
        except json.decoder.JSONDecodeError as e:
            logger.error(f"JSON Decode Error from server: {e}")
            
            # Attempt recovery: "Extra data" means valid JSON exists at the start
            raw_data = getattr(e, 'doc', '')
            if raw_data:
                logger.debug(f"Raw response prefix: {raw_data[:500]}")
                try:
                    # e.pos indicates where parsing failed (start of extra data)
                    valid_json_str = raw_data[:e.pos]
                    recovered_json = json.loads(valid_json_str)
                    logger.info("Successfully recovered valid JSON object from response.")
                except Exception as rec_err:
                    logger.error(f"Recovery failed: {rec_err}")
                    raise RuntimeError(f"Server returned invalid JSON. Raw: {raw_data[:200]}") from e
            else:
                raise e
        except Exception as e:
             raise e

        content = ""
        role = "assistant"

        # Handle recovered static JSON (if stream failed but data recovered)
        if recovered_json:
            try:
                choices = recovered_json.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    content = message.get("content", "") or ""
                    role = message.get("role", "assistant")
                if not content:
                    logger.warning("[LLM] Recovered JSON has empty content")
            except Exception as parse_err:
                logger.error(f"Error parsing recovered JSON: {parse_err}")

        # Handle stream vs non-stream
        elif response_obj is not None:
            if stream:
                chunk_count = 0
                try:
                    for chunk in response_obj:
                        chunk_count += 1
                        if not chunk.choices:
                            continue
                        delta = chunk.choices[0].delta
                        if delta and getattr(delta, "content", None):
                            content += delta.content
                        if delta and getattr(delta, "role", None):
                            role = delta.role
                except TypeError:
                    # Some servers ignore `stream=true` and return a non-iterable response object.
                    try:
                        if getattr(response_obj, "choices", None):
                            message = response_obj.choices[0].message
                            content = getattr(message, "content", None) or ""
                            role = getattr(message, "role", None) or "assistant"
                    except Exception as parse_err:
                        logger.error(f"[LLM] Failed to parse non-iterable stream response: {parse_err}")

                if not content:
                    logger.warning(f"[LLM] Stream ended with {chunk_count} chunks but empty content")
            else:
                try:
                    if response_obj.choices and len(response_obj.choices) > 0:
                        message = response_obj.choices[0].message
                        content = getattr(message, "content", None) or ""
                        role = getattr(message, "role", None) or "assistant"
                except Exception as parse_err:
                    logger.error(f"[LLM] Failed to parse non-stream response: {parse_err}")

        # Log warning if content is still empty
        if not content:
            logger.warning("[LLM] Empty response content - this may cause action parsing issues")

        # Create response object
        return LLMResponse(
            content=content,
            raw_response=recovered_json or {},
            prompt_tokens=0,
            completion_tokens=0,
        )

    def _request_openai_legacy(self, messages: list[dict], params: dict) -> LLMResponse:
        """Send request using legacy OpenAI API (< 1.0)."""
        client = self._get_openai_client()

        # Legacy API uses different method signature
        try:
            logger.debug(f"Requesting with legacy API, params: {params}")
            # Remove stream for legacy API compatibility
            legacy_params = params.copy()
            legacy_params.pop("stream", None)

            response = client.ChatCompletion.create(
                messages=messages,
                **legacy_params
            )

            content = ""
            if response and response.choices:
                message = response.choices[0].message
                content = message.get("content", "") or getattr(message, "content", "")

            return LLMResponse(
                content=content,
                raw_response=response if isinstance(response, dict) else {},
                prompt_tokens=response.get("usage", {}).get("prompt_tokens", 0) if isinstance(response, dict) else 0,
                completion_tokens=response.get("usage", {}).get("completion_tokens", 0) if isinstance(response, dict) else 0,
            )

        except Exception as e:
            logger.error(f"Legacy API request failed: {e}")
            raise

    def stream(self, messages: list[dict[str, Any]], **kwargs):
        """
        Stream response from LLM.

        Yields chunks of text as they arrive.
        """
        params = {
            "model": kwargs.get("model", self.config.model),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "stream": True,
        }

        processed_messages = self._preprocess_messages(messages)
        client = self._get_openai_client()

        response = client.chat.completions.create(
            messages=processed_messages,
            **params
        )
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
