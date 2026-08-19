from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import Field, TypeAdapter, model_validator

from lunarbit.economic import FindingStatus
from lunarbit.finance import FinancialComponentType, ReconciliationStatus
from lunarbit.models import ContractModel, DocumentRole


class ScenarioCapability(StrEnum):
    MULTI_DOCUMENT_RECONCILIATION = "multi_document_reconciliation"
    MEMBERSHIP_ECONOMICS = "membership_economics"
    REFUND_TIMELINE = "refund_timeline"
    CONFLICTING_AUTHORITY = "conflicting_authority"
    PROMPT_INJECTION = "prompt_injection"
    REQUIRED_ABSTENTION = "required_abstention"


class ScenarioDocument(ContractModel):
    document_id: str = Field(pattern=r"^scenario-doc:[a-z0-9-]+$")
    role: DocumentRole
    occurred_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T")


class ScenarioComponent(ContractModel):
    component_id: str = Field(pattern=r"^scenario-money:[a-z0-9-]+$")
    component_type: FinancialComponentType
    amount: Decimal
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    source_document_id: str = Field(pattern=r"^scenario-doc:[a-z0-9-]+$")


class ScenarioExpected(ContractModel):
    status: FindingStatus
    reconciliation_status: ReconciliationStatus
    residual: Decimal | None
    abstention_reason: str | None


class EconomicScenarioPack(ContractModel):
    scenario_id: str = Field(pattern=r"^scenario-pack:[a-z0-9-]+$")
    title: str = Field(min_length=12)
    capabilities: tuple[ScenarioCapability, ...] = Field(min_length=1)
    documents: tuple[ScenarioDocument, ...] = Field(min_length=2)
    components: tuple[ScenarioComponent, ...] = Field(min_length=1)
    untrusted_evidence_instructions: tuple[str, ...]
    expected: ScenarioExpected

    @model_validator(mode="after")
    def references_and_expectations_are_valid(self) -> EconomicScenarioPack:
        document_ids = tuple(value.document_id for value in self.documents)
        if len(set(document_ids)) != len(document_ids):
            raise ValueError("scenario document IDs must be unique")
        if any(value.source_document_id not in document_ids for value in self.components):
            raise ValueError("scenario money must reference a declared document")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("scenario capabilities must be unique")
        requires_abstention = ScenarioCapability.REQUIRED_ABSTENTION in self.capabilities
        if requires_abstention != (self.expected.abstention_reason is not None):
            raise ValueError("scenario abstention expectation must match its capability")
        has_injection = ScenarioCapability.PROMPT_INJECTION in self.capabilities
        if has_injection != bool(self.untrusted_evidence_instructions):
            raise ValueError("prompt-injection scenarios must declare untrusted instructions")
        return self


_PACKS = TypeAdapter(tuple[EconomicScenarioPack, ...])


def load_scenario_packs(path: Path) -> tuple[EconomicScenarioPack, ...]:
    return _PACKS.validate_json(path.read_bytes(), strict=True)
