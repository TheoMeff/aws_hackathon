#!/usr/bin/env python3
"""
Simple Medical Transcription Proxy using streaming_transcribe.py
Real AWS Transcribe Medical streaming with speaker diarization
"""

import asyncio
import json
import logging
import websockets
import os
from typing import Dict, Any
from integration.streaming_transcribe import create_medical_transcriber

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleTranscribeProxy:
    """Simple medical transcription proxy using streaming_transcribe.py"""

    def __init__(self, region: str = None):
        self.region = region or os.getenv('AWS_REGION', 'us-east-1')
        self.active_sessions = {}
        self.audio_queues = {}

        # Set AWS credentials from environment
        self.aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.aws_session_token = os.getenv('AWS_SESSION_TOKEN')

        logger.info(f"Simple Transcribe Proxy initialized for region: {self.region}")

        if not self.aws_access_key_id:
            logger.warning("No AWS credentials found in environment variables")

    async def handle_websocket_connection(self, websocket):
        """Handle incoming WebSocket connections"""
        logger.info("🔗 New transcription WebSocket connection")

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._handle_message(websocket, data)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                    await self._send_error(websocket, "Invalid JSON format")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
                    await self._send_error(websocket, f"Message handling error: {str(e)}")

        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            # Clean up any active sessions for this connection
            await self._cleanup_connection(websocket)

    async def _handle_message(self, websocket, data: Dict[str, Any]):
        """Handle incoming WebSocket messages"""
        message_type = data.get('type')

        if message_type == 'start_transcription':
            await self._start_transcription(websocket, data)
        elif message_type == 'audio_chunk':
            await self._handle_audio_chunk(websocket, data)
        elif message_type == 'stop_transcription':
            await self._stop_transcription(websocket, data)
        else:
            logger.warning(f"Unknown message type: {message_type}")
            await self._send_error(websocket, f"Unknown message type: {message_type}")

    async def _start_transcription(self, websocket, data: Dict[str, Any]):
        """Start a new transcription session"""
        # Handle both direct parameters and nested config object
        config = data.get('config', data)
        session_id = config.get('session_id', f"session_{asyncio.get_event_loop().time()}")
        language = config.get('language', 'en-US')
        use_medical = config.get('use_medical', True)  # Default to medical transcription

        logger.info(f"🚀 Starting transcription: {session_id}")
        logger.info(f"   Language: {language}, Medical: {use_medical}")

        try:
            # Create audio queue for this session
            audio_queue = asyncio.Queue()
            self.audio_queues[session_id] = audio_queue

            # Create medical transcriber
            transcriber = create_medical_transcriber(
                audio_queue=audio_queue,
                enable_diarization=True,  # Enable speaker diarization
                region=self.region
            )

            # Store the session
            self.active_sessions[session_id] = {
                'transcriber': transcriber,
                'websocket': websocket,
                'task': None
            }

            # Start the transcription task
            task = asyncio.create_task(self._run_transcription(session_id, transcriber, websocket))
            self.active_sessions[session_id]['task'] = task

            # Send success response
            await websocket.send(json.dumps({
                'type': 'transcription_started',
                'session_id': session_id,
                'status': 'success'
            }))

            logger.info(f"✅ Transcription session {session_id} started")

        except Exception as e:
            logger.error(f"❌ Failed to start transcription: {e}")
            await self._send_error(websocket, f"Failed to start transcription: {str(e)}")

    async def _run_transcription(self, session_id: str, transcriber, websocket):
        """Run the transcription stream"""
        try:
            logger.info(f"🎯 Starting transcription stream for session {session_id}")

            async for transcript_event in transcriber.run():
                if session_id not in self.active_sessions:
                    break

                # Send transcript result to client
                await websocket.send(json.dumps({
                    'type': 'transcription_result',
                    'session_id': session_id,
                    'transcript': transcript_event.get('text', ''),
                    'speaker': transcript_event.get('speaker', 'unknown'),
                    'confidence': transcript_event.get('confidence', 0.0),
                    'is_partial': transcript_event.get('is_partial', False),
                    'start_time': transcript_event.get('start_time', 0.0),
                    'end_time': transcript_event.get('end_time', 0.0),
                    'timestamp': transcript_event.get('timestamp', ''),
                    'is_real': True
                }))

                logger.debug(f"📝 [{transcript_event.get('speaker', 'unknown')}] {transcript_event.get('text', '')}")

        except Exception as e:
            logger.error(f"❌ Transcription stream error for {session_id}: {e}")
            await self._send_error(websocket, f"Transcription error: {str(e)}")
        finally:
            logger.info(f"🛑 Transcription stream ended for session {session_id}")

    async def _handle_audio_chunk(self, websocket, data: Dict[str, Any]):
        """Handle incoming audio data"""
        session_id = data.get('session_id')
        audio_data = data.get('audio_data')

        if not session_id or session_id not in self.active_sessions:
            logger.warning(f"Audio chunk for unknown session: {session_id}")
            return

        if not audio_data:
            logger.warning(f"Empty audio data for session: {session_id}")
            return

        try:
            # Get the audio queue for this session
            audio_queue = self.audio_queues.get(session_id)
            if audio_queue:
                # Put audio data in queue for the transcriber
                await audio_queue.put({
                    'audio_bytes': audio_data,
                    'timestamp': asyncio.get_event_loop().time()
                })

        except Exception as e:
            logger.error(f"Error handling audio chunk: {e}")

    async def _stop_transcription(self, websocket, data: Dict[str, Any]):
        """Stop a transcription session"""
        session_id = data.get('session_id')

        if session_id not in self.active_sessions:
            logger.warning(f"Stop request for unknown session: {session_id}")
            return

        logger.info(f"🛑 Stopping transcription session: {session_id}")

        try:
            session = self.active_sessions[session_id]

            # Stop the transcriber
            if session['transcriber']:
                await session['transcriber'].stop()

            # Cancel the task
            if session['task'] and not session['task'].done():
                session['task'].cancel()
                try:
                    await session['task']
                except asyncio.CancelledError:
                    pass

            # Clean up
            del self.active_sessions[session_id]
            if session_id in self.audio_queues:
                del self.audio_queues[session_id]

            # Send confirmation
            await websocket.send(json.dumps({
                'type': 'transcription_stopped',
                'session_id': session_id,
                'status': 'success'
            }))

            logger.info(f"✅ Transcription session {session_id} stopped")

        except Exception as e:
            logger.error(f"Error stopping transcription: {e}")
            await self._send_error(websocket, f"Error stopping transcription: {str(e)}")

    async def _send_error(self, websocket, error_message: str):
        """Send error message to client"""
        try:
            await websocket.send(json.dumps({
                'type': 'error',
                'message': error_message
            }))
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

    async def _cleanup_connection(self, websocket):
        """Clean up sessions for a disconnected WebSocket"""
        sessions_to_remove = []

        for session_id, session in self.active_sessions.items():
            if session['websocket'] == websocket:
                sessions_to_remove.append(session_id)

        for session_id in sessions_to_remove:
            logger.info(f"🧹 Cleaning up session {session_id}")
            try:
                session = self.active_sessions[session_id]

                if session['transcriber']:
                    await session['transcriber'].stop()

                if session['task'] and not session['task'].done():
                    session['task'].cancel()

                del self.active_sessions[session_id]
                if session_id in self.audio_queues:
                    del self.audio_queues[session_id]

            except Exception as e:
                logger.error(f"Error cleaning up session {session_id}: {e}")

async def main():
    """Main entry point"""
    host = os.getenv('TRANSCRIBE_HOST', 'localhost')
    port = int(os.getenv('TRANSCRIBE_PORT', '8083'))

    # Create proxy instance
    proxy = SimpleTranscribeProxy()

    logger.info(f"🚀 Starting Simple Medical Transcribe proxy on {host}:{port}")

    try:
        async with websockets.serve(proxy.handle_websocket_connection, host, port):
            logger.info(f"✅ Simple Medical Transcribe proxy server started")
            logger.info(f"🎯 Using AWS region: {proxy.region}")
            logger.info(f"🔑 AWS credentials configured: {bool(proxy.aws_access_key_id)}")

            # Keep the server running
            await asyncio.Future()  # Run forever

    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())