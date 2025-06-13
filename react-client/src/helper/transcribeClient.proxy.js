// Amazon Transcribe Client using Backend Proxy
// Uses boto3/AWS CLI credentials via backend service instead of Cognito

let proxySocket = null;
let isRecording = false;
let sessionReady = false; // NEW: Track if session is ready to receive audio
let audioContext = null;
let mediaStream = null;
let processor = null;
let currentCallback = null;
let sessionId = null;

const PROXY_CONFIG = {
    host: process.env.REACT_APP_TRANSCRIBE_PROXY_HOST || 'localhost',
    port: process.env.REACT_APP_TRANSCRIBE_PROXY_PORT || 8083,  // Use real proxy port
    protocol: process.env.REACT_APP_TRANSCRIBE_PROXY_PROTOCOL || 'ws'
};

/**
 * Start recording with backend proxy (REAL AWS Transcribe)
 * @param {string} language - Language code (e.g., 'en-US')
 * @param {function} callback - Callback for transcription results
 * @param {boolean} useMedical - Whether to use medical transcription
 * @param {string} specialty - Medical specialty
 * @returns {Promise<boolean>}
 */
export const startRecording = async (language, callback, useMedical = false, specialty = 'PRIMARYCARE') => {
    if (!language) {
        console.error('Language parameter is required');
        return false;
    }

    if (isRecording) {
        await stopRecording();
    }

    try {
        console.log(`🚀 Starting REAL AWS Transcribe streaming - Medical: ${useMedical}, Specialty: ${specialty}`);

        // Reset session state
        sessionReady = false;

        // Connect to proxy WebSocket
        await connectToProxy();

        // Set up audio capture (but don't start sending chunks yet)
        await setupAudioCapture();

        // Start transcription session
        sessionId = generateSessionId();
        currentCallback = callback;

        const sessionConfig = {
            session_id: sessionId,
            language: language,
            use_medical: useMedical,
            specialty: specialty
        };

        console.log(`📤 Sending start_transcription for session: ${sessionId}`);
        await sendToProxy({
            type: 'start_transcription',
            config: sessionConfig
        });

        // Wait for session confirmation before marking as recording
        console.log('⏳ Waiting for session confirmation...');
        await waitForSessionReady();

        isRecording = true;
        console.log('✅ REAL AWS Transcribe streaming started successfully');
        return true;

    } catch (error) {
        console.error('❌ Failed to start REAL AWS Transcribe streaming:', error);
        await stopRecording();
        throw error;
    }
};

/**
 * Wait for session ready confirmation
 */
const waitForSessionReady = () => {
    return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
            reject(new Error('Session setup timeout - no confirmation received'));
        }, 10000); // 10 second timeout

        const checkReady = () => {
            if (sessionReady) {
                clearTimeout(timeout);
                resolve();
            } else {
                setTimeout(checkReady, 100); // Check every 100ms
            }
        };
        checkReady();
    });
};

/**
 * Connect to the backend proxy WebSocket
 */
const connectToProxy = async () => {
    return new Promise((resolve, reject) => {
        try {
            const wsUrl = `${PROXY_CONFIG.protocol}://${PROXY_CONFIG.host}:${PROXY_CONFIG.port}`;
            console.log(`🔗 Connecting to AWS Transcribe WebSocket proxy: ${wsUrl}`);

            proxySocket = new WebSocket(wsUrl);

            proxySocket.onopen = () => {
                console.log('✅ Connected to AWS Transcribe WebSocket proxy');
                resolve();
            };

            proxySocket.onmessage = (event) => {
                handleProxyMessage(event.data);
            };

            proxySocket.onerror = (error) => {
                console.error('❌ AWS Transcribe WebSocket proxy error:', error);
                reject(new Error('Failed to connect to AWS Transcribe WebSocket proxy'));
            };

            proxySocket.onclose = () => {
                console.log('🔌 AWS Transcribe WebSocket proxy connection closed');
                sessionReady = false;
                if (isRecording) {
                    console.warn('⚠️ AWS Transcribe proxy connection lost during recording');
                }
            };

        } catch (error) {
            reject(error);
        }
    });
};

