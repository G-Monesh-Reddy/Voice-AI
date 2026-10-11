"""Automated multi-turn conversation flow tests for Home Credit LAP Voice Agent."""

import pytest
from app.qualification_state import ConversationStage
from app.voice_platform import LocalSimulatorAdapter


class TestConversationFlows:
    """Verifies complete end-to-end multi-turn dialogue paths."""

    def test_flow_fully_eligible_salaried_customer(self):
        """Simulate complete 10-turn call leading to QUALIFIED_HANDOFF."""
        sim = LocalSimulatorAdapter(customer_name="Rahul Sharma", language="English")
        assert "Rahul Sharma" in sim.start_conversation()

        turns = [
            "Yes, speaking. How are you?",
            "Sure, I have two minutes to speak.",
            "Yes, I am interested in exploring this loan.",
            "It is a residential flat.",
            "Sole ownership, in my own name.",
            "Yes, original registry documents are available in my bank locker.",
            "I need around 50 lakhs.",
            "I am salaried in an MNC, income comes directly to my bank account.",
            "Current market value is about 90 lakhs.",
            "I want a tenure of 10 years.",
        ]

        for text in turns[:-1]:
            turn_res = sim.send_customer_utterance(text)
            assert turn_res["is_terminal"] is False

        # Final turn
        final_turn = sim.send_customer_utterance(turns[-1])
        assert final_turn["is_terminal"] is True
        assert final_turn["current_stage"] == ConversationStage.QUALIFIED_HANDOFF.value
        assert "Congratulations" in final_turn["agent_response"]
        assert sim.get_state().disqualification_status is False

    def test_flow_agricultural_disqualification(self):
        """Simulate call where customer mentions agricultural land."""
        sim = LocalSimulatorAdapter(customer_name="Suresh Patel", language="English")
        sim.start_conversation()

        sim.send_customer_utterance("Yes, speaking.")
        sim.send_customer_utterance("Yes, I have time.")
        sim.send_customer_utterance("Yes, tell me more.")

        # Mention agricultural property
        disq_turn = sim.send_customer_utterance("I have agricultural farmland.")
        assert disq_turn["is_terminal"] is True
        assert disq_turn["current_stage"] == ConversationStage.DISQUALIFIED.value
        assert disq_turn["disqualified"] is True
        assert "unable to proceed" in disq_turn["agent_response"]

    def test_flow_cash_income_disqualification(self):
        """Simulate call where customer receives income in cash."""
        sim = LocalSimulatorAdapter(customer_name="Vikram Singh", language="English")
        sim.start_conversation()

        sim.send_customer_utterance("Yes, speaking.")
        sim.send_customer_utterance("Yes, go ahead.")
        sim.send_customer_utterance("Yes, interested.")
        sim.send_customer_utterance("Commercial shop.")
        sim.send_customer_utterance("Sole owner.")
        sim.send_customer_utterance("Yes, original papers are there.")
        sim.send_customer_utterance("40 lakhs.")

        # Cash income utterance
        turn = sim.send_customer_utterance("I run a shop and take all my earnings in cash.")
        assert turn["is_terminal"] is True
        assert turn["current_stage"] == ConversationStage.DISQUALIFIED.value
        assert turn["disqualified"] is True

    def test_flow_loan_cap_accepted(self):
        """Customer asks for 90L, accepts 75L cap, and proceeds to qualify."""
        sim = LocalSimulatorAdapter(customer_name="Ananya Roy", language="English")
        sim.start_conversation()

        sim.send_customer_utterance("Yes speaking.")
        sim.send_customer_utterance("Yes, tell me.")
        sim.send_customer_utterance("Interested.")
        sim.send_customer_utterance("Residential house.")
        sim.send_customer_utterance("Joint with husband.")
        sim.send_customer_utterance("Yes, originals available.")

        # Request 90 Lakhs
        turn_90l = sim.send_customer_utterance("I am looking for 90 lakhs.")
        assert turn_90l["current_stage"] == ConversationStage.LOAN_CAP_CONFIRMATION.value
        assert "maximum loan amount we can offer is ₹75 Lakhs" in turn_90l["agent_response"]

        # Accept 75L cap
        turn_accept = sim.send_customer_utterance("Yes, 75 lakhs works. Proceed with 75 lakhs.")
        assert turn_accept["current_stage"] == ConversationStage.ELIGIBILITY_CHECKLIST.value

        # Complete remaining checklist items
        sim.send_customer_utterance("Self-employed doctor, fees credited to bank account.")
        sim.send_customer_utterance("Market value is 1.5 crore.")
        final_turn = sim.send_customer_utterance("8 years repayment tenure.")

        assert final_turn["current_stage"] == ConversationStage.QUALIFIED_HANDOFF.value
        assert final_turn["is_terminal"] is True

    def test_flow_loan_cap_rejected(self):
        """Customer asks for 90L, rejects 75L cap, leading to exit."""
        sim = LocalSimulatorAdapter(customer_name="Rajiv Khanna", language="English")
        sim.start_conversation()

        sim.send_customer_utterance("Yes speaking.")
        sim.send_customer_utterance("Sure.")
        sim.send_customer_utterance("Interested.")
        sim.send_customer_utterance("Commercial office.")
        sim.send_customer_utterance("Sole owner.")
        sim.send_customer_utterance("Yes, documents available.")

        # Request 90 Lakhs
        sim.send_customer_utterance("I need 90 lakhs.")

        # Decline 75L cap
        decline_turn = sim.send_customer_utterance("No, 75 lakhs is too less. Please cancel.")
        assert decline_turn["is_terminal"] is True
        assert decline_turn["current_stage"] == ConversationStage.DISQUALIFIED.value
        assert "unable to proceed" in decline_turn["agent_response"]

    def test_flow_balance_transfer_branch(self):
        """Customer mentions existing loan and balance transfer / EMI reduction."""
        sim = LocalSimulatorAdapter(customer_name="Amit Saxena", language="English")
        sim.start_conversation()

        sim.send_customer_utterance("Yes, speaking.")
        sim.send_customer_utterance("Sure, go ahead.")

        # Transfer intent
        transfer_turn = sim.send_customer_utterance("I already have a property loan and want to reduce my EMI by transfer.")
        assert transfer_turn["is_terminal"] is True
        assert transfer_turn["current_stage"] == ConversationStage.TRANSFER_BRANCH.value
        assert transfer_turn["is_transfer_lead"] is True
        assert "Loan Transfer Specialist" in transfer_turn["agent_response"]

    def test_flow_busy_customer_reschedule(self):
        """Busy customer requests callback, terminating call politely without pitch."""
        sim = LocalSimulatorAdapter(customer_name="Neha Gupta", language="English")
        sim.start_conversation()

        sim.send_customer_utterance("Yes, Neha speaking.")
        busy_turn = sim.send_customer_utterance("I am driving right now. Call me tomorrow at 4 pm.")
        assert busy_turn["is_terminal"] is True
        assert "schedule a callback" in busy_turn["agent_response"]
        assert sim.get_state().callback_time is not None

    def test_flow_wrong_person(self):
        """Call answered by wrong person terminates immediately."""
        sim = LocalSimulatorAdapter(customer_name="Arun Kumar", language="English")
        sim.start_conversation()

        turn = sim.send_customer_utterance("Wrong number, Arun is not here.")
        assert turn["is_terminal"] is True
        assert "wrong number" in turn["agent_response"]

    def test_flow_customer_not_interested(self):
        """Customer not interested terminates call politely."""
        sim = LocalSimulatorAdapter(customer_name="Deepak", language="English")
        sim.start_conversation()

        sim.send_customer_utterance("Yes, speaking.")
        sim.send_customer_utterance("Yes, I have two minutes.")
        turn = sim.send_customer_utterance("No, I am not interested, don't call me.")
        assert turn["is_terminal"] is True
        assert "always here for you" in turn["agent_response"]
