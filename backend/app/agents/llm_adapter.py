"""Optional read-only structured LLM adapter with strict evidence-ID grounding."""

import json

import httpx
from pydantic import BaseModel, Field

from app.config import Settings
from app.schemas.investigation import EvidenceBundle


class LLMStructuredNarrative(BaseModel):
    """Strict schema required from an external LLM provider."""

    summary: str = Field(min_length=10, max_length=1000)
    root_cause_hypothesis: str = Field(min_length=10, max_length=1000)
    cited_evidence_ids: list[str] = Field(min_length=1)
    contributing_factors: list[str] = Field(min_length=1)
    recommended_next_steps: list[str] = Field(min_length=1)


class GroundingValidationError(ValueError):
    """Raised when an LLM output references evidence IDs not present in the EvidenceBundle."""


class OptionalLLMAdapter:
    """Safe, read-only adapter to an OpenAI-compatible JSON endpoint with grounding checks."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def is_enabled(self) -> bool:
        """Return True only when AI mode allows LLM calls and an API key is configured."""
        if self._settings.ai_mode == "deterministic":
            return False
        return bool(self._settings.llm_api_key)

    def synthesize_narrative(self, bundle: EvidenceBundle) -> LLMStructuredNarrative:
        """Call configured LLM with EvidenceBundle only and validate every cited evidence_id."""
        if not self._settings.llm_api_key:
            raise RuntimeError("LLM API key is not configured.")

        valid_ids = {item.evidence_id for item in bundle.items}
        evidence_payload = [
            {
                "evidence_id": item.evidence_id,
                "source_type": item.source_type,
                "service_id": item.service_id,
                "observation": item.observation,
            }
            for item in bundle.items[:30]
        ]

        system_prompt = (
            "You are NEXUS Investigator, a read-only infrastructure incident analyst. "
            "Analyze ONLY the supplied evidence_items. Do NOT invent metrics, events, or IDs. "
            "Do NOT propose shell commands or automated execution. "
            "Respond strictly as JSON with keys: summary, root_cause_hypothesis, "
            "cited_evidence_ids (subset of provided evidence_id values), "
            "contributing_factors (array of strings), recommended_next_steps (array of strings)."
        )
        user_prompt = json.dumps(
            {
                "incident_id": bundle.incident_id,
                "affected_services": bundle.affected_services,
                "unaffected_services": bundle.unaffected_services,
                "detector_root_cause_candidate": bundle.detector_root_cause_candidate,
                "propagation_paths": bundle.propagation_paths,
                "evidence_items": evidence_payload,
            }
        )

        url = f"{self._settings.llm_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self._settings.llm_model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        with httpx.Client(timeout=self._settings.llm_timeout_seconds) as client:
            resp = client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        raw_content = data["choices"][0]["message"]["content"]
        parsed = LLMStructuredNarrative.model_validate_json(raw_content)

        # Reject any hallucinated or ungrounded evidence references
        invalid_ids = [eid for eid in parsed.cited_evidence_ids if eid not in valid_ids]
        if invalid_ids:
            raise GroundingValidationError(
                f"LLM referenced ungrounded evidence IDs: {', '.join(invalid_ids)}"
            )

        return parsed

