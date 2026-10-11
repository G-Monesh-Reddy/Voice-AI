"""Deterministic Eligibility Engine for Home Credit LAP Agent.

Enforces business rules, normalizes financial values, protects terminal states,
and guarantees that natural language never overrides deterministic logic.
"""

import re
from typing import Optional, Tuple, Any
from app.config import settings
from app.qualification_state import (
    QualificationState,
    ExtractedFacts,
    PropertyType,
    OwnershipStatus,
    DocumentAvailability,
    OccupationType,
    IncomeMode,
    ConversationStage,
)


class EligibilityEngine:
    """Deterministic business rules engine for Home Credit LAP qualification."""

    # -------------------------------------------------------------------------
    # NORMALIZATION UTILITIES
    # -------------------------------------------------------------------------

    @staticmethod
    def normalize_currency(val: Any) -> Optional[int]:
        """Convert conversational Indian currency expressions to integer rupees.
        
        Examples:
            - "50 lakhs", "50L", "50 lac", "₹50,00,000" -> 5000000
            - "1.5 crore", "1.5 cr", "1 cr" -> 15000000
            - "7500000", 7500000 -> 7500000
            - "pachaas lakh" -> 5000000
        """
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return int(val)

        text = str(val).strip().lower().replace(",", "").replace("₹", "").replace("rs.", "").replace("rs", "")

        # Word-based Hindi / Indian numbers
        hindi_numbers = {
            "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5,
            "chhah": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10, "pandrah": 15,
            "bees": 20, "pachees": 25, "tees": 30, "chalis": 40, "chaalis": 40,
            "pachaas": 50, "pachas": 50, "saath": 60, "sattar": 70, "assi": 80, "nabbe": 90,
            "sau": 100
        }
        for word, num in hindi_numbers.items():
            text = re.sub(rf"\b{word}\b", str(num), text)

        # Match Crore patterns
        cr_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:crore|crores|cr)\b", text)
        if cr_match:
            try:
                num = float(cr_match.group(1))
                return int(num * 10_000_000)
            except ValueError:
                pass

        # Match Lakh patterns
        lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|lacs|l)\b", text)
        if lakh_match:
            try:
                num = float(lakh_match.group(1))
                return int(num * 100_000)
            except ValueError:
                pass

        # Match Thousand / k patterns
        k_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:thousand|thousands|k)\b", text)
        if k_match:
            try:
                num = float(k_match.group(1))
                return int(num * 1_000)
            except ValueError:
                pass

        # Match raw integers
        num_match = re.search(r"\b(\d+)\b", text)
        if num_match:
            try:
                return int(num_match.group(1))
            except ValueError:
                pass

        return None

    @staticmethod
    def normalize_tenure(val: Any) -> Optional[int]:
        """Convert duration strings to integer years.
        
        Examples:
            - "5 years", "5 yrs", "5 saal", "5" -> 5
            - "60 months", "36 mahine" -> 5, 3
            - "dedh saal" -> 1 (or 2)
        """
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return int(val)

        text = str(val).strip().lower()

        # Check for months first
        months_match = re.search(r"(\d+)\s*(?:months|month|mahine|mahina|m)\b", text)
        if months_match:
            try:
                months = int(months_match.group(1))
                return int(round(months / 12.0))
            except ValueError:
                pass

        # Check for years / saal
        years_match = re.search(r"(\d+)\s*(?:years|year|yrs|yr|saal|sal|y)?\b", text)
        if years_match:
            try:
                return int(years_match.group(1))
            except ValueError:
                pass

        return None

    # -------------------------------------------------------------------------
    # DETERMINISTIC BUSINESS RULES
    # -------------------------------------------------------------------------

    @classmethod
    def validate_property_type(cls, prop_type: PropertyType) -> Tuple[bool, Optional[str]]:
        """Rule 1: Property Type Validation.
        
        Accepted: Residential, Commercial, Industrial.
        Disqualification: Agricultural property.
        """
        if prop_type == PropertyType.AGRICULTURAL:
            return False, "Agricultural property is strictly not accepted for this loan scheme."
        if prop_type in (PropertyType.RESIDENTIAL, PropertyType.COMMERCIAL, PropertyType.INDUSTRIAL):
            return True, None
        return False, "Unrecognized or unsupported property type."

    @classmethod
    def validate_ownership(cls, ownership: OwnershipStatus) -> Tuple[bool, Optional[str]]:
        """Rule 2: Ownership Validation.
        
        Accepted: Sole ownership, Joint ownership.
        Neither form is a disqualifier.
        """
        if ownership in (OwnershipStatus.SOLE, OwnershipStatus.JOINT):
            return True, None
        return False, "Unrecognized ownership structure."

    @classmethod
    def validate_original_documents(cls, docs: DocumentAvailability) -> Tuple[bool, Optional[str]]:
        """Rule 3: Original Documents Validation.
        
        Original documents must be available for legal verification.
        If confirmed unavailable/lost, disqualify immediately.
        """
        if docs == DocumentAvailability.AVAILABLE:
            return True, None
        if docs == DocumentAvailability.UNAVAILABLE:
            return False, "Original property documents must be available for legal verification before loan disbursal."
        return False, "Document availability status is unknown or ambiguous."

    @classmethod
    def validate_loan_amount(cls, amount: Optional[int], cap_confirmed: Optional[bool] = None) -> Tuple[bool, bool, Optional[str]]:
        """Rule 4: Loan Amount Validation.
        
        Maximum loan limit: ₹75,00,000.
        Returns: (is_eligible, needs_cap_confirmation, reason)
        """
        if amount is None or amount <= 0:
            return False, False, "Valid loan amount is required."

        max_limit = settings.max_loan_amount

        if amount <= max_limit:
            return True, False, None

        # Customer requested > 75 Lakhs
        if cap_confirmed is True:
            # Customer accepted ₹75 Lakh cap
            return True, False, None
        elif cap_confirmed is False:
            # Customer refused ₹75 Lakh cap
            return False, False, f"Requested loan amount (₹{amount:,}) exceeds the maximum scheme limit of ₹{max_limit:,} and customer declined the ₹75 Lakh cap."
        else:
            # Requires explicit confirmation
            return False, True, f"Requested loan amount (₹{amount:,}) exceeds the maximum limit of ₹{max_limit:,}. Explicit customer acceptance of ₹75 Lakh is required."

    @classmethod
    def validate_occupation_and_income_mode(
        cls, occupation: OccupationType, income_mode: IncomeMode
    ) -> Tuple[bool, Optional[str]]:
        """Rule 5: Occupation and Income Mode Validation.
        
        Accepted occupations: Salaried, Self-employed.
        Income mode: Must be received through a bank account.
        Cash income: Immediate disqualification.
        """
        if income_mode == IncomeMode.CASH:
            return False, "Income received in cash is not eligible. Income must be credited directly to a bank account."

        if occupation not in (OccupationType.SALARIED, OccupationType.SELF_EMPLOYED):
            return False, "Occupation must be either Salaried or Self-Employed."

        if income_mode == IncomeMode.BANK:
            return True, None

        return False, "Income mode must be verified via bank account."

    @classmethod
    def validate_market_value(cls, market_value: Optional[int]) -> Tuple[bool, Optional[str]]:
        """Rule 6: Property Market Value Validation.
        
        Capture customer's estimated property value.
        No minimum market value is specified.
        """
        if market_value is not None and market_value > 0:
            return True, None
        return False, "Estimated property market value must be provided."

    @classmethod
    def validate_tenure(cls, tenure_years: Optional[int]) -> Tuple[bool, Optional[str]]:
        """Rule 7: Repayment Tenure Validation.
        
        Accepted: 3 through 15 years inclusive.
        Disqualification: Below 3 years or above 15 years.
        """
        if tenure_years is None:
            return False, "Repayment tenure is required."

        min_t = settings.min_tenure_years
        max_t = settings.max_tenure_years

        if min_t <= tenure_years <= max_t:
            return True, None
        elif tenure_years < min_t:
            return False, f"Repayment tenure of {tenure_years} years is below the minimum allowed period of {min_t} years."
        else:
            return False, f"Repayment tenure of {tenure_years} years exceeds the maximum allowed period of {max_t} years."

    # -------------------------------------------------------------------------
    # STATE EVALUATION & TRANSITIONS
    # -------------------------------------------------------------------------

    @classmethod
    def evaluate_state(cls, state: QualificationState) -> QualificationState:
        """Evaluate full qualification state against business rules deterministically."""
        # Terminal state protection: Never mutate terminal state
        if state.terminal_status:
            return state

        # Check wrong person / identity failure
        if state.identity_verified is False:
            state.terminal_status = True
            state.current_stage = ConversationStage.CALL_TERMINATED
            return state

        # Check busy / callback request
        if state.customer_available is False:
            state.terminal_status = True
            state.current_stage = ConversationStage.CALL_TERMINATED
            return state

        # Check customer refusal
        if state.offer_accepted is False:
            state.terminal_status = True
            state.current_stage = ConversationStage.CALL_TERMINATED
            return state

        # Check Loan Transfer / EMI reduction branch
        if state.existing_property_loan is True and (state.emi_reduction_intent is True or state.is_transfer_lead is True):
            state.is_transfer_lead = True
            state.current_stage = ConversationStage.TRANSFER_BRANCH
            state.terminal_status = True
            return state

        # Immediate Disqualification Checks (Priority Evaluation)
        # 1. Agricultural property
        if state.property_type == PropertyType.AGRICULTURAL:
            state.disqualification_status = True
            state.disqualification_reason = "Agricultural property is not eligible for this offer."
            state.current_stage = ConversationStage.DISQUALIFIED
            state.terminal_status = True
            return state

        # 2. Original documents unavailable
        if state.original_documents_available == DocumentAvailability.UNAVAILABLE:
            state.disqualification_status = True
            state.disqualification_reason = "Original property documents unavailable for legal verification."
            state.current_stage = ConversationStage.DISQUALIFIED
            state.terminal_status = True
            return state

        # 3. Cash income mode
        if state.income_mode == IncomeMode.CASH:
            state.disqualification_status = True
            state.disqualification_reason = "Income received in cash is not eligible; bank account receipt is mandatory."
            state.current_stage = ConversationStage.DISQUALIFIED
            state.terminal_status = True
            return state

        # 4. Tenure out of bounds (<3 or >15)
        if state.tenure_years is not None:
            is_valid_tenure, reason = cls.validate_tenure(state.tenure_years)
            if not is_valid_tenure:
                state.disqualification_status = True
                state.disqualification_reason = reason
                state.current_stage = ConversationStage.DISQUALIFIED
                state.terminal_status = True
                return state

        # 5. Loan amount > 75L and customer rejected the 75L cap
        if state.loan_amount is not None and state.loan_amount > settings.max_loan_amount:
            if state.loan_cap_confirmed is False:
                state.disqualification_status = True
                state.disqualification_reason = f"Loan amount ₹{state.loan_amount:,} exceeds ₹75 Lakh limit and customer declined capped offer."
                state.current_stage = ConversationStage.DISQUALIFIED
                state.terminal_status = True
                return state
            elif state.loan_cap_confirmed is None:
                # Need explicit confirmation before proceeding
                state.current_stage = ConversationStage.LOAN_CAP_CONFIRMATION
                return state

        # Check if all 7 checklist items are gathered and pass all rules
        if state.is_checklist_complete():
            # Validate every item passes
            p_valid, _ = cls.validate_property_type(state.property_type)
            o_valid, _ = cls.validate_ownership(state.ownership_status)
            d_valid, _ = cls.validate_original_documents(state.original_documents_available)
            l_valid, _, _ = cls.validate_loan_amount(state.loan_amount, state.loan_cap_confirmed)
            occ_valid, _ = cls.validate_occupation_and_income_mode(state.occupation, state.income_mode)
            m_valid, _ = cls.validate_market_value(state.property_market_value)
            t_valid, _ = cls.validate_tenure(state.tenure_years)

            if p_valid and o_valid and d_valid and l_valid and occ_valid and m_valid and t_valid:
                # All pass! Authorize qualified handoff
                state.current_stage = ConversationStage.QUALIFIED_HANDOFF
                state.terminal_status = True
                return state

        # Stage progression
        if state.identity_verified is True and state.customer_available is None:
            state.current_stage = ConversationStage.AVAILABILITY_CHECK
            return state

        if state.customer_available is True and state.offer_accepted is None:
            state.current_stage = ConversationStage.OFFER_PRESENTATION
            return state

        if state.offer_accepted is True:
            state.current_stage = ConversationStage.ELIGIBILITY_CHECKLIST
            return state

        return state

    @classmethod
    def apply_facts_to_state(cls, state: QualificationState, facts: ExtractedFacts) -> QualificationState:
        """Safely update qualification state with extracted facts, handling corrections."""
        # Terminal state lockdown: Do not mutate an already terminated call
        if state.terminal_status:
            return state

        # Identity & Wrong person
        if facts.wrong_person is True:
            state.identity_verified = False
        elif facts.identity_verified is not None:
            state.identity_verified = facts.identity_verified

        # Customer availability
        if facts.customer_available is not None:
            state.customer_available = facts.customer_available
        if facts.callback_time:
            state.callback_time = facts.callback_time
            state.customer_available = False

        # Customer refusal
        if facts.customer_declined is True:
            state.offer_accepted = False

        # Offer acceptance
        if facts.offer_accepted is not None:
            state.offer_accepted = facts.offer_accepted

        # Existing loan & EMI reduction intent
        if facts.existing_property_loan is not None:
            state.existing_property_loan = facts.existing_property_loan
        if facts.emi_reduction_intent is not None:
            state.emi_reduction_intent = facts.emi_reduction_intent
            if facts.emi_reduction_intent is True:
                state.existing_property_loan = True
                state.is_transfer_lead = True

        # Property Type (supports corrections)
        if facts.property_type is not None and facts.property_type != PropertyType.UNKNOWN:
            state.property_type = facts.property_type

        # Ownership Status (supports corrections)
        if facts.ownership_status is not None and facts.ownership_status != OwnershipStatus.UNKNOWN:
            state.ownership_status = facts.ownership_status

        # Document Availability (supports corrections)
        if facts.original_documents_available is not None and facts.original_documents_available != DocumentAvailability.UNKNOWN:
            state.original_documents_available = facts.original_documents_available

        # Loan Amount & Cap Confirmation
        if facts.loan_amount is not None:
            state.loan_amount = facts.loan_amount
            # If new loan amount is <= 75L, clear cap confirmation requirement
            if facts.loan_amount <= settings.max_loan_amount:
                state.loan_cap_confirmed = True
            else:
                state.loan_cap_confirmed = None

        if facts.loan_cap_confirmed is not None:
            state.loan_cap_confirmed = facts.loan_cap_confirmed
            if facts.loan_cap_confirmed is True:
                # If confirmed, ensure amount is capped at 75L for processing
                state.loan_amount = settings.max_loan_amount
            elif facts.loan_cap_confirmed is False:
                state.disqualification_status = True
                state.disqualification_reason = f"Loan amount ₹{state.loan_amount:,} exceeds ₹75 Lakh limit and customer declined capped offer."
                state.current_stage = ConversationStage.DISQUALIFIED
                state.terminal_status = True
                return state

        # Occupation & Income Mode (stored separately)
        if facts.occupation is not None and facts.occupation != OccupationType.UNKNOWN:
            state.occupation = facts.occupation
        if facts.income_mode is not None and facts.income_mode != IncomeMode.UNKNOWN:
            state.income_mode = facts.income_mode

        # Property Market Value (supports corrections)
        if facts.property_market_value is not None:
            state.property_market_value = facts.property_market_value

        # Tenure (supports corrections)
        if facts.tenure_years is not None:
            state.tenure_years = facts.tenure_years

        # Run deterministic business logic evaluation
        return cls.evaluate_state(state)
