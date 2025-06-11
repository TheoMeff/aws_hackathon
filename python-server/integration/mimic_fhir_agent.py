import os
import json
import re
import asyncio
import boto3
import concurrent.futures
from typing import Dict, Any
from matplotlib import pyplot as plt
from integration.mimic_patient_class import MimicPatient
from integration.mimic_fhir_mcp_client import MimicFhirMcpClient
import logging
from strands import Agent, tool
from strands.models import BedrockModel
from botocore.config import Config

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
        self.current_patient_object = None
        
        logger.info("MIMIC FHIR client initialized for agent.")

        # Initialize Bedrock model with more robust configuration
        boto_config = Config(
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            connect_timeout=10,
            read_timeout=30,
            max_pool_connections=10
        )
        
        session = boto3.Session(region_name=os.getenv("AWS_REGION", "us-east-1"))
        bedrock_model = BedrockModel(
            model_id=os.getenv("FHIR_AGENT_MODEL", "amazon.nova-sonic-v1:0"),
            boto_session=session,
            config=boto_config
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
            
            # Use a simple synchronous approach to avoid AWS CRT errors
            result = None
            error = None
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            
            def execute_tool_call():
                # Use a local event loop that's completely separate
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(self._safe_tool_call(tool_name, data))
                except Exception as e:
                    logger.exception(f"Thread execution error: {e}")
                    return {"error": f"Tool execution failed: {str(e)}"}
                finally:
                    loop.close()
            
            # Execute in separate thread with timeout
            try:
                future = executor.submit(execute_tool_call)
                result = future.result(timeout=40)
            except concurrent.futures.TimeoutError:
                error = "Tool call timed out after 40 seconds"
                logger.error(error)
                result = {"error": error}
            except Exception as e:
                error = f"Unexpected error in tool thread: {str(e)}"
                logger.exception(error)
                result = {"error": error}
            finally:
                executor.shutdown(wait=False)
            
            # Apply fallback if needed
            if result is None:
                result = {"error": error or "Unknown execution error"}
                
            # Ensure we have a valid result
            if isinstance(result, list) and not result:
                logger.info(f"MIMIC FHIR Tool returned empty list for {tool_name}")
                # Return empty list instead of null
                return json.dumps([])
            elif isinstance(result, dict) and "error" in result:
                logger.warning(f"MIMIC FHIR Tool returned an error: {result['error']}")
            elif isinstance(result, list):
                logger.info(f"MIMIC FHIR Tool result: {len(result)} resources returned")
            
            return json.dumps(result)
        except Exception as e:
            logger.exception(f"An unexpected error occurred in mimicFhirTool: {e}")
            return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})
            
    async def _safe_tool_call(self, tool_name, data):
        """
        Execute tool calls with retries and additional error handling to prevent AWS CRT errors
        
        Args:
            tool_name: Name of the tool to call
            data: Parameters to pass to the tool
            
        Returns:
            Result from the tool call or error dictionary
        """
        max_retries = 2
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries + 1):
            try:
                # Apply request throttling to avoid overwhelming AWS services
                if attempt > 0:
                    await asyncio.sleep(retry_delay * attempt)
                
                # Call the tool with a reasonable timeout
                result = await asyncio.wait_for(
                    self.client.call_tool({
                        "tool": tool_name,
                        "parameters": data
                    }),
                    timeout=20
                )
                
                # Success - return the result
                return result
                
            except asyncio.TimeoutError:
                logger.warning(f"Attempt {attempt+1} timed out for {tool_name}")
                if attempt == max_retries:
                    return {"error": f"Tool call timed out after {max_retries+1} attempts"}
            except Exception as e:
                logger.error(f"Attempt {attempt+1} failed for {tool_name}: {e}")
                if attempt == max_retries:
                    return {"error": f"Tool call failed after retries: {str(e)}"}
        
        # This shouldn't be reached but as a fallback
        return {"error": "Failed to execute tool call after retries"}

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
    
    def process_query(self, input: str) -> str:
        """Enhanced query processing with patient context"""
        
        # Check if query is asking for patient dashboard
        if any(word in input.lower() for word in ["dashboard", "summary", "visualize", "chart", "graph"]):
            if self.current_patient:
                # Generate dashboard and return description
                try:
                    fig = self.current_patient.create_patient_dashboard()
                    # In real implementation, you'd save this image and return path
                    # For voice response, return summary
                    plt.close(fig)
                    return f"I've created a comprehensive dashboard for {self.current_patient.demographics.name}. " + \
                           self.current_patient.get_voice_summary()
                except Exception as e:
                    return f"I encountered an issue creating the dashboard: {str(e)}"
            else:
                return "No patient is currently selected. Please search for a patient first."
        
        # Regular query processing
        response = super().query(input)
        
        # Check if we need to update current patient
        self._update_current_patient_from_response(input, response)
        
        return response
    
    def _update_current_patient_from_response(self, query: str, response: str):
        """Update current patient based on query and response"""
        
        # If we found a patient, try to create patient object
        if "patient" in query.lower() and "found" in response.lower():
            # Extract patient ID from response (this would need to be implemented)
            # For now, this is a placeholder
            pass
    
    def get_patient_analysis(self, patient_id: str) -> Dict[str, Any]:
        """Get comprehensive patient analysis"""
        if not self.current_patient or self.current_patient.demographics.patient_id != patient_id:
            # Load patient data
            result = self.call_tool("find_patient", {"query": patient_id})
            if result and isinstance(result, list):
                self.current_patient = MimicPatient(patient_id)
                self.current_patient.parse_patient_resource(result[0])
        
        if self.current_patient:
            return {
                "summary": self.current_patient.get_summary_statistics(),
                "voice_summary": self.current_patient.get_voice_summary(),
                "demographics": self.current_patient.demographics.__dict__,
                "data_counts": {
                    "observations": len(self.current_patient.clinical_data.observations),
                    "conditions": len(self.current_patient.clinical_data.conditions),
                    "medications": len(self.current_patient.clinical_data.medications),
                    "encounters": len(self.current_patient.clinical_data.encounters),
                    "procedures": len(self.current_patient.clinical_data.procedures)
                }
            }
        
        return {"error": "Patient not found or not loaded"}
        
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
    
    def call_tool(self, tool_name: str, parameters: dict) -> Any:
        """
        Directly invoke the mimicFhirTool for programmatic access.
        
        Args:
            tool_name: MIMIC FHIR tool name
            parameters: Tool parameters as dictionary
        
        Returns:
            Parsed JSON result (Python dictionary/list)
        """
        result_json = self.mimicFhirTool(tool_name, json.dumps(parameters))
        try:
            # Parse the result back from JSON string to Python object
            return json.loads(result_json)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in call_tool: {e}")
            # If parsing fails, return the raw string
            return {"error": f"Failed to parse result: {str(e)}", "raw_result": result_json}
    
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