/**
 * Handle messages from the proxy
 */
const handleProxyMessage = (data) => {
    try {
        const message = JSON.parse(data);

        console.log(`📨 Received AWS Transcribe message:`, message);

        switch (message.type) {
            case 'transcription_started':
                console.log(`✅ Session confirmed: ${message.session_id}`);
                sessionReady = true;
                break;

            case 'transcription_result':
                if (currentCallback && message.transcript) {
                    // ONLY REAL AWS TRANSCRIBE - NO SIMULATION ALLOWED!
                    console.log(`🎯 REAL AWS TRANSCRIBE [${message.speaker || 'Unknown'}]: "${message.transcript}"`);
                    console.log(`   Confidence: ${(message.confidence * 100).toFixed(1)}%`);
                    console.log(`   Type: ${message.transcription_type || 'unknown'}`);
                    console.log(`   ✅ REAL AWS Transcribe - NO FAKE DATA!`);

                    // Add metadata to the transcription for the UI
                    const enhancedTranscript = message.transcript + ' ';

                    // Call the callback with enhanced information
                    currentCallback(enhancedTranscript, {
                        speaker: message.speaker,
                        confidence: message.confidence,
                        type: message.transcription_type,
                        isReal: true, // ALWAYS TRUE - NO FAKE DATA!
                        timestamp: message.timestamp
                    });
                } else {
                    console.log(`⚠️ Transcription result but no callback or transcript:`, message);
                }
                break;

            case 'error':
                console.error('❌ REAL AWS Transcribe error:', message.message);
                sessionReady = false;
                if (currentCallback) {
                    // Show clear error message to user - NO FAKE DATA EVER!
                    currentCallback(`❌ REAL AWS TRANSCRIBE FAILED: ${message.message}`);
                    currentCallback(`🚫 NO SIMULATION MODE - REAL AWS CREDENTIALS REQUIRED!`);
                    currentCallback(`🔧 Configure valid AWS credentials: aws configure`);
                    currentCallback(`💡 Or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY`);
                    currentCallback(`⚠️  NO FAKE TRANSCRIPTS WILL BE PROVIDED!`);
                }
                // Stop recording immediately on any error
                stopRecording();
                break;

            default:
                console.log('❓ Unknown AWS Transcribe message type:', message.type, message);
        }

    } catch (error) {
        console.error('❌ Error parsing AWS Transcribe message:', error);
    }
};

/**
 * Send message to proxy
 */
const sendToProxy = async (message) => {
    if (proxySocket && proxySocket.readyState === WebSocket.OPEN) {
        proxySocket.send(JSON.stringify(message));
    } else {
        throw new Error('AWS Transcribe WebSocket proxy not connected');
    }
};

/**
 * Set up audio capture and processing
 */
const setupAudioCapture = async () => {
    try {
        console.log('🎵 Setting up AWS Transcribe audio capture...');

        // Request microphone access
        const constraints = {
            video: false,
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
                sampleRate: 44100,
                channelCount: 1,
                sampleSize: 16
            }
        };

        mediaStream = await navigator.mediaDevices.getUserMedia(constraints);

        // Create audio context
        audioContext = new (window.AudioContext || window.webkitAudioContext)({
            latencyHint: 'interactive',
            sampleRate: 44100
        });

        // Create audio processing chain
        const source = audioContext.createMediaStreamSource(mediaStream);
        processor = audioContext.createScriptProcessor(2048, 1, 1);

        // Connect audio nodes
        source.connect(processor);
        processor.connect(audioContext.destination);

        // Set up audio processing
        processor.onaudioprocess = async (event) => {
            // CRITICAL FIX: Only send audio if recording AND session is ready
            if (!isRecording || !sessionReady) return;

            try {
                const inputBuffer = event.inputBuffer;
                const inputData = inputBuffer.getChannelData(0);

                // Resample to 16kHz for Transcribe
                const resampled = await resampleAudio(inputData, 44100, 16000);

                // Convert to PCM
                const pcmData = convertToPCM(resampled);

                // Convert to base64 for transmission
                const base64Audio = arrayBufferToBase64(pcmData);

                // Send to proxy
                await sendToProxy({
                    type: 'audio_chunk',
                    session_id: sessionId,
                    audio_data: base64Audio
                });

            } catch (error) {
                console.error('❌ Error processing REAL audio chunk:', error);
            }
        };

        console.log('✅ REAL audio capture setup complete');

    } catch (error) {
        console.error('❌ Failed to setup REAL audio capture:', error);
        throw error;
    }
};

