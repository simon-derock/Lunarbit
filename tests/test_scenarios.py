from __future__ import annotations

from pathlib import Path

from lunarbit.scenarios import ScenarioCapability, load_scenario_packs

FIXTURES = Path("tests/fixtures/economic_scenarios.json")


def test_complex_economic_scenario_packs_cover_high_risk_capabilities() -> None:
    packs = load_scenario_packs(FIXTURES)
    capabilities = {capability for pack in packs for capability in pack.capabilities}

    assert len(packs) >= 3
    assert capabilities >= {
        ScenarioCapability.MULTI_DOCUMENT_RECONCILIATION,
        ScenarioCapability.MEMBERSHIP_ECONOMICS,
        ScenarioCapability.REFUND_TIMELINE,
        ScenarioCapability.CONFLICTING_AUTHORITY,
        ScenarioCapability.PROMPT_INJECTION,
        ScenarioCapability.REQUIRED_ABSTENTION,
    }


def test_scenario_money_is_source_addressable_and_expected_outcomes_are_explicit() -> None:
    packs = load_scenario_packs(FIXTURES)

    for pack in packs:
        document_ids = {document.document_id for document in pack.documents}
        assert len(document_ids) >= 2
        assert all(component.source_document_id in document_ids for component in pack.components)
        assert pack.expected.status
        if ScenarioCapability.REQUIRED_ABSTENTION in pack.capabilities:
            assert pack.expected.abstention_reason


def test_prompt_injection_pack_keeps_untrusted_text_outside_expected_truth() -> None:
    pack = next(
        value
        for value in load_scenario_packs(FIXTURES)
        if ScenarioCapability.PROMPT_INJECTION in value.capabilities
    )

    assert pack.untrusted_evidence_instructions
    assert all("ignore" in value.casefold() for value in pack.untrusted_evidence_instructions)
    assert pack.expected.abstention_reason == "incomplete_refund_evidence"
