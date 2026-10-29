"""
Pytest integration test suite running all 30 scripted conversation scenarios.
"""

import json
import pytest
from scripts.run_conversation_tests import run_scenario


with open("scenarios/conversations.json", "r", encoding="utf-8") as f:
    scenarios = json.load(f)


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", scenarios, ids=[s["id"] for s in scenarios])
async def test_scripted_conversation(scenario):
    result = await run_scenario(scenario)
    assert result["passed"], (
        f"Scenario {scenario['id']} ({scenario['scenario']}) failed: "
        f"State: {result['actual_final_state']} (expected {result['expected_final_state']}), "
        f"Handoff: {result['actual_handoff']} (expected {result['expected_handoff']}), "
        f"Appointment: {result['actual_appt']} (expected {result['expected_appt']})"
    )
