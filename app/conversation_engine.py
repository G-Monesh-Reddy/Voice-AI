"""Conversation Engine for Home Credit LAP Voice Agent.

Executes natural language fact extraction, normalization, deterministic state updating,
handling of interruptions, corrections, compound answers, and dialogue synthesis.
"""

import re
import json
from typing import Dict, Any, Optional, Tuple
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
from app.information_extractor import InformationExtractor


class ConversationEngine:
    """Orchestrates natural language conversations according to business logic."""

    def __init__(
        self,
        state: Optional[QualificationState] = None,
        extractor: Optional[InformationExtractor] = None,
    ):
        self.state = state or QualificationState()
        self.engine = EligibilityEngine()
        self.extractor = extractor or InformationExtractor()

    # -------------------------------------------------------------------------
    # STEP 1 & 2: FACT EXTRACTION & NORMALIZATION
    # -------------------------------------------------------------------------

    def extract_facts(self, utterance: str) -> ExtractedFacts:
        """Extract structured facts and intent from customer utterance."""
        return self.extractor.extract(
            utterance=utterance,
            customer_name=self.state.customer_name,
            language=self.state.language,
            current_stage=self.state.current_stage,
            last_question_asked=self.state.last_question_asked,
        )

    # -------------------------------------------------------------------------
    # STEP 3 THROUGH 9: CONVERSATION CYCLE & DIALOGUE GENERATION
    # -------------------------------------------------------------------------

    def process_utterance(self, utterance: str) -> Dict[str, Any]:
        """Execute complete 9-step conversation turn cycle."""
        # Record customer turn
        self.state.conversation_history.append({"speaker": "Customer", "text": utterance})

        # Step 1 & 2: Extract & Normalize
        facts = self.extract_facts(utterance)

        # Step 3, 4, 5, 6: Update state deterministically
        self.state = self.engine.apply_facts_to_state(self.state, facts)

        # Generate agent response based on resulting stage and questions
        response_text = self._generate_response(facts)

        # Record agent turn
        self.state.conversation_history.append({"speaker": "Agent", "text": response_text})

        return {
            "agent_response": response_text,
            "extracted_facts": facts.model_dump(exclude_none=True),
            "current_stage": self.state.current_stage.value,
            "is_terminal": self.state.terminal_status,
            "disqualified": self.state.disqualification_status,
            "disqualification_reason": self.state.disqualification_reason,
            "is_transfer_lead": self.state.is_transfer_lead,
            "missing_fields": self.state.get_missing_checklist_items(),
            "state_snapshot": self.state.to_readable_summary(),
        }

    def _generate_response(self, facts: ExtractedFacts) -> str:
        """Formulate natural, professional agent response based on evaluated state."""
        customer = self.state.customer_name
        company = settings.company_name
        is_hindi = self.state.language.lower() == "hindi"

        # Interruption preamble (if customer asked a question like interest rate)
        preamble = ""
        if facts.customer_query_or_interruption == "interest_rate":
            if is_hindi:
                preamble = "Humare Loan Against Property ke interest rates kafi aakarshak hain. Exact rate aapki property evaluation aur profile par depend karta hai, jo hamare senior loan expert bataenge. "
            else:
                preamble = "Our Loan Against Property interest rates are very competitive, typically starting from attractive market rates. The exact rate will be customized based on your property evaluation and profile by our senior loan expert. "

        # Terminal Stage 1: Identity Failure / Wrong Person
        if self.state.identity_verified is False:
            if is_hindi:
                return "Maaf kijiye, lagta hai galat number dial ho gaya hai. Aapka samay lene ke liye kshama chahenge. Shubh din!"
            return f"I apologize, it seems I have reached the wrong number. Thank you for your time with {company}, and have a good day."

        # Terminal Stage 2: Busy Customer / Callback
        if self.state.customer_available is False:
            time_str = self.state.callback_time or "a convenient time"
            if is_hindi:
                return f"Bilkul samajh sakti hoon. Main note kar leti hoon ki aapko {time_str} par call kiya jaye. Aapka dhanyawaad aur shubh din!"
            return f"I completely understand. I have noted to schedule a callback for {time_str}. Thank you for your time with {company}, and have a wonderful day!"

        # Terminal Stage 3: Customer Declined / Not Interested
        if self.state.offer_accepted is False:
            if is_hindi:
                return f"Dhanyawaad {customer} ji. Agar bhavishya mein property loan ki zaroorat ho, toh {company} hamesha aapki seva mein hai. Shubh din!"
            return f"Thank you for letting me know, {customer}. If you ever need a property loan in the future, {company} is always here for you. Have a great day!"

        # Terminal Stage 4: Loan Transfer Branch
        if self.state.current_stage == ConversationStage.TRANSFER_BRANCH:
            if is_hindi:
                return f"{preamble}Hum loan balance transfer aur EMI reduction mein poori madad karte hain. Main aapki request turant hamare Dedicated Loan Transfer Specialist ko forward kar rahi hoon, jo jaldi hi aapse behtareen refinancing options ke sath judenge. {company} ke sath judne ke liye dhanyawaad!"
            return f"{preamble}We definitely assist with loan balance transfers and EMI reduction. I am forwarding your request directly to our dedicated Loan Transfer Specialist, who will contact you shortly with the best refinancing options. Thank you for choosing {company}!"

        # Terminal Stage 5: Immediate Disqualification
        if self.state.current_stage == ConversationStage.DISQUALIFIED:
            if is_hindi:
                return f"{preamble}{customer} ji, jaankari saajha karne ke liye dhanyawaad. Khed hai ki is vishesh offer ki eligibility criteria ke anusaar, hum abhi aage nahi badh sakte. {company} ke sath jude rehne ke liye aapka aabhar. Shubh din!"
            return f"{preamble}Thank you for sharing those details, {customer}. Based on the eligibility criteria for this specific offer, we are unable to proceed with your application at this time. We sincerely appreciate your relationship with {company} and hope to serve you in the future. Have a good day!"

        # Stage: Loan Cap Confirmation Required (> 75 Lakhs requested)
        if self.state.current_stage == ConversationStage.LOAN_CAP_CONFIRMATION:
            if is_hindi:
                return f"{preamble}Is pre-approved scheme ke antargat maximum loan amount ₹75 Lakh tak hi uplabdh hai. Kya aap preliminary assessment ke liye ₹75 Lakh ke sath aage badhna chahenge?"
            return f"{preamble}Under this special pre-approved scheme, the maximum loan amount we can offer is ₹75 Lakhs. Would you like to proceed with ₹75 Lakhs for your preliminary assessment?"

        # Terminal Stage 7: Qualified Handoff (All 7 checklist items passed)
        if self.state.current_stage == ConversationStage.QUALIFIED_HANDOFF:
            if is_hindi:
                return f"{preamble}Badhai ho {customer} ji! Aapne hamari sabhi preliminary eligibility criteria poori kar li hain. {company} ke ek senior loan expert jaldi hi aapse sampark karenge jo exact interest rate, legal verification aur quick disbursal process samjhaenge. Aapka dhanyawaad aur shubh din!"
            return f"{preamble}Congratulations {customer}, you have successfully met our preliminary criteria for the Loan Against Property offer! A senior loan expert from {company} will contact you shortly to walk you through the exact interest rate, documentation verification, and fast sanction process. Thank you, and have a wonderful day!"

        # Active Progression: Ask Earliest Unanswered Question
        return preamble + self._ask_next_question()

    def _ask_next_question(self) -> str:
        """Select and format the earliest unanswered eligibility question."""
        customer = self.state.customer_name
        company = settings.company_name
        is_hindi = self.state.language.lower() == "hindi"

        # If identity not yet established
        if self.state.identity_verified is None:
            self.state.last_question_asked = "identity"
            if is_hindi:
                return f"Namaskar, kya meri baat {customer} ji se ho rahi hai?"
            return f"Hello, am I speaking with {customer}?"

        # If availability not checked
        if self.state.customer_available is None:
            self.state.last_question_asked = "availability"
            if is_hindi:
                return f"Main {company} se baat kar rahi hoon hamare exclusive property loan benefit ke baare mein. Kya aapke paas baat karne ke liye do minute hain?"
            return f"I am calling from {company} regarding an exclusive property loan benefit. Do you have two minutes to speak?"

        # If offer not presented
        if self.state.offer_accepted is None:
            self.state.last_question_asked = "offer"
            if is_hindi:
                return f"{customer} ji, {company} ke sath aapke relation ke aadhar par hum aapke liye ₹75 Lakh tak ka vishesh Loan Against Property offer le kar aaye hain. Yeh ek preliminary assessment call hai. Kya aap iski jaankari lena chahenge?"
            return f"{customer}, based on your relationship with {company}, you are eligible for our special Loan Against Property offer of up to ₹75 Lakhs for your personal or business needs. This is a preliminary assessment call to check your requirements. Would you be interested in exploring this today?"

        # 7 Checklist Items in prioritized order:
        # Item 1: Property Type
        if self.state.property_type is None or self.state.property_type == PropertyType.UNKNOWN:
            self.state.last_question_asked = "property_type"
            if is_hindi:
                return "Aapke paas kis tarah ki property hai—residential, commercial, ya industrial?"
            return "What type of property do you own—is it residential, commercial, or industrial?"

        # Item 2: Ownership Status
        if self.state.ownership_status is None or self.state.ownership_status == OwnershipStatus.UNKNOWN:
            self.state.last_question_asked = "ownership_status"
            if is_hindi:
                return "Yeh property akele aapke naam par hai, ya joint ownership mein hai?"
            return "Is the property solely in your name, or is it jointly owned?"

        # Item 3: Original Documents
        if self.state.original_documents_available is None or self.state.original_documents_available == DocumentAvailability.UNKNOWN:
            self.state.last_question_asked = "original_documents"
            if is_hindi:
                return "Kya property ke original documents legal verification ke liye uplabdh hain? (Aapko abhi call par hath me lene ki zaroorat nahi hai)."
            return "Do you have the original property documents available for physical verification during loan processing? (You do not need to hold them right now during the call)."

        # Item 4: Loan Amount
        if self.state.loan_amount is None:
            self.state.last_question_asked = "loan_amount"
            if is_hindi:
                return "Aapko lagbhag kitne loan amount ki avashyakta hai?"
            return "How much loan amount are you looking to borrow?"

        # Item 5: Occupation & Income Mode
        if (self.state.occupation is None or self.state.occupation == OccupationType.UNKNOWN) or \
           (self.state.income_mode is None or self.state.income_mode == IncomeMode.UNKNOWN):
            self.state.last_question_asked = "occupation_income_mode"
            if is_hindi:
                return "Aap salaried hain ya self-employed, aur kya aapki aamdani bank account mein aati hai ya cash mein?"
            return "Are you salaried or self-employed, and do you receive your primary income in a bank account or in cash?"

        # Item 6: Property Market Value
        if self.state.property_market_value is None:
            self.state.last_question_asked = "property_market_value"
            if is_hindi:
                return "Aapke anumaan ke anusaar is property ki vartamaan market value kitni hogi?"
            return "What is the approximate current market value of your property?"

        # Item 7: Repayment Tenure
        if self.state.tenure_years is None:
            self.state.last_question_asked = "tenure_years"
            if is_hindi:
                return "Aap is loan ko kitne saalon mein chukana pasand karenge—3 se 15 saal ke beech?"
            return "Over how many years would you prefer to repay the loan—between 3 and 15 years?"

        # Fallback if somehow all answered
        return "Thank you, all details have been captured."

    def get_greeting(self) -> str:
        """Initial opening greeting for initiating an outbound call."""
        customer = self.state.customer_name
        is_hindi = self.state.language.lower() == "hindi"
        self.state.last_question_asked = "identity"
        if is_hindi:
            return f"Namaskar, kya meri baat {customer} ji se ho rahi hai?"
        return f"Hello, am I speaking with {customer}?"
