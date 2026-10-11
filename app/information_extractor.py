"""Information Extractor module for Home Credit LAP Voice Agent.

Combines Google Gemini API extraction with Pydantic validation,
currency/tenure normalization, and deterministic fallback parsing.
"""

import re
import logging
from typing import Optional, Dict, Any

from app.qualification_state import (
    ExtractedFacts,
    PropertyType,
    OwnershipStatus,
    DocumentAvailability,
    OccupationType,
    IncomeMode,
    ConversationStage,
)
from app.eligibility_engine import EligibilityEngine
from app.gemini_client import GeminiClient

logger = logging.getLogger(__name__)


class InformationExtractor:
    """Hybrid extractor: uses Google Gemini API when available, with deterministic fallback."""

    def __init__(self, gemini_client: Optional[GeminiClient] = None):
        self.gemini_client = gemini_client or GeminiClient()
        self.engine = EligibilityEngine()

    def extract(
        self,
        utterance: str,
        customer_name: str = "Customer",
        language: str = "English",
        current_stage: ConversationStage = ConversationStage.GREETING_VERIFICATION,
        last_question_asked: Optional[str] = None,
    ) -> ExtractedFacts:
        """Extract structured facts from utterance with validation and normalization."""
        # 1. Attempt Gemini extraction if client is available
        if self.gemini_client.is_available:
            try:
                gemini_data = self.gemini_client.extract_facts_with_gemini(
                    utterance=utterance,
                    customer_name=customer_name,
                    language=language,
                    current_stage=current_stage.value,
                    last_question=last_question_asked,
                )
                if gemini_data:
                    validated = self._validate_and_normalize_gemini_output(gemini_data, utterance)
                    if validated:
                        logger.info("Successfully extracted facts via Google Gemini API.")
                        return validated
            except Exception as e:
                logger.warning(f"Gemini extraction encountered an issue, falling back to rule engine: {e}")

        # 2. Deterministic high-precision fallback extractor
        return self._extract_deterministic(utterance, current_stage, last_question_asked)

    def _validate_and_normalize_gemini_output(
        self, data: Dict[str, Any], raw_utterance: str
    ) -> Optional[ExtractedFacts]:
        """Validate raw dictionary from Gemini against ExtractedFacts schema and normalize values."""
        try:
            # Normalize currency and tenure if string representation was returned
            loan_amt = data.get("loan_amount")
            if loan_amt is not None and not isinstance(loan_amt, int):
                loan_amt = self.engine.normalize_currency(loan_amt)

            market_val = data.get("property_market_value")
            if market_val is not None and not isinstance(market_val, int):
                market_val = self.engine.normalize_currency(market_val)

            tenure = data.get("tenure_years")
            if tenure is not None and not isinstance(tenure, int):
                tenure = self.engine.normalize_tenure(tenure)

            facts = ExtractedFacts(
                raw_utterance=raw_utterance,
                identity_verified=data.get("identity_verified"),
                wrong_person=data.get("wrong_person"),
                customer_available=data.get("customer_available"),
                callback_time=data.get("callback_time"),
                customer_declined=data.get("customer_declined"),
                offer_accepted=data.get("offer_accepted"),
                existing_property_loan=data.get("existing_property_loan"),
                emi_reduction_intent=data.get("emi_reduction_intent"),
                property_type=PropertyType(data["property_type"]) if data.get("property_type") in [e.value for e in PropertyType] else None,
                ownership_status=OwnershipStatus(data["ownership_status"]) if data.get("ownership_status") in [e.value for e in OwnershipStatus] else None,
                original_documents_available=DocumentAvailability(data["original_documents_available"]) if data.get("original_documents_available") in [e.value for e in DocumentAvailability] else None,
                loan_amount=loan_amt,
                loan_cap_confirmed=data.get("loan_cap_confirmed"),
                occupation=OccupationType(data["occupation"]) if data.get("occupation") in [e.value for e in OccupationType] else None,
                income_mode=IncomeMode(data["income_mode"]) if data.get("income_mode") in [e.value for e in IncomeMode] else None,
                property_market_value=market_val,
                tenure_years=tenure,
                customer_query_or_interruption=data.get("customer_query_or_interruption"),
            )
            return facts
        except Exception as e:
            logger.error(f"Failed to validate Gemini output against Pydantic schema: {e}")
            return None

    def _extract_deterministic(
        self,
        utterance: str,
        current_stage: ConversationStage,
        last_question_asked: Optional[str] = None,
    ) -> ExtractedFacts:
        """Deterministic extractor providing 100% reliable offline testing."""
        text = utterance.strip()
        lower = text.lower()
        facts = ExtractedFacts(raw_utterance=text)

        # Identity & Wrong person
        wrong_person_phrases = ["not me", "wrong number", "galat number", "wrong person", "not available", "nahin hoon"]
        if any(phrase in lower for phrase in wrong_person_phrases):
            facts.wrong_person = True
            facts.identity_verified = False
        elif any(phrase in lower for phrase in [
            "yes speaking", "speaking", "ha bol raha", "haan bol raha", "haan bol rahi",
            "ha bol rahi", "this is", "myself", "yes i am", "haan main", "ji haan", "ji ha"
        ]):
            facts.identity_verified = True
            facts.wrong_person = False
        elif current_stage == ConversationStage.GREETING_VERIFICATION or last_question_asked == "identity":
            if any(re.search(rf"\b{w}\b", lower) for w in ["yes", "haan", "ha", "ji", "yep", "sure", "speaking"]):
                facts.identity_verified = True
                facts.wrong_person = False

        # Availability & Busy
        busy_triggers = [
            "busy", "driving", "in a meeting", "call later", "baad me call", "baad mein",
            "call back", "not free", "fursat nahi", "meeting me hoon", "drive kar raha"
        ]
        if any(trig in lower for trig in busy_triggers):
            facts.customer_available = False
            time_match = re.search(
                r"(?:call(?: me)? (?:at|around|after|tomorrow|in)?\s*)?(\d{1,2}(?::\d{2})?\s*(?:am|pm|baje)|evening|morning|tomorrow|afternoon|kal|shaam|dopahar)",
                lower
            )
            facts.callback_time = time_match.group(0).strip() if time_match else "later"
        elif current_stage == ConversationStage.AVAILABILITY_CHECK or last_question_asked == "availability":
            avail_words = ["yes", "haan", "ha", "ji", "sure", "okay", "fine", "boliye", "bataiye", "two minutes", "go ahead", "speak", "free", "time"]
            if any(re.search(rf"\b{w}\b", lower) for w in avail_words):
                facts.customer_available = True

        # Refusal vs Offer Acceptance
        refusal_triggers = [
            "not interested", "don't want", "dont want", "no need", "nahi chahiye",
            "nahi lena", "mat karo call", "stop calling", "decline", "cut the call", "disconnect"
        ]
        if any(trig in lower for trig in refusal_triggers):
            facts.customer_declined = True
            facts.offer_accepted = False
        elif current_stage == ConversationStage.OFFER_PRESENTATION or last_question_asked == "offer":
            offer_words = ["yes", "haan", "ha", "sure", "okay", "batao", "interested", "proceed", "chahiye", "explore", "tell me"]
            if any(re.search(rf"\b{w}\b", lower) for w in offer_words):
                facts.offer_accepted = True

        # Transfer / EMI Reduction intent
        if re.search(r"\b(?:reduce|lower|kam)\s+(?:\w+\s+)?emi\b", lower) or any(
            t in lower for t in [
                "already have a loan", "existing loan", "running loan", "current loan",
                "loan transfer", "balance transfer", "transfer my loan", "transfer the loan",
                "transfer it", "transfer the balance", "transferring the balance",
                "another bank", "dusre bank", "current bank loan"
            ]
        ):
            facts.existing_property_loan = True
            facts.emi_reduction_intent = True

        # Property Type
        if any(w in lower for w in ["agricultural", "agriculture", "kheti", "farmland", "farm land", "krishi", "khet"]):
            facts.property_type = PropertyType.AGRICULTURAL
        elif any(w in lower for w in ["commercial", "shop", "office", "dukan", "showroom"]):
            facts.property_type = PropertyType.COMMERCIAL
        elif any(w in lower for w in ["industrial", "factory", "warehouse", "karkhana", "godown"]):
            facts.property_type = PropertyType.INDUSTRIAL
        elif any(w in lower for w in ["residential", "house", "home", "flat", "apartment", "makan", "ghar", "villa"]):
            facts.property_type = PropertyType.RESIDENTIAL

        # Property Ownership
        if any(w in lower for w in ["joint", "jointly", "wife", "father", "mother", "brother", "husband", "partner", "co-owner", "spouse"]):
            facts.ownership_status = OwnershipStatus.JOINT
        elif any(w in lower for w in ["sole", "alone", "only me", "my own name", "single name", "mere akele", "khud ke naam"]):
            facts.ownership_status = OwnershipStatus.SOLE

        # Original Documents
        if any(w in lower for w in ["cannot produce", "lost", "missing", "don't have original", "no original", "gum ho gaye", "nahi hai", "unavailable", "only photocopies"]):
            facts.original_documents_available = DocumentAvailability.UNAVAILABLE
        elif any(w in lower for w in ["have original", "original is there", "originals available", "yes available", "in locker", "at home", "locker me hai", "ghar pe hai", "originals are there", "documents are ready", "yes i have them", "original registry", "original papers"]):
            facts.original_documents_available = DocumentAvailability.AVAILABLE
        elif last_question_asked == "original_documents":
            if any(re.search(rf"\b{w}\b", lower) for w in ["yes", "haan", "ha", "ji", "available", "hain", "ready", "there", "locker"]):
                facts.original_documents_available = DocumentAvailability.AVAILABLE
            elif any(re.search(rf"\b{w}\b", lower) for w in ["no", "nahi", "nahin", "lost", "unavailable"]):
                facts.original_documents_available = DocumentAvailability.UNAVAILABLE

        # Loan Cap Confirmation
        if current_stage == ConversationStage.LOAN_CAP_CONFIRMATION:
            pos_words = ["yes", "haan", "ha", "ok", "okay", "fine", "proceed", "chalega", "works", "sure", "agreed"]
            neg_words = ["no", "nahi", "nahin", "cancel", "drop", "less", "low", "reject"]
            if any(re.search(rf"\b{w}\b", lower) for w in pos_words):
                facts.loan_cap_confirmed = True
            elif any(re.search(rf"\b{w}\b", lower) for w in neg_words):
                facts.loan_cap_confirmed = False
        else:
            amount_patterns = [
                r"(?:loan of|need|want|looking for|require|chahiye|borrow)\s*(?:around|approx|upto)?\s*([0-9\.]+\s*(?:crore|crores|cr|lakh|lakhs|lac|lacs|l|k|thousand)?|[0-9,]+)",
                r"([0-9\.]+\s*(?:crore|crores|cr|lakh|lakhs|lac|lacs))\s*(?:ka loan|loan|chahiye)\b",
            ]
            extracted_amount = None
            for pattern in amount_patterns:
                amt_match = re.search(pattern, lower)
                if amt_match:
                    extracted_amount = self.engine.normalize_currency(amt_match.group(1))
                    if extracted_amount and extracted_amount > 50_000:
                        break

            if not extracted_amount and last_question_asked == "loan_amount":
                extracted_amount = self.engine.normalize_currency(lower)

            if extracted_amount and extracted_amount > 50_000:
                facts.loan_amount = extracted_amount

        # Occupation & Income Mode
        if any(w in lower for w in ["salaried", "job", "private job", "govt job", "government employee", "service", "company me"]):
            facts.occupation = OccupationType.SALARIED
        elif any(w in lower for w in ["self employed", "self-employed", "business", "own business", "freelance", "trader", "dukan", "shopkeeper", "consultant", "doctor", "architect"]):
            facts.occupation = OccupationType.SELF_EMPLOYED

        if any(w in lower for w in ["cash", "in hand", "nakad", "rokhad"]):
            facts.income_mode = IncomeMode.CASH
        elif any(w in lower for w in ["bank", "account", "transfer", "cheque", "check", "neft", "rtgs", "direct deposit", "khate me", "credited"]):
            facts.income_mode = IncomeMode.BANK

        # Property Market Value
        value_patterns = [
            r"(?:value is|worth|market value|valued at|keemat|valuation)\s*(?:around|approx|is|of)?\s*([0-9\.]+\s*(?:crore|crores|cr|lakh|lakhs|lac|lacs|l)?|[0-9,]+)",
            r"([0-9\.]+\s*(?:crore|crores|cr|lakh|lakhs|lac|lacs))\s*(?:ki value|ki property|market value)\b",
        ]
        extracted_value = None
        for pattern in value_patterns:
            v_match = re.search(pattern, lower)
            if v_match:
                extracted_value = self.engine.normalize_currency(v_match.group(1))
                if extracted_value and extracted_value > 50_000:
                    break

        if not extracted_value and last_question_asked == "property_market_value":
            extracted_value = self.engine.normalize_currency(lower)

        if extracted_value and extracted_value > 50_000:
            facts.property_market_value = extracted_value

        # Repayment Tenure
        tenure_patterns = [
            r"(\d{1,2})\s*(?:years|year|yrs|yr|saal|sal|months|mahine)\b",
            r"(?:tenure of|duration of|period of)\s*(\d{1,2})\b",
            r"(?:over|for)\s*(\d{1,2})\s*(?:years|year|yrs|yr|saal|sal|months|mahine)\b",
        ]
        extracted_tenure = None
        for pattern in tenure_patterns:
            t_match = re.search(pattern, lower)
            if t_match:
                extracted_tenure = self.engine.normalize_tenure(t_match.group(1))
                if extracted_tenure is not None:
                    break

        if extracted_tenure is None and last_question_asked == "tenure_years":
            extracted_tenure = self.engine.normalize_tenure(lower)

        if extracted_tenure is not None:
            facts.tenure_years = extracted_tenure

        # Customer Interruption / Query
        interruption_triggers = [
            "what is the interest rate", "interest rate", "byaj kitna", "roi",
            "how much interest", "processing fee", "charges", "hidden charges",
            "what are the rates"
        ]
        if any(trig in lower for trig in interruption_triggers):
            facts.customer_query_or_interruption = "interest_rate"

        return facts
