from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("app.ollama")


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url.rstrip("/")

    async def generate(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.2,
        format_json: bool = False,
        timeout_s: float = 120.0,
    ) -> str:
        url = f"{self.base_url}/api/generate"
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if format_json:
            payload["format"] = "json"

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                logger.exception(
                    "ollama_generate_failed model=%s error=%s",
                    model,
                    exc,
                )
                raise

        if "response" not in data:
            raise RuntimeError("Ollama response missing 'response' field")
        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "ollama_generate model=%s prompt_chars=%s temp=%.2f json=%s duration_ms=%.2f",
            model,
            len(prompt),
            temperature,
            format_json,
            duration_ms,
        )
        return data["response"]

    async def list_models(self, timeout_s: float = 10.0) -> list[str]:
        url = f"{self.base_url}/api/tags"
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                logger.exception("ollama_list_models_failed error=%s", exc)
                raise

        models = []
        for entry in data.get("models", []):
            name = entry.get("name")
            if name:
                models.append(name)
        duration_ms = (time.monotonic() - start) * 1000
        logger.info("ollama_list_models count=%s duration_ms=%.2f", len(models), duration_ms)
        return models
