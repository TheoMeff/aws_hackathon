# Amazon Transcribe Integration Setup

This document explains how to set up and use the new Amazon Transcribe functionality that has been added parallel to the Nova Sonic workflow.

## Overview

The Amazon Transcribe integration allows you to:
- Run real-time speech-to-text transcription **parallel** to Nova Sonic
- Use both services simultaneously without interference
- Get immediate text output from Amazon Transcribe
- Clear and manage transcribed text independently
- **Medical transcription support** for healthcare applications with specialized medical vocabularies
- Choose from multiple medical specialties for enhanced medical terminology accuracy

## Current Implementation vs AWS HealthScribe

### Current Implementation (Amazon Transcribe Medical)
- ✅ **Simple setup** - Frontend-only, no backend changes required
- ✅ **Real-time transcription** - Immediate text output
- ✅ **Medical vocabulary** - 6 medical specialties supported
- ✅ **Parallel operation** - Works alongside Nova Sonic
- ❌ **Basic output** - Plain text only
- ❌ **No speaker identification** - Single audio stream
- ❌ **No clinical note generation** - Raw transcription only

### AWS HealthScribe (Advanced Alternative)
- ✅ **Advanced clinical features** - Automatic clinical note generation
- ✅ **Speaker diarization** - Identifies CLINICIAN vs PATIENT
- ✅ **Structured output** - SOAP notes, clinical templates
- ✅ **Multi-channel audio** - Separate clinician/patient streams
- ✅ **S3 integration** - Automatic clinical document storage
- ❌ **Complex setup** - Requires backend service integration
- ❌ **Higher cost** - Premium AWS service
- ❌ **Additional permissions** - IAM roles, S3 buckets required

### Recommendation: Hybrid Approach

For your FHIR healthcare application, consider this upgrade path:

**Phase 1 (Current):** Keep existing Amazon Transcribe Medical
- ✅ Already implemented and working
- ✅ Provides immediate medical transcription value
- ✅ No additional infrastructure required

**Phase 2 (Future Enhancement):** Add HealthScribe Backend Service
- Add Python backend service for HealthScribe processing
- Implement structured clinical note generation
- Integrate with FHIR resources for automatic documentation
- Add speaker role identification for patient encounters

**Implementation Strategy:**
```javascript
// Enhanced transcribe client with HealthScribe support
export const startAdvancedRecording = async (mode, callback) => {
    if (mode === 'healthscribe') {
        // Use backend HealthScribe service
        return await startHealthScribeSession(callback);
    } else {
        // Use current Transcribe Medical (fallback)
        return await startMedicalRecording(language, callback, specialty);
    }
};
```

## Setup Requirements

### 1. AWS Credentials

You need to configure AWS credentials for Amazon Transcribe. Create or update your `.env` file in the `react-client` directory:

```bash
REACT_APP_AWS_REGION=us-east-1
REACT_APP_AWS_IDENTITY_POOL_ID=your-cognito-identity-pool-id
```

### 2. Cognito Identity Pool

Create an Amazon Cognito Identity Pool:

