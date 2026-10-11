# Home Credit Loan Against Property (LAP) Voice Agent - Architecture Documentation

## 1. System Overview

The **Home Credit LAP Qualification Voice Agent** is an enterprise conversational AI system designed to proactively reach out to existing Home Credit customers, introduce a pre-qualified Loan Against Property (LAP) offer of up to **₹75,00,000 (₹75 Lakhs)** for preliminary assessment, collect seven critical eligibility criteria, enforce deterministic business logic, and route qualified customers to a Senior Loan Expert.

The architecture strictly separates **natural language understanding** (powered by the **Google Gemini API** using the official `google-genai` Python SDK) from **deterministic business logic** (implemented in pure Python with Pydantic schemas). Natural language models never unilaterally override loan caps, property criteria, or terminal states.

---

## 2. End-to-End Pipeline Architecture

```mermaid
flowchart TD
    A[Customer Spoken Utterance] --> B[Voice Platform STT (Retell AI / Bolna)]
    B --> C[Google Gemini API Extraction]
    C --> D[Pydantic Fact Validation (ExtractedFacts)]
    D --> E[Normalization Engine (INR Currency, Tenure)]
    E --> F[Deterministic Eligibility Engine]
    F --> G{Business Rules Evaluation}
    G -->|Disqualifying Condition| H[DISQUALIFIED Terminal State]
    G -->|Existing Loan / EMI Reduction| I[TRANSFER_BRANCH Terminal State]
    G -->|Amount > 75L| J[LOAN_CAP_CONFIRMATION State]
    G -->|All 7 Criteria Met & Valid| K[QUALIFIED_HANDOFF Terminal State]
    G -->|Checklist Incomplete| L[Ask Next Unanswered Question]
    H --> M[Agent Spoken Response Formulation]
    I --> M
    J --> M
    K --> M
    L --> M
    M --> N[Voice Platform TTS (ElevenLabs / Azure Voice)]
    N --> O[Customer Audio Output]
```

---

## 3. Technology Stack

| Layer | Component | Description |
|---|---|---|
| **Language** | Python 3.11+ (Runtime: 3.12.6) | Core programming language for all logic and services |
| **LLM Provider** | Google Gemini API | Official `google-genai` SDK (`from google import genai`) with `gemini-2.5-flash` |
| **Data Validation** | Pydantic v2 & Pydantic-Settings | Strict typing, enum definition, and runtime data validation |
| **Business Logic** | `EligibilityEngine` | Deterministic Python rule enforcement, currency and tenure normalization |
| **Conversation Orchestration** | `ConversationEngine` & `InformationExtractor` | Multi-turn state transitions, out-of-order handling, interruptions |
| **Voice Platform Adapters** | `RetellAIAdapter`, `BolnaAdapter`, `LocalSimulatorAdapter` | Provider abstraction layer for telephony, transcripts, and webhooks |
| **API Server** | FastAPI & Uvicorn | Webhook receiver and orchestration endpoints |
| **Testing Suite** | Pytest 9.1.1 | 61 automated unit, state, flow, and edge case tests |

---

## 4. The Seven Eligibility Business Rules

All business rules are evaluated deterministically in `app/eligibility_engine.py`:

| # | Item | Accepted Values | Disqualifying Criteria | Gating / Special Handling |
|---|---|---|---|---|
| **1** | **Property Type** | Residential, Commercial, Industrial | Agricultural property / Farmland | Immediate disqualification |
| **2** | **Ownership Status** | Sole ownership, Joint ownership | None | Neither is a disqualifier |
| **3** | **Original Documents** | Available for physical verification | Confirmed lost / unavailable | Immediate disqualification (no need to hold on call) |
| **4** | **Loan Amount** | Up to ₹75,00,000 | > ₹75 Lakhs without cap acceptance | > ₹75L triggers alternative offer. Customer must explicitly accept ₹75L cap to proceed |
| **5** | **Occupation & Income Mode** | Salaried, Self-Employed with **Bank** credit | Income received in **Cash** | Cash income causes immediate disqualification. Fields captured separately |
| **6** | **Market Value** | Any positive estimated value (> 0) | None | No minimum property valuation threshold is enforced |
| **7** | **Repayment Tenure** | 3 through 15 years inclusive | < 3 years or > 15 years | Below 3 or above 15 causes immediate disqualification |

---

## 5. State Management & Lifecycle Stages

The call progresses through structured stages in `app/qualification_state.py`:

1. **`GREETING_VERIFICATION`**: Verifies that the recipient is the intended customer before disclosing financial benefits. If wrong person, exits politely.
2. **`AVAILABILITY_CHECK`**: Asks if customer has 2 minutes. If busy/driving, extracts preferred callback time and exits immediately without pitch.
3. **`OFFER_PRESENTATION`**: Explains pre-approved property loan benefit of up to ₹75 Lakhs as a *preliminary assessment* (never guarantees final approval).
4. **`TRANSFER_BRANCH`**: If customer has an existing mortgage and seeks balance transfer or EMI reduction, stops fresh loan flow and routes directly to Dedicated Loan Transfer Specialist.
5. **`ELIGIBILITY_CHECKLIST`**: Sequentially asks the earliest unanswered question among the 7 items.
6. **`LOAN_CAP_CONFIRMATION`**: If customer requests > ₹75 Lakhs, pauses checklist to ask for explicit consent to proceed with ₹75 Lakhs.
7. **`DISQUALIFIED`**: Triggered immediately upon confirmed failure of any eligibility rule. Terminal state.
8. **`QUALIFIED_HANDOFF`**: Triggered only when **all 7 checklist items are complete and eligible**. Authorizes handoff to Senior Loan Expert.
9. **`CALL_TERMINATED`**: Terminal status locked. No subsequent utterance can re-open or resume qualification.

---

## 6. Enterprise Edge Case Handling

- **Out-of-Order Extraction**: Customers often supply multiple facts in compound sentences (e.g., *"I need 40 lakhs for 10 years on my self-owned flat"*). The extractor captures all facts simultaneously; the engine skips already captured items and asks only missing criteria.
- **Customer Corrections**: If a customer changes their answer (*"Actually, it's agricultural farmland, not residential"*), the state manager immediately overwrites the field and re-evaluates the rules deterministically.
- **Product Interruptions & RAG Guardrails**: When customers ask *"What is the interest rate?"*, the agent explains that rates are competitive and that the exact rate will be customized by the Senior Loan Expert, then seamlessly bridges back to the active checklist question.
- **Terminal State Lock**: Once a call enters a terminal stage (`DISQUALIFIED`, `TRANSFER_BRANCH`, `QUALIFIED_HANDOFF`, `CALL_TERMINATED`), `terminal_status = True` locks the session, preventing any subsequent user utterance from resurrecting qualification.
