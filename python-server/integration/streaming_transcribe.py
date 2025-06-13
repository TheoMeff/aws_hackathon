"""Enhanced AWS Transcribe Medical streaming client with speaker diarization.
Designed for parallel execution with Sonic to provide real-time transcription
with speaker identification for clinical conversations.
"""
from __future__ import annotations

import asyncio
import json
import logging
import base64
from typing import AsyncGenerator, Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Import the AWS Transcribe streaming SDK
try:
    from amazon_transcribe.client import TranscribeStreamingClient
    from amazon_transcribe.handlers import TranscriptResultStreamHandler
    from amazon_transcribe.model import TranscriptEvent, TranscriptResultStream
    TRANSCRIBE_AVAILABLE = True
except ImportError:
    TRANSCRIBE_AVAILABLE = False
    logging.warning("amazon-transcribe package not installed. Install with: pip install amazon-transcribe")

logger = logging.getLogger(__name__)

@dataclass
class TranscriptLine:
    """Represents a line of transcribed speech with speaker information"""
    line_id: str
    speaker: str
    text: str
    confidence: float
    start_time: float
    end_time: float
    is_partial: bool
    timestamp: datetime

class TranscribeEventHandler(TranscriptResultStreamHandler):
    """Custom event handler for processing transcription results"""

    def __init__(self, transcript_result_stream, output_queue: asyncio.Queue, speaker_labels: bool = True):
        super().__init__(transcript_result_stream)
        self.output_queue = output_queue
        self.speaker_labels = speaker_labels
        self.partial_transcript = ""
        self.speaker_map = {}  # Map speaker labels to friendly names

    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        """Handle incoming transcript events"""
        try:
            results = transcript_event.transcript.results

            for result in results:
                if not result.alternatives:
                    continue

                alternative = result.alternatives[0]
                transcript_text = alternative.transcript

                if not transcript_text.strip():
                    continue

                # Extract speaker information if available
                speaker_label = "unknown"
                confidence = getattr(alternative, 'confidence', 0.0)

                if self.speaker_labels and hasattr(result, 'speaker_label'):
                    speaker_label = result.speaker_label
                    # Map to friendly names (Doctor/Patient)
                    speaker_label = self._get_friendly_speaker_name(speaker_label)

                # Extract timing information
                start_time = getattr(result, 'start_time', 0.0)
                end_time = getattr(result, 'end_time', 0.0)
                is_partial = getattr(result, 'is_partial', False)

                # Skip partial results; only emit final transcripts
                if is_partial:
                    continue

                # Create transcript line
                line = TranscriptLine(
                    line_id=f"transcript_{datetime.now().timestamp()}",
                    speaker=speaker_label,
                    text=transcript_text,
                    confidence=confidence,
                    start_time=start_time,
                    end_time=end_time,
                    is_partial=is_partial,
                    timestamp=datetime.now()
                )

                # Send to output queue
                await self.output_queue.put(line)

                logger.debug(f"Transcribed: [{speaker_label}] {transcript_text} (confidence: {confidence:.2f})")

        except Exception as e:
            logger.error(f"Error processing transcript event: {e}")

    def _get_friendly_speaker_name(self, speaker_label: str) -> str:
        """Map AWS speaker labels to friendly names"""
        if speaker_label not in self.speaker_map:
            # Simple mapping - first speaker is doctor, second is patient
            speaker_count = len(self.speaker_map)
            silence_chunk = b'\x00' * 320  # 20 ms of silence at 16 kHz PCM
            if speaker_count == 0:
                friendly_name = "doctor"
            elif speaker_count == 1:
                friendly_name = "patient"
            else:
                friendly_name = f"speaker_{speaker_count + 1}"

            self.speaker_map[speaker_label] = friendly_name
            logger.info(f"Mapped speaker {speaker_label} to {friendly_name}")

        return self.speaker_map[speaker_label]

