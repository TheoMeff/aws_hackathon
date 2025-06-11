import asyncio
import re
import warnings
import uuid
import logging
import pandas as pd
import time
import json
import sys
import io
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from aws_sdk_bedrock_runtime.client import BedrockRuntimeClient, InvokeModelWithBidirectionalStreamOperationInput
from aws_sdk_bedrock_runtime.models import InvokeModelWithBidirectionalStreamInputChunk, BidirectionalInputPayloadPart
from aws_sdk_bedrock_runtime.config import Config, HTTPAuthSchemeResolver, SigV4AuthScheme
from s2s_events import S2sEvent
from smithy_aws_core.credentials_resolvers.environment import EnvironmentCredentialsResolver
from integration.fhir_mcp_client import FhirMcpClient
from integration.mimic_fhir_mcp_client import MimicFhirMcpClient
from integration.mimic_patient_class import MimicPatient

# Configure logging
logger = logging.getLogger(__name__)

# Suppress warnings
warnings.filterwarnings("ignore")

# Names of FHIR tool methods
FHIR_TOOL_NAMES = [
    "search_by_type", "search_by_id", "search_by_text",
    "find_patient", "get_patient_observations", "get_patient_conditions",
    "get_patient_medications", "get_patient_encounters", "get_patient_allergies",
    "get_patient_procedures", "get_patient_careteam", "get_patient_careplans",
    "get_vital_signs", "get_lab_results", "get_medications_history",
    "clinical_query", "get_resource_by_type_and_id", "get_all_resources",
    "get_resource_types", "get_patient_data",
]

DEBUG = False

def debug_print(message):
    """Print only if debug mode is enabled"""
    if DEBUG:
        print(message)

def camel_to_snake(name):
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


