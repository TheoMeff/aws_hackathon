# AWS HealthScribe Integration Setup (Updated)

## ⚠️ **IMPORTANT: Choose Your Path**

Based on the AWS documentation review, you have **two options**:

### 🏥 **Option 1: AWS HealthScribe (RECOMMENDED for Clinical Use)**
- **Advanced clinical documentation** with automatic note generation
- **Participant role identification** (CLINICIAN vs PATIENT)
- **Built-in clinical templates** and structured output
- **Automatic PHI handling** and encryption
- **Post-session clinical note generation**

### 🔬 **Option 2: Medical Stream Transcription (Simpler Alternative)**
- **Basic medical transcription** with speaker diarization
- **Medical specialty optimization** 
- **Medical entity extraction**
- **More control over output format**

## 🚀 **Option 1: AWS HealthScribe Setup (Recommended)**

### 1. Dependencies and Permissions

```bash
# Install required packages
pip install amazon-transcribe boto3

# Additional HealthScribe requirements
pip install aiobotocore  # For async AWS operations
```

### IAM Permissions for HealthScribe
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "transcribe:StartMedicalScribeStream",
                "transcribe:CreateMedicalVocabulary",
                "transcribe:ListMedicalVocabularies",
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket",
                "kms:Encrypt",
                "kms:Decrypt",
                "kms:GenerateDataKey"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": "iam:PassRole",
            "Resource": "arn:aws:iam::*:role/HealthScribeServiceRole"
        }
    ]
}
```

### 2. Create HealthScribe Service Role

```bash
# Create the HealthScribe service role
aws iam create-role \
    --role-name HealthScribeServiceRole \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "transcribe.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }'

# Attach required policies
aws iam attach-role-policy \
    --role-name HealthScribeServiceRole \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonTranscribeServiceRole
```

### 3. Environment Configuration

```bash
# HealthScribe Configuration
AWS_REGION=us-east-1
HEALTHSCRIBE_OUTPUT_BUCKET=your-clinical-notes-bucket
HEALTHSCRIBE_KMS_KEY_ID=your-kms-key-id  # Optional
HEALTHSCRIBE_TEMPLATE=primary_care_soap   # Clinical note template
MEDICAL_SPECIALTY=PRIMARYCARE             # PRIMARYCARE, CARDIOLOGY, etc.
CONVERSATION_TYPE=CONVERSATION            # CONVERSATION or DICTATION
```

### 4. S3 Bucket Setup for Clinical Notes

```bash
# Create S3 bucket for clinical note output
aws s3 mb s3://your-clinical-notes-bucket

# Set bucket policy for HealthScribe access
aws s3api put-bucket-policy \
    --bucket your-clinical-notes-bucket \
    --policy '{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "transcribe.amazonaws.com"
                },
                "Action": [
                    "s3:PutObject",
                    "s3:GetObject"
                ],
                "Resource": "arn:aws:s3:::your-clinical-notes-bucket/*"
            }
        ]
    }'
```

### 5. Update Your Code

**Replace your streaming_transcribe.py** with the enhanced HealthScribe implementation above.

**Update s2s_session_manager.py:**

```python
from integration.streaming_transcribe import create_primary_care_scribe, MedicalSpecialty

# Update the _run_transcribe method:
async def _run_transcribe(self):
    """Run HealthScribe with clinical documentation"""
    try:
        # Create HealthScribe client based on use case
        scribe = create_primary_care_scribe(
            audio_queue=self.audio_input_queue,
            region=self.region,
            output_bucket=os.getenv('HEALTHSCRIBE_OUTPUT_BUCKET')
        )
        
        logger.info("Starting HealthScribe clinical documentation")
        
        async for transcript_event in scribe.run():
            if not self.is_active:
                break
            
            # Create enhanced conversation line event
            conversation_event = self._create_clinical_conversation_event(transcript_event)
            await self.output_queue.put(conversation_event)
            
            logger.debug(f"HealthScribe: [{transcript_event['speaker']}] {transcript_event['text']}")
    
    except Exception as e:
        logger.error(f"HealthScribe error: {e}")
    finally:
        logger.info("HealthScribe session ended")

