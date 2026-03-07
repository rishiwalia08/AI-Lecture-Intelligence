"""
src/llm/hf_client.py
--------------------
Hugging Face Inference API client for cloud-deployable LLM inference.

Replaces Ollama for cloud deployment (Render, Heroku, etc).

Models:
    - mistralai/Mistral-7B-Instruct (default, recommended)
    - meta-llama/Llama-2-7b-chat-hf
    - tiiuae/falcon-7b-instruct

Requires:
    - HF_API_KEY environment variable (get from https://huggingface.co/settings/tokens)
    - huggingface_hub library

Installation:
    pip install huggingface_hub

Usage:
    from src.llm.hf_client import HFClient

    client = HFClient(model="mistralai/Mistral-7B-Instruct")
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "What is AI?"}
    ]
    response = client.generate(messages)
    print(response.content)
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


class HFClient:
    """
    Hugging Face Inference API wrapper for cloud-deployable LLM inference.

    Attributes:
        model: Model ID (e.g., "mistralai/Mistral-7B-Instruct")
        api_key: HF API key (from environment or parameter)
        temperature: Sampling temperature (0.0-1.0)
        max_tokens: Maximum tokens to generate
        timeout: Request timeout in seconds
    """

    # Default model - Mistral 7B Instruct (fast, accurate, open source)
    DEFAULT_MODEL = "mistralai/Mistral-7B-Instruct"

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        timeout: int = 120,
    ):
        """
        Initialize HF Inference API client.

        Parameters:
            model: Model ID from Hugging Face Hub
            api_key: Hugging Face API key (defaults to HF_API_KEY env var)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
        """
        self.model = model or self.DEFAULT_MODEL
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

        # Get API key from parameter or environment
        self.api_key = api_key or os.getenv("HF_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Hugging Face API key not found. "
                "Set HF_API_KEY environment variable or pass api_key parameter.\n"
                "Get your API key from: https://huggingface.co/settings/tokens"
            )

        logger.info(f"✅ HFClient initialized: model={self.model}")

    def generate(self, messages: List[Dict[str, str]]) -> str:
        """
        Generate text response from messages.

        Parameters:
            messages: List of dicts with "role" and "content" keys
                     Roles: "system", "user", "assistant"

        Returns:
            Generated text response

        Raises:
            ImportError: If huggingface_hub not installed
            ValueError: If API key missing
            Exception: On network/API errors
        """
        try:
            from huggingface_hub import InferenceClient
        except ImportError as e:
            raise ImportError(
                "huggingface_hub not installed. "
                "Install with: pip install huggingface_hub"
            ) from e

        # Format messages for API
        formatted_prompt = self._format_messages(messages)

        logger.debug(f"Calling HF API: model={self.model}, tokens_max={self.max_tokens}")

        try:
            client = InferenceClient(model=self.model, token=self.api_key)

            t0 = time.perf_counter()
            response = client.text_generation(
                prompt=formatted_prompt,
                max_new_tokens=self.max_tokens,
                temperature=self.temperature,
                do_sample=True,
            )
            latency = time.perf_counter() - t0

            logger.info(
                f"✅ HF API response ({latency:.2f}s): {len(response)} chars"
            )

            return response.strip()

        except Exception as e:
            error_msg = str(e).lower()

            # Specific error handling
            if "invalid api token" in error_msg or "unauthorized" in error_msg:
                logger.error("❌ Invalid HF API key. Check HF_API_KEY environment variable.")
                raise ValueError(
                    "Invalid Hugging Face API key. "
                    "Get one from: https://huggingface.co/settings/tokens"
                ) from e

            elif "rate limit" in error_msg or "too many requests" in error_msg:
                logger.error("⚠️  Rate limited by HF API. Try again in a moment.")
                raise RuntimeError(
                    "Hit Hugging Face API rate limit. Try again in a few minutes."
                ) from e

            elif "model not found" in error_msg or "not a valid model" in error_msg:
                logger.error(f"❌ Model not found: {self.model}")
                raise ValueError(
                    f"Model '{self.model}' not found on Hugging Face Hub. "
                    f"Use a valid model like: mistralai/Mistral-7B-Instruct"
                ) from e

            elif "connection" in error_msg or "timeout" in error_msg:
                logger.error("❌ Network error connecting to HF API.")
                raise RuntimeError(
                    "Network error connecting to Hugging Face API. Check your internet."
                ) from e

            else:
                logger.error(f"❌ HF API error: {e}")
                raise RuntimeError(f"Hugging Face API error: {e}") from e

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """
        Convert chat messages to prompt format for Mistral/Instruct models.

        Parameters:
            messages: List of {"role": "...", "content": "..."} dicts

        Returns:
            Formatted prompt string
        """
        prompt_parts = []

        for msg in messages:
            role = msg.get("role", "user").lower()
            content = msg.get("content", "")

            if role == "system":
                prompt_parts.append(f"[SYSTEM]\n{content}")
            elif role == "user":
                prompt_parts.append(f"[USER]\n{content}")
            elif role == "assistant":
                prompt_parts.append(f"[ASSISTANT]\n{content}")

        # Add assistant prompt to trigger response
        prompt_parts.append("[ASSISTANT]\n")

        return "\n\n".join(prompt_parts)

    def health_check(self) -> Dict[str, Any]:
        """
        Check if API is accessible and key is valid.

        Returns:
            Dict with status, model, and message
        """
        try:
            from huggingface_hub import InferenceClient

            client = InferenceClient(model=self.model, token=self.api_key)

            # Test with minimal request
            response = client.text_generation(
                prompt="Test",
                max_new_tokens=5,
            )

            return {
                "status": "ok",
                "model": self.model,
                "message": "HF API accessible",
            }

        except Exception as e:
            error_msg = str(e).lower()

            if "invalid api token" in error_msg:
                return {
                    "status": "error",
                    "error": "invalid_api_key",
                    "message": "Invalid HF API key",
                }
            elif "rate limit" in error_msg:
                return {
                    "status": "error",
                    "error": "rate_limit",
                    "message": "Rate limited",
                }
            else:
                return {
                    "status": "error",
                    "error": "api_error",
                    "message": str(e),
                }
