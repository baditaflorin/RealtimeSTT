#!/usr/bin/env python3
"""
Room-level transcription server for heritage building documentation.
Combines RealtimeSTT with WebSocket broadcasting to central hub.
"""

import asyncio
import websockets
import json
import time
import argparse
import queue
import threading
from datetime import datetime
from RealtimeSTT import AudioToTextRecorder
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RoomTranscriptionServer:
    def __init__(self, room_name, central_hub_url, whisper_model="base"):
        self.room_name = room_name
        self.central_hub_url = central_hub_url
        self.websocket = None
        self.is_connected = False

        # Initialize RealtimeSTT
        self.recorder = AudioToTextRecorder(
            model=whisper_model,
            language="en",
            silero_sensitivity=0.6,  # Adjust based on room acoustics
            webrtc_sensitivity=3,    # Good for heritage building acoustics
            post_speech_silence_duration=1.0,  # Quick response
            min_length_of_recording=1.0,
            min_gap_between_recordings=0.25,
            enable_realtime_transcription=True,
            realtime_processing_pause=0.1,
            on_realtime_transcription_update=self.on_partial_transcription
        )

        # Track transcription state
        self.current_transcription = ""
        self.transcription_counter = 0

    async def connect_to_hub(self):
        """Connect to central hub with retry logic"""
        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                self.websocket = await websockets.connect(self.central_hub_url)
                self.is_connected = True
                logger.info(f"Connected to central hub at {self.central_hub_url}")

                # Send initial connection message
                await self.send_to_hub({
                    "type": "connection",
                    "room": self.room_name,
                    "status": "connected",
                    "timestamp": time.time()
                })
                return True

            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff

        logger.error("Failed to connect to central hub after all retries")
        return False

    async def send_to_hub(self, data):
        """Send data to central hub with error handling"""
        if not self.is_connected or not self.websocket:
            logger.warning("Not connected to hub, storing transcription locally")
            self.store_locally(data)
            return

        try:
            await self.websocket.send(json.dumps(data))
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection to hub lost, attempting reconnect...")
            self.is_connected = False
            await self.connect_to_hub()
        except Exception as e:
            logger.error(f"Error sending to hub: {e}")
            self.store_locally(data)

    def store_locally(self, data):
        """Store transcription locally as backup"""
        filename = f"{self.room_name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        with open(filename, 'a') as f:
            f.write(json.dumps(data) + '\n')

    def on_partial_transcription(self, text):
        """Handle real-time transcription updates"""
        self.current_transcription = text
        # Send partial updates for live display
        asyncio.create_task(self.send_to_hub({
            "type": "partial",
            "room": self.room_name,
            "text": text,
            "timestamp": time.time(),
            "id": self.transcription_counter
        }))

    async def start_transcription(self):
        """Start the transcription service"""
        logger.info(f"Starting transcription for room: {self.room_name}")

        # Connect to central hub
        if not await self.connect_to_hub():
            logger.warning("Proceeding in offline mode")

        logger.info(f"Room {self.room_name} transcription service started")
        logger.info("Speak into the microphone. Press Ctrl+C to stop.")

        # Create a queue for communication between threads
        import queue
        import threading

        self.transcription_queue = queue.Queue()

        def transcription_worker():
            """Worker thread for RealtimeSTT"""
            try:
                def process_final_text(text):
                    if text.strip():  # Only process non-empty transcriptions
                        self.transcription_counter += 1
                        logger.info(f"[{self.room_name}] Final: {text}")

                        # Put transcription in queue for async processing
                        self.transcription_queue.put({
                            "type": "final",
                            "room": self.room_name,
                            "text": text.strip(),
                            "timestamp": time.time(),
                            "id": self.transcription_counter,
                            "confidence": 0.9
                        })

                # Start continuous transcription
                with self.recorder:
                    while True:
                        try:
                            self.recorder.text(process_final_text)
                        except Exception as e:
                            logger.error(f"Transcription error: {e}")
                            break

            except Exception as e:
                logger.error(f"Worker thread error: {e}")

        # Start transcription worker thread
        worker_thread = threading.Thread(target=transcription_worker, daemon=True)
        worker_thread.start()

        try:
            # Main async loop - process transcriptions from queue
            while True:
                try:
                    # Check for new transcriptions (non-blocking)
                    transcription = self.transcription_queue.get_nowait()
                    await self.send_to_hub(transcription)
                except queue.Empty:
                    # No new transcriptions, continue
                    pass
                except Exception as e:
                    logger.error(f"Error processing transcription: {e}")

                # Check connection health
                if self.is_connected and self.websocket:
                    try:
                        pong = await self.websocket.ping()
                        await asyncio.wait_for(pong, timeout=5)
                    except:
                        logger.warning("Hub connection lost, attempting reconnect...")
                        self.is_connected = False
                        await self.connect_to_hub()

                # Small delay to prevent busy loop
                await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("Shutdown requested by user.")
            await self.shutdown()

    async def shutdown(self):
        """Clean shutdown"""
        logger.info("Shutting down transcription service...")

        # Stop recorder
        try:
            if hasattr(self.recorder, 'shutdown'):
                self.recorder.shutdown()
        except Exception as e:
            logger.warning(f"Error shutting down recorder: {e}")

        # Close WebSocket connection
        if self.websocket:
            try:
                await self.send_to_hub({
                    "type": "disconnection",
                    "room": self.room_name,
                    "status": "disconnected",
                    "timestamp": time.time()
                })
                await self.websocket.close()
            except Exception as e:
                logger.warning(f"Error closing websocket: {e}")

        logger.info("Shutdown complete.")

async def main():
    parser = argparse.ArgumentParser(description="Room transcription server")
    parser.add_argument("--room", required=True, help="Room identifier (e.g., 'Hall A')")
    parser.add_argument("--hub-url", default="ws://localhost:9000",
                        help="Central hub WebSocket URL (default: ws://localhost:9000)")
    parser.add_argument("--model", default="base",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper model to use")

    args = parser.parse_args()

    # Create and start transcription server
    server = RoomTranscriptionServer(
        room_name=args.room,
        central_hub_url=args.hub_url,
        whisper_model=args.model
    )

    await server.start_transcription()

if __name__ == "__main__":
    # Required for RealtimeSTT multiprocessing
    asyncio.run(main())