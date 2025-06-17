#!/usr/bin/env python3
"""
Central hub server for heritage building transcription system.
Receives WebSocket streams from room transcription servers and displays them.
"""
import argparse
import asyncio
import websockets
import json
import time
from datetime import datetime
from flask import Flask, render_template, render_template_string, request
from flask_socketio import SocketIO, emit
import threading
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flask app for web interface
app = Flask(__name__)
app.config['SECRET_KEY'] = 'heritage-transcription-secret'
# Initialize SocketIO with the Flask app
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Thread-safe Global State ---
from collections import defaultdict
from threading import Lock

_lock = Lock()
connected_rooms = {}
transcription_history = defaultdict(list)
room_stats = defaultdict(lambda: {'total_transcriptions': 0})


# --- HTML Template ---
DISPLAY_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Heritage Building Transcription Hub</title>
    <!-- Use the latest version of Socket.IO client from a CDN -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.8.1/socket.io.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a0a; color: #ffffff;
            height: 100vh; overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            padding: 1rem; text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
        .header h1 { font-size: 2rem; margin-bottom: 0.5rem; }
        .status-bar { display: flex; justify-content: center; gap: 2rem; font-size: 0.9rem; opacity: 0.9; }
        .room-container { display: flex; height: calc(100vh - 120px); gap: 1px; background: #333; }
        .room-panel {
            flex: 1; background: #1a1a1a; display: flex; flex-direction: column;
            border-radius: 8px 8px 0 0; overflow: hidden;
        }
        .room-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1rem; text-align: center; position: relative;
        }
        .room-header h2 { font-size: 1.2rem; margin-bottom: 0.5rem; }
        .room-status { font-size: 0.8rem; opacity: 0.9; }
        .connection-indicator {
            position: absolute; top: 10px; right: 10px; width: 12px; height: 12px;
            border-radius: 50%; background: #ff4444; transition: all 0.3s ease;
        }
        .connection-indicator.connected { background: #44ff44; box-shadow: 0 0 10px #44ff44; }
        .transcription-area {
            flex: 1; padding: 1rem; overflow-y: auto;
            font-family: 'Courier New', monospace; line-height: 1.6;
        }
        .transcription-line {
            margin-bottom: 1rem; padding: 0.5rem; background: rgba(255,255,255,0.05);
            border-radius: 4px; border-left: 3px solid #667eea;
            animation: fadeIn 0.3s ease-in;
        }
        .transcription-line.partial { opacity: 0.7; border-left-color: #ffa500; }
        .timestamp { font-size: 0.7rem; color: #888; margin-bottom: 0.2rem; }
        .text { font-size: 0.9rem; }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .controls { position: fixed; bottom: 20px; right: 20px; display: flex; gap: 10px; }
        .control-btn {
            background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2);
            color: white; padding: 10px 15px; border-radius: 5px; cursor: pointer;
            font-size: 0.8rem; transition: all 0.3s ease;
        }
        .control-btn:hover { background: rgba(255,255,255,0.2); }
        @media (max-width: 1024px) {
            .room-container { flex-direction: column; }
            .room-panel { min-height: 300px; }
        }
        .transcription-area::-webkit-scrollbar { width: 8px; }
        .transcription-area::-webkit-scrollbar-track { background: rgba(255,255,255,0.1); }
        .transcription-area::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.3); border-radius: 4px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Heritage Building Transcription Hub</h1>
        <div class="status-bar">
            <span id="total-rooms">Rooms: 0</span>
            <span id="session-time">Session: 00:00:00</span>
            <span id="total-transcriptions">Transcriptions: 0</span>
        </div>
    </div>
    <div class="room-container" id="roomContainer"></div>
    <div class="controls">
        <button class="control-btn" onclick="clearAll()">Clear All</button>
        <button class="control-btn" onclick="exportTranscriptions()">Export</button>
        <button class="control-btn" onclick="toggleFullscreen()">Fullscreen</button>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // This code runs after the DOM is fully loaded, ensuring all elements are available.
            const socket = io(); // This will now work correctly.
            let sessionStartTime = Date.now();
            let totalTranscriptions = 0;
            let rooms = {};

            // Helper to create safe IDs for DOM elements
            function getSafeRoomId(roomName) {
                return `room-${roomName.replace(/[^a-zA-Z0-9]/g, '-')}`;
            }

            // --- Socket.IO Event Handlers ---
            socket.on('connect', () => {
                console.log('Successfully connected to hub server!');
                socket.emit('get_room_status');
            });

            socket.on('room_connected', function(data) {
                console.log('Room connected event received:', data.room);
                createRoomPanel(data.room);
                updateRoomStatus(data.room, 'connected');
            });
            
            socket.on('room_disconnected', function(data) {
                console.log('Room disconnected event received:', data.room);
                updateRoomStatus(data.room, 'disconnected');
            });
            
            socket.on('transcription_update', function(data) {
                if (!data.room) return;
                createRoomPanel(data.room); // Create panel if it doesn't exist
                updateTranscription(data);
                if (data.type === 'final') {
                    totalTranscriptions++;
                    document.getElementById('total-transcriptions').textContent = `Transcriptions: ${totalTranscriptions}`;
                }
            });

            // --- DOM Manipulation Functions ---
            function createRoomPanel(roomName) {
                const safeRoomId = getSafeRoomId(roomName);
                if (document.getElementById(safeRoomId)) return; // Already exists
                
                console.log(`Creating panel for ${roomName} with ID ${safeRoomId}`);
                const container = document.getElementById('roomContainer');
                const panel = document.createElement('div');
                panel.className = 'room-panel';
                panel.id = safeRoomId;
                
                panel.innerHTML = `
                    <div class="room-header">
                        <div class="connection-indicator" id="status-${safeRoomId}"></div>
                        <h2>${roomName}</h2>
                        <div class="room-status" id="stats-${safeRoomId}">Waiting for audio...</div>
                    </div>
                    <div class="transcription-area" id="transcriptions-${safeRoomId}">
                        <div class="transcription-line"><div class="text">Microphone active, waiting for speech...</div></div>
                    </div>`;
                
                container.appendChild(panel);
                rooms[roomName] = { panel, transcriptionArea: panel.querySelector('.transcription-area') };
                document.getElementById('total-rooms').textContent = `Rooms: ${Object.keys(rooms).length}`;
            }
            
            function updateRoomStatus(roomName, status) {
                const statusElement = document.getElementById(`status-${getSafeRoomId(roomName)}`);
                if (statusElement) {
                    statusElement.className = `connection-indicator ${status === 'connected' ? 'connected' : ''}`;
                }
            }
            
            function updateTranscription(data) {
                const room = rooms[data.room];
                if (!room) return;

                const transcriptionArea = room.transcriptionArea;
                const isPartial = data.type === 'partial';
                let line;

                if (isPartial) {
                    // For partials, we find and update a line with a specific class.
                    line = transcriptionArea.querySelector('.partial-line-for-' + getSafeRoomId(data.room));
                    if (!line) {
                        line = document.createElement('div');
                        line.className = 'transcription-line partial partial-line-for-' + getSafeRoomId(data.room);
                        transcriptionArea.appendChild(line);
                    }
                } else {
                    // For final results, we remove any lingering partial and create a final line.
                    const partialLine = transcriptionArea.querySelector('.partial-line-for-' + getSafeRoomId(data.room));
                    if (partialLine) partialLine.remove();
                    line = document.createElement('div');
                    line.className = 'transcription-line final';
                    transcriptionArea.appendChild(line);
                }
                
                line.innerHTML = `<div class="timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</div><div class="text">${data.text}</div>`;
                transcriptionArea.scrollTop = transcriptionArea.scrollHeight;
                
                const statsElement = document.getElementById(`stats-${getSafeRoomId(data.room)}`);
                if (statsElement) {
                    statsElement.textContent = isPartial ? 'Speaking...' : `Last: ${new Date(data.timestamp * 1000).toLocaleTimeString()}`;
                }
            }

            // --- Control Button Functions ---
            window.clearAll = function() {
                Object.values(rooms).forEach(room => {
                    room.transcriptionArea.innerHTML = '<div class="transcription-line"><div class="text">Transcriptions cleared</div></div>';
                });
                totalTranscriptions = 0;
                document.getElementById('total-transcriptions').textContent = 'Transcriptions: 0';
            };

            window.exportTranscriptions = function() {
                const exportData = { session_start: new Date(sessionStartTime).toISOString(), export_time: new Date().toISOString(), rooms: {} };
                Object.keys(rooms).forEach(roomName => {
                    const lines = rooms[roomName].transcriptionArea.querySelectorAll('.transcription-line:not(.partial)');
                    exportData.rooms[roomName] = Array.from(lines).map(line => ({
                        timestamp: line.querySelector('.timestamp')?.textContent || '',
                        text: line.querySelector('.text').textContent
                    }));
                });
                const blob = new Blob([JSON.stringify(exportData, null, 2)], {type: 'application/json'});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `heritage-transcription-${new Date().toISOString().slice(0,19)}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            };

            window.toggleFullscreen = function() {
                if (!document.fullscreenElement) {
                    document.documentElement.requestFullscreen();
                } else {
                    document.exitFullscreen();
                }
            };

            // Update session timer
            setInterval(() => {
                const elapsed = Date.now() - sessionStartTime;
                const hours = Math.floor(elapsed / 3600000);
                const minutes = Math.floor((elapsed % 3600000) / 60000);
                const seconds = Math.floor((elapsed % 60000) / 1000);
                document.getElementById('session-time').textContent =
                    `Session: ${String(hours).padStart(2,'0')}:${String(minutes).padStart(2,'0')}:${String(seconds).padStart(2,'0')}`;
            }, 1000);
        });
    </script>
</body>
</html>
"""

# --- Main Server Logic ---

class CentralHub:
    def __init__(self, websocket_port=9000, web_port=8000):
        self.websocket_port = websocket_port
        self.web_port = web_port

    def run(self):
        """Starts both the WebSocket and Web servers."""
        # Run WebSocket server in a separate thread
        websocket_thread = threading.Thread(target=self.start_websocket_server, daemon=True)
        websocket_thread.start()

        # Run Flask-SocketIO server (this is the main blocking call)
        logger.info(f"Starting web server MODIFIED on http://0.0.0.0:{self.web_port}")
        socketio.run(app, host='0.0.0.0', port=self.web_port, debug=False)

    def start_websocket_server(self):
        """Initializes and runs the asyncio WebSocket server."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.websocket_server_logic())

    async def websocket_server_logic(self):
        """The core logic for the websockets server."""
        async def connection_handler(websocket, path=None):
            # Handle both old and new websockets library versions
            if path is None and hasattr(websocket, 'path'):
                path = websocket.path
            elif path is None:
                path = '/'

            client_address = websocket.remote_address
            room_name = None
            logger.info(f"Room client connecting from {client_address} on path '{path}'...")
            try:
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        current_room_name = data.get('room')
                        if not current_room_name:
                            continue

                        if not room_name:
                            room_name = current_room_name
                            logger.info(f"Connection from {client_address} identified as Room: '{room_name}'")

                        self.process_room_message(data)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON from {client_address}: {message}")
                    except Exception as e:
                        logger.error(f"Error processing message from {room_name}: {e}", exc_info=True)
            except websockets.exceptions.ConnectionClosed:
                logger.info(f"Room client {client_address} (Room: {room_name}) disconnected.")
            finally:
                if room_name:
                    self.process_room_message({'type': 'disconnection', 'room': room_name})

        async with websockets.serve(connection_handler, "0.0.0.0", self.websocket_port):
            logger.info(f"WebSocket server listening on port {self.websocket_port}")
            await asyncio.Future()  # Run forever

    def process_room_message(self, data):
        """Processes messages and emits to the web interface via SocketIO."""
        message_type = data.get('type')
        room_name = data.get('room')

        with _lock:
            if message_type == 'connection':
                connected_rooms[room_name] = {'status': 'connected', 'last_seen': time.time()}
            elif message_type == 'disconnection':
                if room_name in connected_rooms:
                    connected_rooms[room_name]['status'] = 'disconnected'
            elif message_type in ['partial', 'final']:
                connected_rooms[room_name] = {'status': 'connected', 'last_seen': time.time()}
                if message_type == 'final':
                    transcription_history[room_name].append(data)
                    room_stats[room_name]['total_transcriptions'] += 1

        # Emit outside the lock to avoid holding it during network I/O
        if message_type == 'connection':
            socketio.emit('room_connected', {'room': room_name})
            logger.info(f"Emitted 'room_connected' for '{room_name}'")
        elif message_type == 'disconnection':
            socketio.emit('room_disconnected', {'room': room_name})
            logger.info(f"Emitted 'room_disconnected' for '{room_name}'")
        elif message_type in ['partial', 'final']:
            socketio.emit('transcription_update', data)


# --- Flask-SocketIO Routes ---
@app.route('/')
def index():
    return render_template_string(DISPLAY_TEMPLATE)

# --- ADD THIS NEW BLOCK ---
@app.route('/mobile')
def mobile():
    """Serves the mobile client page."""
    return render_template('mobile.html')
# --- END OF NEW BLOCK ---

@socketio.on('connect')
def handle_web_connect():
    logger.info(f"Web client connected: {request.sid}")

@socketio.on('get_room_status')
def handle_room_status_request():
    with _lock:
        for room_name, room_data in connected_rooms.items():
            if room_data.get('status') == 'connected':
                emit('room_connected', {'room': room_name})


# --- Main Execution ---
# --- Main Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Central transcription hub")
    parser.add_argument("--websocket-port", type=int, default=9000, help="WebSocket port for room connections")
    parser.add_argument("--web-port", type=int, default=8000, help="Web server port for display interface")
    args = parser.parse_args()

    # Define the SSL context using the generated files
    ssl_context = ('cert.pem', 'key.pem')

    # The CentralHub class doesn't need to change, but how we run socketio does.
    # We will modify the CentralHub's run method slightly.
    class CentralHub:
        def __init__(self, websocket_port=9000, web_port=8000):
            self.websocket_port = websocket_port
            self.web_port = web_port

        def run(self, ssl_context=None): # Add ssl_context parameter
            """Starts both the WebSocket and Web servers."""
            # Run WebSocket server in a separate thread
            websocket_thread = threading.Thread(target=self.start_websocket_server, daemon=True)
            websocket_thread.start()

            # Run Flask-SocketIO server with SSL
            logger.info(f"Starting web server MODIFIED on https://0.0.0.0:{self.web_port}")
            socketio.run(app, host='0.0.0.0', port=self.web_port, debug=False, ssl_context=ssl_context)

        def start_websocket_server(self):
            """Initializes and runs the asyncio WebSocket server."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Create a secure websocket server context
            ssl_server_context = None
            if ssl_context:
                import ssl
                ssl_server_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                ssl_server_context.load_cert_chain(certfile=ssl_context[0], keyfile=ssl_context[1])

            loop.run_until_complete(self.websocket_server_logic(ssl_server_context))

        async def websocket_server_logic(self, ssl_context=None):
            """The core logic for the websockets server."""
            async def connection_handler(websocket, path=None):
                if path is None and hasattr(websocket, 'path'): path = websocket.path
                elif path is None: path = '/'

                client_address = websocket.remote_address
                room_name = None
                logger.info(f"Room client connecting from {client_address} on path '{path}'...")
                try:
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            current_room_name = data.get('room')
                            if not current_room_name: continue
                            if not room_name:
                                room_name = current_room_name
                                logger.info(f"Connection from {client_address} identified as Room: '{room_name}'")
                            self.process_room_message(data)
                        except json.JSONDecodeError: logger.error(f"Invalid JSON from {client_address}: {message}")
                        except Exception as e: logger.error(f"Error processing message from {room_name}: {e}", exc_info=True)
                except websockets.exceptions.ConnectionClosed: logger.info(f"Room client {client_address} (Room: {room_name}) disconnected.")
                finally:
                    if room_name: self.process_room_message({'type': 'disconnection', 'room': room_name})

            async with websockets.serve(connection_handler, "0.0.0.0", self.websocket_port, ssl=ssl_context):
                logger.info(f"Secure WebSocket server listening on port {self.websocket_port}")
                await asyncio.Future()

        def process_room_message(self, data):
            message_type, room_name = data.get('type'), data.get('room')
            with _lock:
                if message_type == 'connection': connected_rooms[room_name] = {'status': 'connected', 'last_seen': time.time()}
                elif message_type == 'disconnection':
                    if room_name in connected_rooms: connected_rooms[room_name]['status'] = 'disconnected'
                elif message_type in ['partial', 'final']:
                    connected_rooms[room_name] = {'status': 'connected', 'last_seen': time.time()}
                    if message_type == 'final':
                        transcription_history[room_name].append(data)
                        room_stats[room_name]['total_transcriptions'] += 1
            if message_type == 'connection':
                socketio.emit('room_connected', {'room': room_name})
                logger.info(f"Emitted 'room_connected' for '{room_name}'")
            elif message_type == 'disconnection':
                socketio.emit('room_disconnected', {'room': room_name})
                logger.info(f"Emitted 'room_disconnected' for '{room_name}'")
            elif message_type in ['partial', 'final']: socketio.emit('transcription_update', data)

    # --- Create Hub and Run ---
    hub = CentralHub(websocket_port=args.websocket_port, web_port=args.web_port)
    try:
        hub.run(ssl_context=ssl_context)
    except KeyboardInterrupt:
        logger.info("\nCentral Hub shutting down...")