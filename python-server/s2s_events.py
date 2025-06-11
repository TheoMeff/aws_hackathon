import json

class S2sEvent:
  # Default configuration values
  DEFAULT_INFER_CONFIG = {
        "maxTokens": 1024,
        "topP": 0.95,
        "temperature": 0.7
    }
  #DEFAULT_SYSTEM_PROMPT = "You are a friend. The user and you will engage in a spoken dialog " \
  #            "exchanging the transcripts of a natural real-time conversation. Keep your responses short, " \
  #            "generally two or three sentences for chatty scenarios."
  DEFAULT_SYSTEM_PROMPT = "You are a friendly assistant. The user and you will engage in a spoken dialog " \
    "exchanging the transcripts of a natural real-time conversation. Keep your responses short, " \
    "generally two or three sentences for chatty scenarios."

  DEFAULT_AUDIO_INPUT_CONFIG = {
        "mediaType":"audio/lpcm",
        "sampleRateHertz":16000,
        "sampleSizeBits":16,
        "channelCount":1,
        "audioType":"SPEECH","encoding":"base64"
      }
  DEFAULT_AUDIO_OUTPUT_CONFIG = {
          "mediaType": "audio/lpcm",
          "sampleRateHertz": 24000,
          "sampleSizeBits": 16,
          "channelCount": 1,
          "voiceId": "matthew",
          "encoding": "base64",
          "audioType": "SPEECH"
        }
  DEFAULT_TOOL_CONFIG = {
        "tools": [
          {
            "toolSpec": {
              "name": "searchByType",
              "description": "Return every FHIR resource of the specified type (e.g., Patient, Observation, Encounter).",
              "inputSchema": {
                "json": '''{
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {
                    "resource_type": {
                      "type": "string",
                      "description": "FHIR resource type to search for."
                    }
                  },
                  "required": ["resource_type"]
                }'''
              }
            }
          },
          {
            "toolSpec": {
              "name": "searchById",
              "description": "Fetch a specific FHIR resource by its logical ID.",
              "inputSchema": {
                "json": '''{
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {
                    "resource_id": {
                      "type": "string",
                      "description": "The logical ID of the resource."
                    }
                  },
                  "required": ["resource_id"]
                }'''
              }
            }
          },
          {
            "toolSpec": {
              "name": "searchByText",
              "description": "Full-text search across all stored FHIR JSON documents.",
              "inputSchema": {
                "json": '''{
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {
                    "query": {
                      "type": "string",
                      "description": "Free-text search expression."
                    }
                  },
                  "required": ["query"]
                }'''
              }
            }
          },
          {
            "toolSpec": {
              "name": "findPatient",
              "description": "Locate patients by name, birth date, or other demographic identifiers.",
              "inputSchema": {
                "json": '''{
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {
                    "query": {
                      "type": "string",
                      "description": "Name fragment, DOB (YYYY-MM-DD), MRN, etc."
                    }
                  },
                  "required": ["query"]
                }'''
              }
            }
          },
          {
            "toolSpec": {
              "name": "getPatientObservations",
              "description": "Retrieve Observation resources (vitals and labs) for a patient.",
              "inputSchema": {
                "json": '''{
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {
                    "patient_id": {
                      "type": "string",
                      "description": "FHIR logical ID of the Patient resource."
                    }
                  },
                  "required": ["patient_id"]
                }'''
              }
            }
          },
          {
            "toolSpec": {
              "name": "getPatientConditions",
              "description": "List active Condition resources for a patient.",
              "inputSchema": {
                "json": '''{
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {
                    "patient_id": {
                      "type": "string",
                      "description": "Patient ID."
                    }
                  },
                  "required": ["patient_id"]
                }'''
              }
            }
          },
          {
            "toolSpec": {
              "name": "getPatientMedications",
              "description": "List current MedicationRequest / MedicationStatement items for the patient.",
              "inputSchema": {
                "json": '''{
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {
                    "patient_id": {
                      "type": "string",
                      "description": "Patient ID."
                    }
                  },
                  "required": ["patient_id"]
                }'''
              }
            }
          },
          {
            "toolSpec": {
              "name": "getPatientEncounters",
              "description": "Return Encounter records (visits, admissions) for the patient.",
              "inputSchema": {
                "json": '''{
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {
                    "patient_id": {
                      "type": "string",
                      "description": "Patient ID."
                    }
                  },
                  "required": ["patient_id"]
                }'''
              }
            }
          },
          {
            "toolSpec": {
              "name": "getPatientAllergies",
              "description": "Retrieve AllergyIntolerance resources for the patient.",
              "inputSchema": {
                "json": '''{
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {
                    "patient_id": {
                      "type": "string",
                      "description": "Patient ID."
                    }
                  },
                  "required": ["patient_id"]
                }'''
              }
            }
          },
          {
            "toolSpec": {
              "name": "getPatientProcedures",
              "description": "Return Procedure resources for the patient.",
              "inputSchema": {
                "json": '''{
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {
                    "patient_id": {
                      "type": "string",
                      "description": "Patient ID."
                    }
                  },
                  "required": ["patient_id"]
                }'''
              }
            }
          },
          {
            "toolSpec": {
              "name": "getPatientCareTeam",
              "description": "List CareTeam participants assigned to the patient.",
              "inputSchema": {
                "json": '''{
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {
                    "patient_id": {
                      "type": "string",
                      "description": "Patient ID."
                    }
                  },
                  "required": ["patient_id"]
                }'''
              }
            }
          },
          {
            "toolSpec": {
              "name": "getPatientCarePlans",
              "description": "Fetch active CarePlan resources for the patient.",
              "inputSchema": {
                "json": '''{
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {
                    "patient_id": {
                      "type": "string",
                      "description": "Patient ID."
                    }
                  },
                  "required": ["patient_id"]
                }'''
              }
            }
          },
          {
            "toolSpec": {
              "name": "getVitalSigns",
              "description": "Return classic vital-sign Observations (BP, HR, RR, Temp, O2Sat, Height, Weight, BMI).",
              "inputSchema": {
                "json": '''{
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {
                    "patient_id": {
                      "type": "string",
                      "description": "Patient ID."
                    }
                  },
                  "required": ["patient_id"]
                }'''
              }
            }
          },
          {
            "toolSpec": {
              "name": "getLabResults",
              "description": "Return Observation resources categorised as laboratory results for the patient.",
              "inputSchema": {
                "json": '''{
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {
                    "patient_id": {
                      "type": "string",
                      "description": "Patient ID."
                    }
                  },
                  "required": ["patient_id"]
                }'''
              }
            }
          },
          {
            "toolSpec": {
              "name": "getMedicationsHistory",
              "description": "Retrieve historic MedicationRequest / MedicationStatement entries for the patient.",
              "inputSchema": {
                "json": '''{
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {
                    "patient_id": {
                      "type": "string",
                      "description": "Patient ID."
                    }
                  },
                  "required": ["patient_id"]
                }'''
              }
            }
          },
          {
            "toolSpec": {
              "name": "executeClinicalQuery",
              "description": "Run any raw FHIR search expression (e.g., \"Condition?patient=12345&status=active\").",
              "inputSchema": {
                "json": '''{
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {
                    "query": {
                      "type": "string",
                      "description": "A valid FHIR search query string."
                    }
                  },
                  "required": ["query"]
                }'''
              }
            }
          },
          {
            "toolSpec": {
              "name": "listResourceTypes",
              "description": "Return an array of distinct FHIR resource types available in the database.",
              "inputSchema": {
                "json": '''{
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {},
                  "required": []
                }'''
              }
            }
          },
          {
            "toolSpec": {
              "name": "listAllResources",
              "description": "Return every stored FHIR resource (use carefully—may be large).",
              "inputSchema": {
                "json": '''{
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {},
                  "required": []
                }'''
              }
            }
          }
        ]
  }

  MIMIC_TOOL_CONFIG = {
      "tools": [
          {
              "toolSpec": {
                  "name": "findPatient",
                  "description": "Search for MIMIC patients by MIMIC ID (e.g., 10000032), name pattern (Patient_10000032), or text search. MIMIC patients have unique identifiers and standardized naming.",
                  "inputSchema": {
                      "json": '''{
                          "$schema": "http://json-schema.org/draft-07/schema#",
                          "type": "object",
                          "properties": {
                              "query": {
                                  "type": "string",
                                  "description": "MIMIC patient identifier (like 10000032), patient name (like Patient_10000032), or search text"
                              }
                          },
                          "required": ["query"]
                      }'''
                  }
              }
          },
          {
              "toolSpec": {
                  "name": "searchByType",
                  "description": "Search MIMIC resources by FHIR type. MIMIC data includes Patient, Observation, Encounter, Condition, Procedure, and other clinical resources.",
                  "inputSchema": {
                      "json": '''{
                          "$schema": "http://json-schema.org/draft-07/schema#",
                          "type": "object",
                          "properties": {
                              "resource_type": {
                                  "type": "string",
                                  "description": "FHIR resource type (Patient, Observation, Encounter, Condition, Procedure, etc.)",
                                  "enum": ["Patient", "Observation", "Encounter", "Condition", "Procedure", "MedicationRequest", "DiagnosticReport", "AllergyIntolerance"]
                              },
                              "count": {
                                  "type": "integer",
                                  "description": "Maximum number of resources to return (default: 50)",
                                  "default": 50
                              }
                          },
                          "required": ["resource_type"]
                      }'''
                  }
              }
          },
          {
              "toolSpec": {
                  "name": "searchById",
                  "description": "Get a specific MIMIC resource by its FHIR logical ID or MIMIC identifier.",
                  "inputSchema": {
                      "json": '''{
                          "$schema": "http://json-schema.org/draft-07/schema#",
                          "type": "object",
                          "properties": {
                              "resource_id": {
                                  "type": "string",
                                  "description": "FHIR logical ID (UUID format) or MIMIC identifier"
                              },
                              "resource_type": {
                                  "type": "string",
                                  "description": "FHIR resource type",
                                  "default": "Patient"
                              }
                          },
                          "required": ["resource_id"]
                      }'''
                  }
              }
          },
          {
              "toolSpec": {
                  "name": "getPatientObservations",
                  "description": "Get all clinical observations for a MIMIC patient including vital signs, lab results, and other measurements. MIMIC has extensive observation data.",
                  "inputSchema": {
                      "json": '''{
                          "$schema": "http://json-schema.org/draft-07/schema#",
                          "type": "object",
                          "properties": {
                              "patient_id": {
                                  "type": "string",
                                  "description": "MIMIC patient FHIR ID or MIMIC identifier"
                              },
                              "category": {
                                  "type": "string",
                                  "description": "Observation category (vital-signs, laboratory, survey, etc.)",
                                  "enum": ["vital-signs", "laboratory", "survey", "imaging", "procedure", "therapy", "activity"]
                              },
                              "count": {
                                  "type": "integer",
                                  "description": "Maximum observations to return",
                                  "default": 100
                              }
                          },
                          "required": ["patient_id"]
                      }'''
                  }
              }
          },
          {
              "toolSpec": {
                  "name": "getPatientConditions",
                  "description": "Get active medical conditions and diagnoses for a MIMIC patient. MIMIC includes detailed ICD-coded conditions.",
                  "inputSchema": {
                      "json": '''{
                          "$schema": "http://json-schema.org/draft-07/schema#",
                          "type": "object",
                          "properties": {
                              "patient_id": {
                                  "type": "string",
                                  "description": "MIMIC patient FHIR ID or identifier"
                              }
                          },
                          "required": ["patient_id"]
                      }'''
                  }
              }
          },
          {
              "toolSpec": {
                  "name": "getPatientEncounters",
                  "description": "Get hospital encounters and visits for a MIMIC patient. MIMIC focuses on ICU stays and hospital admissions.",
                  "inputSchema": {
                      "json": '''{
                          "$schema": "http://json-schema.org/draft-07/schema#",
                          "type": "object",
                          "properties": {
                              "patient_id": {
                                  "type": "string",
                                  "description": "MIMIC patient FHIR ID or identifier"
                              }
                          },
                          "required": ["patient_id"]
                      }'''
                  }
              }
          },
          {
              "toolSpec": {
                  "name": "getPatientMedications",
                  "description": "Get medication orders and administrations for a MIMIC patient. MIMIC includes detailed ICU medication data.",
                  "inputSchema": {
                      "json": '''{
                          "$schema": "http://json-schema.org/draft-07/schema#",
                          "type": "object",
                          "properties": {
                              "patient_id": {
                                  "type": "string",
                                  "description": "MIMIC patient FHIR ID or identifier"
                              }
                          },
                          "required": ["patient_id"]
                      }'''
                  }
              }
          },
          {
              "toolSpec": {
                  "name": "getPatientProcedures",
                  "description": "Get medical procedures performed on a MIMIC patient. MIMIC includes ICU procedures and interventions.",
                  "inputSchema": {
                      "json": '''{
                          "$schema": "http://json-schema.org/draft-07/schema#",
                          "type": "object",
                          "properties": {
                              "patient_id": {
                                  "type": "string",
                                  "description": "MIMIC patient FHIR ID or identifier"
                              }
                          },
                          "required": ["patient_id"]
                      }'''
                  }
              }
          },
          {
              "toolSpec": {
                  "name": "getVitalSigns",
                  "description": "Get vital signs observations for a MIMIC patient (blood pressure, heart rate, temperature, respiratory rate, oxygen saturation).",
                  "inputSchema": {
                      "json": '''{
                          "$schema": "http://json-schema.org/draft-07/schema#",
                          "type": "object",
                          "properties": {
                              "patient_id": {
                                  "type": "string",
                                  "description": "MIMIC patient FHIR ID or identifier"
                              },
                              "count": {
                                  "type": "integer",
                                  "description": "Maximum vital signs to return",
                                  "default": 50
                              }
                          },
                          "required": ["patient_id"]
                      }'''
                  }
              }
          },
          {
              "toolSpec": {
                  "name": "getLabResults",
                  "description": "Get laboratory test results for a MIMIC patient. MIMIC has extensive lab data including blood work, chemistry panels, and specialized tests.",
                  "inputSchema": {
                      "json": '''{
                          "$schema": "http://json-schema.org/draft-07/schema#",
                          "type": "object",
                          "properties": {
                              "patient_id": {
                                  "type": "string",
                                  "description": "MIMIC patient FHIR ID or identifier"
                              },
                              "count": {
                                  "type": "integer",
                                  "description": "Maximum lab results to return",
                                  "default": 100
                              }
                          },
                          "required": ["patient_id"]
                      }'''
                  }
              }
          },
          {
              "toolSpec": {
                  "name": "searchByText",
                  "description": "Full-text search across all MIMIC FHIR resources. Useful for finding specific terms, conditions, medications, or procedures.",
                  "inputSchema": {
                      "json": '''{
                          "$schema": "http://json-schema.org/draft-07/schema#",
                          "type": "object",
                          "properties": {
                              "query": {
                                  "type": "string",
                                  "description": "Search terms to find across all MIMIC data"
                              },
                              "count": {
                                  "type": "integer",
                                  "description": "Maximum results to return",
                                  "default": 20
                              }
                          },
                          "required": ["query"]
                      }'''
                  }
              }
          },
          {
              "toolSpec": {
                  "name": "getDateTimeTool",
                  "description": "Get current date and time in UTC",
                  "inputSchema": {
                      "json": '''{
                          "$schema": "http://json-schema.org/draft-07/schema#",
                          "type": "object",
                          "properties": {},
                          "required": []
                      }'''
                  }
              }
          }
      ]
  }
    
  # Enhanced system prompt for MIMIC data
  MIMIC_SYSTEM_PROMPT = (
    "You are a clinical AI assistant with access to MIMIC-IV FHIR data from Beth Israel Deaconess Medical Center. "
    "This is de-identified ICU patient data with future dates (2089-2180) for privacy. "
    "You can search patients by MIMIC ID (like 10000032), analyze vital signs, lab results, medications, "
    "procedures, and conditions. MIMIC patients are named like 'Patient_10000032'. "
    "Provide accurate clinical information while being clear about the nature of this research dataset. "
    "Keep responses concise and clinically relevant."
  )

  # MIMIC-specific tool configuration
  MIMIC_TOOL_CONFIG = DEFAULT_TOOL_CONFIG

  @staticmethod
  def prompt_start_mimic(prompt_name, audio_output_config=None, tool_config=None):
      """Create prompt start event specifically configured for MIMIC data."""
      if audio_output_config is None:
          audio_output_config = S2sEvent.DEFAULT_AUDIO_OUTPUT_CONFIG
      if tool_config is None:
          tool_config = S2sEvent.MIMIC_TOOL_CONFIG
      return {
          "event": {
              "promptStart": {
                  "promptName": prompt_name,
                  "textOutputConfiguration": {"mediaType": "text/plain"},
                  "audioOutputConfiguration": audio_output_config,
                  "toolUseOutputConfiguration": {"mediaType": "application/json"},
                  "toolConfiguration": tool_config
              }
          }
      }

  @staticmethod
  def text_input_mimic(prompt_name, content_name, system_prompt=None):
      """Create text input event with MIMIC-specific system prompt."""
      if system_prompt is None:
          system_prompt = S2sEvent.MIMIC_SYSTEM_PROMPT
      return {
          "event": {
              "textInput": {
                  "promptName": prompt_name,
                  "contentName": content_name,
                  "content": system_prompt
              }
          }
      }

  # BYOLLM tool configuration
  BYOLLM_TOOL_CONFIG = {
      "tools": [
          {
              "toolSpec": {
                  "name": "lookup",
                  "description": "Runs query against a knowledge base to retrieve information.",
        "inputSchema": {
          "json": "{\"$schema\":\"http://json-schema.org/draft-07/schema#\",\"type\":\"object\",\"properties\":{\"query\":{\"type\":\"string\",\"description\":\"the query to search\"}},\"required\":[\"query\"]}"
        }
      }
    },
          {
              "toolSpec": {
                  "name": "locationMcpTool",
                  "description": "Access location services like finding places, getting place details, and geocoding. Use with tool names: search_places, get_place, search_nearby, reverse_geocode",
                  "inputSchema": {
                      "json": "{\"$schema\":\"http://json-schema.org/draft-07/schema#\",\"type\":\"object\",\"properties\":{\"argName1\":{\"type\":\"string\",\"description\":\"JSON string containing 'tool' (one of: search_places, get_place, search_nearby, reverse_geocode) and 'params' (the parameters for the tool)\"}},\"required\":[\"argName1\"]}"
                  }
              }
          },
          {
              "toolSpec": {
                  "name": "getBookingDetails",
                  "description": "Get booking details by booking ID or manage bookings",
                  "inputSchema": {
                      "json": "{\"$schema\":\"http://json-schema.org/draft-07/schema#\",\"type\":\"object\",\"properties\":{\"operation\":{\"type\":\"string\",\"description\":\"The operation to perform (get_booking, create_booking, update_booking, delete_booking, list_bookings)\",\"enum\":[\"get_booking\",\"create_booking\",\"update_booking\",\"delete_booking\",\"list_bookings\"]},\"booking_id\":{\"type\":\"string\",\"description\":\"The ID of the booking to retrieve, update, or delete\"},\"booking_details\":{\"type\":\"object\",\"description\":\"The booking details to create\"},\"update_data\":{\"type\":\"object\",\"description\":\"The data to update for a booking\"},\"limit\":{\"type\":\"integer\",\"description\":\"The maximum number of bookings to return when listing\"}},\"required\":[\"operation\"]}"
                  }
              }
          }
      ]
  }

  @staticmethod
  def session_start(inference_config=DEFAULT_INFER_CONFIG): 
      return {"event":{"sessionStart":{"inferenceConfiguration":inference_config}}}

  @staticmethod
  def prompt_start(prompt_name, 
                    audio_output_config=DEFAULT_AUDIO_OUTPUT_CONFIG, 
                    tool_config=BYOLLM_TOOL_CONFIG):
      return {
        "event": {
          "promptStart": {
            "promptName": prompt_name,
            "textOutputConfiguration": {
              "mediaType": "text/plain"
            },
            "audioOutputConfiguration": audio_output_config,
            "toolUseOutputConfiguration": {
              "mediaType": "application/json"
            },
            "toolConfiguration": tool_config
          }
        }
      }

  @staticmethod
  def content_start_text(prompt_name, content_name):
      return {
          "event":{
              "contentStart":{
                  "promptName":prompt_name,
                  "contentName":content_name,
                  "type":"TEXT",
                  "interactive":True,
                  "role": "SYSTEM",
                  "textInputConfiguration":{
                      "mediaType":"text/plain"
                  }
              }
          }
      }
    
  @staticmethod
  def text_input(prompt_name, content_name, system_prompt=DEFAULT_SYSTEM_PROMPT):
      return {
          "event":{
              "textInput":{
                  "promptName":prompt_name,
                  "contentName":content_name,
                  "content":system_prompt,
              }
          }
      }
    
  @staticmethod
  def content_end(prompt_name, content_name):
      return {
          "event":{
              "contentEnd":{
                  "promptName":prompt_name,
                  "contentName":content_name
              }
          }
      }
  @staticmethod
  def content_start_audio(prompt_name, content_name, audio_input_config=DEFAULT_AUDIO_INPUT_CONFIG):
      return {
          "event":{
              "contentStart":{
                  "promptName":prompt_name,
                  "contentName":content_name,
                  "type":"AUDIO",
                  "interactive":True,
                  "audioInputConfiguration":audio_input_config
              }
          }
      }
    
  @staticmethod
  def audio_input(prompt_name, content_name, content):
      return {
          "event": {
              "audioInput": {
                  "promptName": prompt_name,
                  "contentName": content_name,
                  "content": content,
              }
          }
      }
    
  @staticmethod
  def content_start_tool(prompt_name, content_name, tool_use_id):
      return {
          "event": {
              "contentStart": {
                  "promptName": prompt_name,
                  "contentName": content_name,
                  "interactive": False,
                  "type": "TOOL",
                  "role": "TOOL",
                  "toolResultInputConfiguration": {
                      "toolUseId": tool_use_id,
                      "type": "TEXT",
                      "textInputConfiguration": {
                          "mediaType": "text/plain"
                      }
                  }
              }
          }
      }
  
  @staticmethod
  def text_input_tool(prompt_name, content_name, content):
      return {
          "event": {
              "toolResult": {
                  "promptName": prompt_name,
                  "contentName": content_name,
                  "content": content,
                  #"role": "TOOL"
              }
          }
      }
  
  @staticmethod
  def prompt_end(prompt_name):
      return {
          "event": {
              "promptEnd": {
                  "promptName": prompt_name
              }
          }
      }
  
  @staticmethod
  def session_end():
      return {
          "event": {
              "sessionEnd": {}
          }
      }