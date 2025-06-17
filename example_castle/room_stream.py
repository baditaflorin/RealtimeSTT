#!/usr/bin/env python3
"""
Room-level transcription server for heritage building documentation.
Combines RealtimeSTT with WebSocket broadcasting to central hub.
"""

import asyncio
import websockets
import json
import time
import ssl
import argparse
import threading
from datetime import datetime
from RealtimeSTT import AudioToTextRecorder
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RoomTranscriptionServer:
    def __init__(self, room_name, central_hub_url, whisper_model="base"):
        self.room_name = room_name
        self.central_hub_url = central_hub_url
        self.websocket = None
        self.is_connected = False
        self.loop = None  # To store the main event loop
        self.shutdown_event = threading.Event() # Use a thread-safe event
        self.transcription_counter = 0

        # Initialize RealtimeSTT with a callback for partial results.
        # The final result is handled by the blocking recorder.text() call in a separate thread.
        self.recorder = AudioToTextRecorder(
            model=whisper_model,
            language="en",
            silero_sensitivity=0.6,
            webrtc_sensitivity=3,
            post_speech_silence_duration=1.0,
            min_length_of_recording=0.5,
            min_gap_between_recordings=0.25,
            enable_realtime_transcription=True,
            on_realtime_transcription_update=self.on_partial_transcription,
            realtime_processing_pause=0.2,
        )

    def on_partial_transcription(self, text):
        """ Callback for partial transcription results (from a background thread) """
        if not text.strip() or not self.loop or self.shutdown_event.is_set():
            return

        logger.debug(f"Partial transcription: {text}")
        payload = {
            "type": "partial",
            "room": self.room_name,
            "text": text.strip(),
            "timestamp": time.time(),
            "id": self.transcription_counter + 1
        }
        asyncio.run_coroutine_threadsafe(self.send_to_hub(payload), self.loop)

    def on_final_transcription(self, text):
        """ Callback for final transcription results (from a background thread) """
        if not text.strip() or not self.loop or self.shutdown_event.is_set():
            return

        self.transcription_counter += 1
        logger.info(f"[{self.room_name}] Final: {text}")
        payload = {
            "type": "final",
            "room": self.room_name,
            "text": text.strip(),
            "timestamp": time.time(),
            "id": self.transcription_counter,
            "confidence": 0.95
        }
        asyncio.run_coroutine_threadsafe(self.send_to_hub(payload), self.loop)

    async def connect_to_hub(self):
        """Connect to central hub with retry logic"""
        max_retries = 10
        retry_delay = 2

        # Create an SSL context that does not verify the certificate
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        for attempt in range(max_retries):
            if self.shutdown_event.is_set(): return False
            try:
                # Pass the custom SSL context to the connect call
                self.websocket = await websockets.connect(self.central_hub_url, ssl=ssl_context)
                self.is_connected = True
                logger.info(f"Connected to central hub at {self.central_hub_url}")

                await self.send_to_hub({
                    "type": "connection",
                    "room": self.room_name,
                    "status": "connected",
                    "timestamp": time.time()
                })
                return True

            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 30)

        logger.error("Failed to connect to central hub. Running in offline mode.")
        self.is_connected = False
        return False

    async def send_to_hub(self, data):
        """Send data to central hub with error handling"""
        if not self.is_connected or not self.websocket:
            self.store_locally(data)
            return

        try:
            await self.websocket.send(json.dumps(data))
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection to hub lost. Will attempt to reconnect on next message.")
            self.is_connected = False
            self.store_locally(data)
        except Exception as e:
            logger.error(f"Error sending to hub: {e}")
            self.store_locally(data)

    def store_locally(self, data):
        """Store transcription locally as backup"""
        filename = f"{self.room_name}_backup_{datetime.now().strftime('%Y%m%d')}.jsonl"
        try:
            with open(filename, 'a') as f:
                f.write(json.dumps(data) + '\n')
        except Exception as e:
            logger.error(f"Failed to store transcription locally: {e}")

    def transcription_worker(self):
        """Worker thread to handle blocking transcription calls."""
        try:
            with self.recorder:
                while not self.shutdown_event.is_set():
                    try:
                        self.recorder.text(self.on_final_transcription)
                    except Exception as e:
                        if not self.shutdown_event.is_set():
                            logger.error(f"Error in transcription worker: {e}", exc_info=True)
                        break
        except Exception as e:
            if not self.shutdown_event.is_set():
                logger.error(f"AudioToTextRecorder failed to start: {e}", exc_info=True)

    async def start_transcription(self):
        """Start the transcription service and keep it running."""
        self.loop = asyncio.get_running_loop()
        logger.info(f"Starting transcription for room: {self.room_name}")

        await self.connect_to_hub()

        logger.info(f"Room '{self.room_name}' transcription service started.")
        logger.info("Speak into the microphone. Press Ctrl+C to stop.")

        worker_thread = threading.Thread(target=self.transcription_worker, daemon=True)
        worker_thread.start()

        while worker_thread.is_alive() and not self.shutdown_event.is_set():
            await asyncio.sleep(0.5)

    async def shutdown(self):
        """Clean shutdown"""
        if self.shutdown_event.is_set():
            return

        logger.info("Shutting down transcription service...")
        self.shutdown_event.set()

        # Give the recorder a moment to release the microphone
        await asyncio.sleep(0.5)

        if self.is_connected and self.websocket:
            try:
                await self.send_to_hub({
                    "type": "disconnection",
                    "room": self.room_name,
                    "status": "disconnected",
                    "timestamp": time.time()
                })
                await self.websocket.close()
            except Exception as e:
                logger.warning(f"Error during websocket close: {e}")
        logger.info("Shutdown complete.")

async def main():
    parser = argparse.ArgumentParser(description="Room transcription server")
    parser.add_argument("--room", required=True, help="Room identifier (e.g., 'Hall A')")
    parser.add_argument("--hub-url", default="ws://localhost:9000",
                        help="Central hub WebSocket URL")
    parser.add_argument("--model", default="base",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper model to use")

    args = parser.parse_args()

    server = RoomTranscriptionServer(
        room_name=args.room,
        central_hub_url=args.hub_url,
        whisper_model=args.model
    )

    try:
        await server.start_transcription()
    except KeyboardInterrupt:
        logger.info("User requested shutdown.")
    finally:
        await server.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by user.")