class TranscribeStreamer:
    """AWS Transcribe streaming client with speaker diarization for clinical conversations"""

    def __init__(self, audio_queue: asyncio.Queue,
                 region: str = "us-east-1",
                 language_code: str = "en-US",
                 sample_rate: int = 16000,
                 enable_speaker_diarization: bool = True,
                 max_speaker_labels: int = 2,
                 medical_vocabulary: Optional[str] = None):
        """
        Initialize the Transcribe streamer

        Args:
            audio_queue: Queue containing PCM audio data
            region: AWS region for Transcribe service
            language_code: Language code for transcription
            sample_rate: Audio sample rate in Hz
            enable_speaker_diarization: Enable speaker identification
            max_speaker_labels: Maximum number of speakers to identify
            medical_vocabulary: Custom medical vocabulary name
        """
        self.audio_queue = audio_queue
        self.region = region
        self.language_code = language_code
        self.sample_rate = sample_rate
        self.enable_speaker_diarization = enable_speaker_diarization
        self.max_speaker_labels = max_speaker_labels
        self.medical_vocabulary = medical_vocabulary

        self.output_queue = asyncio.Queue()
        self._stopped = asyncio.Event()
        self._client = None
        self._stream = None
        self._last_chunk_ts = datetime.now()

        # Audio processing settings
        self.chunk_size = 1024 * 4  # 4KB chunks
        self.audio_buffer = bytearray()

        logger.info(f"TranscribeStreamer initialized: {language_code}, {sample_rate}Hz, diarization={enable_speaker_diarization}")

    async def _initialize_client(self) -> bool:
        """Initialize the Transcribe streaming client"""
        if not TRANSCRIBE_AVAILABLE:
            logger.error("Amazon Transcribe SDK not available")
            return False

        try:
            # Create boto3 session
            session = boto3.Session(region_name=self.region)

            # Test credentials
            try:
                sts = session.client('sts')
                identity = sts.get_caller_identity()
                logger.info(f"AWS authentication successful: {identity.get('Account', 'unknown')}")
            except Exception as e:
                logger.error(f"AWS authentication failed: {e}")
                return False

            # Create Transcribe streaming client
            self._client = TranscribeStreamingClient(region=self.region)
            logger.info("Transcribe streaming client initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Transcribe client: {e}")
            return False

    async def _create_stream(self):
        """Create the transcription stream with medical settings"""
        try:
            # Build stream parameters with correct AWS SDK parameter names (snake_case)
            stream_params = {
                "language_code": self.language_code,
                "media_sample_rate_hz": self.sample_rate,  # Correct parameter name
                "media_encoding": "pcm",
            }

            # Add speaker diarization if enabled (correct parameter names)
            if self.enable_speaker_diarization:
                stream_params["show_speaker_label"] = True
                logger.info(f"Speaker diarization enabled")

            # Add medical vocabulary if specified
            if self.medical_vocabulary:
                stream_params["vocabulary_name"] = self.medical_vocabulary
                logger.info(f"Using medical vocabulary: {self.medical_vocabulary}")

            # Add medical-specific settings with correct parameter names
            stream_params.update({
                "enable_partial_results_stabilization": True,
                "partial_results_stability": "medium",
                "content_identification_type": "PII",  # Identify PII for medical use
            })

            # Start the streaming transcription first to get the stream
            self._stream = await self._client.start_stream_transcription(
                **stream_params
            )

            # Create event handler with the stream's output (result) stream
            handler = TranscribeEventHandler(
                self._stream.output_stream,
                self.output_queue,
                speaker_labels=self.enable_speaker_diarization
            )

            # Assign the handler to the stream
            self._stream.handler = handler

            logger.info("Transcription stream created successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to create transcription stream: {e}")
            return False

    async def _process_audio_data(self):
        """Process audio data from the queue and send to Transcribe"""
        try:
            while not self._stopped.is_set():
                try:
                    # Get audio data from queue with timeout
                    audio_data = await asyncio.wait_for(
                        self.audio_queue.get(),
                        timeout=1.0
                    )

                    if not audio_data or not isinstance(audio_data, dict):
                        continue

                    # Extract audio bytes
                    audio_bytes = audio_data.get('audio_bytes')
                    if not audio_bytes:
                        continue

                    # Decode base64 audio data
                    if isinstance(audio_bytes, str):
                        try:
                            audio_bytes = base64.b64decode(audio_bytes)
                        except Exception as e:
                            logger.error(f"Failed to decode base64 audio: {e}")
                            continue

                    # Add to buffer
                    self.audio_buffer.extend(audio_bytes)

                    # Send chunks to Transcribe when buffer is large enough
                    while len(self.audio_buffer) >= self.chunk_size:
                        chunk = bytes(self.audio_buffer[:self.chunk_size])
                        self.audio_buffer = self.audio_buffer[self.chunk_size:]

                        if self._stream:
                            await self._stream.input_stream.send_audio_event(
                                audio_chunk=chunk
                            )

                except asyncio.TimeoutError:
                    # Send any remaining buffer data
                    if len(self.audio_buffer) > 0 and self._stream:
                        chunk = bytes(self.audio_buffer)
                        self.audio_buffer.clear()
                        await self._stream.input_stream.send_audio_event(
                            audio_chunk=chunk
                        )
                    continue
                except Exception as e:
                    logger.error(f"Error processing audio data: {e}")
                    continue

        except Exception as e:
            logger.error(f"Audio processing error: {e}")
        finally:
            # Send final buffer data
            if len(self.audio_buffer) > 0 and self._stream:
                try:
                    chunk = bytes(self.audio_buffer)
                    await self._stream.input_stream.send_audio_event(
                        audio_chunk=chunk
                    )
                except Exception as e:
                    logger.error(f"Error sending final audio chunk: {e}")

    async def run(self) -> AsyncGenerator[Dict[str, str], None]:
        """
        Main run loop that yields transcription events

        Yields:
            Dict with speaker and text keys for each transcribed segment
        """
        if not await self._initialize_client():
            logger.error("Failed to initialize Transcribe client")
            return

        if not await self._create_stream():
            logger.error("Failed to create transcription stream – check SDK version and parameters")
            return

        logger.info("Starting transcription stream")

        # Start audio processing task
        audio_task = asyncio.create_task(self._process_audio_data())
        logger.info("Audio processing task started")

        # Start result event handler task
        self.result_task = asyncio.create_task(self._stream.handler.handle_events())
        logger.info("Result event handler task started")

        try:
            while not self._stopped.is_set():
                try:
                    # Get transcription results
                    transcript_line = await asyncio.wait_for(
                        self.output_queue.get(),
                        timeout=5.0
                    )

                    # Yield transcript event for S2S integration
                    yield {
                        "speaker": transcript_line.speaker,
                        "text": transcript_line.text,
                        "confidence": transcript_line.confidence,
                        "start_time": transcript_line.start_time,
                        "end_time": transcript_line.end_time,
                        "is_partial": transcript_line.is_partial,
                        "line_id": transcript_line.line_id,
                        "timestamp": transcript_line.timestamp.isoformat()
                    }

                except asyncio.TimeoutError:
                    # Continue listening
                    continue
                except Exception as e:
                    logger.error(f"Error yielding transcript: {e}")
                    continue

        except Exception as e:
            logger.error(f"Transcription run error: {e}")
        finally:
            logger.info("Exiting transcription run loop – initiating stop()")
            await self.stop()

            # Cancel audio processing task
            if not audio_task.done():
                audio_task.cancel()
                try:
                    await audio_task
                except asyncio.CancelledError:
                    pass

            # Cancel result handler task
            if hasattr(self, "result_task") and self.result_task and not self.result_task.done():
                self.result_task.cancel()
                try:
                    await self.result_task
                except asyncio.CancelledError:
                    pass

    async def stop(self):
        """Stop the transcription stream"""
        logger.info("Stopping TranscribeStreamer")
        self._stopped.set()

        if self._stream:
            try:
                # End the input side; ignore errors if already closed
                try:
                    await self._stream.input_stream.end_stream()
                    logger.debug("Input stream ended successfully")
                except Exception as inner:
                    logger.warning(f"Failed to end input stream cleanly: {inner}")

                # Output stream will finish naturally after input closes; no explicit close needed
            except Exception as e:
                logger.error(f"Error stopping stream: {e}")

        # Cancel result handler task if still running
        if hasattr(self, "result_task") and self.result_task and not self.result_task.done():
            self.result_task.cancel()
            try:
                await self.result_task
            except asyncio.CancelledError:
                pass

        logger.info("TranscribeStreamer stopped and resources cleared")
        self._stream = None
        self._client = None

    def get_speaker_mapping(self) -> Dict[str, str]:
        """Get the current speaker label mapping"""
        if hasattr(self, '_stream') and self._stream:
            handler = getattr(self._stream, 'handler', None)
            if handler and hasattr(handler, 'speaker_map'):
                return handler.speaker_map.copy()
        return {}

# Factory function for easy integration
def create_medical_transcriber(audio_queue: asyncio.Queue,
                             enable_diarization: bool = True,
                             region: str = "us-east-1") -> TranscribeStreamer:
    """
    Factory function to create a medical transcription streamer

    Args:
        audio_queue: Queue containing audio data
        enable_diarization: Whether to enable speaker diarization
        region: AWS region

    Returns:
        TranscribeStreamer instance configured for medical use
    """
    return TranscribeStreamer(
        audio_queue=audio_queue,
        region=region,
        language_code="en-US",
        sample_rate=16000,
        enable_speaker_diarization=enable_diarization,
        max_speaker_labels=2,  # Doctor and patient
        medical_vocabulary=None  # Can be set to custom medical vocabulary
    )