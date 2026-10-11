"""Voice Platform Adapter layer for Home Credit LAP Voice Agent.

Provides clean integration with Retell AI, Bolna, and local simulation
without contaminating core business logic.
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import requests

from app.config import settings
from app.qualification_state import QualificationState
from app.conversation_engine import ConversationEngine

logger = logging.getLogger(__name__)


class VoicePlatformAdapter(ABC):
    """Abstract interface for voice platform providers."""

    @abstractmethod
    def initiate_call(self, to_number: str, customer_name: str, dynamic_vars: Dict[str, Any]) -> Dict[str, Any]:
        """Initiate an outbound phone call."""
        pass

    @abstractmethod
    def get_transcript(self, call_id: str) -> Dict[str, Any]:
        """Fetch call transcript by call ID."""
        pass

    @abstractmethod
    def get_recording_url(self, call_id: str) -> Optional[str]:
        """Retrieve audio recording URL if supported."""
        pass

    @abstractmethod
    def handle_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming webhook event from voice platform."""
        pass


class RetellAIAdapter(VoicePlatformAdapter):
    """Adapter for Retell AI platform (https://www.retellai.com)."""

    BASE_URL = "https://api.retellai.com"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.retell_api_key

    def _get_headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise ValueError(
                "RETELL_API_KEY is not configured. Please set RETELL_API_KEY in your .env file or environment variables."
            )
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def initiate_call(self, to_number: str, customer_name: str, dynamic_vars: Dict[str, Any]) -> Dict[str, Any]:
        """Create outbound call using Retell AI v2 endpoint."""
        agent_id = settings.retell_agent_id
        if not agent_id:
            raise ValueError("RETELL_AGENT_ID is not configured in settings or environment.")

        url = f"{self.BASE_URL}/v2/create-phone-call"
        payload = {
            "to_number": to_number,
            "agent_id": agent_id,
            "retell_llm_dynamic_variables": {
                "customer_name": customer_name,
                "company_name": settings.company_name,
                **dynamic_vars,
            },
        }

        try:
            response = requests.post(url, json=payload, headers=self._get_headers(), timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Retell AI call initiation failed: {e}")
            return {"error": str(e), "status": "failed"}

    def get_transcript(self, call_id: str) -> Dict[str, Any]:
        """Retrieve transcript from Retell AI."""
        url = f"{self.BASE_URL}/v2/get-call/{call_id}"
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=15)
            response.raise_for_status()
            data = response.json()
            return {
                "call_id": call_id,
                "transcript": data.get("transcript"),
                "status": data.get("call_status"),
                "disconnection_reason": data.get("disconnection_reason"),
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Retell AI get_transcript failed: {e}")
            return {"error": str(e), "status": "failed"}

    def get_recording_url(self, call_id: str) -> Optional[str]:
        """Retrieve audio recording URL from Retell AI."""
        url = f"{self.BASE_URL}/v2/get-call/{call_id}"
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=15)
            response.raise_for_status()
            data = response.json()
            return data.get("recording_url")
        except requests.exceptions.RequestException as e:
            logger.error(f"Retell AI get_recording_url failed: {e}")
            return None

    def handle_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming Retell AI webhook event."""
        event_type = payload.get("event")
        call_id = payload.get("call", {}).get("call_id")
        logger.info(f"Retell AI webhook received: {event_type} for call {call_id}")
        return {
            "event": event_type,
            "call_id": call_id,
            "status": "processed",
        }


class BolnaAdapter(VoicePlatformAdapter):
    """Adapter for Bolna AI platform (https://www.bolna.dev)."""

    BASE_URL = "https://api.bolna.dev"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.bolna_api_key

    def _get_headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise ValueError(
                "BOLNA_API_KEY is not configured. Please set BOLNA_API_KEY in your .env file or environment variables."
            )
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def initiate_call(self, to_number: str, customer_name: str, dynamic_vars: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch call via Bolna /call API."""
        agent_id = settings.bolna_agent_id
        if not agent_id:
            raise ValueError("BOLNA_AGENT_ID is not configured in settings or environment.")

        url = f"{self.BASE_URL}/call"
        payload = {
            "agent_id": agent_id,
            "recipient_phone_number": to_number,
            "user_data": {
                "customer_name": customer_name,
                "company_name": settings.company_name,
                **dynamic_vars,
            },
        }

        try:
            response = requests.post(url, json=payload, headers=self._get_headers(), timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Bolna call initiation failed: {e}")
            return {"error": str(e), "status": "failed"}

    def get_transcript(self, call_id: str) -> Dict[str, Any]:
        """Fetch execution transcript from Bolna."""
        agent_id = settings.bolna_agent_id
        url = f"{self.BASE_URL}/agent/{agent_id}/execution/{call_id}"
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=15)
            response.raise_for_status()
            data = response.json()
            return {
                "call_id": call_id,
                "transcript": data.get("conversation_history"),
                "status": data.get("status"),
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Bolna get_transcript failed: {e}")
            return {"error": str(e), "status": "failed"}

    def get_recording_url(self, call_id: str) -> Optional[str]:
        """Fetch recording from Bolna execution."""
        data = self.get_transcript(call_id)
        return data.get("recording_url")

    def handle_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming Bolna webhook."""
        execution_id = payload.get("execution_id")
        status = payload.get("status")
        return {"execution_id": execution_id, "status": status}


class LocalSimulatorAdapter:
    """High-fidelity local simulation adapter for CLI testing and inspection.
    
    Provides complete visibility into extracted facts, intermediate state,
    and deterministic rule evaluations.
    """

    def __init__(self, customer_name: str = "Rahul Sharma", language: str = "English"):
        self.state = QualificationState(
            customer_name=customer_name,
            agent_name=settings.default_agent_name,
            language=language,
        )
        self.engine = ConversationEngine(state=self.state)

    def start_conversation(self) -> str:
        """Begin simulated call and return opening greeting."""
        return self.engine.get_greeting()

    def send_customer_utterance(self, text: str) -> Dict[str, Any]:
        """Process one customer utterance and return full turn inspection."""
        return self.engine.process_utterance(text)

    def get_state(self) -> QualificationState:
        """Return current qualification state."""
        return self.engine.state
