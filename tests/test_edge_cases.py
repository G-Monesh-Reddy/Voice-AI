"""Comprehensive Automated Tests for 25 Specific Edge Cases and Boundaries."""

import pytest
from app.config import settings
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
from app.conversation_engine import ConversationEngine
from app.voice_platform import LocalSimulatorAdapter
from app.gemini_client import GeminiClient


class TestEdgeCasesAndBoundaries:
    """Verifies all 25 specific test requirements and strict boundary conditions."""

    # -------------------------------------------------------------------------
    # CASE 1: Successful qualification
    # -------------------------------------------------------------------------
    def test_case_01_successful_qualification(self):
        """Case 1: Fully eligible customer completes all 7 checklist items."""
        sim = LocalSimulatorAdapter(customer_name="Sunil Rao")
        sim.start_conversation()
        sim.send_customer_utterance("Yes speaking.")
        sim.send_customer_utterance("Sure, two minutes.")
        sim.send_customer_utterance("Interested in the loan.")
        sim.send_customer_utterance("Residential flat.")
        sim.send_customer_utterance("Sole owner.")
        sim.send_customer_utterance("Yes original papers available.")
        sim.send_customer_utterance("50 lakhs.")
        sim.send_customer_utterance("Salaried, salary in bank account.")
        sim.send_customer_utterance("Market value is 80 lakhs.")
        turn = sim.send_customer_utterance("10 years tenure.")

        assert turn["current_stage"] == ConversationStage.QUALIFIED_HANDOFF.value
        assert turn["is_terminal"] is True
        assert turn["disqualified"] is False

    # -------------------------------------------------------------------------
    # CASE 2: Agricultural property
    # -------------------------------------------------------------------------
    def test_case_02_agricultural_property(self):
        """Case 2: Agricultural property leads to immediate disqualification."""
        state = QualificationState(property_type=PropertyType.AGRICULTURAL)
        evaluated = EligibilityEngine.evaluate_state(state)
        assert evaluated.disqualification_status is True
        assert evaluated.current_stage == ConversationStage.DISQUALIFIED
        assert evaluated.terminal_status is True

    # -------------------------------------------------------------------------
    # CASE 3: Cash income
    # -------------------------------------------------------------------------
    def test_case_03_cash_income(self):
        """Case 3: Income in cash leads to immediate disqualification."""
        state = QualificationState(
            occupation=OccupationType.SELF_EMPLOYED,
            income_mode=IncomeMode.CASH,
        )
        evaluated = EligibilityEngine.evaluate_state(state)
        assert evaluated.disqualification_status is True
        assert evaluated.current_stage == ConversationStage.DISQUALIFIED
        assert evaluated.terminal_status is True

    # -------------------------------------------------------------------------
    # CASE 4: Missing original documents
    # -------------------------------------------------------------------------
    def test_case_04_missing_original_documents(self):
        """Case 4: Confirmed unavailable original documents causes disqualification."""
        state = QualificationState(original_documents_available=DocumentAvailability.UNAVAILABLE)
        evaluated = EligibilityEngine.evaluate_state(state)
        assert evaluated.disqualification_status is True
        assert evaluated.current_stage == ConversationStage.DISQUALIFIED
        assert evaluated.terminal_status is True

    # -------------------------------------------------------------------------
    # CASE 5: Tenure below 3 years
    # -------------------------------------------------------------------------
    def test_case_05_tenure_below_three_years(self):
        """Case 5: Tenure of 2 years (<3) triggers immediate disqualification."""
        state = QualificationState(tenure_years=2)
        evaluated = EligibilityEngine.evaluate_state(state)
        assert evaluated.disqualification_status is True
        assert evaluated.current_stage == ConversationStage.DISQUALIFIED
        assert evaluated.terminal_status is True

    # -------------------------------------------------------------------------
    # CASE 6: Tenure above 15 years
    # -------------------------------------------------------------------------
    def test_case_06_tenure_above_fifteen_years(self):
        """Case 6: Tenure of 20 years (>15) triggers immediate disqualification."""
        state = QualificationState(tenure_years=20)
        evaluated = EligibilityEngine.evaluate_state(state)
        assert evaluated.disqualification_status is True
        assert evaluated.current_stage == ConversationStage.DISQUALIFIED
        assert evaluated.terminal_status is True

    # -------------------------------------------------------------------------
    # CASE 7: ₹90 lakh request with acceptance of ₹75 lakh
    # -------------------------------------------------------------------------
    def test_case_07_request_90L_accepted_75L(self):
        """Case 7: Customer requesting 90L agrees to 75L cap and passes."""
        state = QualificationState()
        facts_90 = ExtractedFacts(loan_amount=9_000_000)
        state = EligibilityEngine.apply_facts_to_state(state, facts_90)
        assert state.current_stage == ConversationStage.LOAN_CAP_CONFIRMATION

        facts_accept = ExtractedFacts(loan_cap_confirmed=True)
        state = EligibilityEngine.apply_facts_to_state(state, facts_accept)
        assert state.loan_amount == 7_500_000
        assert state.disqualification_status is False

    # -------------------------------------------------------------------------
    # CASE 8: ₹90 lakh request with rejection of ₹75 lakh
    # -------------------------------------------------------------------------
    def test_case_08_request_90L_rejected_75L(self):
        """Case 8: Customer requesting 90L declines 75L cap and is terminated."""
        state = QualificationState(loan_amount=9_000_000)
        facts_reject = ExtractedFacts(loan_cap_confirmed=False)
        state = EligibilityEngine.apply_facts_to_state(state, facts_reject)
        assert state.disqualification_status is True
        assert state.current_stage == ConversationStage.DISQUALIFIED
        assert state.terminal_status is True

    # -------------------------------------------------------------------------
    # CASE 9: Joint ownership
    # -------------------------------------------------------------------------
    def test_case_09_joint_ownership(self):
        """Case 9: Joint ownership is accepted and not a disqualifier."""
        is_valid, reason = EligibilityEngine.validate_ownership(OwnershipStatus.JOINT)
        assert is_valid is True
        assert reason is None

    # -------------------------------------------------------------------------
    # CASE 10: Existing property loan
    # -------------------------------------------------------------------------
    def test_case_10_existing_property_loan_transfer(self):
        """Case 10: Existing loan with transfer request routes to specialist."""
        state = QualificationState()
        facts = ExtractedFacts(existing_property_loan=True, emi_reduction_intent=True)
        state = EligibilityEngine.apply_facts_to_state(state, facts)
        assert state.is_transfer_lead is True
        assert state.current_stage == ConversationStage.TRANSFER_BRANCH
        assert state.terminal_status is True

    # -------------------------------------------------------------------------
    # CASE 11: EMI reduction request
    # -------------------------------------------------------------------------
    def test_case_11_emi_reduction_request(self):
        """Case 11: EMI reduction intent triggers transfer branch."""
        sim = LocalSimulatorAdapter()
        sim.start_conversation()
        sim.send_customer_utterance("Yes speaking.")
        turn = sim.send_customer_utterance("I want to reduce my EMI on my current bank loan.")
        assert turn["is_transfer_lead"] is True
        assert turn["current_stage"] == ConversationStage.TRANSFER_BRANCH.value
        assert turn["is_terminal"] is True

    # -------------------------------------------------------------------------
    # CASE 12: Busy customer
    # -------------------------------------------------------------------------
    def test_case_12_busy_customer(self):
        """Case 12: Busy customer captures callback time and ends call without pitch."""
        sim = LocalSimulatorAdapter()
        sim.start_conversation()
        turn = sim.send_customer_utterance("I am busy in a meeting. Call me tomorrow at 3 pm.")
        assert turn["is_terminal"] is True
        assert sim.get_state().customer_available is False
        assert sim.get_state().callback_time is not None

    # -------------------------------------------------------------------------
    # CASE 13: Out-of-order answers
    # -------------------------------------------------------------------------
    def test_case_13_out_of_order_answers(self):
        """Case 13: Tenure and amount given before property type are preserved."""
        state = QualificationState()
        facts = ExtractedFacts(tenure_years=7, loan_amount=3_500_000)
        state = EligibilityEngine.apply_facts_to_state(state, facts)
        assert state.tenure_years == 7
        assert state.loan_amount == 3_500_000
        assert state.property_type is None

    # -------------------------------------------------------------------------
    # CASE 14: Multiple facts in one utterance
    # -------------------------------------------------------------------------
    def test_case_14_multiple_facts_in_one_utterance(self):
        """Case 14: Single utterance with property, tenure, and occupation."""
        sim = LocalSimulatorAdapter()
        sim.start_conversation()
        sim.send_customer_utterance("Yes speaking.")
        sim.send_customer_utterance("Sure.")
        turn = sim.send_customer_utterance("I want 40 lakhs for 5 years on my residential flat, I am salaried.")
        state = sim.get_state()
        assert state.loan_amount == 4_000_000
        assert state.tenure_years == 5
        assert state.property_type == PropertyType.RESIDENTIAL
        assert state.occupation == OccupationType.SALARIED

    # -------------------------------------------------------------------------
    # CASE 15: Contradictory corrections
    # -------------------------------------------------------------------------
    def test_case_15_contradictory_correction(self):
        """Case 15: Customer corrects earlier residential answer to agricultural."""
        sim = LocalSimulatorAdapter()
        sim.start_conversation()
        sim.send_customer_utterance("Yes speaking.")
        sim.send_customer_utterance("Sure.")
        sim.send_customer_utterance("Interested.")
        sim.send_customer_utterance("Residential flat.")
        assert sim.get_state().property_type == PropertyType.RESIDENTIAL

        # Correction
        turn = sim.send_customer_utterance("Actually, it is strictly agricultural farmland.")
        assert sim.get_state().property_type == PropertyType.AGRICULTURAL
        assert turn["disqualified"] is True
        assert turn["is_terminal"] is True

    # -------------------------------------------------------------------------
    # CASE 16: Ambiguous answers
    # -------------------------------------------------------------------------
    def test_case_16_ambiguous_answers(self):
        """Case 16: Ambiguous document availability does not authorize handoff."""
        state = QualificationState(original_documents_available=DocumentAvailability.UNKNOWN)
        assert state.is_checklist_complete() is False

    # -------------------------------------------------------------------------
    # CASE 17: Missing market value
    # -------------------------------------------------------------------------
    def test_case_17_missing_market_value(self):
        """Case 17: Market value missing prevents qualification handoff."""
        state = QualificationState(
            property_type=PropertyType.RESIDENTIAL,
            ownership_status=OwnershipStatus.SOLE,
            original_documents_available=DocumentAvailability.AVAILABLE,
            loan_amount=5_000_000,
            occupation=OccupationType.SALARIED,
            income_mode=IncomeMode.BANK,
            tenure_years=10,
            property_market_value=None,  # Missing!
        )
        assert "property_market_value" in state.get_missing_checklist_items()
        evaluated = EligibilityEngine.evaluate_state(state)
        assert evaluated.current_stage != ConversationStage.QUALIFIED_HANDOFF

    # -------------------------------------------------------------------------
    # CASE 18: Missing occupation or income mode
    # -------------------------------------------------------------------------
    def test_case_18_missing_occupation_or_income_mode(self):
        """Case 18: Missing occupation or income mode blocks qualification."""
        state = QualificationState(
            property_type=PropertyType.RESIDENTIAL,
            ownership_status=OwnershipStatus.SOLE,
            original_documents_available=DocumentAvailability.AVAILABLE,
            loan_amount=5_000_000,
            property_market_value=10_000_000,
            tenure_years=10,
            occupation=None,  # Missing!
            income_mode=IncomeMode.BANK,
        )
        assert "occupation_income_mode" in state.get_missing_checklist_items()
        evaluated = EligibilityEngine.evaluate_state(state)
        assert evaluated.current_stage != ConversationStage.QUALIFIED_HANDOFF

    # -------------------------------------------------------------------------
    # CASE 19: Interest-rate interruption
    # -------------------------------------------------------------------------
    def test_case_19_interest_rate_interruption(self):
        """Case 19: Customer interrupts asking for interest rate, agent answers and continues."""
        sim = LocalSimulatorAdapter()
        sim.start_conversation()
        sim.send_customer_utterance("Yes speaking.")
        turn = sim.send_customer_utterance("Before proceeding, what is your interest rate?")
        assert "interest rates" in turn["agent_response"].lower()
        assert turn["is_terminal"] is False

    # -------------------------------------------------------------------------
    # CASE 20: Customer refusal
    # -------------------------------------------------------------------------
    def test_case_20_customer_refusal(self):
        """Case 20: Customer declines offer, terminating call gracefully."""
        sim = LocalSimulatorAdapter()
        sim.start_conversation()
        sim.send_customer_utterance("Yes speaking.")
        sim.send_customer_utterance("Sure.")
        turn = sim.send_customer_utterance("Not interested, please disconnect.")
        assert turn["is_terminal"] is True
        assert sim.get_state().offer_accepted is False

    # -------------------------------------------------------------------------
    # CASE 21: Wrong person answers the call
    # -------------------------------------------------------------------------
    def test_case_21_wrong_person(self):
        """Case 21: Wrong person terminates call immediately."""
        sim = LocalSimulatorAdapter()
        sim.start_conversation()
        turn = sim.send_customer_utterance("Wrong number, wrong person.")
        assert turn["is_terminal"] is True
        assert sim.get_state().identity_verified is False

    # -------------------------------------------------------------------------
    # CASE 22: Transfer intent appearing midway through qualification
    # -------------------------------------------------------------------------
    def test_case_22_transfer_intent_midway(self):
        """Case 22: Transfer intent expressed midway through checklist halts flow."""
        sim = LocalSimulatorAdapter()
        sim.start_conversation()
        sim.send_customer_utterance("Yes speaking.")
        sim.send_customer_utterance("Sure.")
        sim.send_customer_utterance("Interested.")
        sim.send_customer_utterance("Residential flat.")
        # Midway transfer intent
        turn = sim.send_customer_utterance("Actually, I already have an existing loan and want to transfer it.")
        assert turn["is_transfer_lead"] is True
        assert turn["current_stage"] == ConversationStage.TRANSFER_BRANCH.value
        assert turn["is_terminal"] is True

    # -------------------------------------------------------------------------
    # CASE 23: Disqualifying information supplied out of order
    # -------------------------------------------------------------------------
    def test_case_23_disqualification_out_of_order(self):
        """Case 23: Disqualifying tenure supplied before property type halts flow."""
        sim = LocalSimulatorAdapter()
        sim.start_conversation()
        sim.send_customer_utterance("Yes speaking.")
        sim.send_customer_utterance("Sure.")
        sim.send_customer_utterance("Interested.")
        turn = sim.send_customer_utterance("I want to pay it back in 1 year.")
        assert turn["disqualified"] is True
        assert turn["is_terminal"] is True
        assert turn["current_stage"] == ConversationStage.DISQUALIFIED.value

    # -------------------------------------------------------------------------
    # CASE 24: Handoff attempted before all fields complete
    # -------------------------------------------------------------------------
    def test_case_24_handoff_blocked_if_incomplete(self):
        """Case 24: Final handoff strictly blocked when any checklist item is missing."""
        state = QualificationState(
            identity_verified=True,
            customer_available=True,
            offer_accepted=True,
            property_type=PropertyType.RESIDENTIAL,
            ownership_status=OwnershipStatus.SOLE,
            original_documents_available=DocumentAvailability.AVAILABLE,
            loan_amount=5_000_000,
            occupation=OccupationType.SALARIED,
            income_mode=IncomeMode.BANK,
            property_market_value=10_000_000,
            tenure_years=None,  # Missing tenure
        )
        evaluated = EligibilityEngine.evaluate_state(state)
        assert evaluated.current_stage != ConversationStage.QUALIFIED_HANDOFF
        assert evaluated.terminal_status is False

    # -------------------------------------------------------------------------
    # CASE 25: Terminal state cannot resume qualification
    # -------------------------------------------------------------------------
    def test_case_25_terminal_state_protected(self):
        """Case 25: Once disqualified, subsequent utterances cannot resurrect the flow."""
        sim = LocalSimulatorAdapter()
        sim.start_conversation()
        sim.send_customer_utterance("Wrong number.")
        assert sim.get_state().terminal_status is True

        # Attempt recovery
        turn = sim.send_customer_utterance("Wait, actually I am interested in a residential loan of 50 lakhs.")
        assert turn["is_terminal"] is True
        assert sim.get_state().current_stage == ConversationStage.CALL_TERMINATED

    # -------------------------------------------------------------------------
    # BOUNDARY TESTS
    # -------------------------------------------------------------------------
    def test_boundaries_amount_and_tenure(self):
        """Verify exact boundaries: ₹75L passes, 3y passes, 15y passes."""
        # Amount 75 Lakhs exactly
        val_75l, needs_cap, _ = EligibilityEngine.validate_loan_amount(7_500_000)
        assert val_75l is True
        assert needs_cap is False

        # Tenure 3 years exactly
        val_3y, _ = EligibilityEngine.validate_tenure(3)
        assert val_3y is True

        # Tenure 15 years exactly
        val_15y, _ = EligibilityEngine.validate_tenure(15)
        assert val_15y is True

        # Tenure 2 years (invalid)
        val_2y, _ = EligibilityEngine.validate_tenure(2)
        assert val_2y is False

        # Tenure 16 years (invalid)
        val_16y, _ = EligibilityEngine.validate_tenure(16)
        assert val_16y is False