/**
 * Resample audio data
 */
const resampleAudio = async (inputData, inputSampleRate, outputSampleRate) => {
    const offlineContext = new OfflineAudioContext({
        numberOfChannels: 1,
        length: Math.ceil(inputData.length * outputSampleRate / inputSampleRate),
        sampleRate: outputSampleRate
    });

    const buffer = offlineContext.createBuffer(1, inputData.length, inputSampleRate);
    buffer.copyToChannel(inputData, 0);

    const source = offlineContext.createBufferSource();
    source.buffer = buffer;
    source.connect(offlineContext.destination);
    source.start(0);

    const renderedBuffer = await offlineContext.startRendering();
    return renderedBuffer.getChannelData(0);
};

/**
 * Convert audio to PCM format
 */
const convertToPCM = (audioData) => {
    const buffer = new ArrayBuffer(audioData.length * 2);
    const view = new DataView(buffer);

    for (let i = 0; i < audioData.length; i++) {
        const sample = Math.max(-1, Math.min(1, audioData[i]));
        view.setInt16(i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true);
    }

    return buffer;
};

/**
 * Convert ArrayBuffer to base64
 */
const arrayBufferToBase64 = (buffer) => {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
};

/**
 * Generate unique session ID
 */
const generateSessionId = () => {
    return 'real_session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
};

/**
 * Stop recording and clean up resources
 */
export const stopRecording = async () => {
    console.log('🛑 Stopping REAL transcription via proxy...');
    isRecording = false;
    sessionReady = false; // Reset session ready flag

    try {
        // Stop transcription session
        if (sessionId && proxySocket && proxySocket.readyState === WebSocket.OPEN) {
            await sendToProxy({
                type: 'stop_transcription',
                session_id: sessionId
            });
        }

        // Clean up audio resources
        if (processor) {
            processor.disconnect();
            processor = null;
        }

        if (mediaStream) {
            mediaStream.getTracks().forEach(track => track.stop());
            mediaStream = null;
        }

        if (audioContext && audioContext.state !== 'closed') {
            await audioContext.close();
            audioContext = null;
        }

        // Close proxy connection
        if (proxySocket) {
            proxySocket.close();
            proxySocket = null;
        }

        // Reset state
        sessionId = null;
        currentCallback = null;

        console.log('✅ REAL transcription stopped and resources cleaned up');

    } catch (error) {
        console.error('❌ Error stopping REAL transcription:', error);
    }
};

/**
 * Start medical recording
 */
export const startMedicalRecording = async (language, callback, specialty = 'PRIMARYCARE') => {
    return await startRecording(language, callback, true, specialty);
};

/**
 * Get available medical specialties
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
 */
export const isMedicalTranscriptionAvailable = () => {
    return true; // Available via REAL proxy
};

/**
 * Check proxy connection status
 */
export const isProxyConnected = () => {
    return proxySocket && proxySocket.readyState === WebSocket.OPEN;
};

/**
 * Get proxy configuration
 */
export const getProxyConfig = () => {
    return { ...PROXY_CONFIG };
};