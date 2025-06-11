import os
import json
import re
import asyncio
import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from integration.fhir_mcp_client import FhirMcpClient

class FhirAgent:
    """Agent that uses strands.Agent to reason over FHIR queries and invoke fhirTool."""
    def __init__(self):
        db_path = os.getenv("FHIR_DB_PATH", "fhir_data.db")
        self.client = FhirMcpClient(db_path=db_path)

        session = boto3.Session(region_name=os.getenv("AWS_REGION", "us-east-1"))
        bedrock_model = BedrockModel(
            model_id=os.getenv("FHIR_AGENT_MODEL", "amazon.nova-sonic-v1:0"),
            boto_session=session
        )

        tools = [self.fhirTool]
        system_prompt = (
            "You are a FHIR data assistant. "
            "Use fhirTool(tool_name, parameters) to query the FHIR data store."
        )
        self.agent = Agent(tools=tools, model=bedrock_model, system_prompt=system_prompt)

    @tool
    def fhirTool(self, tool_name: str, parameters: str) -> str:
        """FHIR search tool: invoke FHIRSearch methods via FhirMcpClient."""
        print("fhirTool:", tool_name, parameters)
        data = json.loads(parameters)
        result = asyncio.run(self.client.call_tool({"tool": tool_name, "parameters": data}))
        print("fhirTool result:", result)
        return json.dumps(result)

    def query(self, input: str) -> str:
        """Send input to the agent for reasoning and tool invocation."""
        output = str(self.agent(input))
        match = re.search(r"<response>(.*?)</response>", output, re.DOTALL)
        return match.group(1) if match else output

    def call_tool(self, tool_name: str, parameters: dict) -> str:
        """Directly invoke the fhirTool."""
        print("call_tool:", tool_name, parameters)
        return self.fhirTool(tool_name, json.dumps(parameters))

    def close(self):
        """Close the FHIR client."""
        if self.client:
            self.client.close()