1. Go to AWS Cognito console
2. Create a new Identity Pool
3. Enable "Allow unauthenticated identities"
4. Note the Identity Pool ID
5. Attach a policy to the unauthenticated role with these permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "transcribe:StartStreamTranscriptionWebSocket",
                "transcribe:StartMedicalStreamTranscriptionWebSocket"
            ],
            "Resource": "*"
        }
    ]
}
```

### 3. Install Dependencies

The required npm packages are already added to `package.json`. Run:

```bash
cd react-client
npm install
```

## Usage

### Starting the Application

1. Start the Python backend:
```bash
cd python-server
python server.py --agent mimic_fhir
```

2. Start the React frontend:
```bash
cd react-client
npm start
```

### Using Amazon Transcribe

1. **Choose Transcription Mode**: 
   - **Standard Transcription**: General-purpose speech-to-text
   - **Medical Transcription**: Optimized for medical terminology and healthcare conversations
   - Select medical specialty if using medical mode (Primary Care, Cardiology, Neurology, etc.)

2. **Independent Operation**: You can use Transcribe without starting Nova Sonic
   - Select transcription mode (Standard or Medical)
   - Click "Start Transcribe" button
   - Begin speaking
   - See real-time transcription in the "Amazon Transcribe Output" section

3. **Parallel Operation**: Use both services simultaneously
   - Start Nova Sonic conversation with "Start Conversation"
   - Configure and start Transcribe independently
   - Both services will process audio independently
   - Nova Sonic provides conversational AI responses
   - Transcribe provides pure speech-to-text output

4. **Managing Transcribed Text**:
   - Use "Clear Text" button to reset the transcription
   - View character and word counts in the metadata
   - Text accumulates as you speak
   - Mode and specialty selections are disabled during recording

## Features

### Visual Indicators
- **Green pulsing dot**: Transcribe is actively listening
- **Red dot**: Transcribe is stopped
- **Green background**: Active transcription mode
- **Character/word count**: Displayed when text is present

### Error Handling
- AWS credential errors will show as alerts
- Microphone permission issues are handled gracefully
- Network connectivity problems are reported

### Browser Compatibility
- Works in modern browsers (Chrome, Firefox, Safari, Edge)
- Requires microphone permissions
- Uses Web Audio API for audio processing

## Troubleshooting

### Common Issues

1. **"Unable to start transcription" error**:
   - Check AWS credentials in `.env` file
   - Verify Cognito Identity Pool ID is correct
   - Ensure IAM permissions are properly set

2. **No microphone access**:
   - Check browser permissions for microphone
   - Ensure you're using HTTPS (required for microphone in most browsers)
   - Try refreshing the page and granting permissions again

3. **No transcription appearing**:
   - Speak clearly and at normal volume
   - Check microphone input levels in browser settings
   - Ensure you're speaking in English (default language)

4. **Transcribe button not responding**:
   - Check browser console for JavaScript errors
   - Verify all npm dependencies are installed
   - Restart the React development server

### Language Support

Currently configured for English (en-US). To change language, modify the `language` variable in the `startTranscribe` method in `s2s.js`.

### Medical Specialties

When using Medical Transcription mode, you can select from these specialties for optimized recognition:
- **PRIMARYCARE**: General practice and primary care medicine
- **CARDIOLOGY**: Heart and cardiovascular conditions  
- **NEUROLOGY**: Nervous system and neurological conditions
- **ONCOLOGY**: Cancer and oncology treatments
- **RADIOLOGY**: Medical imaging and diagnostic procedures
- **UROLOGY**: Urinary system and reproductive health

### Medical vs Standard Transcription

**Medical Transcription Benefits:**
- Enhanced recognition of medical terminology
- Better accuracy for drug names, procedures, and conditions
- Optimized for clinical conversations and dictation
- Specialized vocabulary for each medical specialty

**When to Use Medical Transcription:**
- Clinical documentation
- Patient consultations  
- Medical procedure discussions
- Any healthcare-related conversation with technical terminology

## Future Enhancement: AWS HealthScribe Integration

### What is AWS HealthScribe?
AWS HealthScribe is an advanced clinical documentation service that goes beyond basic transcription:

- **Automatic Clinical Note Generation**: Creates structured SOAP notes
- **Speaker Diarization**: Identifies clinician vs patient speech
- **Medical Entity Extraction**: Identifies medications, conditions, procedures
- **Clinical Templates**: Specialty-specific note formats
- **FHIR Integration**: Direct integration with healthcare systems

### Benefits for Your FHIR Application
- **Automated Documentation**: Generate clinical notes automatically
- **FHIR Resource Creation**: Auto-create Encounter, Observation resources
- **Compliance**: Built-in PHI handling and HIPAA compliance
- **Workflow Integration**: Seamless integration with existing FHIR workflows

### Implementation Considerations
- **Backend Service Required**: Python/Node.js service for HealthScribe API
- **Additional AWS Services**: S3 for note storage, IAM roles
- **Cost**: Premium service with per-minute pricing
- **Complexity**: More complex setup and configuration

### Migration Path
1. **Keep Current Implementation**: Continue using Amazon Transcribe Medical
2. **Add Backend Service**: Implement HealthScribe Python service
3. **Gradual Migration**: Offer both options to users
4. **Full Integration**: Replace basic transcription with clinical documentation

## Technical Details

### Architecture
- **Client-side processing**: Transcribe runs entirely in the browser
- **Separate audio streams**: Nova Sonic and Transcribe use independent audio processing
- **AWS SDK v3**: Uses modern AWS SDK with tree-shaking for smaller bundle size
- **Real-time streaming**: Audio is streamed to AWS Transcribe service continuously

### Security
- Uses Cognito Identity Pool for temporary AWS credentials
- No permanent AWS credentials stored in browser
- Audio data is processed by AWS Transcribe (not stored locally)

### Performance
- Minimal impact on Nova Sonic performance
- Efficient audio processing using Web Audio API
- Automatic cleanup of resources when components unmount

## Development Notes

### File Structure
```
react-client/src/
├── helper/
│   ├── awsID.js              # AWS configuration
│   └── transcribeClient.js   # Transcribe functionality
├── transcribe.css            # Transcribe-specific styles
└── s2s.js                    # Main component with integration
```

### State Management
The Transcribe functionality adds these state variables:
- `transcribeStarted`: Boolean indicating if transcription is active
- `transcribeText`: Accumulated transcribed text
- `transcribeAlert`: Error messages for transcription issues

### Integration Points
- Import statements for Transcribe client
- Button in main UI for Transcribe control
- Container component for displaying transcribed text
- Cleanup in component lifecycle methods 