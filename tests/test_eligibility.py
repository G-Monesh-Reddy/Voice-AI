"""Automated Unit Tests for Deterministic Business Rules in EligibilityEngine."""

import pytest
from app.config import settings
from app.qualification_state import (
    QualificationState,
    PropertyType,
    OwnershipStatus,
    DocumentAvailability,
    OccupationType,
    IncomeMode,
    ConversationStage,
)
from app.eligibility_engine import EligibilityEngine


class TestEligibilityRules:
    """Test suite for isolated and integrated deterministic eligibility rules."""

    # -------------------------------------------------------------------------
    # RULE 1: PROPERTY TYPE
    # -------------------------------------------------------------------------

    def test_property_type_accepted(self):
        """Residential, commercial, and industrial properties must be accepted."""
        for p_type in [PropertyType.RESIDENTIAL, PropertyType.COMMERCIAL, PropertyType.INDUSTRIAL]:
            is_valid, reason = EligibilityEngine.validate_property_type(p_type)
            assert is_valid is True
            assert reason is None

    def test_property_type_agricultural_disqualification(self):
        """Agricultural property must trigger immediate failure."""
        is_valid, reason = EligibilityEngine.validate_property_type(PropertyType.AGRICULTURAL)
        assert is_valid is False
        assert "Agricultural property is strictly not accepted" in reason

    # -------------------------------------------------------------------------
    # RULE 2: OWNERSHIP STATUS
    # -------------------------------------------------------------------------

    def test_ownership_sole_and_joint_accepted(self):
        """Sole and Joint ownership must both be accepted; neither is a disqualifier."""
        for ownership in [OwnershipStatus.SOLE, OwnershipStatus.JOINT]:
            is_valid, reason = EligibilityEngine.validate_ownership(ownership)
            assert is_valid is True
            assert reason is None

    # -------------------------------------------------------------------------
    # RULE 3: ORIGINAL PROPERTY DOCUMENTS
    # -------------------------------------------------------------------------

    def test_original_documents_available(self):
        """Available original documents pass verification."""
        is_valid, reason = EligibilityEngine.validate_original_documents(DocumentAvailability.AVAILABLE)
        assert is_valid is True
        assert reason is None

    def test_original_documents_unavailable_disqualification(self):
        """Unavailable original documents must fail immediately."""
        is_valid, reason = EligibilityEngine.validate_original_documents(DocumentAvailability.UNAVAILABLE)
        assert is_valid is False
        assert "Original property documents must be available" in reason

    def test_original_documents_ambiguous(self):
        """Ambiguous/Unknown document status fails verification."""
        is_valid, _ = EligibilityEngine.validate_original_documents(DocumentAvailability.UNKNOWN)
        assert is_valid is False

    # -------------------------------------------------------------------------
    # RULE 4: LOAN AMOUNT BOUNDARIES & CAP CONFIRMATION
    # -------------------------------------------------------------------------

    def test_loan_amount_boundary_75_lakh_passes(self):
        """Loan amount of exactly ₹75,00,000 must pass without requiring cap confirmation."""
        is_valid, needs_cap, reason = EligibilityEngine.validate_loan_amount(7_500_000)
        assert is_valid is True
        assert needs_cap is False
        assert reason is None

    def test_loan_amount_below_75_lakh_passes(self):
        """Loan amount below ₹75,00,000 (e.g., ₹50 Lakhs) must pass directly."""
        is_valid, needs_cap, reason = EligibilityEngine.validate_loan_amount(5_000_000)
        assert is_valid is True
        assert needs_cap is False
        assert reason is None

    def test_loan_amount_above_75_lakh_triggers_cap_confirmation(self):
        """Loan amount above ₹75,00,000 (e.g., ₹90 Lakhs) requires cap confirmation."""
        is_valid, needs_cap, reason = EligibilityEngine.validate_loan_amount(9_000_000, cap_confirmed=None)
        assert is_valid is False
        assert needs_cap is True
        assert "exceeds the maximum limit" in reason

    def test_loan_amount_above_75_lakh_accepted_cap(self):
        """Loan amount above ₹75,00,000 with explicit customer acceptance passes."""
        is_valid, needs_cap, reason = EligibilityEngine.validate_loan_amount(9_000_000, cap_confirmed=True)
        assert is_valid is True
        assert needs_cap is False
        assert reason is None

    def test_loan_amount_above_75_lakh_rejected_cap(self):
        """Loan amount above ₹75,00,000 with customer rejection of ₹75L cap fails."""
        is_valid, needs_cap, reason = EligibilityEngine.validate_loan_amount(9_000_000, cap_confirmed=False)
        assert is_valid is False
        assert needs_cap is False
        assert "declined the ₹75 Lakh cap" in reason

    # -------------------------------------------------------------------------
    # RULE 5: OCCUPATION & INCOME MODE
    # -------------------------------------------------------------------------

    def test_salaried_and_self_employed_with_bank_income_passes(self):
        """Salaried and Self-employed with bank credit income must pass."""
        for occ in [OccupationType.SALARIED, OccupationType.SELF_EMPLOYED]:
            is_valid, reason = EligibilityEngine.validate_occupation_and_income_mode(occ, IncomeMode.BANK)
            assert is_valid is True
            assert reason is None

    def test_cash_income_immediate_disqualification(self):
        """Income received in cash must disqualify immediately."""
        for occ in [OccupationType.SALARIED, OccupationType.SELF_EMPLOYED]:
            is_valid, reason = EligibilityEngine.validate_occupation_and_income_mode(occ, IncomeMode.CASH)
            assert is_valid is False
            assert "cash is not eligible" in reason

    # -------------------------------------------------------------------------
    # RULE 6: PROPERTY MARKET VALUE
    # -------------------------------------------------------------------------

    def test_market_value_captured_passes_without_arbitrary_minimum(self):
        """Market value must pass for any positive number without arbitrary floor."""
        for val in [500_000, 2_500_000, 10_000_000]:
            is_valid, reason = EligibilityEngine.validate_market_value(val)
            assert is_valid is True
            assert reason is None

    def test_market_value_missing_fails(self):
        """Missing or zero market value fails."""
        is_valid, reason = EligibilityEngine.validate_market_value(None)
        assert is_valid is False
        is_valid_zero, _ = EligibilityEngine.validate_market_value(0)
        assert is_valid_zero is False

    # -------------------------------------------------------------------------
    # RULE 7: REPAYMENT TENURE BOUNDARIES
    # -------------------------------------------------------------------------

    def test_tenure_boundary_3_years_passes(self):
        """Tenure of 3 years (lower boundary) must pass."""
        is_valid, reason = EligibilityEngine.validate_tenure(3)
        assert is_valid is True
        assert reason is None

    def test_tenure_boundary_15_years_passes(self):
        """Tenure of 15 years (upper boundary) must pass."""
        is_valid, reason = EligibilityEngine.validate_tenure(15)
        assert is_valid is True
        assert reason is None

    def test_tenure_below_3_years_disqualification(self):
        """Tenure of 2 years (<3) must fail immediately."""
        is_valid, reason = EligibilityEngine.validate_tenure(2)
        assert is_valid is False
        assert "below the minimum allowed period of 3 years" in reason

    def test_tenure_above_15_years_disqualification(self):
        """Tenure of 20 years (>15) must fail immediately."""
        is_valid, reason = EligibilityEngine.validate_tenure(20)
        assert is_valid is False
        assert "exceeds the maximum allowed period of 15 years" in reason

    # -------------------------------------------------------------------------
    # NORMALIZATION TESTS
    # -------------------------------------------------------------------------

    def test_currency_normalization(self):
        """Verify normalization of various Indian currency expressions."""
        assert EligibilityEngine.normalize_currency("50 lakhs") == 5_000_000
        assert EligibilityEngine.normalize_currency("50L") == 5_000_000
        assert EligibilityEngine.normalize_currency("1.5 crore") == 15_000_000
        assert EligibilityEngine.normalize_currency("75,00,000") == 7_500_000
        assert EligibilityEngine.normalize_currency("pachaas lakh") == 5_000_000

    def test_tenure_normalization(self):
        """Verify normalization of tenure expressions."""
        assert EligibilityEngine.normalize_tenure("5 years") == 5
        assert EligibilityEngine.normalize_tenure("5 saal") == 5
        assert EligibilityEngine.normalize_tenure("60 months") == 5
        assert EligibilityEngine.normalize_tenure("36 months") == 3
        assert EligibilityEngine.normalize_tenure("10 yrs") == 10
