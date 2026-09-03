"""Provider-backed structured query planning with safe fallback semantics."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any, Protocol, cast

from pydantic import Field

from lunarbit.agent import QueryPlan, build_query_plan, build_query_plan_from_templates
from lunarbit.retrieval import QueryTemplate
from lunarbit.runtime import QuerySlots


class StructuredQueryProposal(QuerySlots):
    """Model output: slots plus one or more governed operation names."""

    operations: tuple[QueryTemplate, ...] = Field(min_length=1, max_length=6)


class StructuredPlanner(Protocol):
    def plan(self, question: str) -> StructuredQueryProposal: ...


_SYSTEM = """You plan Lunarbit food-commerce GraphRAG queries. Return JSON only.
Choose one or more operation names from: merchant_order_ranking, merchant_order_count,
merchant_item_price_history, delivery_mention_count, financial_component_sum,
evidence_for_money_component, order_reconstruction, fulltext_evidence.
Extract only explicit slots. Never write Cypher, invent values, or answer the question.
JSON shape: {operations:[string], merchant_name?, item_name?, delivery_name?, platform?,
component_type?, component_id?, order_id?, lexical_query?, limit?}."""


def _json_object(body: Mapping[str, Any]) -> StructuredQueryProposal:
    raw = body.get("operations")
    if not isinstance(raw, list):
        raise ValueError("planner response omitted operations")
    values = dict(body)
    values["operations"] = tuple(QueryTemplate(str(item)) for item in raw)
    return StructuredQueryProposal.model_validate(values)


class _HttpPlanner:
    def __init__(self, *, timeout: float = 45.0) -> None:
        self.timeout = timeout

    def _post(self, url: str, payload: Mapping[str, Any], key: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, separators=(",", ":")).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            raise RuntimeError("planner provider unavailable") from error
        if not isinstance(result, dict):
            raise ValueError("planner provider returned a non-object")
        return cast(dict[str, Any], result)


class GeminiPlanner(_HttpPlanner):
    def __init__(
        self, api_key: str, *, model: str = "gemini-2.5-flash", timeout: float = 45.0
    ) -> None:
        super().__init__(timeout=timeout)
        self.api_key = api_key
        self.model = model

    def plan(self, question: str) -> StructuredQueryProposal:
        body = self._post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}",
            {
                "system_instruction": {"parts": [{"text": _SYSTEM}]},
                "contents": [{"parts": [{"text": question}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            self.api_key,
        )
        text = body["candidates"][0]["content"]["parts"][0]["text"]
        return _json_object(json.loads(text))


class MistralPlanner(_HttpPlanner):
    def __init__(
        self, api_key: str, *, model: str = "mistral-large-latest", timeout: float = 45.0
    ) -> None:
        super().__init__(timeout=timeout)
        self.api_key = api_key
        self.model = model

    def plan(self, question: str) -> StructuredQueryProposal:
        body = self._post(
            "https://api.mistral.ai/v1/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": question},
                ],
                "response_format": {"type": "json_object"},
            },
            self.api_key,
        )
        text = body["choices"][0]["message"]["content"]
        return _json_object(json.loads(text))


class ResilientQueryPlanner:
    """Gemini-primary/Mistral-secondary planner; deterministic fallback preserves service."""

    def __init__(
        self, primary: StructuredPlanner | None, fallback: StructuredPlanner | None
    ) -> None:
        self.primary = primary
        self.fallback = fallback

    def plan(self, question: str) -> tuple[QueryPlan, QuerySlots]:
        for planner in (self.primary, self.fallback):
            if planner is None:
                continue
            try:
                proposal = planner.plan(question)
                plan = build_query_plan_from_templates(question, proposal.operations)
                self._validate_slots(plan, proposal)
                return plan, proposal
            except (RuntimeError, ValueError, KeyError, IndexError, TypeError):
                continue
        return build_query_plan(question), QuerySlots()

    @staticmethod
    def _validate_slots(plan: QueryPlan, slots: QuerySlots) -> None:
        required: dict[QueryTemplate, tuple[str, ...]] = {
            QueryTemplate.MERCHANT_ORDER_COUNT: ("merchant_name",),
            QueryTemplate.MERCHANT_ITEM_PRICE_HISTORY: ("merchant_name", "item_name"),
            QueryTemplate.DELIVERY_MENTION_COUNT: ("delivery_name",),
            QueryTemplate.FINANCIAL_COMPONENT_SUM: ("component_type", "platform"),
            QueryTemplate.EVIDENCE_FOR_MONEY_COMPONENT: ("component_id",),
            QueryTemplate.ORDER_RECONSTRUCTION: ("order_id",),
            QueryTemplate.FULLTEXT_EVIDENCE: ("lexical_query",),
        }
        for template in plan.selected_templates:
            missing = tuple(
                name for name in required.get(template, ()) if getattr(slots, name) is None
            )
            if missing:
                raise ValueError(f"structured plan missing required slots: {','.join(missing)}")


def planner_from_environment() -> ResilientQueryPlanner:
    gemini = os.environ.get("GEMINI_API_KEY")
    mistral = os.environ.get("MISTRAL_API_KEY")
    return ResilientQueryPlanner(
        GeminiPlanner(gemini) if gemini else None,
        MistralPlanner(mistral) if mistral else None,
    )