class S2sSessionManager:
    """Manages bidirectional streaming with AWS Bedrock using asyncio"""
    
    def __init__(self, model_id='amazon.nova-sonic-v1:0', region='us-east-1', mcp_loc_client=None, strands_agent=None, fhir_agent=None, mimic_fhir_agent=None):
        """Initialize the stream manager."""
        self.model_id = model_id
        self.region = region
        
        # Client setup
        if mimic_fhir_agent:
            self.mcp_loc_client = mimic_fhir_agent.client
        elif fhir_agent:
            self.mcp_loc_client = fhir_agent.client
        else:
            self.mcp_loc_client = mcp_loc_client
        
        print(f"SessionManager initialized with client: {type(self.mcp_loc_client)}")

        self.strands_agent = strands_agent

        # Audio and output queues
        self.audio_input_queue = asyncio.Queue()
        self.output_queue = asyncio.Queue()
        
        self.response_task = None
        self.stream = None
        self.is_active = False
        self.bedrock_client = None
        
        # Session information
        self.prompt_name = None
        self.content_name = None
        self.audio_content_name = None
        self.toolUseContent = ""
        self.toolUseId = ""
        self.toolName = ""
        
        # Initialize patient data structure to store FHIR data
        self.patient = MimicPatient()

    def _initialize_client(self):
        """Initialize the Bedrock client."""
        config = Config(
            endpoint_uri=f"https://bedrock-runtime.{self.region}.amazonaws.com",
            region=self.region,
            aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
            http_auth_scheme_resolver=HTTPAuthSchemeResolver(),
            http_auth_schemes={"aws.auth#sigv4": SigV4AuthScheme()}
        )
        self.bedrock_client = BedrockRuntimeClient(config=config)

    async def initialize_stream(self):
        # Skip any Bedrock CRT streaming when running with pure FHIR MCP client
        if hasattr(self, 'mcp_loc_client') and isinstance(self.mcp_loc_client, FhirMcpClient) and self.strands_agent is None:
            self.is_active = False
            return self

        try:
            if not self.bedrock_client:
                self._initialize_client()
        except Exception as ex:
            self.is_active = False
            print(f"Failed to initialize Bedrock client: {ex}")
            raise

        try:
            # Initialize the stream
            self.stream = await self.bedrock_client.invoke_model_with_bidirectional_stream(
                InvokeModelWithBidirectionalStreamOperationInput(model_id=self.model_id)
            )
            self.is_active = True
            
            # Start listening for responses
            self.response_task = asyncio.create_task(self._process_responses())

            # Start processing audio input
            asyncio.create_task(self._process_audio_input())
            
            # Wait a bit to ensure everything is set up
            await asyncio.sleep(0.1)
            
            debug_print("Stream initialized successfully")
            return self
        except Exception as e:
            self.is_active = False
            print(f"Failed to initialize stream: {str(e)}")
            raise
    
    async def send_raw_event(self, event_data):
        """Send a raw event to the Bedrock stream."""
        try:
            if not self.stream or not self.is_active:
                debug_print("Stream not initialized or closed")
                return
            
            event_json = json.dumps(event_data)
            debug_print(f"Sending event: {event_json[:80] if len(event_json) > 80 else event_json}...")
            
            # Send the event through the stream
            event = InvokeModelWithBidirectionalStreamInputChunk(
                value=BidirectionalInputPayloadPart(bytes_=event_json.encode('utf-8'))
            )
            await self.stream.input_stream.send(event)
            
            # Close session if session end event
            if "sessionEnd" in event_data.get("event", {}):
                self.close()
        except Exception as e:
            debug_print(f"Error sending event: {str(e)}")
            
    async def send_heartbeat(self):
        """Send a heartbeat event to keep the connection alive."""
        try:
            # Create a simple ping event
            heartbeat_id = str(uuid.uuid4())
            heartbeat_event = {
                "event": {
                    "heartbeat": {
                        "id": heartbeat_id,
                        "timestamp": int(time.time() * 1000)
                    }
                }
            }
            
            logger.info("Sending heartbeat to keep connection alive")
            await self.send_raw_event(heartbeat_event)
        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")

    async def add_audio_chunk(self, prompt_name, content_name, audio_data):
        """Add an audio chunk to the queue."""
        # The audio_data is already a base64 string from the frontend
        self.audio_input_queue.put_nowait({
            'prompt_name': prompt_name,
            'content_name': content_name,
            'audio_bytes': audio_data
        })
    
    async def _process_audio_input(self):
        """Process audio input from the queue and send to Bedrock."""
        while self.is_active:
            try:
                # Get audio data from the queue
                data = await self.audio_input_queue.get()
                
                # Extract data from the queue item
                prompt_name = data.get('prompt_name')
                content_name = data.get('content_name')
                audio_bytes = data.get('audio_bytes')
                
                if not audio_bytes or not prompt_name or not content_name:
                    debug_print("Missing required audio data properties")
                    continue

                # Create the audio input event
                audio_event = S2sEvent.audio_input(prompt_name, content_name, audio_bytes.decode('utf-8') if isinstance(audio_bytes, bytes) else audio_bytes)
                
                # Send the event
                await self.send_raw_event(audio_event)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                debug_print(f"Error processing audio: {e}")
                if DEBUG:
                    import traceback
                    traceback.print_exc()
    
    async def _process_responses(self):
        """Process incoming responses from Bedrock."""
        while self.is_active:
            try:            
                # Add timeout to prevent hanging indefinitely waiting for events
                try:
                    output = await asyncio.wait_for(self.stream.await_output(), timeout=30.0)
                    result = await asyncio.wait_for(output[1].receive(), timeout=10.0)
                except asyncio.TimeoutError:
                    logger.warning("Timeout waiting for stream output, processing next event")
                    # Send a heartbeat event to keep the connection alive
                    await self.send_heartbeat()
                    continue
                
                # Gracefully skip empty chunks
                if not result or not getattr(result, "value", None):
                    logger.debug("Received empty result chunk, skipping")
                    continue
                if not getattr(result.value, "bytes_", None):
                    logger.debug("Result chunk has no bytes, skipping")
                    continue
                
                response_data = result.value.bytes_.decode('utf-8')
                
                json_data = json.loads(response_data)
                json_data["timestamp"] = int(time.time() * 1000)  # Milliseconds since epoch
                
                event_name = None
                if 'event' in json_data:
                    event_name = list(json_data["event"].keys())[0]
                    # if event_name == "audioOutput":
                    #     print(json_data)
                    
                    # Handle tool use detection
                    if event_name == 'toolUse':
                        self.toolUseContent = json_data['event']['toolUse']
                        self.toolName = json_data['event']['toolUse']['toolName']
                        self.toolUseId = json_data['event']['toolUse']['toolUseId']
                        debug_print(f"Tool use detected: {self.toolName}, ID: {self.toolUseId}, "+ json.dumps(json_data['event']))

                    # Process tool use when content ends
                    elif event_name == 'contentEnd' and json_data['event'][event_name].get('type') == 'TOOL':
                        prompt_name = json_data['event']['contentEnd'].get("promptName")
                        debug_print("Processing tool use and sending result")
                        toolResult = await self.processToolUse(self.toolName, self.toolUseContent)
                            
                        # Send tool start event
                        toolContent = str(uuid.uuid4())
                        tool_start_event = S2sEvent.content_start_tool(prompt_name, toolContent, self.toolUseId)
                        await self.send_raw_event(tool_start_event)
                        
                        # Send tool result event
                        if isinstance(toolResult, dict):
                            content_json_string = json.dumps(toolResult)
                        else:
                            content_json_string = toolResult

                        tool_result_event = S2sEvent.text_input_tool(prompt_name, toolContent, content_json_string)
                        print("Tool result", tool_result_event)
                        await self.send_raw_event(tool_result_event)

                        # Send tool content end event
                        tool_content_end_event = S2sEvent.content_end(prompt_name, toolContent)
                        await self.send_raw_event(tool_content_end_event)
                        
                        # Push generated tool events to frontend queue as well
                        now_ms = lambda: int(time.time()*1000)
                        for ev in (tool_start_event, tool_result_event, tool_content_end_event):
                            ev_with_ts = {**ev, "timestamp": now_ms()}
                            await self.output_queue.put(ev_with_ts)
                    
                # Put the response in the output queue for forwarding to the frontend
                await self.output_queue.put(json_data)


            except json.JSONDecodeError as ex:
                print(ex)
                await self.output_queue.put({"raw_data": response_data})
            except StopAsyncIteration as ex:
                # Stream has ended
                print(ex)
            except Exception as e:
                # Handle ValidationException properly
                if "ValidationException" in str(e):
                    error_message = str(e)
                    print(f"Validation error: {error_message}")
                else:
                    print(f"Error receiving response: {e}")
                break

        self.is_active = False
        self.close()

    async def processToolUse(self, toolName, toolUseContent):
        """Process tool use events and return the tool result
        
        Additionally parses FHIR data into the Patient object when relevant
        """
        print(f"Tool Use Content: {toolUseContent}")

        toolName = camel_to_snake(toolName)
        print(f"Normalized tool name: {toolName}")
        content, result = None, None
        try:
            if toolUseContent.get("content"):
                # Parse the JSON string in the content field
                query_json = json.loads(toolUseContent.get("content"))
                content = toolUseContent.get("content")  # Pass the JSON string directly to the agent
                print(f"Extracted query: {content}")
            
            # Simple toolUse to get system time in UTC
            if toolName == "getdatetool":
                from datetime import datetime, timezone
                result = datetime.now(timezone.utc).strftime('%A, %Y-%m-%d %H-%M-%S')
            
            # Special shortcut: return cached aggregated patient data
            if toolName == "get_patient_data":
                patient_data = self.patient.to_dict()
                return {"result": patient_data, "patientData": patient_data}

            # FHIR MCP integration - FHIRSearch methods
            if toolName in FHIR_TOOL_NAMES:
                if self.mcp_loc_client:
                    fhir_input = {"tool": toolName, "parameters": query_json}
                    result = await self.mcp_loc_client.call_tool(fhir_input)
                    
                    # Parse FHIR data into patient object
                    if result:
                        # Special handling for find_patient which returns a list directly
                        if toolName == "find_patient" and isinstance(result, list) and len(result) > 0:
                            # Directly use the first patient in the list
                            patient_resource = result[0]
                            logger.info(f"Processing patient resource from find_patient: {patient_resource.get('id')}")
                            self.patient.parse_patient_resource(patient_resource)
                            
                            # Ensure we have a valid result for the response
                            result_dict = {"result": result}
                        else:
                            # Convert result to dict if it's a JSON string
                            if isinstance(result, str):
                                try:
                                    result_dict = json.loads(result)
                                except json.JSONDecodeError:
                                    result_dict = {"result": result}
                            else:
                                result_dict = result
                            
                            # From the logs, it appears the result is in an array format within the "result" key
                            # The actual FHIR resources are in this array
                            if "result" in result_dict and isinstance(result_dict["result"], list):
                                # Process each resource in the result array
                                for resource in result_dict["result"]:
                                    resource_type = resource.get("resourceType")
                                    
                                    if resource_type == "Patient":
                                        self.patient.parse_patient_resource(resource)
                                    elif resource_type == "Observation":
                                        self.patient.parse_observation_resource(resource)
                                    elif resource_type == "Condition":
                                        self.patient.parse_condition_resource(resource)
                                    elif resource_type == "MedicationRequest":
                                        self.patient.parse_medication_request(resource)
                                    elif resource_type == "Encounter":
                                        self.patient.parse_encounter_resource(resource)
                            
                            # Also handle direct resources or bundles (not in a result array)
                            elif "resourceType" in result_dict:
                                resource_type = result_dict["resourceType"]
                                
                                if resource_type == "Bundle" and "entry" in result_dict:
                                    self.patient.parse_fhir_bundle(result_dict)
                                elif resource_type == "Patient":
                                    self.patient.parse_patient_resource(result_dict)
                                elif resource_type == "Observation":
                                    self.patient.parse_observation_resource(result_dict)
                                elif resource_type == "Condition":
                                    self.patient.parse_condition_resource(result_dict)
                                elif resource_type == "MedicationRequest":
                                    self.patient.parse_medication_request(result_dict)
                                elif resource_type == "Encounter":
                                    self.patient.parse_encounter_resource(result_dict)
                
            # Include parsed patient data in the result
            if toolName in FHIR_TOOL_NAMES:
                patient_data = self.patient.to_dict()
                # For find_patient, ensure we have non-null result to avoid client-side errors
                if toolName == "find_patient" and (result is None or (isinstance(result, list) and len(result) == 0)):
                    logger.warning("find_patient returned null/empty result, using synthetic data")
                    # Create synthetic result using patient data
                    if patient_data and patient_data.get("demographics") and patient_data["demographics"].get("patient_id"):
                        synthetic_result = [{
                            "resourceType": "Patient",
                            "id": patient_data["demographics"]["patient_id"],
                            "_synthetic": True
                        }]
                        return {"result": synthetic_result, "patientData": patient_data}
                return {"result": result, "patientData": patient_data}
            else:
                return {"result": result}

            # Handle patient dashboard requests
            if toolName == "getpatientdashboard":
                try:
                    patient_id = query_json.get("patient_id")
                    if not patient_id:
                        return {"error": "Patient ID required for dashboard"}
                    
                    # Get or create patient object
                    if isinstance(self.mcp_loc_client, MimicFhirMcpClient):
                        patient_obj = await self.mcp_loc_client.get_patient_object(patient_id)
                        
                        if patient_obj:
                            # Generate dashboard
                            dashboard_base64 = self.get_patient_dashboard()
                            voice_summary = patient_obj.get_voice_summary()
                            
                            return {
                                "dashboard_image": dashboard_base64,
                                "voice_summary": voice_summary,
                                "patient_summary": patient_obj.get_summary_statistics()
                            }
                        else:
                            return {"error": f"Could not load patient data for {patient_id}"}
                    else:
                        return {"error": "FHIR client not available"}
                        
                except Exception as e:
                    logger.error(f"Dashboard generation error: {e}")
                    return {"error": f"Dashboard generation failed: {str(e)}"}
            
            # Handle patient trend analysis
            elif toolName == "analyzepatienttrends":
                try:
                    patient_id = query_json.get("patient_id")
                    analysis_type: str = query_json.get("analysis_type", "comprehensive")
                    
                    if isinstance(self.mcp_loc_client, MimicFhirMcpClient):
                        patient_obj = await self.mcp_loc_client.get_patient_object(patient_id)
                        
                        if patient_obj:
                            # Perform trend analysis
                            trends = self._analyze_patient_trends(patient_obj, analysis_type)
                            return trends
                        else:
                            return {"error": f"Could not load patient data for {patient_id}"}
                    else:
                        return {"error": "FHIR client not available"}
                        
                except Exception as e:
                    logger.error(f"Trend analysis error: {e}")
                    return {"error": f"Trend analysis failed: {str(e)}"}
            
            # Handle patient comparison
            elif toolName == "comparepatients":
                try:
                    patient_ids = query_json.get("patient_ids", [])
                    comparison_criteria = query_json.get("comparison_criteria", ["demographics", "conditions"])
                    
                    if len(patient_ids) < 2:
                        return {"error": "At least 2 patient IDs required for comparison"}
                    
                    if isinstance(self.mcp_loc_client, MimicFhirMcpClient):
                        # Load all patient objects
                        patient_objects = []
                        for pid in patient_ids:
                            patient_obj = await self.mcp_loc_client.get_patient_object(pid)
                            if patient_obj:
                                patient_objects.append(patient_obj)
                        
                        if len(patient_objects) >= 2:
                            comparison = self._compare_patients(patient_objects, comparison_criteria)
                            return comparison
                        else:
                            return {"error": "Could not load sufficient patient data for comparison"}
                    else:
                        return {"error": "FHIR client not available"}
                        
                except Exception as e:
                    logger.error(f"Patient comparison error: {e}")
                    return {"error": f"Patient comparison failed: {str(e)}"}
                
        except Exception as ex:
            print(f"Error in processToolUse: {ex}")
            import traceback
            traceback.print_exc()
            return {"result": "An error occurred while attempting to retrieve information related to the toolUse event."}

    async def _handle_fhir_tool_with_memory(self, toolName: str, query_json: Dict) -> Any:
        """Enhanced FHIR tool handling with patient objects"""
        
        # Call the FHIR tool to get the result
        success = False
        try:
            # Check if we're using a MIMIC FHIR client
            if isinstance(self.mcp_loc_client, MimicFhirMcpClient):
                success, result = await self.mcp_loc_client.call_fhir_tool(toolName, query_json)
            else:
                # Use regular FHIR client
                success, result = await self.mcp_loc_client.call_tool({"tool": toolName, "parameters": query_json})
                
            if not success:
                logger.error(f"FHIR tool call failed: {result}")
                return {"error": f"FHIR tool call failed: {result}"}
        except Exception as e:
            logger.error(f"Error calling FHIR tool: {e}")
            return {"error": f"Error calling FHIR tool: {str(e)}"}
        
        # If this is a patient-related query, create/update patient object
        if toolName == "find_patient" and isinstance(result, list) and result:
            patient_resource = result[0]
            patient_id = patient_resource.get("id")
            
            if patient_id:
                # Check if we have a cached patient object
                if hasattr(self, 'fhir_memory') and hasattr(self.fhir_memory, 'get_patient_object'):
                    patient_obj = self.fhir_memory.get_patient_object(patient_id)
                    
                    if not patient_obj:
                        # Create new patient object
                        patient_obj = MimicPatient(patient_id)
                        patient_obj.parse_patient_resource(patient_resource)
                        
                        # Store in memory
                        self.fhir_memory.store_patient_object(patient_obj)
                    
                    # Set as current patient
                    self.current_patient_object = patient_obj
                    self.current_patient_id = patient_id
                    
                    logger.info(f"Set current patient object: {patient_obj.demographics.name}")
        
        # For other patient-specific tools, update current patient object
        elif toolName.startswith("get_patient_") and hasattr(self, 'current_patient_object') and self.current_patient_object:
            if isinstance(result, list):
                for resource in result:
                    self.current_patient_object.parse_resource(resource)
                
                # Update stored patient object
                if hasattr(self, 'fhir_memory') and hasattr(self.fhir_memory, 'store_patient_object'):
                    self.fhir_memory.store_patient_object(self.current_patient_object)
        
        return result
    
    def get_patient_dashboard(self) -> Optional[str]:
        """Get current patient dashboard as base64 image"""
        if not self.current_patient_object:
            return None
        
        try:
            import io
            import base64
            
            # Create dashboard
            fig = self.current_patient_object.create_patient_dashboard()
            
            # Convert to base64
            img_buffer = io.BytesIO()
            fig.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
            plt.close(fig)
            
            return img_base64
            
        except Exception as e:
            logger.error(f"Error creating patient dashboard: {e}")
            return None
    
    def get_patient_voice_summary(self) -> str:
        """Get voice-friendly patient summary"""
        if self.current_patient_object:
            return self.current_patient_object.get_voice_summary()
        return "No patient currently selected."

    def _analyze_patient_trends(self, patient: MimicPatient, analysis_type: str) -> Dict[str, Any]:
        """Analyze patient clinical trends"""
        try:
            trends = {
                "patient_id": patient.demographics.patient_id,
                "patient_name": patient.demographics.name,
                "analysis_type": analysis_type,
                "trends": {}
            }
            
            # Create data frames for analysis
            dfs = patient.create_data_frames()
            
            if analysis_type in ["vital_trends", "comprehensive"]:
                if "vital_signs" in dfs and not dfs["vital_signs"].empty:
                    vital_trends = self._analyze_vital_trends(dfs["vital_signs"])
                    trends["trends"]["vital_signs"] = vital_trends
            
            if analysis_type in ["lab_trends", "comprehensive"]:
                if "lab_results" in dfs and not dfs["lab_results"].empty:
                    lab_trends = self._analyze_lab_trends(dfs["lab_results"])
                    trends["trends"]["lab_results"] = lab_trends
            
            if analysis_type in ["medication_timeline", "comprehensive"]:
                if "medications" in dfs and not dfs["medications"].empty:
                    med_trends = self._analyze_medication_trends(dfs["medications"])
                    trends["trends"]["medications"] = med_trends
            
            # Generate voice-friendly summary
            trends["voice_summary"] = self._generate_trends_voice_summary(trends)
            
            return trends
            
        except Exception as e:
            logger.error(f"Error analyzing patient trends: {e}")
            return {"error": f"Trend analysis failed: {str(e)}"}

    def _analyze_vital_trends(self, vitals_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze vital signs trends"""
        trends = {}
        
        if "effective_date" in vitals_df.columns:
            vitals_df["effective_date"] = pd.to_datetime(vitals_df["effective_date"])
            vitals_df = vitals_df.sort_values("effective_date")
            
            # Group by vital sign type
            for vital_type in vitals_df["code_display"].unique():
                vital_data = vitals_df[vitals_df["code_display"] == vital_type]
                
                if "value_numeric" in vital_data.columns and vital_data["value_numeric"].notna().any():
                    values = vital_data["value_numeric"].dropna()
                    
                    if len(values) > 1:
                        trends[vital_type] = {
                            "count": len(values),
                            "mean": float(values.mean()),
                            "min": float(values.min()),
                            "max": float(values.max()),
                            "trend": "increasing" if values.iloc[-1] > values.iloc[0] else "decreasing",
                            "latest_value": float(values.iloc[-1]),
                            "latest_date": vital_data["effective_date"].iloc[-1].isoformat()
                        }
        
        return trends

    def _analyze_lab_trends(self, labs_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze laboratory results trends"""
        trends = {}
        
        if "effective_date" in labs_df.columns:
            labs_df["effective_date"] = pd.to_datetime(labs_df["effective_date"])
            labs_df = labs_df.sort_values("effective_date")
            
            # Group by lab test type
            for lab_type in labs_df["code_display"].unique():
                lab_data = labs_df[labs_df["code_display"] == lab_type]
                
                if "value_numeric" in lab_data.columns and lab_data["value_numeric"].notna().any():
                    values = lab_data["value_numeric"].dropna()
                    
                    if len(values) > 1:
                        trends[lab_type] = {
                            "count": len(values),
                            "mean": float(values.mean()),
                            "min": float(values.min()),
                            "max": float(values.max()),
                            "trend": "increasing" if values.iloc[-1] > values.iloc[0] else "decreasing",
                            "latest_value": float(values.iloc[-1]),
                            "latest_date": lab_data["effective_date"].iloc[-1].isoformat()
                        }
        
        return trends

    def _analyze_medication_trends(self, meds_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze medication trends"""
        trends = {
            "total_medications": len(meds_df),
            "medication_types": {},
            "timeline": []
        }
        
        # Count by medication type
        if "type" in meds_df.columns:
            type_counts = meds_df["type"].value_counts().to_dict()
            trends["medication_types"] = type_counts
        
        # Extract medication names and timeline
        med_names = []
        for _, row in meds_df.iterrows():
            med_info = row.get("medication", {})
            if isinstance(med_info, dict):
                med_name = med_info.get("display", "Unknown")
                med_names.append(med_name)
        
        # Count unique medications
        from collections import Counter
        med_counts = Counter(med_names)
        trends["most_common_medications"] = dict(med_counts.most_common(10))
        
        return trends

    def _compare_patients(self, patients: List[MimicPatient], criteria: List[str]) -> Dict[str, Any]:
        """Compare multiple patients"""
        comparison = {
            "patient_count": len(patients),
            "patients": [],
            "comparison": {}
        }
        
        # Add patient summaries
        for patient in patients:
            comparison["patients"].append({
                "id": patient.demographics.patient_id,
                "name": patient.demographics.name,
                "age": patient._calculate_age(),
                "gender": patient.demographics.gender
            })
        
        # Compare demographics
        if "demographics" in criteria:
            comparison["comparison"]["demographics"] = {
                "ages": [p._calculate_age() for p in patients],
                "genders": [p.demographics.gender for p in patients],
                "races": [p.demographics.race for p in patients]
            }
        
        # Compare conditions
        if "conditions" in criteria:
            all_conditions = []
            for patient in patients:
                patient_conditions = [c.get("code", "") for c in patient.clinical_data.conditions]
                all_conditions.append(patient_conditions)
            
            comparison["comparison"]["conditions"] = {
                "patient_condition_counts": [len(conds) for conds in all_conditions],
                "common_conditions": self._find_common_conditions(all_conditions)
            }
        
        # Compare medications
        if "medications" in criteria:
            all_medications = []
            for patient in patients:
                patient_meds = [m.get("medication", {}).get("display", "") for m in patient.clinical_data.medications]
                all_medications.append(patient_meds)
            
            comparison["comparison"]["medications"] = {
                "patient_medication_counts": [len(meds) for meds in all_medications],
                "common_medications": self._find_common_medications(all_medications)
            }
        
        return comparison

    def _find_common_conditions(self, condition_lists: List[List[str]]) -> List[str]:
        """Find conditions common across patients"""
        if not condition_lists:
            return []
        
        # Find intersection of all condition lists
        common = set(condition_lists[0])
        for conditions in condition_lists[1:]:
            common = common.intersection(set(conditions))
        
        return list(common)

    def _find_common_medications(self, medication_lists: List[List[str]]) -> List[str]:
        """Find medications common across patients"""
        if not medication_lists:
            return []
        
        # Find intersection of all medication lists
        common = set(medication_lists[0])
        for medications in medication_lists[1:]:
            common = common.intersection(set(medications))
        
        return list(common)

    def _generate_trends_voice_summary(self, trends: Dict[str, Any]) -> str:
        """Generate voice-friendly summary of trends"""
        patient_name = trends.get("patient_name", "Patient")
        analysis_type = trends.get("analysis_type", "comprehensive")
        
        summary_parts = [f"Analysis complete for {patient_name}."]
        
        if "vital_signs" in trends.get("trends", {}):
            vital_count = len(trends["trends"]["vital_signs"])
            if vital_count > 0:
                summary_parts.append(f"Found trends in {vital_count} vital sign types.")
        
        if "lab_results" in trends.get("trends", {}):
            lab_count = len(trends["trends"]["lab_results"])
            if lab_count > 0:
                summary_parts.append(f"Analyzed {lab_count} different lab test trends.")
        
        if "medications" in trends.get("trends", {}):
            med_info = trends["trends"]["medications"]
            med_count = med_info.get("total_medications", 0)
            if med_count > 0:
                summary_parts.append(f"Patient has {med_count} medication records.")
        
        return " ".join(summary_parts)
    
    async def close(self):
        """Close the stream properly."""
        if not self.is_active:
            return
            
        self.is_active = False
        
        if self.stream:
            await self.stream.input_stream.close()
        
        if self.response_task and not self.response_task.done():
            self.response_task.cancel()
            try:
                await self.response_task
            except asyncio.CancelledError:
                pass