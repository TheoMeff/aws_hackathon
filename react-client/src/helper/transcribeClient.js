// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

/*
Enhanced Amazon Transcribe Client with Medical Support
Based on AWS SDK for JavaScript version 3 (v3) and Live Meeting Assistant patterns
Supports both standard and medical transcription for FHIR healthcare applications
*/

import { CognitoIdentityClient } from "@aws-sdk/client-cognito-identity";
import { fromCognitoIdentityPool } from "@aws-sdk/credential-provider-cognito-identity";
import { TranscribeStreamingClient } from "@aws-sdk/client-transcribe-streaming";
import MicrophoneStream from "microphone-stream";
import {
    StartStreamTranscriptionCommand,
    StartMedicalStreamTranscriptionCommand
} from "@aws-sdk/client-transcribe-streaming";
import * as awsID from "./awsID.js";

/** @type {MicrophoneStream} */
const MicrophoneStreamImpl = MicrophoneStream.default;

const SAMPLE_RATE = 44100;
/** @type {MicrophoneStream | undefined} */
let microphoneStream = undefined;
/** @type {TranscribeStreamingClient | undefined} */
let transcribeClient = undefined;

// Configuration options for transcription
const TRANSCRIBE_CONFIG = {
  sampleRate: SAMPLE_RATE,
  maxResults: 5,
  partialResultsStability: 'high',
  vocabularyFilterMethod: 'remove', // For PII filtering if needed
  showSpeakerLabel: false,
  enableChannelIdentification: false
};

/**
 * Start recording with enhanced options for medical or standard transcription
 * @param {string} language - Language code (e.g., 'en-US')
 * @param {function} callback - Callback for transcription results
 * @param {boolean} useMedical - Whether to use medical transcription
 * @param {string} specialty - Medical specialty (for medical transcription)
 * @returns {Promise<boolean>}
 */
export const startRecording = async (language, callback, useMedical = false, specialty = 'PRIMARYCARE') => {
  if (!language) {
    console.error('Language parameter is required');
    return false;
  }

  if (microphoneStream || transcribeClient) {
    await stopRecording();
  }

  try {
    await createTranscribeClient();
    await createMicrophoneStream();
    await startStreaming(language, callback, useMedical, specialty);
    return true;
  } catch (error) {
    console.error('Failed to start recording:', error);
    await stopRecording();
    throw error;
  }
};

/**
 * Stop recording and clean up resources
 * @returns {Promise<void>}
 */
export const stopRecording = async () => {
  console.log('Stopping transcription and cleaning up resources...');

  try {
    if (microphoneStream) {
      microphoneStream.stop();
      microphoneStream.destroy();
      microphoneStream = undefined;
    }
  } catch (error) {
    console.error('Error stopping microphone stream:', error);
  }

  try {
    if (transcribeClient) {
      transcribeClient.destroy();
      transcribeClient = undefined;
    }
  } catch (error) {
    console.error('Error destroying transcribe client:', error);
  }

  console.log('Transcription cleanup completed');
};

/**
 * Create and configure the Transcribe client with proper authentication
 * @returns {Promise<void>}
 */
const createTranscribeClient = async () => {
  try {
    if (!awsID.IDENTITY_POOL_ID || awsID.IDENTITY_POOL_ID === 'YOUR_IDENTITY_POOL_ID') {
      throw new Error('AWS Identity Pool ID not configured. Please set REACT_APP_AWS_IDENTITY_POOL_ID in your .env file');
    }

    transcribeClient = new TranscribeStreamingClient({
      region: awsID.REGION,
      credentials: fromCognitoIdentityPool({
        client: new CognitoIdentityClient({ region: awsID.REGION }),
        identityPoolId: awsID.IDENTITY_POOL_ID,
      }),
      maxAttempts: 3, // Retry configuration
      requestHandler: {
        requestTimeout: 5000, // 5 second timeout
      },
    });

    console.log(`Transcribe client created for region: ${awsID.REGION}`);
  } catch (error) {
    console.error('Failed to create Transcribe client:', error);
    throw error;
  }
};

/**
 * Create microphone stream with enhanced audio settings
 * @returns {Promise<void>}
 */
const createMicrophoneStream = async () => {
  try {
    console.log('Requesting microphone access...');

    const constraints = {
      video: false,
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        sampleRate: SAMPLE_RATE,
        channelCount: 1, // Mono audio for better transcription
        sampleSize: 16
      }
    };

    const stream = await window.navigator.mediaDevices.getUserMedia(constraints);

    microphoneStream = new MicrophoneStreamImpl();
    microphoneStream.setStream(stream);

    console.log('Microphone stream created successfully');
  } catch (error) {
    console.error('Failed to create microphone stream:', error);

    if (error.name === 'NotAllowedError') {
      throw new Error('Microphone permission denied. Please allow microphone access and try again.');
    } else if (error.name === 'NotFoundError') {
      throw new Error('No microphone found. Please connect a microphone and try again.');
    } else {
      throw new Error(`Microphone error: ${error.message}`);
    }
  }
};

/**
 * Start streaming transcription with support for both standard and medical transcription
 * @param {string} language - Language code
 * @param {function} callback - Callback for transcription results
 * @param {boolean} useMedical - Whether to use medical transcription
 * @param {string} specialty - Medical specialty for medical transcription
 * @returns {Promise<void>}
 */
