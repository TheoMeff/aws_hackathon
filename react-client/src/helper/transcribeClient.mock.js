// Mock Amazon Transcribe Client for Testing
// This allows testing the UI without AWS credentials

let mockRecording = false;
let mockInterval = null;

const MOCK_MEDICAL_PHRASES = [
    "Patient presents with chest pain and shortness of breath.",
    "Blood pressure is elevated at 140 over 90.",
    "Prescribed lisinopril 10 milligrams daily.",
    "Recommend echocardiogram and stress test.",
    "Patient has history of hypertension and diabetes.",
    "Laboratory results show elevated troponin levels.",
    "Administered nitroglycerin sublingual.",
    "Patient reports improvement in symptoms."
];

const MOCK_STANDARD_PHRASES = [
    "Hello, how are you feeling today?",
    "Can you describe your symptoms?",
    "When did this pain start?",
    "Have you taken any medication?",
    "Let's schedule a follow-up appointment.",
    "Please take care of yourself.",
    "Do you have any questions?",
    "Thank you for coming in today."
];

/**
 * Mock start recording function
 */
export const startRecording = async (language, callback, useMedical = false, specialty = 'PRIMARYCARE') => {
    console.log(`Mock: Starting ${useMedical ? 'medical' : 'standard'} transcription...`);

    if (mockRecording) {
        await stopRecording();
    }

    mockRecording = true;

    // Simulate transcription with mock phrases
    const phrases = useMedical ? MOCK_MEDICAL_PHRASES : MOCK_STANDARD_PHRASES;
    let phraseIndex = 0;

    mockInterval = setInterval(() => {
        if (mockRecording && phraseIndex < phrases.length) {
            const phrase = phrases[phraseIndex];
            console.log(`Mock transcription: ${phrase}`);
            callback(phrase + " ");
            phraseIndex++;
        } else if (phraseIndex >= phrases.length) {
            // Reset to beginning for continuous demo
            phraseIndex = 0;
        }
    }, 3000); // New phrase every 3 seconds

    return true;
};

/**
 * Mock start medical recording function
 */
export const startMedicalRecording = async (language, callback, specialty = 'PRIMARYCARE') => {
    return await startRecording(language, callback, true, specialty);
};

/**
 * Mock stop recording function
 */
export const stopRecording = async () => {
    console.log('Mock: Stopping transcription...');
    mockRecording = false;

    if (mockInterval) {
        clearInterval(mockInterval);
        mockInterval = null;
    }
};

/**
 * Get list of available medical specialties
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
    return true; // Always available in mock mode
};