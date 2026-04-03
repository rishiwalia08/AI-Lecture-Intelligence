from __future__ import annotations

from openai import OpenAI

from config import settings


class LLMService:
    def __init__(self) -> None:
        self.backend = settings.llm_backend.lower().strip()
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self._hf_pipe = None

    def _get_hf_pipe(self):
        if self._hf_pipe is None:
            from transformers import pipeline

            preferred_task = getattr(settings, "hf_task", "text-generation")
            tried: list[str] = []
            for task_name in [preferred_task, "text-generation", "text2text-generation"]:
                if task_name in tried:
                    continue
                tried.append(task_name)
                try:
                    self._hf_pipe = pipeline(task_name, model=settings.hf_chat_model)
                    break
                except Exception:
                    continue

            if self._hf_pipe is None:
                raise RuntimeError(
                    "Failed to initialize Hugging Face pipeline. "
                    f"Tried tasks={tried} with model={settings.hf_chat_model}."
                )
        return self._hf_pipe

    def available(self) -> bool:
        if self.backend == "openai":
            return self.client is not None
        if self.backend == "huggingface":
            return True
        return False

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.1) -> str:
        if self.backend == "openai":
            if not self.client:
                raise RuntimeError("OPENAI_API_KEY is not configured")

            resp = self.client.chat.completions.create(
                model=settings.openai_chat_model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return resp.choices[0].message.content or ""

        if self.backend == "huggingface":
            prompt = (
                f"System instruction:\n{system_prompt}\n\n"
                f"User request:\n{user_prompt}\n\n"
                "Return a concise grounded answer."
            )
            hf = self._get_hf_pipe()
            output = hf(
                prompt,
                max_new_tokens=512,
                do_sample=temperature > 0,
                temperature=max(0.01, float(temperature)),
            )
            if output and isinstance(output, list):
                return output[0].get("generated_text", "")
            return ""

        raise RuntimeError("LLM backend disabled. Set LLM_BACKEND to huggingface or openai.")
