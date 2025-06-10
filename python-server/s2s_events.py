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
    return  {
      "event": {
        "sessionEnd": {}
      }
    }
