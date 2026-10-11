"""Conversation state model and data structures for Home Credit LAP Agent."""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ConversationStage(str, Enum):
    """Lifecycle stages of the voice qualification call."""
    GREETING_VERIFICATION = "greeting_verification"
    AVAILABILITY_CHECK = "availability_check"
    OFFER_PRESENTATION = "offer_presentation"
    ELIGIBILITY_CHECKLIST = "eligibility_checklist"
    LOAN_CAP_CONFIRMATION = "loan_cap_confirmation"
    TRANSFER_BRANCH = "transfer_branch"
    DISQUALIFIED = "disqualified"
    QUALIFIED_HANDOFF = "qualified_handoff"
    CALL_TERMINATED = "call_terminated"


class PropertyType(str, Enum):
    """Accepted and disqualifying property categories."""
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    AGRICULTURAL = "agricultural"
    UNKNOWN = "unknown"


class OwnershipStatus(str, Enum):
    """Property ownership structures."""
    SOLE = "sole"
    JOINT = "joint"
    UNKNOWN = "unknown"


class DocumentAvailability(str, Enum):
    """Availability of original documents for legal verification."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class OccupationType(str, Enum):
    """Customer employment classifications."""
    SALARIED = "salaried"
    SELF_EMPLOYED = "self_employed"
    UNKNOWN = "unknown"


class IncomeMode(str, Enum):
    """Mode of primary income receipt."""
    BANK = "bank"
    CASH = "cash"
    UNKNOWN = "unknown"


class ExtractedFacts(BaseModel):
    """Structured facts extracted from a single customer utterance."""
    # Identity & Availability
    identity_verified: Optional[bool] = None
    wrong_person: Optional[bool] = None
    customer_available: Optional[bool] = None
    callback_time: Optional[str] = None
    customer_declined: Optional[bool] = None

    # Offer & Transfer intent
    offer_accepted: Optional[bool] = None
    existing_property_loan: Optional[bool] = None
    emi_reduction_intent: Optional[bool] = None

    # 7 Eligibility Checklist Items
    property_type: Optional[PropertyType] = None
    ownership_status: Optional[OwnershipStatus] = None
    original_documents_available: Optional[DocumentAvailability] = None
    loan_amount: Optional[int] = None
    loan_cap_confirmed: Optional[bool] = None
    occupation: Optional[OccupationType] = None
    income_mode: Optional[IncomeMode] = None
    property_market_value: Optional[int] = None
    tenure_years: Optional[int] = None

    # Conversation control
    customer_query_or_interruption: Optional[str] = None
    raw_utterance: Optional[str] = None


class QualificationState(BaseModel):
    """Complete, explicit session state of a customer qualification call."""
    customer_name: str = "Valued Customer"
    agent_name: str = "Pooja"
    language: str = "English"

    # Stage 1: Identity Verification
    identity_verified: Optional[bool] = None

    # Stage 2: Availability
    customer_available: Optional[bool] = None
    callback_time: Optional[str] = None

    # Stage 3 & 4: Offer Presentation & Transfer
    offer_accepted: Optional[bool] = None
    existing_property_loan: Optional[bool] = None
    emi_reduction_intent: Optional[bool] = None
    is_transfer_lead: bool = False

    # Stage 5: Seven Checklist Items
    # 1. Property Type
    property_type: Optional[PropertyType] = None
    # 2. Ownership Status
    ownership_status: Optional[OwnershipStatus] = None
    # 3. Original Documents
    original_documents_available: Optional[DocumentAvailability] = None
    # 4. Loan Amount & Cap Confirmation
    loan_amount: Optional[int] = None
    loan_cap_confirmed: Optional[bool] = None
    # 5. Occupation & Income Mode (stored separately)
    occupation: Optional[OccupationType] = None
    income_mode: Optional[IncomeMode] = None
    # 6. Property Market Value
    property_market_value: Optional[int] = None
    # 7. Repayment Tenure
    tenure_years: Optional[int] = None

    # Disqualification tracking
    disqualification_status: bool = False
    disqualification_reason: Optional[str] = None

    # Lifecycle & Flow Control
    current_stage: ConversationStage = ConversationStage.GREETING_VERIFICATION
    terminal_status: bool = False
    last_question_asked: Optional[str] = None
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)

    def is_checklist_complete(self) -> bool:
        """Verify whether all seven checklist items have been explicitly captured."""
        return (
            self.property_type is not None and self.property_type != PropertyType.UNKNOWN
            and self.ownership_status is not None and self.ownership_status != OwnershipStatus.UNKNOWN
            and self.original_documents_available is not None and self.original_documents_available != DocumentAvailability.UNKNOWN
            and self.loan_amount is not None
            and self.occupation is not None and self.occupation != OccupationType.UNKNOWN
            and self.income_mode is not None and self.income_mode != IncomeMode.UNKNOWN
            and self.property_market_value is not None
            and self.tenure_years is not None
        )

    def get_missing_checklist_items(self) -> List[str]:
        """Return list of missing checklist items in prioritized order."""
        missing = []
        if self.property_type is None or self.property_type == PropertyType.UNKNOWN:
            missing.append("property_type")
        if self.ownership_status is None or self.ownership_status == OwnershipStatus.UNKNOWN:
            missing.append("ownership_status")
        if self.original_documents_available is None or self.original_documents_available == DocumentAvailability.UNKNOWN:
            missing.append("original_documents")
        if self.loan_amount is None:
            missing.append("loan_amount")
        if (self.occupation is None or self.occupation == OccupationType.UNKNOWN) or \
           (self.income_mode is None or self.income_mode == IncomeMode.UNKNOWN):
            missing.append("occupation_income_mode")
        if self.property_market_value is None:
            missing.append("property_market_value")
        if self.tenure_years is None:
            missing.append("tenure_years")
        return missing

    def to_readable_summary(self) -> Dict[str, Any]:
        """Output clean dictionary summary of the customer state."""
        return {
            "customer_name": self.customer_name,
            "identity_verified": self.identity_verified,
            "stage": self.current_stage.value,
            "is_transfer_lead": self.is_transfer_lead,
            "disqualified": self.disqualification_status,
            "disqualification_reason": self.disqualification_reason,
            "terminal": self.terminal_status,
            "checklist": {
                "property_type": self.property_type.value if self.property_type else "UNKNOWN",
                "ownership_status": self.ownership_status.value if self.ownership_status else "UNKNOWN",
                "original_documents": self.original_documents_available.value if self.original_documents_available else "UNKNOWN",
                "loan_amount": f"₹{self.loan_amount:,}" if self.loan_amount else "UNKNOWN",
                "loan_cap_confirmed": self.loan_cap_confirmed,
                "occupation": self.occupation.value if self.occupation else "UNKNOWN",
                "income_mode": self.income_mode.value if self.income_mode else "UNKNOWN",
                "property_market_value": f"₹{self.property_market_value:,}" if self.property_market_value else "UNKNOWN",
                "tenure_years": f"{self.tenure_years} years" if self.tenure_years else "UNKNOWN",
            }
        }
