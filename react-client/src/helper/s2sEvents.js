class S2sEvent {
    static DEFAULT_INFER_CONFIG = {
      maxTokens: 1024,
      topP: 0.95,
      temperature: 0.7
    };
  
    static DEFAULT_SYSTEM_PROMPT = "You are a Medical Data Expert. Your task is to retrieve and communicate medical data to the doctor user.";
  
    static DEFAULT_AUDIO_INPUT_CONFIG = {
      mediaType: "audio/lpcm",
      sampleRateHertz: 16000,
      sampleSizeBits: 16,
      channelCount: 1,
      audioType: "SPEECH",
      encoding: "base64"
    };
  
    static DEFAULT_AUDIO_OUTPUT_CONFIG = {
      mediaType: "audio/lpcm",
      sampleRateHertz: 24000,
      sampleSizeBits: 16,
      channelCount: 1,
      voiceId: "matthew",
      encoding: "base64",
      audioType: "SPEECH"
    };
  
    static DEFAULT_TOOL_CONFIG = {
      tools: [
        {
        toolSpec: {
          name: "getPatientData",
          description: "retrieve the patient data",
          inputSchema: {
            json: JSON.stringify({
                "type": "object",
                "properties": {},
                "required": []
                }
            )
          }
        }
      },
      {
        toolSpec: {
          name: "searchByType",
          description: "return every FHIR resource of a given type (Patient, Observation, Encounter …).",
          inputSchema: {
            json: JSON.stringify({
                "type": "object",
                "properties": {
                  "resource_type": {
                    "type": "string",
                    "description": "FHIR resource type to search for (case-sensitive)."
                  }},
                "required": ["resource_type"]
              }
            )
          }
        }
      },
      {
        toolSpec: {
          name: "searchById",
          description: "Fetch a specific FHIR resource when you already know its id.",
          inputSchema: {
            json: JSON.stringify({
                "type": "object",
                "properties": {
                  "resource_id": {
                    "type": "string",
                    "description": "The logical id of the resource."
                  }
                },
                "required": ["resource_id"]
              }
            )
          }
        }
      },
      {
        toolSpec: {
          name: "searchByText",
          description: "Full-text search across all stored FHIR JSON blobs.",
          inputSchema: {
            json: JSON.stringify({
                "type": "object",
                "properties": {
                  "query": {
                    "type": "string",
                    "description": "Free-text search expression."
                  }
                },
                "required": ["query"]
              }
            )
          }
        }
      },
      {
        toolSpec: {
          name: "findPatient",
          description: "Locate patients by name, birth-date or any demographic identifier.",
          inputSchema: {
            json: JSON.stringify({
              "type": "object",
              "properties": {
                "query": {
                  "type": "string",
                  "description": "Name fragment, DOB (YYYY-MM-DD) or MRN to match."
                }
              },
              "required": ["query"]
            })
          }
        }
      },
      {
        toolSpec: {
          name: "getPatientObservations",
          description: "Return raw Observation resources (vitals & labs) for a patient id.",
          inputSchema: {
            json: JSON.stringify({
              "type": "object",
              "properties": {
                "patient_id": {
                  "type": "string",
                  "description": "The logical id of the patient."
                }
              },
              "required": ["patient_id"]
            })
          }
        }
      },
      {
        toolSpec: {
          name: "getPatientEncounters",
          description: "Return raw Encounter resources for a patient id.",
          inputSchema: {
            json: JSON.stringify({
              "type": "object",
              "properties": {
                "patient_id": {
                  "type": "string",
                  "description": "The logical id of the patient."
                }
              },
              "required": ["patient_id"]
            })
          }
        }
      },
      {
        toolSpec: {
          name: "getPatientMedication",
          description: "Return raw Medication resources for a patient id.",
          inputSchema: {
            json: JSON.stringify({
              "type": "object",
              "properties": {
                "patient_id": {
                  "type": "string",
                  "description": "The logical id of the patient."
                }
              },
              "required": ["patient_id"]
            })
          }
        }
      }
    ]
    };

    static DEFAULT_CHAT_HISTORY = [
      {
        "content": "I need to find FHIR resources for patient with id 123456",
        "role": "USER"
      },
      {
        "content": "Hello! I'd like to find FHIR resources for patient with id 123456",
        "role": "ASSISTANT"
      }
    ];
  
    static sessionStart(inferenceConfig = S2sEvent.DEFAULT_INFER_CONFIG) {
      return { event: { sessionStart: { inferenceConfiguration: inferenceConfig } } };
    }
  
    static promptStart(promptName, audioOutputConfig = S2sEvent.DEFAULT_AUDIO_OUTPUT_CONFIG, toolConfig = S2sEvent.DEFAULT_TOOL_CONFIG) {
      return {
        "event": {
          "promptStart": {
            "promptName": promptName,
            "textOutputConfiguration": {
              "mediaType": "text/plain"
            },
            "audioOutputConfiguration": audioOutputConfig,
          
          "toolUseOutputConfiguration": {
            "mediaType": "application/json"
          },
          "toolConfiguration": toolConfig
        }
        }
      }
    }
  
    static contentStartText(promptName, contentName, role="SYSTEM") {
      return {
        "event": {
          "contentStart": {
            "promptName": promptName,
            "contentName": contentName,
            "type": "TEXT",
            "interactive": true,
            "role": role,
            "textInputConfiguration": {
              "mediaType": "text/plain"
            }
          }
        }
      }
    }
  
    static textInput(promptName, contentName, systemPrompt = S2sEvent.DEFAULT_SYSTEM_PROMPT) {
      var evt = {
        "event": {
          "textInput": {
            "promptName": promptName,
            "contentName": contentName,
            "content": systemPrompt
          }
        }
      }
      return evt;
    }
  
    static contentEnd(promptName, contentName) {
      return {
        "event": {
          "contentEnd": {
            "promptName": promptName,
            "contentName": contentName
          }
        }
      }
    }
  
    static contentStartAudio(promptName, contentName, audioInputConfig = S2sEvent.DEFAULT_AUDIO_INPUT_CONFIG) {
      return {
        "event": {
          "contentStart": {
            "promptName": promptName,
            "contentName": contentName,
            "type": "AUDIO",
            "interactive": true,
            "role": "USER",
            "audioInputConfiguration": {
              "mediaType": "audio/lpcm",
              "sampleRateHertz": 16000,
              "sampleSizeBits": 16,
              "channelCount": 1,
              "audioType": "SPEECH",
              "encoding": "base64"
            }
          }
        }
      }
    }
  
    static audioInput(promptName, contentName, content) {
      return {
        event: {
          audioInput: {
            promptName,
            contentName,
            content,
          }
        }
      };
    }
  
    static contentStartTool(promptName, contentName, toolUseId) {
      return {
        event: {
          contentStart: {
            promptName,
            contentName,
            interactive: false,
            type: "TOOL",
            toolResultInputConfiguration: {
              toolUseId,
              type: "TEXT",
              textInputConfiguration: { mediaType: "text/plain" }
            }
          }
        }
      };
    }
  
    static textInputTool(promptName, contentName, content) {
      return {
        event: {
          textInput: {
            promptName,
            contentName,
            content,
            role: "TOOL"
          }
        }
      };
    }
  
    static promptEnd(promptName) {
      return {
        event: {
          promptEnd: {
            promptName
          }
        }
      };
    }
  
    static sessionEnd() {
      return { event: { sessionEnd: {} } };
    }
  }
  export default S2sEvent;