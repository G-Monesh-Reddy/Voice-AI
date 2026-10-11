"""Main entrypoint for Home Credit LAP Voice Agent.

Provides CLI simulation modes and a FastAPI webhook server for live platform integration.
"""

import sys
import json
import argparse
import logging
from typing import Dict, Any, Optional

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure backward compatibility between FastAPI and Starlette
from starlette.routing import Router
_orig_router_init = Router.__init__
def _safe_router_init(self, *args, **kwargs):
    kwargs.pop("on_startup", None)
    kwargs.pop("on_shutdown", None)
    return _orig_router_init(self, *args, **kwargs)
Router.__init__ = _safe_router_init

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

# Patch FastAPI for compatibility with modern Starlette versions
if not hasattr(FastAPI, "max_body_size"):
    FastAPI.max_body_size = None

from app.config import settings
from app.qualification_state import QualificationState
from app.conversation_engine import ConversationEngine
from app.voice_platform import LocalSimulatorAdapter, RetellAIAdapter, BolnaAdapter

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("home_credit_voice_agent")

app = FastAPI(
    title="Home Credit LAP Voice Qualification API",
    description="Webhook and orchestration service for AI Voice Qualification Agent",
    version="1.0.0",
)
app.max_body_size = None


@app.get("/")
def health_check():
    """Service health and capability probe."""
    return {
        "status": "healthy",
        "service": "Home Credit LAP Voice Agent",
        "version": "1.0.0",
        "company": settings.company_name,
        "max_loan_cap": settings.max_loan_amount,
        "tenure_bounds": f"{settings.min_tenure_years}-{settings.max_tenure_years} years",
    }


@app.post("/api/simulate-turn")
async def simulate_turn(request: Request):
    """Process a single turn via REST API for web-based testing."""
    body = await request.json()
    utterance = body.get("utterance", "")
    state_dict = body.get("state")

    state = QualificationState(**state_dict) if state_dict else QualificationState()
    engine = ConversationEngine(state=state)
    result = engine.process_utterance(utterance)
    return result


@app.post("/webhook/retell")
async def retell_webhook(request: Request):
    """Handle incoming webhook events from Retell AI."""
    payload = await request.json()
    adapter = RetellAIAdapter()
    result = adapter.handle_webhook_event(payload)
    return JSONResponse(content=result)


@app.post("/webhook/bolna")
async def bolna_webhook(request: Request):
    """Handle incoming webhook events from Bolna."""
    payload = await request.json()
    adapter = BolnaAdapter()
    result = adapter.handle_webhook_event(payload)
    return JSONResponse(content=result)


# -----------------------------------------------------------------------------
# CLI INTERACTIVE SIMULATOR
# -----------------------------------------------------------------------------

def run_interactive_simulator(customer_name: str = "Rahul Sharma", language: str = "English"):
    """Run an interactive turn-by-turn conversation in the terminal."""
    print("=" * 75)
    print("HOME CREDIT LAP VOICE AGENT - LOCAL INTERACTIVE SIMULATOR")
    print(f"Customer: {customer_name} | Language: {language}")
    print("Type your responses below. Type 'exit' or 'quit' to end early.")
    print("=" * 75)

    sim = LocalSimulatorAdapter(customer_name=customer_name, language=language)
    greeting = sim.start_conversation()
    print(f"\n[AGENT ({settings.default_agent_name})]: {greeting}")

    while not sim.get_state().terminal_status:
        try:
            user_input = input(f"\n[{customer_name}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting simulation.")
            break

        if not user_input or user_input.lower() in ("exit", "quit"):
            print("Simulation ended by user.")
            break

        turn = sim.send_customer_utterance(user_input)

        print("-" * 75)
        print(f"[EXTRACTED FACTS]: {json.dumps(turn['extracted_facts'], indent=2)}")
        print(f"[CURRENT STAGE]: {turn['current_stage'].upper()}")
        print(f"[MISSING FIELDS]: {turn['missing_fields']}")
        print(f"[DECISION / TERMINAL]: {'TERMINAL' if turn['is_terminal'] else 'ACTIVE'}")
        if turn['disqualified']:
            print(f"[DISQUALIFIED REASON]: {turn['disqualification_reason']}")
        if turn['is_transfer_lead']:
            print(f"[TRANSFER BRANCH]: Routed to Loan Transfer Specialist")
        print(f"\n[AGENT ({settings.default_agent_name})]: {turn['agent_response']}")
        print("-" * 75)

    print("\n" + "=" * 75)
    print("FINAL CONVERSATION SUMMARY:")
    print(json.dumps(sim.get_state().to_readable_summary(), indent=2))
    print("=" * 75)


def run_scenario_file(filepath: str):
    """Execute a batch scenario test from a JSON file and print results."""
    print(f"Loading test scenarios from: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    scenarios = data.get("scenarios", [])
    print(f"Found {len(scenarios)} scenarios to execute.\n")

    for i, scen in enumerate(scenarios, 1):
        name = scen.get("name", f"Scenario {i}")
        description = scen.get("description", "")
        customer_name = scen.get("customer_name", "Rahul Sharma")
        language = scen.get("language", "English")
        utterances = scen.get("customer_utterances", [])

        print("*" * 75)
        print(f"SCENARIO {i}: {name}")
        print(f"Goal: {description}")
        print("*" * 75)

        sim = LocalSimulatorAdapter(customer_name=customer_name, language=language)
        print(f"[AGENT]: {sim.start_conversation()}")

        for text in utterances:
            print(f"\n[CUSTOMER]: {text}")
            turn = sim.send_customer_utterance(text)
            print(f"[AGENT]: {turn['agent_response']}")
            print(f"  -> Stage: {turn['current_stage']} | Terminal: {turn['is_terminal']}")
            if turn['is_terminal']:
                break

        final_summary = sim.get_state().to_readable_summary()
        print("\nFINAL STATE:")
        print(json.dumps(final_summary, indent=2))
        print("\n")


def main():
    """Main CLI argument dispatcher."""
    parser = argparse.ArgumentParser(description="Home Credit LAP Voice Agent Orchestrator")
    parser.add_argument("--interactive", "-i", action="store_true", help="Launch interactive CLI simulation")
    parser.add_argument("--scenario", "-s", type=str, help="Path to scenario JSON file")
    parser.add_argument("--server", action="store_true", help="Run FastAPI webhook server")
    parser.add_argument("--name", type=str, default="Rahul Sharma", help="Customer name for simulation")
    parser.add_argument("--language", type=str, default="English", help="Conversation language (English/Hindi)")

    args = parser.parse_args()

    if args.server:
        print(f"Starting server on {settings.host}:{settings.port}...")
        uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
    elif args.scenario:
        run_scenario_file(args.scenario)
    else:
        # Default to interactive simulation if invoked without args
        run_interactive_simulator(customer_name=args.name, language=args.language)


if __name__ == "__main__":
    main()
