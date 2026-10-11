# Home Credit LAP Voice Agent - Testing Report

## 1. Executive Summary

This report documents the automated testing, verification, and regression analysis of the **Home Credit Loan Against Property (LAP) Qualification Voice Agent**.

- **Total Test Cases Executed**: 66
- **Passed**: 65
- **Skipped**: 1 (Optional live network Gemini integration test, skipped cleanly when `GEMINI_API_KEY` is not provided)
- **Failed**: 0
- **Test Framework**: Pytest 9.1.1 on Python 3.12.6 (Windows)
- **Deterministic Test Execution Time**: ~1.46 seconds

All business rules, state transitions, out-of-order fact extractions, corrections, interruptions, terminal-state protections, and REST/webhook API endpoints were tested and verified.

---

## 2. Test Suite Breakdown

| Test Module | Tests | Status | Scope |
|---|---|---|---|
| [`tests/test_api_server.py`](file:///c:/Users/mones/Desktop/Voice%20AI/tests/test_api_server.py) | 4 | **PASSED** | FastAPI endpoints (Health check probe, `/api/simulate-turn`, Retell AI webhook, Bolna webhook) |
| [`tests/test_eligibility.py`](file:///c:/Users/mones/Desktop/Voice%20AI/tests/test_eligibility.py) | 21 | **PASSED** | Deterministic business rules (Property types, ownership, documents, loan amount caps, income modes, market value, tenure boundaries) and normalization |
| [`tests/test_state_management.py`](file:///c:/Users/mones/Desktop/Voice%20AI/tests/test_state_management.py) | 5 | **PASSED** | Compound utterances, out-of-order extraction, customer corrections, UNKNOWN field gating, terminal lockdown |
| [`tests/test_conversation_flows.py`](file:///c:/Users/mones/Desktop/Voice%20AI/tests/test_conversation_flows.py) | 9 | **PASSED** | End-to-end multi-turn dialogs (Eligible customer, Agricultural exit, Cash exit, Loan cap accept/reject, Balance transfer, Busy reschedule, Wrong person, Refusal) |
| [`tests/test_edge_cases.py`](file:///c:/Users/mones/Desktop/Voice%20AI/tests/test_edge_cases.py) | 26 | **PASSED** | All 25 required edge cases from project requirements plus numeric boundary tests (₹75L, 3y, 15y, 2y, 20y) |
| [`tests/test_gemini_integration.py`](file:///c:/Users/mones/Desktop/Voice%20AI/tests/test_gemini_integration.py) | 1 | **SKIPPED** (Optional) | Live Google Gemini API call via `google-genai` SDK (executes automatically when `GEMINI_API_KEY` is supplied) |

---

## 3. Detailed Results Matrix (All 25 Required Cases)

| Case # | Scenario Name | Customer Utterance Snippet | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|---|---|
| **1** | Fully Eligible Customer | 10-turn complete qualification conversation | Complete all 7 checklist items; authorize handoff | All 7 items captured; routed to `QUALIFIED_HANDOFF` | **PASS** |
| **2** | Agricultural Property | *"Dekho mere paas gaon mein 5 acre agricultural farmland hai"* | Immediate disqualification | State set to `DISQUALIFIED`, terminal lock enabled | **PASS** |
| **3** | Cash Income | *"I run a local shop and take all earnings in cash"* | Immediate disqualification | State set to `DISQUALIFIED`, cash income blocked | **PASS** |
| **4** | Missing Original Docs | *"Original documents are lost and unavailable, only photocopies"* | Immediate disqualification | State set to `DISQUALIFIED`, exit message triggered | **PASS** |
| **5** | Two-Year Tenure | *"I want to repay in just 2 years"* | Disqualify (< 3 years limit) | Rejected with tenure < 3y reason; call terminated | **PASS** |
| **6** | Twenty-Year Tenure | *"I want a long tenure of 20 years to keep EMI low"* | Disqualify (> 15 years limit) | Rejected with tenure > 15y reason; call terminated | **PASS** |
| **7** | ₹90L Request + ₹75L Accepted | *"I need 90 lakhs"*, then *"Yes, 75 lakhs works"* | Offer ₹75L cap; upon consent, proceed with ₹75L | Capped at ₹75,00,000; continued qualification flow | **PASS** |
| **8** | ₹90L Request + ₹75L Rejected | *"I need 90 lakhs"*, then *"No, 75L is too less. Cancel"* | Offer ₹75L cap; upon refusal, terminate politely | Disqualified for exceeding cap; call terminated | **PASS** |
| **9** | Joint Ownership | *"Jointly owned with my wife"* | Accepted; not a disqualifier | Recorded as `JOINT`; continues to next question | **PASS** |
| **10** | Existing Loan Balance Transfer | *"I already have a property loan and want to transfer"* | Stop fresh loan flow; route to Transfer Specialist | `is_transfer_lead=True`, stage `TRANSFER_BRANCH` | **PASS** |
| **11** | EMI-Reduction Request | *"I want to reduce my EMI on my current bank loan"* | Stop fresh loan flow; route to Transfer Specialist | `is_transfer_lead=True`, stage `TRANSFER_BRANCH` | **PASS** |
| **12** | Busy Customer Reschedule | *"I am driving right now. Call me tomorrow at 3 pm"* | Capture callback time; end call without pitch | `callback_time` saved; terminated politely | **PASS** |
| **13** | Out-of-Order Answers | Tenure & amount provided before property type | Extract both; ask missing property type | Tenure & amount saved; asks property type next | **PASS** |
| **14** | Multiple Facts in One Turn | *"I want 40L for 5 years on my residential flat, salaried"* | Extract all 4 parameters simultaneously | 4 fields populated; asks only remaining 3 fields | **PASS** |
| **15** | Contradictory Correction | Residential flat corrected to agricultural land | Overwrite with latest fact; trigger rule failure | Overwritten to `AGRICULTURAL`; disqualified | **PASS** |
| **16** | Ambiguous Documents | Ambiguous answer where document status is `UNKNOWN` | Do not mark complete; keep in checklist | Checklist incomplete; blocks handoff | **PASS** |
| **17** | Missing Market Value | All 6 items complete except property market value | Block handoff until market value is captured | `is_checklist_complete()=False`; handoff blocked | **PASS** |
| **18** | Missing Occupation/Income | Checklist complete except occupation/income mode | Block handoff until occupation & mode captured | Blocked; asks occupation & income mode | **PASS** |
| **19** | Interest Rate Interruption | *"Before proceeding, what is your interest rate?"* | Answer indicative rate advisory, resume flow | Informs about competitive rates, asks next question | **PASS** |
| **20** | Customer Refusal | *"Not interested, please disconnect"* | Respect customer wish; exit politely | `offer_accepted=False`; call terminated | **PASS** |
| **21** | Wrong Person | *"Wrong number, wrong person"* | Apologize and terminate call immediately | `identity_verified=False`; call terminated | **PASS** |
| **22** | Transfer Intent Midway | Transfer intent mentioned during property questions | Immediately halt fresh loan checklist; route | Flow halted; routed to Loan Transfer Specialist | **PASS** |
| **23** | Disqualification Out-of-Order | Disqualifying tenure (1 year) mentioned at start | Immediately halt conversation and disqualify | Disqualified immediately; no further questions | **PASS** |
| **24** | Incomplete Checklist Gate | Any single required field is `None` or `UNKNOWN` | Strictly deny `QUALIFIED_HANDOFF` | Gating blocks handoff for every individual field | **PASS** |
| **25** | Terminal State Protection | Additional utterances sent after terminal status | Never re-open or resume conversation | State locked; refuses mutation after terminal | **PASS** |

---

## 4. Boundary Analysis

- **Amount Cap Boundary**:
  - `₹75,00,000` (Exact Upper Bound): **PASSED** directly without cap confirmation requirement.
  - `₹75,00,001` (Above Cap): **PASSED** by triggering `LOAN_CAP_CONFIRMATION` flow.
- **Tenure Boundaries**:
  - `3 years` (Lower Bound): **PASSED**.
  - `15 years` (Upper Bound): **PASSED**.
  - `2 years` (Below Bound): **DISQUALIFIED** immediately.
  - `16 years` (Above Bound): **DISQUALIFIED** immediately.
- **Market Valuation**:
  - Confirmed no arbitrary minimum cutoff is enforced; all positive values (e.g. ₹5 Lakhs, ₹50 Lakhs, ₹2 Crores) pass.

---

## 5. Development Issues Found & Resolved

1. **Stage Progression Stalling**: Early prototypes failed to advance stages from `GREETING_VERIFICATION` to `AVAILABILITY_CHECK` and `OFFER_PRESENTATION` upon affirmation. Resolved by adding explicit deterministic stage progressions in `EligibilityEngine.evaluate_state`.
2. **Ambiguous Numeric Regex Collision**: Phrases like *"I am looking for 90 lakhs"* previously matched optional tenure patterns (`for 90`). Resolved by making time unit keywords (`years`, `months`, `saal`) strictly mandatory in tenure regexes.
3. **Loan Cap Rejection Overwrite**: When declining a 75L cap (*"No, 75 lakhs is too less"*), the presence of "75 lakhs" previously re-extracted as loan amount. Resolved by gating loan amount extraction during `LOAN_CAP_CONFIRMATION` stage and prioritizing refusal triggers.
4. **Flexible EMI Reduction Matching**: Phrases like *"reduce my EMI"* failed an exact substring match on *"reduce emi"*. Resolved by introducing word-boundary regex `\b(?:reduce|lower|kam)\s+(?:\w+\s+)?emi\b`.
5. **FastAPI / Starlette 1.x `max_body_size` Compatibility**: Requests to the FastAPI server raised `AttributeError: 'FastAPI' object has no attribute 'max_body_size'` due to a modern Starlette 1.7+ attribute expectation. Resolved by injecting `FastAPI.max_body_size = None` compatibility shim into `app/main.py` and establishing automated test coverage in `tests/test_api_server.py`.
