import json
import os
import sys
import boto3
import asyncio
from typing import Any, Dict, List
import logging
import requests
from requests_aws4auth import AWS4Auth

# Ensure the fhir directory is on the Python path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'fhir')))

from fhir_search import FHIRSearch

logger = logging.getLogger(__name__)

class FhirMcpClient:
    """
    Adapter to expose FHIRSearch methods as MCP-style tools.
    """
    def __init__(self, db_path: str = None):
        """Initialize the FHIR search store or AWS HealthLake Data API client."""
        if db_path is None:
            db_path = os.getenv("FHIR_DB_PATH", "fhir_data.db")
        # REST-based FHIR client via AWS4Auth
        self.aws_enabled = os.getenv('USE_HEALTHLAKE', 'false').lower() == 'true'
        if self.aws_enabled:
            endpoint = os.getenv('HEALTHLAKE_ENDPOINT_URL')
            if not endpoint:
                raise ValueError('HEALTHLAKE_ENDPOINT_URL is required when USE_HEALTHLAKE=true')
            self.rest_endpoint = endpoint.rstrip('/')
            region = os.getenv('AWS_REGION')
            session = boto3.Session(region_name=region)
            creds = session.get_credentials().get_frozen_credentials()
            self.auth = AWS4Auth(
                creds.access_key,
                creds.secret_key,
                region,
                'healthlake',
                session_token=creds.token,
            )
        else:
            self.rest_endpoint = None
            self.search = FHIRSearch(db_path=db_path)

    async def connect_to_server(self) -> None:
        """No-op initialization for FHIR client."""
        return

    async def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """
        Return a list of tool definitions for FHIRSearch methods.
        """
        tools: List[Dict[str, Any]] = []

        method_specs = [
            ("search_by_type", "Search for resources by FHIR resource type", ["resource_type"]),
            ("search_by_id", "Search for a resource by its ID", ["resource_id"]),
            ("search_by_text", "Search for resources containing specific text", ["query"]),
            ("find_patient", "Search patients by name, DOB, or identifier", ["query"]),
            ("get_patient_observations", "Retrieve observations/vitals for a patient", ["patient_id"]),
            ("get_patient_conditions", "Get active conditions for a patient", ["patient_id"]),
            ("get_patient_medications", "Get current medications for a patient", ["patient_id"]),
            ("get_patient_encounters", "Get clinical encounters for a patient", ["patient_id"]),
            ("get_patient_allergies", "Get allergies/intolerances for a patient", ["patient_id"]),
            ("get_patient_procedures", "Get procedures for a patient", ["patient_id"]),
            ("get_patient_careteam", "Get care team members for a patient", ["patient_id"]),
            ("get_patient_careplans", "Get active care plans for a patient", ["patient_id"]),
            ("get_vital_signs", "Get vital signs (BP, HR, etc.) for a patient", ["patient_id"]),
            ("get_lab_results", "Get lab results for a patient", ["patient_id"]),
            ("get_medications_history", "Get medication history for a patient", ["patient_id"]),
            ("clinical_query", "Execute custom FHIR query string", ["query"]),
            ("get_resource_by_type_and_id", "Get a specific resource by type and ID", ["resource_type", "resource_id"]),
            ("get_all_resources", "Retrieve all resources in the store", []),
            ("get_resource_types", "List available resource types", []),
        ]

        for name, description, required in method_specs:
            params_schema: Dict[str, Any] = {
                "type": "object",
                "properties": {},
                "required": required.copy(),
            }
            for param in required:
                params_schema["properties"][param] = {"type": "string"}
            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": params_schema,
                },
            })
        return tools

    async def call_tool(self, input: Any) -> Any:
        """
        Invoke the specified FHIRSearch method.
        Input must include 'tool' (method name) and optional 'parameters'.
        """
        if isinstance(input, str):
            input = json.loads(input)

        tool_name = input.get("tool")
        params = input.get("parameters", {})
        if not tool_name:
            raise ValueError("Missing 'tool' in input payload")

        # REST-based AWS HealthLake branch
        if self.aws_enabled:
            base = self.rest_endpoint
            try:
                # search by resource type
                if tool_name == 'search_by_type':
                    url = f"{base}/{params['resource_type']}"
                    r = await asyncio.to_thread(requests.get, url, auth=self.auth)
                    bundle = r.json()
                    return [e['resource'] for e in bundle.get('entry', [])]
                # get resource by ID
                if tool_name == 'search_by_id':
                    url = f"{base}/{params['resource_type']}/{params['resource_id']}"
                    r = await asyncio.to_thread(requests.get, url, auth=self.auth)
                    return r.json()
                # free-text search
                if tool_name in ('search_by_text', 'clinical_query'):
                    url = base
                    r = await asyncio.to_thread(
                        requests.get, url, auth=self.auth,
                        params={'_text': params.get('query', '')}
                    )
                    bundle = r.json()
                    return [e['resource'] for e in bundle.get('entry', [])]
                # find patient by name
                if tool_name == 'find_patient':
                    url = f"{base}/Patient"
                    r = await asyncio.to_thread(
                        requests.get, url, auth=self.auth,
                        params={'name:contains': params['query']}
                    )
                    bundle = r.json()
                    return [e['resource'] for e in bundle.get('entry', [])]
                # patient-centric queries
                patient_map = {
                    'get_patient_observations': 'Observation',
                    'get_patient_conditions': 'Condition',
                    'get_patient_medications': 'MedicationRequest',
                    'get_patient_encounters': 'Encounter',
                    'get_patient_allergies': 'AllergyIntolerance',
                    'get_patient_procedures': 'Procedure',
                    'get_patient_careteam': 'CareTeam',
                    'get_patient_careplans': 'CarePlan'
                }
                if tool_name in patient_map:
                    resource = patient_map[tool_name]
                    url = f"{base}/{resource}"
                    r = await asyncio.to_thread(
                        requests.get, url, auth=self.auth,
                        params={'patient': f"Patient/{params.get('patient_id')}"}
                    )
                    bundle = r.json()
                    return [e['resource'] for e in bundle.get('entry', [])]
            except Exception as e:
                logger.error(f"FHIR REST error for '{tool_name}': {e}", exc_info=True)
                return []
        # Local FHIRSearch fallback
        method = getattr(self.search, tool_name)
        return method(**params)

    async def cleanup(self) -> None:
        """Close the FHIR search store."""
        # Close local DB connection if used
        if not self.aws_enabled:
            self.search.close()
