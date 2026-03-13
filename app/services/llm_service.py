from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import settings


logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self) -> None:
        self.timeout = settings.straive_timeout_seconds
        self.max_retries = settings.straive_max_retries

    async def generate_grounded_summary(self, prompt: str, context: dict[str, Any]) -> str:
        if settings.use_mock_llm or not settings.straive_base_url or not settings.straive_api_key:
            return self._mock_summary(prompt, context)

        payload = {
            "model": settings.straive_model,
            "prompt": prompt,
            "context": context,
        }
        headers = {
            "Authorization": f"Bearer {settings.straive_api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(settings.straive_base_url, headers=headers, json=payload)
                    response.raise_for_status()
                    body = response.json()
                    logger.info("straive_llm_success", extra={"attempt": attempt, "model": settings.straive_model})
                    return body.get("text") or body.get("output") or self._mock_summary(prompt, context)
            except Exception as exc:
                logger.warning(
                    "straive_llm_failure",
                    extra={"attempt": attempt, "error": str(exc), "payload_size": len(json.dumps(payload))},
                )
                if attempt == self.max_retries:
                    return self._mock_summary(prompt, context)
        return self._mock_summary(prompt, context)

    def _mock_summary(self, prompt: str, context: dict[str, Any]) -> str:
        top_actions = context.get("top_actions", [])
        top_driver = context.get("top_driver", "warehouse congestion")
        high_risk = context.get("high_risk_shipments", 0)
        affected = context.get("top_affected_warehouse", "ATL-01")
        return (
            f"{prompt.split('?')[0]}. Current posture shows {high_risk} high-risk shipments, led by "
            f"{affected}. The strongest delay driver is {top_driver}. Recommended focus is {', '.join(top_actions[:3])}."
        )

    async def answer_copilot(self, question: str, context: dict[str, Any]) -> str:
        prompt = f"Answer this logistics control tower question using only the provided data: {question}"
        if settings.use_mock_llm or not settings.straive_base_url or not settings.straive_api_key:
            return self._mock_copilot(question, context)
        return await self.generate_grounded_summary(prompt, context)

    async def test_connection(self, prompt: str) -> dict[str, Any]:
        if not settings.straive_base_url or not settings.straive_api_key:
            return {"ok": False, "message": "Missing Straive endpoint or API key."}

        payload = {
            "model": settings.straive_model,
            "prompt": prompt,
            "context": {"purpose": "connection_test"},
        }
        headers = {
            "Authorization": f"Bearer {settings.straive_api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(settings.straive_base_url, headers=headers, json=payload)
                response.raise_for_status()
                body = response.json()
                text = body.get("text") or body.get("output") or "Connected successfully."
                return {"ok": True, "message": text}
        except Exception as exc:
            logger.warning("straive_llm_test_failure", extra={"error": str(exc)})
            return {"ok": False, "message": str(exc)}

    def _mock_copilot(self, question: str, context: dict[str, Any]) -> str:
        top_driver = context.get("top_driver", "inventory shortage")
        top_warehouse = context.get("top_warehouse", "LAX-01")
        top_actions = context.get("top_actions", [])
        breaches = context.get("predicted_breach_shipments", 0)
        return (
            f"Main driver is {top_driver} centered on {top_warehouse}. "
            f"Predicted SLA breach exposure is {breaches} shipments. "
            f"Recommended next move: {', '.join(top_actions[:2]) or 'reroute and staffing intervention'}."
        )
