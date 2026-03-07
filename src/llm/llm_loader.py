"""
src/llm/llm_loader.py
-----------------------
LLM provider abstraction for the Speech RAG pipeline — Phase 5.

Supports two inference backends:

  1. **Ollama** — local inference, no API key needed.
     Requires Ollama server running: https://ollama.com
     Default model: ``llama3``

  2. **Groq API** — cloud inference, requires ``GROQ_API_KEY`` env var.
     Default model: ``llama3-8b-8192``

Both providers expose the same interface:
    response = provider.generate(messages)  # list[dict]

Usage
-----
    from src.llm.llm_loader import LLMConfig, load_llm

    cfg      = LLMConfig(provider="ollama", model="llama3", temperature=0.2)
    provider = load_llm(cfg)
    response = provider.generate([
        {"role": "system",  "content": "You are a helpful assistant."},
        {"role": "user",    "content": "What is backpropagation?"},
    ])
    print(response.content)
"""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Response model (provider-agnostic)
# ──────────────────────────────────────────────────────────────
@dataclass
class LLMResponse:
    """
    Provider-agnostic response from any LLM.

    Attributes
    ----------
    content : str        The generated text.
    model : str          Model identifier used.
    input_tokens : int   Prompt token count (0 if unavailable).
    output_tokens : int  Completion token count (0 if unavailable).
    latency_s : float    Wall-clock generation time in seconds.
    raw : Any            Raw provider response object.
    """
    content:       str
    model:         str
    input_tokens:  int   = 0
    output_tokens: int   = 0
    latency_s:     float = 0.0
    raw:           Any   = field(default=None, repr=False)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
@dataclass
class LLMConfig:
    """
    Configuration for an LLM provider.

    Attributes
    ----------
    provider : str
        ``"ollama"`` or ``"groq"``.
    model : str
        Model identifier. For Ollama: ``"llama3"``, ``"mistral"``, etc.
        For Groq: ``"llama3-8b-8192"``, ``"mixtral-8x7b-32768"``, etc.
    temperature : float
        Sampling temperature. Lower = more deterministic.
    max_tokens : int
        Maximum tokens to generate.
    api_key : str | None
        Groq API key. Falls back to ``GROQ_API_KEY`` env var if not set.
    base_url : str
        Ollama server URL.
    timeout : int
        Request timeout in seconds.
    """
    provider:    str   = "ollama"
    model:       str   = "llama3"
    temperature: float = 0.2
    max_tokens:  int   = 512
    api_key:     Optional[str] = None
    base_url:    str   = "http://localhost:11434"
    timeout:     int   = 120

    def __post_init__(self) -> None:
        if self.provider not in ("ollama", "groq"):
            raise ValueError(
                f"Unknown provider '{self.provider}'. Choose 'ollama' or 'groq'."
            )

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "LLMConfig":
        llm = raw.get("llm", {})
        return cls(
            provider=llm.get("provider", "ollama"),
            model=llm.get("model", "llama3"),
            temperature=llm.get("temperature", 0.2),
            max_tokens=llm.get("max_tokens", 512),
        )


# ──────────────────────────────────────────────────────────────
# Abstract base
# ──────────────────────────────────────────────────────────────
class LLMProvider(ABC):
    """Abstract interface that all LLM backends must implement."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @abstractmethod
    def generate(self, messages: List[Dict[str, str]]) -> LLMResponse:
        """
        Generate a response given a list of chat messages.

        Parameters
        ----------
        messages : list[dict]
            Each dict must have ``"role"`` (``"system"`` | ``"user"`` |
            ``"assistant"``) and ``"content"`` keys.

        Returns
        -------
        LLMResponse
        """
        ...

    def _time_call(self, fn, *args, **kwargs):
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        return result, time.perf_counter() - t0


# ──────────────────────────────────────────────────────────────
# Ollama provider
# ──────────────────────────────────────────────────────────────
class OllamaProvider(LLMProvider):
    """
    Local Ollama provider — uses the ``ollama`` Python SDK.

    Requires Ollama server running on ``config.base_url``
    (default: http://localhost:11434).

    Install: ``pip install ollama``
    Run server: ``ollama serve`` + ``ollama pull llama3``
    """

    def generate(self, messages: List[Dict[str, str]]) -> LLMResponse:
        try:
            import ollama as _ollama  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "ollama SDK not installed. Run: pip install ollama"
            ) from exc

        logger.debug("OllamaProvider: calling model '%s'.", self.config.model)
        client = _ollama.Client(host=self.config.base_url)

        raw, latency = self._time_call(
            client.chat,
            model=self.config.model,
            messages=messages,
            options={
                "temperature":  self.config.temperature,
                "num_predict":  self.config.max_tokens,
            },
        )

        content = raw.get("message", {}).get("content", "")
        usage   = raw.get("usage", {})

        logger.info(
            "Ollama '%s' responded in %.2fs (%d tokens).",
            self.config.model, latency,
            usage.get("total_tokens", 0),
        )
        return LLMResponse(
            content=content.strip(),
            model=self.config.model,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            latency_s=latency,
            raw=raw,
        )


# ──────────────────────────────────────────────────────────────
# Groq provider
# ──────────────────────────────────────────────────────────────
class GroqProvider(LLMProvider):
    """
    Groq cloud API provider.

    Requires ``GROQ_API_KEY`` environment variable **or** ``config.api_key``.

    Install: ``pip install groq``
    Models : ``"llama3-8b-8192"``, ``"llama3-70b-8192"``, ``"mixtral-8x7b-32768"``
    """

    def generate(self, messages: List[Dict[str, str]]) -> LLMResponse:
        try:
            from groq import Groq  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "groq SDK not installed. Run: pip install groq"
            ) from exc

        api_key = self.config.api_key or os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "Groq API key not found. Set GROQ_API_KEY env var or "
                "pass api_key in LLMConfig."
            )

        client = Groq(api_key=api_key)
        logger.debug("GroqProvider: calling model '%s'.", self.config.model)

        raw, latency = self._time_call(
            client.chat.completions.create,
            model=self.config.model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        choice  = raw.choices[0]
        content = choice.message.content or ""
        usage   = raw.usage

        logger.info(
            "Groq '%s' responded in %.2fs (%d in / %d out tokens).",
            self.config.model, latency,
            usage.prompt_tokens, usage.completion_tokens,
        )
        return LLMResponse(
            content=content.strip(),
            model=raw.model,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            latency_s=latency,
            raw=raw,
        )


# ──────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────
def load_llm(config: Optional[LLMConfig] = None) -> LLMProvider:
    """
    Instantiate and return an LLM provider based on ``config.provider``.

    Parameters
    ----------
    config : LLMConfig, optional
        Defaults to ``LLMConfig()`` (Ollama, llama3).

    Returns
    -------
    LLMProvider

    Raises
    ------
    ValueError
        If the provider string is not recognised.
    """
    cfg = config or LLMConfig()
    logger.info("load_llm: provider='%s', model='%s'.", cfg.provider, cfg.model)

    if cfg.provider == "ollama":
        return OllamaProvider(cfg)
    elif cfg.provider == "groq":
        return GroqProvider(cfg)
    else:
        raise ValueError(f"Unknown provider: '{cfg.provider}'")
