"""Optional Live Gemini API Integration Test.

Executes actual network calls to Google Gemini API only when GEMINI_API_KEY is configured.
"""

import pytest
from app.config import settings
from app.gemini_client import GeminiClient
from app.qualification_state import ConversationStage


@pytest.mark.skipif(
    not settings.gemini_api_key or settings.gemini_api_key == "your_gemini_api_key_here",
    reason="GEMINI_API_KEY not configured. Skipping live network integration test.",
)
def test_live_gemini_extraction():
    """Live call to Google Gemini API verifying JSON fact extraction."""
    client = GeminiClient()
    assert client.is_available is True

    result = client.extract_facts_with_gemini(
        utterance="I want a loan of 50 lakhs for 10 years on my residential flat, I am salaried with bank income.",
        customer_name="Rahul Sharma",
        language="English",
        current_stage=ConversationStage.ELIGIBILITY_CHECKLIST.value,
    )

    assert result is not None
    assert result.get("loan_amount") in (5_000_000, 5000000, "5000000")
    assert result.get("property_type") == "residential"
    assert result.get("occupation") == "salaried"
    assert result.get("income_mode") == "bank"