const startStreaming = async (language, callback, useMedical = false, specialty = 'PRIMARYCARE') => {
  try {
    console.log(`Starting ${useMedical ? 'medical' : 'standard'} transcription streaming...`);

    let command;

    if (useMedical) {
      // Use Amazon Transcribe Medical for better medical terminology accuracy
      command = new StartMedicalStreamTranscriptionCommand({
        LanguageCode: language,
        MediaEncoding: "pcm",
        MediaSampleRateHertz: SAMPLE_RATE,
        AudioStream: getAudioStream(),
        Specialty: specialty, // PRIMARYCARE, CARDIOLOGY, NEUROLOGY, ONCOLOGY, RADIOLOGY, UROLOGY
        Type: "CONVERSATION", // CONVERSATION or DICTATION
        ShowSpeakerLabel: TRANSCRIBE_CONFIG.showSpeakerLabel,
        EnableChannelIdentification: TRANSCRIBE_CONFIG.enableChannelIdentification,
        NumberOfChannels: 1
      });
    } else {
      // Standard transcription
      command = new StartStreamTranscriptionCommand({
        LanguageCode: language,
        MediaEncoding: "pcm",
        MediaSampleRateHertz: SAMPLE_RATE,
        AudioStream: getAudioStream(),
        ShowSpeakerLabel: TRANSCRIBE_CONFIG.showSpeakerLabel,
        EnableChannelIdentification: TRANSCRIBE_CONFIG.enableChannelIdentification,
        NumberOfChannels: 1,
        PartialResultsStability: TRANSCRIBE_CONFIG.partialResultsStability
      });
    }

    const data = await transcribeClient.send(command);

    console.log('Transcription stream started, processing results...');

    for await (const event of data.TranscriptResultStream) {
      try {
        if (useMedical && event.MedicalTranscriptEvent) {
          // Handle medical transcription results
          const results = event.MedicalTranscriptEvent.Transcript.Results || [];
          for (const result of results) {
            if (!result.IsPartial) {
              const transcript = result.Alternatives[0].Transcript;
              if (transcript && transcript.trim()) {
                console.log('Medical transcription:', transcript);
                callback(`${transcript} `);
              }
            }
          }
        } else if (!useMedical && event.TranscriptEvent) {
          // Handle standard transcription results
          const results = event.TranscriptEvent.Transcript.Results || [];
          for (const result of results) {
            if (!result.IsPartial) {
              const transcript = result.Alternatives[0].Transcript;
              if (transcript && transcript.trim()) {
                console.log('Standard transcription:', transcript);
                callback(`${transcript} `);
              }
            }
          }
        }
      } catch (eventError) {
        console.error('Error processing transcription event:', eventError);
        // Continue processing other events
      }
    }
  } catch (error) {
    console.error('Streaming transcription error:', error);
    throw error;
  }
};

/**
 * Generate audio stream from microphone with enhanced error handling
 * @returns {AsyncGenerator}
 */
const getAudioStream = async function* () {
  if (!microphoneStream) {
    throw new Error("Cannot get audio stream. microphoneStream is not initialized.");
  }

  console.log('Starting audio stream...');
  let chunkCount = 0;

  try {
    for await (const chunk of /** @type {[][]} */ (microphoneStream)) {
      if (chunk && chunk.length > 0 && chunk.length <= SAMPLE_RATE) {
        try {
          const encodedChunk = encodePCMChunk(chunk);
          if (encodedChunk && encodedChunk.length > 0) {
            chunkCount++;
            if (chunkCount % 100 === 0) { // Log every 100 chunks for monitoring
              console.log(`Processed ${chunkCount} audio chunks`);
            }

            yield {
              AudioEvent: {
                AudioChunk: encodedChunk,
              },
            };
          }
        } catch (encodeError) {
          console.error('Error encoding audio chunk:', encodeError);
          // Continue with next chunk rather than failing completely
        }
      }
    }
  } catch (streamError) {
    console.error('Error in audio stream:', streamError);
    throw streamError;
  } finally {
    console.log(`Audio stream ended. Total chunks processed: ${chunkCount}`);
  }
};

const encodePCMChunk = (chunk) => {
  /** @type {Float32Array} */
  const input = MicrophoneStreamImpl.toRaw(chunk);
  let offset = 0;
  const buffer = new ArrayBuffer(input.length * 2);
  const view = new DataView(buffer);
  for (let i = 0; i < input.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, input[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return Buffer.from(buffer);
};

/**
 * Start medical transcription specifically for healthcare applications
 * @param {string} language - Language code (e.g., 'en-US')
 * @param {function} callback - Callback for transcription results
 * @param {string} specialty - Medical specialty (PRIMARYCARE, CARDIOLOGY, NEUROLOGY, ONCOLOGY, RADIOLOGY, UROLOGY)
 * @returns {Promise<boolean>}
 */
export const startMedicalRecording = async (language, callback, specialty = 'PRIMARYCARE') => {
  return await startRecording(language, callback, true, specialty);
};

/**
 * Get list of available medical specialties
 * @returns {Array<string>}
 */
export const getMedicalSpecialties = () => {
  return [
    'PRIMARYCARE',
    'CARDIOLOGY',
    'NEUROLOGY',
    'ONCOLOGY',
    'RADIOLOGY',
    'UROLOGY'
  ];
};

/**
 * Check if medical transcription is available
 * @returns {boolean}
 */
export const isMedicalTranscriptionAvailable = () => {
  return typeof StartMedicalStreamTranscriptionCommand !== 'undefined';
};
