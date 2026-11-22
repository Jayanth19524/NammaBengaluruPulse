"""
Unit tests for MockAdapter and AgentContract validation.
"""
import sys, os, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from adapters.mock_adapter import MockAdapter
from contracts.agent_contract import AgentContract


def test_mock_adapter_returns_incidents_in_radius():
    adapter = MockAdapter()
    # Bengaluru city centre — should return all demo incidents within 50 km
    results = asyncio.run(adapter.fetch(12.9716, 77.5946, 50000))
    assert len(results) > 0

def test_mock_adapter_all_simulated():
    adapter = MockAdapter()
    results = asyncio.run(adapter.fetch(12.9716, 77.5946, 50000))
    for r in results:
        assert r.is_simulated is True

def test_mock_adapter_zero_results_outside_city():
    adapter = MockAdapter()
    # Far from Bengaluru (Mumbai coordinates, 50 m radius)
    results = asyncio.run(adapter.fetch(19.0760, 72.8777, 50))
    assert results == []

def test_contract_shape():
    from agent import WaterWatchAgent
    agent = WaterWatchAgent(use_mock=True)
    contracts = asyncio.run(agent.scan(12.9716, 77.5946, 50000))
    assert len(contracts) > 0
    for c in contracts:
        # Validate Pydantic model fields
        assert c.agent.value == "WaterWatch"
        assert c.incident_type in ("supply_disruption", "tanker_shortage", "sensor_anomaly", "demand_spike")
        assert 0.0 <= c.confidence <= 1.0
        assert c.is_simulated is True
        assert c.recommended_action.strip() != ""
        assert isinstance(c.evidence, list)
        assert isinstance(c.source, list)
