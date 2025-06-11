import React from 'react';
import './s2s.css';
import './patient-data.css'
import { Icon, Alert, Button, Modal, Box, SpaceBetween, Container, ColumnLayout, Header, FormField, Select, Textarea, Checkbox } from '@cloudscape-design/components';
import S2sEvent from './helper/s2sEvents';
import Meter from './components/meter';
import S2sEventDisplay from './components/eventDisplay';
import { base64ToFloat32Array } from './helper/audioHelper';
import AudioPlayer from './helper/audioPlayer';

// Deep merge utility for patientData
function deepMerge(target = {}, source = {}) {
  if (Array.isArray(source)) {
    if (!Array.isArray(target)) return [...source];
    const existingIds = new Set(target.map((item) => item && item.id));
    source.forEach((item) => {
      if (item && item.id) {
        if (!existingIds.has(item.id)) target.push(item);
      } else {
        target.push(item);
      }
    });
    return target;
  }
  if (source && typeof source === "object") {
    const merged = { ...(target || {}) };
    Object.keys(source).forEach((key) => {
      merged[key] = deepMerge(merged[key], source[key]);
    });
    return merged;
  }
  return source !== undefined ? source : target;
}

class S2sChatBot extends React.Component {

    constructor(props) {
        super(props);
        this.state = {
            status: "loading", // null, loading, loaded
            alert: null,
            sessionStarted: false,
            showEventJson: false,
            showConfig: false,
            selectedEvent: null,

            chatMessages: {},
            events: [],
            audioChunks: [],
            audioPlayPromise: null,
            includeChatHistory: false,

            promptName: null,
            textContentName: null,
            audioContentName: null,

            showUsage: true,

            // Patient data for FHIR integration
            patientData: {
                demographics: {},
                encounters: [],
                medications: [],
                observations: [],
                conditions: []
            },

            // S2S config items
            configAudioInput: null,
            configSystemPrompt: S2sEvent.DEFAULT_SYSTEM_PROMPT,
            configAudioOutput: S2sEvent.DEFAULT_AUDIO_OUTPUT_CONFIG,
            configVoiceIdOption: { label: "Matthew (en-US)", value: "matthew" },
            configToolUse: JSON.stringify(S2sEvent.DEFAULT_TOOL_CONFIG, null, 2),
            configChatHistory: JSON.stringify(S2sEvent.DEFAULT_CHAT_HISTORY, null, 2),
        };
        this.socket = null;
        this.mediaRecorder = null;
        this.chatMessagesEndRef = React.createRef();
        this.stateRef = React.createRef();  
        this.eventDisplayRef = React.createRef();
        this.meterRef =React.createRef();
        this.audioPlayer = new AudioPlayer();
    }

    componentDidMount() {
        this.stateRef.current = this.state;
        // Initialize audio player early
        this.audioPlayer.start().catch(err => {
            console.error("Failed to initialize audio player:", err);
        });
    }

    componentWillUnmount() {
        this.audioPlayer.stop();
    }


    componentDidUpdate(prevProps, prevState) {
        this.stateRef.current = this.state; 

        if (prevState.chatMessages.length !== this.state.chatMessages.length) {
            this.chatMessagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }
    
    sendEvent(event) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(event));
            event.timestamp = Date.now();

