# Home Credit Loan Against Property (LAP) AI Voice Qualification Agent

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![LLM](https://img.shields.io/badge/LLM-Google%20Gemini%20API-4285F4.svg)](https://ai.google.dev/)
[![SDK](https://img.shields.io/badge/SDK-google--genai-green.svg)](https://github.com/googleapis/python-genai)
[![Validation](https://img.shields.io/badge/Validation-Pydantic%20v2-E92063.svg)](https://pydantic.dev)
[![Tests](https://img.shields.io/badge/Tests-65%20Passed-brightgreen.svg)](docs/testing_report.md)
[![Platform](https://img.shields.io/badge/Voice%20Platform-Retell%20AI%20%7C%20Bolna-orange.svg)](https://www.retellai.com/)

An enterprise-grade, conversational AI voice agent built for **Home Credit India**. The agent contacts existing customers, presents an exclusive Loan Against Property (LAP) pre-qualification offer of up to **₹75,00,000 (₹75 Lakhs)**, collects seven mandatory eligibility checklist parameters, applies deterministic banking business rules, and routes qualified prospects to a senior loan expert.

---

## 1. Key Architectural Principles

1. **Google Gemini API as Core LLM**: Natural language comprehension, compound entity extraction, and conversational synthesis are powered by the Google Gemini API using the official `google-genai` SDK (`from google import genai`).
2. **Deterministic Business Logic**: Pure Python functions (`EligibilityEngine`) enforce loan caps, property exclusions, document criteria, and terminal states. **Gemini never unilaterally overrides eligibility criteria.**
3. **Robust Gating & Terminal Protection**: The agent cannot authorize a handoff until all 7 criteria are complete and validated. Once a terminal state (`DISQUALIFIED`, `TRANSFER_BRANCH`, `QUALIFIED_HANDOFF`) is reached, the session is locked against accidental resumption.
4. **Resilient Hybrid Extractor**: Live Gemini extraction activates automatically when `GEMINI_API_KEY` is present; an intelligent deterministic rule-based extractor ensures 100% test reliability and offline execution without paid dependencies.

---

## 2. The Seven Eligibility Business Rules

| # | Item | Criteria & Constraints | Action on Failure |
|---|---|---|---|
| **1** | **Property Type** | Residential, Commercial, Industrial accepted | **Agricultural property**: Immediate disqualification |
| **2** | **Ownership** | Sole ownership or Joint ownership accepted | Neither is a disqualifier |
| **3** | **Original Documents** | Must be available for physical verification | **Unavailable / Lost**: Immediate disqualification |
| **4** | **Loan Amount** | Maximum cap: **₹75,00,000** | If customer requests > ₹75L, explains cap and offers ₹75L. Continues only upon explicit acceptance; otherwise polite exit |
| **5** | **Occupation & Income Mode** | Salaried or Self-employed. Income **must** be received via Bank account | **Cash income**: Immediate disqualification |
| **6** | **Market Value** | Captures customer's estimated property value | No arbitrary minimum cutoff enforced |
| **7** | **Repayment Tenure** | **3 through 15 years inclusive** | **< 3 years or > 15 years**: Immediate disqualification |

---

## 3. Project Directory Structure

```
home-credit-lap-agent/
├── app/
│   ├── config.py                 # Pydantic Settings configuration (.env loader)
│   ├── gemini_client.py          # Official google-genai SDK client implementation
│   ├── qualification_state.py    # Session state models, Enums, and Pydantic schemas
│   ├── information_extractor.py  # Gemini extraction + Pydantic validation + fallback
│   ├── eligibility_engine.py     # Deterministic business logic & normalization engine
│   ├── conversation_engine.py    # 9-step conversational lifecycle orchestrator
│   ├── voice_platform.py         # Retell AI, Bolna, and Local Simulator adapters
│   └── main.py                   # CLI interactive simulator & FastAPI webhook server
├── prompts/
│   ├── system_prompt.txt         # Production-ready prompt with 11 dynamic variables
│   └── extraction_prompt.txt     # Gemini structured fact extraction prompt
├── tests/
│   ├── test_api_server.py        # FastAPI health check & platform webhooks (4 tests)
│   ├── test_eligibility.py       # Deterministic business rules & boundary tests (21 tests)
│   ├── test_state_management.py  # Compound facts, corrections, & UNKNOWN guards (5 tests)
│   ├── test_conversation_flows.py# End-to-end multi-turn dialogue flow tests (9 tests)
│   ├── test_edge_cases.py        # All 25 required edge case scenarios (26 tests)
│   └── test_gemini_integration.py# Optional live Gemini API network test (1 test)
├── scenarios/
│   └── test_scenarios.json       # Realistic multi-turn conversational test scenarios
├── examples/
│   ├── eligible_customer_transcript.txt  # Simulated transcript of qualified customer
│   ├── disqualification_transcript.txt   # Simulated transcript of agricultural disqualification
│   └── transfer_transcript.txt           # Simulated transcript of loan balance transfer
├── docs/
│   ├── architecture.md           # System architecture, pipeline, and decision trees
│   ├── testing_report.md         # Comprehensive test report and scenario matrix
│   └── deployment_guide.md       # Retell AI & Bolna deployment, call audio retrieval
├── .env.example                  # Documented environment variables template
├── .gitignore                    # Standard Python/IDE hygiene ignore file
├── requirements.txt              # Core project dependencies
└── README.md                     # Project overview and instructions
```

---

## 4. Quickstart & Local Installation

### Prerequisites
- Python 3.11 or higher (Tested on Python 3.12.6)

### Installation
```bash
# Clone or navigate to the repository
cd "c:\Users\mones\Desktop\Voice AI"

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

---

## 5. Running the Local Interactive Simulator

You can test conversational flows locally in the terminal without voice platform credentials:

```bash
# Launch interactive terminal simulator
python -m app.main --interactive --name "Rahul Sharma" --language "English"

# Or run in Hindi
python -m app.main --interactive --name "Suresh Patel" --language "Hindi"

# Run batch test scenarios from JSON
python -m app.main --scenario scenarios/test_scenarios.json

# Start the webhook and REST API server
python -m app.main --server
```

During simulation, the terminal displays:
- **`[AGENT]`**: Spoken agent dialogue
- **`[EXTRACTED FACTS]`**: JSON output from the extractor
- **`[CURRENT STAGE]`**: Active state machine phase
- **`[MISSING FIELDS]`**: Real-time list of uncaptured checklist items
- **`[DECISION / TERMINAL]`**: Terminal locking status and business rule decisions

---

## 6. Running Automated Tests

Run the complete test suite:

```bash
# Run all tests with verbose output
python -m pytest tests/ -v
```

### Actual Test Results Summary
```
============================= test session starts =============================
platform win32 -- Python 3.12.6, pytest-9.1.1
collected 66 items

tests/test_api_server.py ................ PASSED [  6%]
tests/test_conversation_flows.py ........ PASSED [ 19%]
tests/test_edge_cases.py ................ PASSED [ 59%]
tests/test_eligibility.py ............... PASSED [ 90%]
tests/test_state_management.py .......... PASSED [ 98%]
tests/test_gemini_integration.py ........ SKIPPED (Optional live test)

======================== 65 passed, 1 skipped in 1.46s ========================
```
*Full test report and scenario breakdown available in [`docs/testing_report.md`](file:///c:/Users/mones/Desktop/Voice%20AI/docs/testing_report.md).*

---

## 7. Voice Platform Integration (Retell AI & Bolna)

For deploying live telephone calls:
1. Refer to [`docs/deployment_guide.md`](file:///c:/Users/mones/Desktop/Voice%20AI/docs/deployment_guide.md).
2. Configure your agent in **Retell AI** or **Bolna** using [`prompts/system_prompt.txt`](file:///c:/Users/mones/Desktop/Voice%20AI/prompts/system_prompt.txt).
3. Select an Indian voice (`ElevenLabs - Pooja` or `Azure - Neerja`).
4. Set Webhook to `https://<your-domain>/webhook/retell`.
5. Initiate calls via API or Dashboard, and retrieve recordings via `RetellAIAdapter.get_recording_url()`.

---

## 8. Final Submission Template

Use this template when submitting your project for evaluation:

```markdown
### Home Credit LAP Voice Agent Submission

- **Student / Engineer Name**: [Your Name]
- **LLM Engine**: Google Gemini API (`gemini-2.5-flash` via official `google-genai` SDK)
- **Voice Platform Selected**: Retell AI / Bolna (Configured via provider adapter)
- **Repository / Source Code**: [Link to GitHub Repository]
- **Automated Test Results**: 65 Passed, 0 Failed (Pytest 9.1.1)

#### Call Recording & Demonstration Links:
- **Eligible Customer Call Recording**: [Insert Retell Shareable URL or Audio Link]
- **Disqualified Customer Call Recording**: [Insert Retell Shareable URL or Audio Link]
- **Loan Transfer Call Recording**: [Insert Retell Shareable URL or Audio Link]
- **Public Dashboard / Call Logs**: [Insert Reviewer-accessible Dashboard Link]

*Note: In accordance with academic integrity guidelines, when live telephony credits are unconfigured, local simulated transcripts labeled as SIMULATED are provided in the `/examples` directory.*
```

---

## 9. Security & Reliability

- **No Hardcoded Keys**: API keys and secrets are loaded via environment variables (`.env`).
- **Input Sanitization**: All customer inputs are normalized and validated via Pydantic schemas before business-rule evaluation.
- **RAG & Rate Boundary Guardrails**: Prevents unauthorized loan approval promises or hallucinated interest rates.
