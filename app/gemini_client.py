"""Official Google Gemini API Client for Home Credit LAP Voice Agent.

Uses the official `google-genai` SDK (`from google import genai`) with structured JSON
extraction, robust error handling, and mockability for automated tests.
"""

import json
import logging
from typing import Dict, Any, Optional

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)


class GeminiClient:
    """Encapsulates interaction with Google Gemini API via official google-genai SDK."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_model
        self._client: Optional[genai.Client] = None

        if self.api_key and self.api_key.strip() and self.api_key != "your_gemini_api_key_here":
            try:
                self._client = genai.Client(api_key=self.api_key)
                logger.info(f"Initialized Google GenAI Client with model: {self.model}")
            except Exception as e:
                logger.warning(f"Failed to initialize Google GenAI Client: {e}")
                self._client = None
        else:
            logger.info("No GEMINI_API_KEY provided; operating in local deterministic fallback mode.")

    @property
    def is_available(self) -> bool:
        """Check if live Gemini API client is initialized."""
        return self._client is not None

    def extract_facts_with_gemini(
        self,
        utterance: str,
        customer_name: str,
        language: str,
        current_stage: str,
        last_question: Optional[str] = None,
        extraction_prompt_template: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Call Gemini API using structured JSON output to extract eligibility facts.
        
        Returns parsed dictionary or None if unavailable or on error.
        """
        if not self.is_available:
            return None

        prompt_text = (
            f"Customer Name: {customer_name}\n"
            f"Language: {language}\n"
            f"Current Stage: {current_stage}\n"
            f"Last Question Asked: {last_question or 'None'}\n"
            f"Customer Utterance: \"{utterance}\"\n\n"
            "Extract structured facts according to the schema in valid JSON format only."
        )

        system_instruction = (
            "You are an expert NLP extraction engine for Home Credit India's Loan Against Property qualification system. "
            "Extract customer facts accurately into valid JSON. Do not invent details. Output pure JSON without markdown fences."
        )

        try:
            config = types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                system_instruction=system_instruction,
            )

            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt_text,
                config=config,
            )

            if not response or not response.text:
                logger.warning("Empty response received from Gemini API.")
                return None

            raw_text = response.text.strip()
            # Clean possible markdown wrapping if returned
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            parsed_data = json.loads(raw_text.strip())
            logger.debug(f"Gemini successfully extracted facts: {parsed_data}")
            return parsed_data

        except json.JSONDecodeError as jde:
            logger.error(f"Failed to parse JSON from Gemini response: {jde}")
            return None
        except Exception as e:
            logger.error(f"Error calling Gemini API for fact extraction: {e}")
            return None

    def generate_response_with_gemini(
        self,
        system_prompt: str,
        customer_utterance: str,
        conversation_history_text: str,
    ) -> Optional[str]:
        """Generate a natural conversational response using Gemini."""
        if not self.is_available:
            return None

        user_content = (
            f"Conversation History:\n{conversation_history_text}\n\n"
            f"Customer Utterance: \"{customer_utterance}\"\n\n"
            "Generate your natural, concise response (1-3 sentences) adhering strictly to your persona and guidelines."
        )

        try:
            config = types.GenerateContentConfig(
                temperature=0.3,
                system_instruction=system_prompt,
            )

            response = self._client.models.generate_content(
                model=self.model,
                contents=user_content,
                config=config,
            )

            if response and response.text:
                return response.text.strip()
            return None

        except Exception as e:
            logger.error(f"Error calling Gemini API for response generation: {e}")
            return None