            this.eventDisplayRef.current.displayEvent(event, "out");
        }
    }
    
    cancelAudio() {
        this.audioPlayer.bargeIn();
        this.setState({ isPlaying: false });
    }

    handleIncomingMessage (message) {
        const eventType = Object.keys(message?.event)[0];
        
        // Handle FHIR tool results
        if (eventType === "toolResult") {
            try {
                const content = message.event.toolResult.content;
                if (content) {
                    const result = JSON.parse(content);
                    this.processPatientData(result);
                }
            } catch (error) {
                console.error("Error processing tool result:", error);
            }
            this.eventDisplayRef.current.displayEvent(message, "in");
            return;
        }
        
        const role = message.event[eventType]["role"];
        const content = message.event[eventType]["content"];
        const contentId = message.event[eventType].contentId;
        let stopReason = message.event[eventType].stopReason;
        const contentType = message.event[eventType].type;
        var chatMessages = this.state.chatMessages;

        switch(eventType) {
            case "textOutput": 
                // Detect interruption
                if (role === "ASSISTANT" && content.startsWith("{")) {
                    const evt = JSON.parse(content);
                    if (evt.interrupted === true) {
                        this.cancelAudio()
                    }
                }

                if (chatMessages.hasOwnProperty(contentId)) {
                    chatMessages[contentId].content = content;
                    chatMessages[contentId].role = role;
                    if (chatMessages[contentId].raw === undefined)
                        chatMessages[contentId].raw = [];
                    chatMessages[contentId].raw.push(message);
                }
                this.setState({chatMessages: chatMessages});
                break;
            case "audioOutput":
                try {
                    const base64Data = message.event[eventType].content;
                    const audioData = base64ToFloat32Array(base64Data);
                    this.audioPlayer.playAudio(audioData);
                } catch (error) {
                    console.error("Error processing audio chunk:", error);
                }
                break;
            case "contentStart":
                if (contentType === "TEXT") {
                    var generationStage = "";
                    if (message.event.contentStart.additionalModelFields) {
                        generationStage = JSON.parse(message.event.contentStart.additionalModelFields)?.generationStage;
                    }

                    chatMessages[contentId] =  {
                        "content": "", 
                        "role": role,
                        "generationStage": generationStage,
                        "raw": [],
                    };
                    chatMessages[contentId].raw.push(message);
                    this.setState({chatMessages: chatMessages});
                }
                break;
            case "contentEnd":
                if (contentType === "TEXT") {
                    if (chatMessages.hasOwnProperty(contentId)) {
                        if (chatMessages[contentId].raw === undefined)
                            chatMessages[contentId].raw = [];
                        chatMessages[contentId].raw.push(message);
                        chatMessages[contentId].stopReason = stopReason;
                    }
                    this.setState({chatMessages: chatMessages});
                }
                break;
            case "usageEvent":
                if (this.meterRef.current) { 
                    this.meterRef.current.updateMeter(message);
                    if (this.state.showUsage === false) {
                        this.setState({showUsage: true});
                    }
                }
                break;
            default:
                break;

        }

        this.eventDisplayRef.current.displayEvent(message, "in");
    }

    handlePatientVisualization(message) {
        const eventType = Object.keys(message?.event)[0];
        
        if (eventType === "patientDashboard") {
            const dashboardData = message.event[eventType];
            
            if (dashboardData.dashboard_image) {
                // Display dashboard image
                this.displayPatientDashboard(dashboardData.dashboard_image);
            }
            
            if (dashboardData.voice_summary) {
                // Add voice summary to chat
                this.addVoiceSummaryToChat(dashboardData.voice_summary);
            }
        }
    }
    
    displayPatientDashboard(base64Image) {
        // Create image element and display in the Data View section
        const dataViewContainer = document.querySelector('.data-view-container');
        if (dataViewContainer) {
            dataViewContainer.innerHTML = `
                <div class="patient-dashboard">
                    <h3>Patient Dashboard</h3>
                    <img src="data:image/png;base64,${base64Image}" 
                         alt="Patient Dashboard" 
                         style="max-width: 100%; height: auto;" />
                </div>
            `;
        }
    }
    
    addVoiceSummaryToChat(voiceSummary) {
        // Add to chat messages for voice synthesis
        const contentId = crypto.randomUUID();
        const chatMessages = this.state.chatMessages;
        
        chatMessages[contentId] = {
            "content": voiceSummary,
            "role": "ASSISTANT",
            "type": "patient_summary",
            "raw": []
        };
        
        this.setState({chatMessages: chatMessages});
    }

    handleSessionChange = e => {
        if (this.state.sessionStarted) {
            // End session
            this.endSession();
            this.cancelAudio();
            if (this.meterRef.current) this.meterRef.current.stop();
            this.audioPlayer.start(); 
        }
        else {
            // Start session
            this.setState({
                chatMessages:{}, 
                events: [], 
            });
            if (this.eventDisplayRef.current) this.eventDisplayRef.current.cleanup();
            if (this.meterRef.current) this.meterRef.current.start();
            
            // Init S2sSessionManager
            try {
                if (this.socket === null || this.socket.readyState !== WebSocket.OPEN) {
                    this.connectWebSocket();
                }

                // Start microphone 
                this.startMicrophone();
            } catch (error) {
                console.error('Error accessing microphone: ', error);
            }

        }
        this.setState({sessionStarted: !this.state.sessionStarted});
    }

    connectWebSocket() {
        // Connect to the S2S WebSocket server
        if (this.socket === null || this.socket.readyState !== WebSocket.OPEN) {
            const promptName = crypto.randomUUID();
            const textContentName = crypto.randomUUID();
            const audioContentName = crypto.randomUUID();
            this.setState({
                promptName: promptName,
                textContentName: textContentName,
                audioContentName: audioContentName
            })

            const ws_url = process.env.REACT_APP_WEBSOCKET_URL?process.env.REACT_APP_WEBSOCKET_URL:"ws://localhost:8081"
            this.socket = new WebSocket(ws_url);
            this.socket.onopen = () => {
                console.log("WebSocket connected!");
    
                // Start session events
                this.sendEvent(S2sEvent.sessionStart());

                var audioConfig = S2sEvent.DEFAULT_AUDIO_OUTPUT_CONFIG;
                audioConfig.voiceId = this.state.configVoiceIdOption.value;
                var toolConfig = this.state.configToolUse?JSON.parse(this.state.configToolUse):S2sEvent.DEFAULT_TOOL_CONFIG;

                this.sendEvent(S2sEvent.promptStart(promptName, audioConfig, toolConfig));

                this.sendEvent(S2sEvent.contentStartText(promptName, textContentName));

                this.sendEvent(S2sEvent.textInput(promptName, textContentName, this.state.configSystemPrompt));
                this.sendEvent(S2sEvent.contentEnd(promptName, textContentName));

                // Chat history
                if (this.state.includeChatHistory) {
                    var chatHistory = JSON.parse(this.state.configChatHistory);
                    if (chatHistory === null) chatHistory = S2sEvent.DEFAULT_CHAT_HISTORY;
                    for (const chat of chatHistory) {
                        const chatHistoryContentName = crypto.randomUUID();
                        this.sendEvent(S2sEvent.contentStartText(promptName, chatHistoryContentName, chat.role));
                        this.sendEvent(S2sEvent.textInput(promptName, chatHistoryContentName, chat.content));
                        this.sendEvent(S2sEvent.contentEnd(promptName, chatHistoryContentName));
                    }
                    
                }

                this.sendEvent(S2sEvent.contentStartAudio(promptName, audioContentName));
              };

            // Handle incoming messages
            this.socket.onmessage = (message) => {
                const event = JSON.parse(message.data);
                this.handleIncomingMessage(event);
            };
        
            // Handle errors
            this.socket.onerror = (error) => {
                this.setState({alert: "WebSocket Error: ", error});
                console.error("WebSocket Error: ", error);
            };
        
            // Handle connection close
            this.socket.onclose = () => {
                console.log("WebSocket Disconnected");
                if (this.state.sessionStarted)
                    this.setState({alert: "WebSocket Disconnected"});
            };
        }
    }
      
    async startMicrophone() {
        try {
            console.log('Starting microphone with enhanced settings...');
            
            // Request microphone access with higher quality settings
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                    sampleRate: 44100,           // Higher sample rate
                    channelCount: 1,             // Mono for better processing
                    sampleSize: 16               // 16-bit samples
                }
            });
            
            console.log('Microphone access granted, initializing audio context...');
            
            // Use a larger buffer size for stability (2048 instead of 512)
            const bufferSize = 2048;
            const targetSampleRate = 16000;
            
            // Initialize audio context with improved latency settings
            const audioContext = new (window.AudioContext || window.webkitAudioContext)({
                latencyHint: 'interactive',
                sampleRate: 44100 // Match microphone sample rate
            });
            
            console.log(`Audio context created: ${audioContext.sampleRate}Hz`);
            
            // Create analyzer to detect voice activity
            const analyser = audioContext.createAnalyser();
            analyser.fftSize = 1024;
            analyser.smoothingTimeConstant = 0.8;
            
            // Create processing chain
            const source = audioContext.createMediaStreamSource(stream);
            const processor = audioContext.createScriptProcessor(bufferSize, 1, 1);
            
            // Connect audio nodes
            source.connect(analyser);
            analyser.connect(processor);
            processor.connect(audioContext.destination);
            
            // Variables to track silence detection
            let silenceStart = null;
            let isSpeaking = false;
            const silenceThreshold = 0.01; // Adjust based on testing
            const silenceTimeout = 1500;   // 1.5 seconds of silence before we consider speech ended
            
            // Audio processing function
            processor.onaudioprocess = async (e) => {
                if (!this.state.sessionStarted) return;
                
                // Get audio data
                const inputBuffer = e.inputBuffer;
                const inputData = inputBuffer.getChannelData(0);
                
                // Measure audio level
                let sum = 0;
                for (let i = 0; i < inputData.length; i++) {
                    sum += Math.abs(inputData[i]);
                }
                const average = sum / inputData.length;
                
                // Voice activity detection
                if (average > silenceThreshold) {
                    // Speech detected
                    silenceStart = null;
                    isSpeaking = true;
                } else if (isSpeaking) {
                    // Potential end of speech
                    if (!silenceStart) silenceStart = Date.now();
                    else if (Date.now() - silenceStart > silenceTimeout) {
                        // Reset silence detection - long pause detected
                        silenceStart = null;
                        isSpeaking = false;
                    }
                }
                
                try {
                    // Create resampling context
                    const offlineContext = new OfflineAudioContext({
                        numberOfChannels: 1,
                        length: Math.ceil(inputBuffer.duration * targetSampleRate),
                        sampleRate: targetSampleRate
                    });
                    
                    // Prepare buffer for resampling
                    const offlineSource = offlineContext.createBufferSource();
                    const monoBuffer = offlineContext.createBuffer(1, inputBuffer.length, inputBuffer.sampleRate);
                    monoBuffer.copyToChannel(inputData, 0);
                    
                    offlineSource.buffer = monoBuffer;
                    offlineSource.connect(offlineContext.destination);
                    offlineSource.start(0);
                    
                    // Perform resampling
                    const renderedBuffer = await offlineContext.startRendering();
                    const resampled = renderedBuffer.getChannelData(0);
                    
                    // Convert to Int16 PCM (16-bit)
                    const buffer = new ArrayBuffer(resampled.length * 2);
                    const pcmData = new DataView(buffer);
                    
                    for (let i = 0; i < resampled.length; i++) {
                        const s = Math.max(-1, Math.min(1, resampled[i]));
                        pcmData.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
                    }
                    
                    // Convert to base64 for transmission
                    let binary = '';
                    for (let i = 0; i < pcmData.byteLength; i++) {
                        binary += String.fromCharCode(pcmData.getUint8(i));
                    }
                    
                    const currentState = this.stateRef.current;
                    if (currentState && currentState.promptName && currentState.audioContentName) {
                        const event = S2sEvent.audioInput(
                            currentState.promptName,
                            currentState.audioContentName,
                            btoa(binary)
                        );
                        this.sendEvent(event);
                    }
                } catch (err) {
                    console.error('Error processing audio chunk:', err);
                }
            };
            
            // Set up cleanup handler
            window.audioCleanup = () => {
                console.log('Cleaning up audio resources...');
                processor.disconnect();
                analyser.disconnect();
                source.disconnect();
                stream.getTracks().forEach(track => track.stop());
                audioContext.close().catch(e => console.error('Error closing audio context:', e));
            };
            
            // For backup recording in case the processor misses something
            this.mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm;codecs=opus',
                audioBitsPerSecond: 128000
            });
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.state.audioChunks.push(event.data);
                }
            };
            
            // Set data available event timing to 1 second for regular updates
            this.mediaRecorder.start(1000);
            
            this.setState({ sessionStarted: true });
            console.log('Enhanced microphone recording started successfully');
            
        } catch (error) {
            console.error('Failed to initialize microphone:', error);
            this.setState({ 
                alert: `Microphone error: ${error.message || 'Unable to access microphone'}`,
                sessionStarted: false
            });
        }
    }

    // Process incoming patient data from FHIR tools
    processPatientData(result) {
        // If backend already sent aggregated data
        if (result && result.patientData) {
            this.setState((prev) => ({
                patientData: deepMerge({ ...prev.patientData }, result.patientData),
            }));
            return;
        }
        // Legacy fallback handling for individual resource arrays/bundles
        let patientData = { ...this.state.patientData };
        
        // Process patient demographics
        if (Array.isArray(result) && result.length > 0 && result[0].resourceType === "Patient") {
            patientData.demographics = result[0];
            console.log("Patient demographics loaded:", patientData.demographics);
        }
        
        // Process patient encounters
        if (Array.isArray(result) && result.length > 0 && result[0].resourceType === "Encounter") {
            patientData.encounters = result;
            console.log(`Loaded ${result.length} encounters`);
        }
        
        // Process medications
        if (Array.isArray(result) && result.length > 0 && result[0].resourceType === "MedicationRequest") {
            patientData.medications = result;
            console.log(`Loaded ${result.length} medications`);
        }
        
        // Process observations (vital signs, lab results)
        if (Array.isArray(result) && result.length > 0 && result[0].resourceType === "Observation") {
            patientData.observations = result;
            console.log(`Loaded ${result.length} observations`);
        }
        
        // Process conditions
        if (Array.isArray(result) && result.length > 0 && result[0].resourceType === "Condition") {
            patientData.conditions = result;
            console.log(`Loaded ${result.length} conditions`);
        }
        
        // Handle raw FHIR Bundle responses
        if (!Array.isArray(result) && result.resourceType === "Bundle" && Array.isArray(result.entry)) {
            console.log("Processing FHIR Bundle response");
            result.entry.forEach(entry => {
                const resource = entry.resource;
                if (!resource) return;
                
                switch(resource.resourceType) {
                    case "Patient":
                        patientData.demographics = resource;
                        console.log("Patient demographics loaded from bundle");
                        break;
                    case "Encounter":
                        patientData.encounters.push(resource);
                        break;
                    case "MedicationRequest":
                        patientData.medications.push(resource);
                        break;
                    case "Observation":
                        patientData.observations.push(resource);
                        break;
                    case "Condition":
                        patientData.conditions.push(resource);
                        break;
                    default:
                        console.log(`Unhandled resource type in bundle: ${resource.resourceType}`);
                }
            });
        }
        
        // Update state with new data
        this.setState((prev) => ({ patientData: deepMerge({ ...prev.patientData }, patientData) }));
    }
    
    // Format patient data for display
    renderPatientData() {
        const { patientData } = this.state;
        const demographics = (patientData.demographics && typeof patientData.demographics === 'object') ? patientData.demographics : {};
        const { clinical_summary = {}, data_counts = {}, encounters = [], medications = [], observations = [], conditions = [] } = patientData;

        if (!demographics.patient_id) {
            return (
                <div className="placeholder">
                    No patient data yet. Start with <em>"Find patient John Smith"</em>.
                </div>
            );
        }

        return (
            <div className="patient-data">
                {/* Patient Demographics */}
                <div className="patient-section">
                    <h3>Demographics</h3>
                    <div className="patient-info">
                        <p><strong>Name:</strong> {demographics.name || `${demographics.family || ''} ${demographics.given?.join(' ') || ''}`}</p>
                        <p><strong>MIMIC ID:</strong> {demographics.mimic_id}</p>
                        <p><strong>Gender:</strong> {demographics.gender}</p>
                        <p><strong>Birth Date:</strong> {demographics.birth_date}</p>
                        {demographics.age && <p><strong>Age:</strong> {demographics.age}</p>}
                    </div>
                </div>
                {/* Encounters */}
                {encounters.length > 0 && (
                    <div className="patient-section">
                        <h3>Recent Encounters ({encounters.length})</h3>
                        <div className="patient-list">
                            {encounters.slice(0, 5).map((encounter, index) => (
                                <div key={index} className="patient-item">
                                    <p><strong>Date:</strong> {encounter.period?.start}</p>
                                    <p><strong>Class:</strong> {encounter.class?.code}</p>
                                    <p><strong>Type:</strong> {encounter.type?.[0]?.text || "Not specified"}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
                {/* Medications */}
                {medications.length > 0 && (
                    <div className="patient-section">
                        <h3>Medications ({medications.length})</h3>
                        <div className="patient-list">
                            {medications.slice(0, 5).map((med, index) => (
                                <div key={index} className="patient-item">
                                    <p><strong>Medication:</strong> {med.medicationCodeableConcept?.text || "Unknown"}</p>
                                    <p>
                                        <strong>Status:</strong>
                                        <span className={`status-badge status-${med.status === 'active' ? 'active' : med.status === 'completed' ? 'completed' : 'unknown'}`}>
                                            {med.status}
                                        </span>
                                    </p>
                                    <p><strong>Dosage:</strong> {med.dosageInstruction?.[0]?.text || "Not specified"}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
                {/* Conditions */}
                {conditions.length > 0 && (
                    <div className="patient-section">
                        <h3>Conditions ({conditions.length})</h3>
                        <div className="patient-list">
                            {conditions.slice(0, 5).map((condition, index) => (
                                <div key={index} className="patient-item">
                                    <p><strong>Condition:</strong> {condition.code?.text || "Unknown"}</p>
                                    <p>
                                        <strong>Status:</strong>
                                        <span className={`status-badge status-${condition.clinicalStatus?.coding?.[0]?.code === 'active' ? 'active' : condition.clinicalStatus?.coding?.[0]?.code === 'resolved' ? 'completed' : 'unknown'}`}>
                                            {condition.clinicalStatus?.coding?.[0]?.code || "Unknown"}
                                        </span>
                                    </p>
                                    <p><strong>Onset:</strong> {condition.onsetDateTime || "Not specified"}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
                {/* Observations */}
                {observations.length > 0 && (
                    <div className="patient-section">
                        <h3>Observations ({observations.length})</h3>
                        <div className="patient-list">
                            {observations.slice(0, 5).map((obs, index) => (
                                <div key={index} className="patient-item">
                                    <p><strong>{obs.code?.text || "Observation"}:</strong> {obs.valueQuantity ? `${obs.valueQuantity.value} ${obs.valueQuantity.unit}` : (obs.valueString || "Not recorded")}</p>
                                    <p><strong>Date:</strong> {obs.effectiveDateTime || "Unknown"}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        );
    }
    
    endSession() {
        if (this.socket) {
            // Close microphone
            if (this.mediaRecorder && this.state.sessionStarted) {
                this.mediaRecorder.stop();
                console.log('Microphone recording stopped');
            }

            // Close S2sSessionManager
            this.sendEvent(S2sEvent.contentEnd(this.state.promptName, this.state.audioContentName));
            this.sendEvent(S2sEvent.promptEnd(this.state.promptName));
            this.sendEvent(S2sEvent.sessionEnd());

            // Close websocket
            this.socket.close();

            this.setState({sessionStarted: false});
        }
  
    }
    render() {
        return (
            <div className="s2s">
                {this.state.alert !== null && this.state.alert.length > 0?
                <div><Alert statusIconAriaLabel="Warning" type="warning">
                {this.state.alert}
                </Alert><br/></div>:<div/>}
                <div className='top'>
                    <div className='action'>
                        <Button variant='primary' onClick={this.handleSessionChange}>
                            <Icon name={this.state.sessionStarted?"microphone-off":"microphone"} />&nbsp;&nbsp;
                            {this.state.sessionStarted?"End Conversation":"Start Conversation"}
                        </Button>
                        <div className='chathistory'>
                            <Checkbox checked={this.state.includeChatHistory} onChange={({ detail }) => this.setState({includeChatHistory: detail.checked})}>Include chat history</Checkbox>
                            <div className='desc'>You can view sample chat history in the settings.</div>
                        </div>
                    </div>
                    {this.state.showUsage && <Meter ref={this.meterRef}/>}
                    <div className='setting'>
                        <Button onClick={()=> 
                            this.setState({
                                showConfig: true, 
                            })
                        }>
                            <Icon name="settings"/>
                        </Button>
                        
                    </div>
                </div>
                <br/>
                <ColumnLayout columns={3}>
                    <Container header={
                        <Header variant="h2">Conversation</Header>
                    }>
                    <div className="chatarea">
                        {Object.keys(this.state.chatMessages)
                            .filter(key => this.state.chatMessages[key].generationStage !== 'SPECULATIVE')
                            .map((key,index) => {
                             const msg = this.state.chatMessages[key];
                             //if (msg.stopReason === "END_TURN" || msg.role === "USER")
                             return <div className='item'>
                                 <div className={msg.role === "USER"?"user":"bot"} onClick={()=> 
                                         this.setState({
                                             showEventJson: true, 
                                             selectedEvent: {events:msg.raw}
                                         })
                                     }>
                                     <Icon name={msg.role === "USER"?"user-profile":"gen-ai"} />&nbsp;&nbsp;
                                     {msg.content}
                                     {msg.role === "ASSISTANT" && msg.generationStage? ` [${msg.generationStage}]`:""}
                                 </div>
                             </div>
                        })}
                        <div className='endbar' ref={this.chatMessagesEndRef}></div>
                    </div>
                    </Container>
                    <Container header={
                        <Header variant="h2">Patient Data View</Header>
                    }>
                        {this.renderPatientData()}
                    </Container>
                    <Container header={
                        <Header variant="h2">Events</Header>
                    }>
                        <S2sEventDisplay ref={this.eventDisplayRef}></S2sEventDisplay>
                    </Container>
                </ColumnLayout>
                <Modal
                    onDismiss={() => this.setState({showEventJson: false})}
                    visible={this.state.showEventJson}
                    header="Event details"
                    size='medium'
                    footer={
                        <Box float="right">
                        <SpaceBetween direction="horizontal" size="xs">
                            <Button variant="link" onClick={() => this.setState({showEventJson: false})}>Close</Button>
                        </SpaceBetween>
                        </Box>
                    }
                >
                    <div className='eventdetail'>
                    <pre id="jsonDisplay">
                        {this.state.selectedEvent && this.state.selectedEvent.events.map(e=>{
                            const eventType = Object.keys(e?.event)[0];
                            if (eventType === "audioInput" || eventType === "audioOutput")
                                e.event[eventType].content = e.event[eventType].content.substr(0,10) + "...";
                            const ts = new Date(e.timestamp).toLocaleString(undefined, {
                                year: "numeric",
                                month: "2-digit",
                                day: "2-digit",
                                hour: "2-digit",
                                minute: "2-digit",
                                second: "2-digit",
                                fractionalSecondDigits: 3, // Show milliseconds
                                hour12: false // 24-hour format
                            });
                            var displayJson = { ...e };
                            delete displayJson.timestamp;
                            return ts + "\n" + JSON.stringify(displayJson,null,2) + "\n";
                        })}
                    </pre>
                    </div>
                </Modal>
                <Modal  
                    onDismiss={() => this.setState({showConfig: false})}
                    visible={this.state.showConfig}
                    header="Nova S2S settings"
                    size='large'
                    footer={
                        <Box float="right">
                        <SpaceBetween direction="horizontal" size="xs">
                            <Button variant="link" onClick={() => this.setState({showConfig: false})}>Save</Button>
                        </SpaceBetween>
                        </Box>
                    }
                >
                    <div className='config'>
                        <FormField
                            label="Voice Id"
                            stretch={true}
                        >
                            <Select
                                selectedOption={this.state.configVoiceIdOption}
                                onChange={({ detail }) =>
                                    this.setState({configVoiceIdOption: detail.selectedOption})
                                }
                                options={[
                                    { label: "Matthew (en-US)", value: "matthew" },
                                    { label: "Tiffany (en-US)", value: "tiffany" },
                                    { label: "Amy (en-GB)", value: "amy" },
                                ]}
                                />
                        </FormField>
                        <br/>
                        <FormField
                            label="System prompt"
                            description="For the speech model"
                            stretch={true}
                        >
                            <Textarea
                                onChange={({ detail }) => this.setState({configSystemPrompt: detail.value})}
                                value={this.state.configSystemPrompt}
                                placeholder="Speech system prompt"
                                rows={5}
                            />
                        </FormField>
                        <br/>
                        <FormField
                            label="Tool use configuration"
                            description="For external integration such as RAG and Agents"
                            stretch={true}
                        >
                            <Textarea
                                onChange={({ detail }) => this.setState({configToolUse: detail.value})}
                                value={this.state.configToolUse}
                                rows={10}
                                placeholder="{}"
                            />
                        </FormField>
                                <br/>
                        <FormField
                            label="Chat history"
                            description="Sample chat history to resume conversation"
                            stretch={true}
                        >
                            <Textarea
                                onChange={({ detail }) => this.setState({configChatHistory: detail.value})}
                                value={this.state.configChatHistory}
                                rows={15}
                                placeholder="{}"
                            />
                        </FormField>
                    </div>
                </Modal>
                <br/>
            </div>
        );
    }
}

export default S2sChatBot;