import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
import boto3
from integration.fhir_mcp_client import FhirMcpClient

@pytest.mark.asyncio
async def test_local_fallback(monkeypatch, tmp_path):
    # Disable AWS branch
    monkeypatch.setenv('USE_HEALTHLAKE', 'false')
    # Provide fake local FHIRSearch behavior
    class FakeSearch:
        def __init__(self, db_path):
            pass
        def search_by_type(self, resource_type):
            return ['Local:' + resource_type]

    # Instantiate client with dummy DB path
    client = FhirMcpClient(db_path=str(tmp_path / 'db.sqlite'))
    # Swap in FakeSearch for local fallback
    client.search = FakeSearch('')

    result = await client.call_tool({'tool': 'search_by_type', 'parameters': {'resource_type': 'Patient'}})
    assert result == ['Local:Patient']

@pytest.mark.asyncio
async def test_aws_healthlake(monkeypatch):
    # Enable AWS REST branch
    monkeypatch.setenv('USE_HEALTHLAKE', 'true')
    monkeypatch.setenv('AWS_REGION', 'us-east-1')
    monkeypatch.setenv('HEALTHLAKE_ENDPOINT_URL', 'https://example.com/fhir')
    # Fake AWS credentials via boto3.Session
    class FakeCreds:
        def __init__(self):
            self.access_key = 'AK'
            self.secret_key = 'SK'
            self.token = None
        def get_frozen_credentials(self):
            return self
    class FakeSession:
        def __init__(self, region_name=None):
            pass
        def get_credentials(self):
            return FakeCreds()
    monkeypatch.setattr(boto3, 'Session', FakeSession)
    # Fake requests.get to simulate FHIR REST responses
    import requests
    def fake_get(url, auth, params=None):
        if params is None and url.endswith('/Observation'):
            payload = {'entry': [{'resource': {'type': 'Observation', 'id': '1', '_params': None}}]}
        elif params and '_text' in params:
            payload = {'entry': [{'resource': {'id': '2', '_params': params}}]}
        elif params and 'name:contains' in params:
            payload = {'entry': [{'resource': {'id': '3', '_params': params}}]}
        elif url.endswith('/Patient/123'):
            payload = {'resourceType': 'Patient', 'id': '123'}
        elif params and 'patient' in params:
            payload = {'entry': [{'resource': {'id': '4', '_params': params}}]}
        else:
            payload = {'entry': []}
        class R:
            def json(self_inner):
                return payload
        return R()
    monkeypatch.setattr(requests, 'get', fake_get)

    client = FhirMcpClient()
    # Test search_by_type
    out = await client.call_tool({'tool': 'search_by_type', 'parameters': {'resource_type': 'Observation'}})
    assert out == [{'type': 'Observation', 'id': '1', '_params': None}]
    # Test search_by_id
    out = await client.call_tool({'tool': 'search_by_id', 'parameters': {'resource_type': 'Patient', 'resource_id': '123'}})
    assert out == {'resourceType': 'Patient', 'id': '123'}
    # Test full-text search and clinical_query alias
    out = await client.call_tool({'tool': 'search_by_text', 'parameters': {'query': 'foo'}})
    assert out == [{'id': '2', '_params': {'_text': 'foo'}}]
    out = await client.call_tool({'tool': 'clinical_query', 'parameters': {'query': 'bar'}})
    assert out == [{'id': '2', '_params': {'_text': 'bar'}}]
    # Test find_patient
    out = await client.call_tool({'tool': 'find_patient', 'parameters': {'query': 'John'}})
    assert out == [{'id': '3', '_params': {'name:contains': 'John'}}]
    # Test patient-centric tools mapping
    mapping = {
        'get_patient_observations': 'Observation',
        'get_patient_conditions': 'Condition',
        'get_patient_medications': 'MedicationRequest',
    }
    for tool, _ in mapping.items():
        out = await client.call_tool({'tool': tool, 'parameters': {'patient_id': 'p1'}})
        assert out == [{'id': '4', '_params': {'patient': 'Patient/p1'}}]