def _create_clinical_conversation_event(self, transcript_data: dict) -> dict:
    """Create enhanced conversation line event with clinical context"""
    return {
        "event": {
            "conversationLine": {
                "lineId": transcript_data.get("segment_id", str(uuid.uuid4())),
                "role": transcript_data.get("speaker", "unknown"),
                "text": transcript_data.get("text", ""),
                "confidence": transcript_data.get("confidence", 0.0),
                "startTime": transcript_data.get("start_time", 0.0),
                "endTime": transcript_data.get("end_time", 0.0),
                "isPartial": transcript_data.get("is_partial", False),
                "channelId": transcript_data.get("channel_id"),
                "sessionId": transcript_data.get("session_id"),
                "items": transcript_data.get("items", []),
                "timestamp": transcript_data.get("timestamp", "")
            }
        },
        "timestamp": int(time.time() * 1000)
    }
```

## 🔬 **Option 2: Medical Stream Transcription Setup**

If you prefer the simpler medical transcription (without HealthScribe):

### Update Environment Variables
```bash
AWS_REGION=us-east-1
MEDICAL_SPECIALTY=PRIMARYCARE  # Required
CONVERSATION_TYPE=CONVERSATION # Required  
MEDICAL_VOCABULARY=clinical-vocab-name  # Optional
ENABLE_PHI_IDENTIFICATION=true
```

### Simplified Implementation
```python
from integration.streaming_transcribe import MedicalSpecialty, ConversationType

# Create basic medical transcriber
def create_medical_transcriber(audio_queue, specialty=MedicalSpecialty.PRIMARYCARE):
    return HealthScribeStreamer(
        audio_queue=audio_queue,
        specialty=specialty,
        conversation_type=ConversationType.CONVERSATION,
        # Don't set clinical_note_template or output_bucket for basic mode
    )
```

## 📊 **Comparison: HealthScribe vs Medical Transcription**

| Feature | HealthScribe | Medical Transcription |
|---------|-------------|----------------------|
| **Clinical Notes** | ✅ Automatic generation | ❌ Manual creation needed |
| **Participant Roles** | ✅ CLINICIAN/PATIENT | ⚠️ Speaker labels only |
| **Medical Entities** | ✅ Advanced extraction | ✅ Basic extraction |
| **Templates** | ✅ Built-in clinical templates | ❌ Not available |
| **PHI Handling** | ✅ Automatic | ✅ Basic identification |
| **Cost** | 💰 Higher | 💰 Lower |
| **Setup Complexity** | 🔧 More complex | 🔧 Simpler |
| **Output Format** | 📄 Structured clinical notes | 📝 Raw transcription |

## 🎯 **Recommendation for Your Use Case**

Based on your MIMIC FHIR integration and clinical focus, I **strongly recommend HealthScribe** because:

1. **Clinical Context**: Automatically generates structured clinical documentation
2. **FHIR Integration**: Output format aligns better with FHIR resources
3. **Participant Roles**: Better integration with your doctor/patient conversation model
4. **Compliance**: Built-in PHI handling and encryption for medical compliance
5. **Future-Proof**: AWS's advanced medical AI platform with ongoing enhancements

## 🔧 **Testing Your Setup**

```python
# Test script for HealthScribe
import asyncio
from integration.streaming_transcribe import create_primary_care_scribe

async def test_healthscribe():
    audio_queue = asyncio.Queue()
    
    scribe = create_primary_care_scribe(
        audio_queue=audio_queue,
        output_bucket="your-test-bucket"
    )
    
    print("HealthScribe initialized successfully")
    
    # In production, audio_queue would receive real audio data
    # For testing, this verifies the setup works
    
if __name__ == "__main__":
    asyncio.run(test_healthscribe())
```

## ⚠️ **Important Notes**

1. **HealthScribe Availability**: Currently available in limited AWS regions
2. **Costs**: HealthScribe is more expensive but provides much more value
3. **Templates**: You can create custom clinical note templates
4. **Integration**: HealthScribe output integrates better with your MIMIC FHIR workflow

Choose **HealthScribe** for production clinical use, or **Medical Transcription** for simpler transcription needs.
