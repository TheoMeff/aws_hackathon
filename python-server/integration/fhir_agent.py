import os
import json
import re
import asyncio
import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from integration.fhir_mcp_client import FhirMcpClient

# Shared FHIR client instance
tmp_fhir_client = None

@tool
def fhirTool(tool_name: str, parameters: str) -> str:
    """FHIR search tool: invoke FHIRSearch methods via FhirMcpClient."""
    data = json.loads(parameters)
    result = asyncio.run(tmp_fhir_client.call_tool({"tool": tool_name, "parameters": data}))
    return json.dumps(result)

class FhirAgent:
    """Agent that uses strands.Agent to reason over FHIR queries and invoke fhirTool."""
    def __init__(self):
        global tmp_fhir_client
        db_path = os.getenv("FHIR_DB_PATH", "fhir_data.db")
        tmp_fhir_client = FhirMcpClient(db_path=db_path)

        session = boto3.Session(region_name=os.getenv("AWS_REGION", "us-east-1"))
        bedrock_model = BedrockModel(
            model_id=os.getenv("FHIR_AGENT_MODEL", "amazon.nova-sonic-v1:0"),
            boto_session=session
        )

        tools = [fhirTool]
        system_prompt = (
            "You are a FHIR data assistant. "
            "Use fhirTool(tool_name, parameters) to query the FHIR data store."
        )
        self.agent = Agent(tools=tools, model=bedrock_model, system_prompt=system_prompt)

    def query(self, input: str) -> str:
        """Send input to the agent for reasoning and tool invocation."""
        output = str(self.agent(input))
        match = re.search(r"<response>(.*?)</response>", output, re.DOTALL)
        return match.group(1) if match else output

    def call_tool(self, tool_name: str, parameters: dict) -> str:
        """Directly invoke the fhirTool."""
        return fhirTool(tool_name, json.dumps(parameters))

    def close(self):
        """Cleanup the FHIR client."""
        tmp_fhir_client.cleanup()
