import asyncio
import pytest

from types import SimpleNamespace

from integration.mimic_fhir_mcp_client import MimicFhirMcpClient

@pytest.mark.asyncio
async def test_differential_diagnosis(monkeypatch):
    """Ensure differential_diagnosis tool routes to Bedrock helper and returns string."""

    # Fake generator
    def fake_generate(symptoms: str, patient_summary: str, **kwargs):  # noqa: D401
        assert "cough" in symptoms
        return "1. Pneumonia — Because of cough and fever\n2. Common cold — Viral infection"

    monkeypatch.setattr(
        "integration.differential_diagnosis.generate_differential_diagnosis",
        fake_generate,
    )

    client = MimicFhirMcpClient()

    # Stub patient object with get_voice_summary
    async def fake_get_patient_object(pid):  # noqa: D401
        return SimpleNamespace(get_voice_summary=lambda: "42-year-old male, no PMH")

    monkeypatch.setattr(client, "get_patient_object", fake_get_patient_object)

    out = await client.call_tool(
        {
            "tool": "differential_diagnosis",
            "parameters": {"patient_id": "p1", "symptoms": "cough"},
        }
    )

    assert "Pneumonia" in out["result"]
