"""Automated Tests for State Management, Corrections, and Terminal Protection."""

import pytest
from app.qualification_state import (
    QualificationState,
    ExtractedFacts,
    ConversationStage,
    PropertyType,
    OwnershipStatus,
    DocumentAvailability,
    OccupationType,
    IncomeMode,
)
from app.eligibility_engine import EligibilityEngine


class TestStateManagement:
    """Verifies state updates, out-of-order facts, corrections, and terminal guards."""

    def test_out_of_order_and_multiple_facts_in_one_utterance(self):
        """State engine must capture multiple checklist facts in a single turn without loss."""
        state = QualificationState(customer_name="Priya Nair")
        facts = ExtractedFacts(
            property_type=PropertyType.RESIDENTIAL,
            ownership_status=OwnershipStatus.SOLE,
            loan_amount=4_000_000,
            occupation=OccupationType.SALARIED,
            income_mode=IncomeMode.BANK,
            tenure_years=10,
        )
        updated = EligibilityEngine.apply_facts_to_state(state, facts)

        assert updated.property_type == PropertyType.RESIDENTIAL
        assert updated.ownership_status == OwnershipStatus.SOLE
        assert updated.loan_amount == 4_000_000
        assert updated.occupation == OccupationType.SALARIED
        assert updated.income_mode == IncomeMode.BANK
        assert updated.tenure_years == 10
        # Missing documents and market value must still be None
        assert updated.original_documents_available is None
        assert updated.property_market_value is None
        assert updated.is_checklist_complete() is False

    def test_customer_correction_residential_to_agricultural(self):
        """A customer correction from residential to agricultural must overwrite and disqualify."""
        state = QualificationState()
        # Initial turn: residential
        facts1 = ExtractedFacts(property_type=PropertyType.RESIDENTIAL)
        state = EligibilityEngine.apply_facts_to_state(state, facts1)
        assert state.property_type == PropertyType.RESIDENTIAL
        assert state.disqualification_status is False

        # Customer correction turn: agricultural
        facts2 = ExtractedFacts(property_type=PropertyType.AGRICULTURAL)
        state = EligibilityEngine.apply_facts_to_state(state, facts2)
        assert state.property_type == PropertyType.AGRICULTURAL
        assert state.disqualification_status is True
        assert state.current_stage == ConversationStage.DISQUALIFIED
        assert state.terminal_status is True

    def test_customer_correction_sole_to_joint(self):
        """Correction from sole to joint ownership updates cleanly without error."""
        state = QualificationState()
        facts1 = ExtractedFacts(ownership_status=OwnershipStatus.SOLE)
        state = EligibilityEngine.apply_facts_to_state(state, facts1)
        assert state.ownership_status == OwnershipStatus.SOLE

        facts2 = ExtractedFacts(ownership_status=OwnershipStatus.JOINT)
        state = EligibilityEngine.apply_facts_to_state(state, facts2)
        assert state.ownership_status == OwnershipStatus.JOINT
        assert state.disqualification_status is False

    def test_no_final_handoff_while_any_required_field_is_unknown(self):
        """Final handoff MUST NOT be authorized if even one required field is UNKNOWN/None."""
        base_state = QualificationState(
            identity_verified=True,
            customer_available=True,
            offer_accepted=True,
            property_type=PropertyType.RESIDENTIAL,
            ownership_status=OwnershipStatus.SOLE,
            original_documents_available=DocumentAvailability.AVAILABLE,
            loan_amount=5_000_000,
            loan_cap_confirmed=True,
            occupation=OccupationType.SALARIED,
            income_mode=IncomeMode.BANK,
            property_market_value=8_000_000,
            tenure_years=10,
        )

        # Baseline: All 7 fields complete and valid
        evaluated = EligibilityEngine.evaluate_state(base_state.model_copy())
        assert evaluated.current_stage == ConversationStage.QUALIFIED_HANDOFF
        assert evaluated.terminal_status is True

        # Test each checklist field being None blocks handoff
        fields_to_test = [
            ("property_type", None),
            ("ownership_status", None),
            ("original_documents_available", None),
            ("loan_amount", None),
            ("occupation", None),
            ("income_mode", None),
            ("property_market_value", None),
            ("tenure_years", None),
        ]

        for field_name, missing_val in fields_to_test:
            state_copy = base_state.model_copy()
            setattr(state_copy, field_name, missing_val)
            result = EligibilityEngine.evaluate_state(state_copy)
            assert result.current_stage != ConversationStage.QUALIFIED_HANDOFF, f"Failed for missing {field_name}"
            assert result.terminal_status is False, f"Unexpected terminal status for missing {field_name}"

    def test_terminal_state_lockdown(self):
        """Once terminal_status is True, subsequent facts MUST NOT mutate or re-open state."""
        state = QualificationState(
            terminal_status=True,
            current_stage=ConversationStage.DISQUALIFIED,
            disqualification_status=True,
            disqualification_reason="Agricultural property",
        )

        # Attempt to inject eligible answers
        new_facts = ExtractedFacts(
            property_type=PropertyType.RESIDENTIAL,
            loan_amount=5_000_000,
            tenure_years=5,
        )
        updated = EligibilityEngine.apply_facts_to_state(state, new_facts)

        assert updated.terminal_status is True
        assert updated.current_stage == ConversationStage.DISQUALIFIED
        assert updated.disqualification_status is True
        assert updated.property_type != PropertyType.RESIDENTIAL
