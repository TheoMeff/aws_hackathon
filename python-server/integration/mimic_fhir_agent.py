import os
import json
import re
import asyncio
import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from integration.mimic_fhir_mcp_client import MimicFhirMcpClient
import logging

# Configure logging
logger = logging.getLogger(__name__)

class MimicFhirAgent:
    """
    Agent that uses strands.Agent to reason over MIMIC FHIR queries and invoke mimicFhirTool.
    Specifically designed for MIMIC-IV dataset with enhanced clinical reasoning.
    """
    
    def __init__(self):
        """Initialize the agent with MIMIC-specific tools and prompts."""
        
        # Initialize MIMIC FHIR client
        self.client = MimicFhirMcpClient()
        logger.info("MIMIC FHIR client initialized for agent.")

        # Initialize Bedrock model
        session = boto3.Session(region_name=os.getenv("AWS_REGION", "us-east-1"))
        bedrock_model = BedrockModel(
            model_id=os.getenv("FHIR_AGENT_MODEL", "amazon.nova-sonic-v1:0"),
            boto_session=session
        )
        
        # Configure tools
        tools = [self.mimicFhirTool]
        
        # MIMIC-specific system prompt
        system_prompt = self._get_mimic_system_prompt()
        
        # Initialize the agent
        self.agent = Agent(
            tools=tools, 
            model=bedrock_model, 
            system_prompt=system_prompt
        )
        
        logger.info("MIMIC FHIR Agent initialized successfully")
    
    @tool
    def mimicFhirTool(self, tool_name: str, parameters: str) -> str:
        """
        MIMIC FHIR search tool: invoke MIMIC-enhanced FHIRSearch methods via MimicFhirMcpClient.
        
        Args:
            tool_name: FHIR operation name (findPatient, getPatientObservations, etc.)
            parameters: JSON string with operation parameters
        
        Returns:
            JSON string with MIMIC FHIR results
        """
        try:
            logger.info(f"MIMIC FHIR Tool called: {tool_name}")
            logger.debug(f"Parameters: {parameters}")
            
            # Parse parameters
            try:
                data = json.loads(parameters)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON parameters: {e}")
                return json.dumps({"error": f"Invalid JSON parameters: {str(e)}"})
            
            # Call the MIMIC FHIR client
            result = asyncio.run(self.client.call_tool({
                "tool": tool_name, 
                "parameters": data
            }))
            
            # Log result summary
            if isinstance(result, list):
                logger.info(f"MIMIC FHIR Tool result: {len(result)} resources returned")
            elif isinstance(result, dict) and "error" in result:
                logger.warning(f"MIMIC FHIR Tool returned an error: {result['error']}")
            
            return json.dumps(result)
        except Exception as e:
            logger.exception(f"An unexpected error occurred in mimicFhirTool: {e}")
            return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})

    def _get_mimic_system_prompt(self):
        """Get MIMIC-specific system prompt with clinical context"""
        return """You are a clinical AI assistant with access to MIMIC-IV FHIR data from Beth Israel Deaconess Medical Center.

MIMIC-IV Dataset Context:
- De-identified ICU patient data with dates shifted to 2089-2180 for privacy
- Patients named like "Patient_10000032" with MIMIC IDs like "10000032"
- Rich clinical data including vital signs, lab results, medications, procedures, and diagnoses
- Focus on critically ill patients from intensive care units

Available MIMIC FHIR Tools:
- findPatient(query): Search patients by MIMIC ID (10000032) or name (Patient_10000032)
- getPatientObservations(patient_id, category): Get vital signs, lab results, etc.
- getPatientConditions(patient_id): Get diagnoses and medical conditions
- getPatientMedications(patient_id): Get medication orders and administrations
- getPatientEncounters(patient_id): Get ICU stays and hospital visits
- getPatientProcedures(patient_id): Get medical procedures and interventions
- getVitalSigns(patient_id): Get blood pressure, heart rate, temperature, etc.
- getLabResults(patient_id): Get laboratory test results
- searchByType(resource_type): Search for specific FHIR resource types
- searchByText(query): Full-text search across all MIMIC data

Clinical Reasoning Guidelines:
1. Always validate patient identifiers before querying
2. Consider temporal relationships between observations, medications, and procedures
3. Be aware of ICU-specific clinical contexts and interventions
4. Interpret lab values and vital signs in clinical context
5. Explain medical terminology and provide clinical insights
6. Reference the MIMIC dataset nature when discussing findings

Use mimicFhirTool(tool_name, parameters) to query the MIMIC FHIR data store.
Provide clinically relevant insights while being clear about the research dataset nature."""

    def query(self, input: str) -> str:
        """
        Send input to the agent for clinical reasoning and MIMIC FHIR tool invocation.
        
        Args:
            input: Natural language query about MIMIC patient data
        
        Returns:
            Clinical response with MIMIC data insights
        """
        try:
            logger.info(f"MIMIC FHIR Agent query: {input[:100]}...")
            
            # Process the query through the agent
            output = str(self.agent(input))
            
            # Extract response if wrapped in XML tags
            match = re.search(r"<response>(.*?)</response>", output, re.DOTALL)
            if match:
                response = match.group(1).strip()
            else:
                response = output
            
            # Post-process response for MIMIC context
            response = self._enhance_mimic_response(response)
            
            logger.info("MIMIC FHIR Agent query completed")
            return response
            
        except Exception as e:
            logger.error(f"MIMIC FHIR Agent query error: {e}", exc_info=True)
            return f"I encountered an error while processing your query: {str(e)}"
    
    def _enhance_mimic_response(self, response: str) -> str:
        """Enhance response with MIMIC-specific context and explanations"""
        
        # Add MIMIC context reminders for dates
        if any(year in response for year in ["2089", "2090", "2100", "2150", "2180"]):
            response += "\n\n*Note: MIMIC-IV uses future dates (2089-2180) for de-identification purposes.*"
        
        # Enhance patient ID references
        if "Patient_" in response:
            response += "\n\n*MIMIC patients are identified with standardized names like 'Patient_10000032'.*"
        
        # Add clinical context for ICU data
        if any(term in response.lower() for term in ["vital signs", "medications", "procedures", "icu"]):
            response += "\n\n*This data represents intensive care unit patients with complex medical conditions.*"
        
        return response
    
    def call_tool(self, tool_name: str, parameters: dict) -> str:
        """
        Directly invoke the mimicFhirTool for programmatic access.
        
        Args:
            tool_name: MIMIC FHIR tool name
            parameters: Tool parameters as dictionary
        
        Returns:
            JSON string with results
        """
        return self.mimicFhirTool(tool_name, json.dumps(parameters))
    
    def get_patient_summary(self, patient_identifier: str) -> dict:
        """
        Get comprehensive patient summary from MIMIC data.
        
        Args:
            patient_identifier: MIMIC patient ID or name
        
        Returns:
            Dictionary with patient summary
        """
        try:
            logger.info(f"Getting MIMIC patient summary for: {patient_identifier}")
            
            # Find patient
            patient_result = json.loads(self.call_tool("findPatient", {"query": patient_identifier}))
            
            if isinstance(patient_result, dict) and "error" in patient_result:
                return patient_result
            
            if not patient_result or len(patient_result) == 0:
                return {"error": f"Patient not found: {patient_identifier}"}
            
            patient = patient_result[0]
            patient_id = patient.get("id")
            
            summary = {
                "patient": patient,
                "observations": [],
                "conditions": [],
                "medications": [],
                "encounters": [],
                "procedures": []
            }
            
            # Get related data
            try:
                # Get observations (limit to recent)
                obs_result = json.loads(self.call_tool("getPatientObservations", {
                    "patient_id": patient_id, 
                    "count": 20
                }))
                if isinstance(obs_result, list):
                    summary["observations"] = obs_result
                
                # Get conditions
                cond_result = json.loads(self.call_tool("getPatientConditions", {
                    "patient_id": patient_id
                }))
                if isinstance(cond_result, list):
                    summary["conditions"] = cond_result
                
                # Get medications
                med_result = json.loads(self.call_tool("getPatientMedications", {
                    "patient_id": patient_id
                }))
                if isinstance(med_result, list):
                    summary["medications"] = med_result
                
                # Get encounters
                enc_result = json.loads(self.call_tool("getPatientEncounters", {
                    "patient_id": patient_id
                }))
                if isinstance(enc_result, list):
                    summary["encounters"] = enc_result
                
            except Exception as e:
                logger.warning(f"Error getting additional patient data: {e}")
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting patient summary: {e}")
            return {"error": f"Failed to get patient summary: {str(e)}"}
    
    def search_clinical_concept(self, concept: str, limit: int = 10) -> list:
        """
        Search for clinical concepts across MIMIC data.
        
        Args:
            concept: Clinical term to search for
            limit: Maximum results to return
        
        Returns:
            List of matching resources
        """
        try:
            logger.info(f"Searching MIMIC for clinical concept: {concept}")
            
            result = json.loads(self.call_tool("searchByText", {
                "query": concept,
                "count": limit
            }))
            
            if isinstance(result, dict) and "error" in result:
                return []
            
            return result if isinstance(result, list) else []
            
        except Exception as e:
            logger.error(f"Error searching clinical concept: {e}")
            return []
    
    def close(self):
        """Cleanup the MIMIC FHIR client."""
        if self.client:
            self.client.close()
            self.client = None
            logger.info("MIMIC FHIR client closed.")

# For backward compatibility, alias the class
FhirAgent = MimicFhirAgent

# Example usage and testing
if __name__ == "__main__":
    # Test the MIMIC FHIR Agent
    try:
        agent = MimicFhirAgent()
        
        # Test patient search
        print("Testing MIMIC patient search...")
        result = agent.query("Find patient with MIMIC ID 10000032")
        print(f"Result: {result}")
        
        # Test clinical reasoning
        print("\nTesting clinical reasoning...")
        result = agent.query("What are the vital signs for patient 10000032?")
        print(f"Result: {result}")
        
        # Test direct tool call
        print("\nTesting direct tool call...")
        result = agent.call_tool("findPatient", {"query": "10000032"})
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        if 'agent' in locals():
            agent.close()
