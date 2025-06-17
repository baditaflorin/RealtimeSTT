#!/usr/bin/env python3
"""
Central hub server for heritage building transcription system.
Receives WebSocket streams from room transcription servers and displays them.
"""

import asyncio
import websockets
import json
import time
from datetime import datetime
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
import threading
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app for web interface
app = Flask(__name__)
app.config['SECRET_KEY'] = 'heritage-transcription-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global state
connected_rooms = {}
transcription_history = {}
room_stats = {}

# HTML template for the display interface
DISPLAY_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Heritage Building Transcription Hub</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.4/socket.io.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a0a;
            color: #ffffff;
            height: 100vh;
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            padding: 1rem;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
        
        .header h1 {
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }
        
        .status-bar {
            display: flex;
            justify-content: center;
            gap: 2rem;
            font-size: 0.9rem;
            opacity: 0.9;
        }
        
        .room-container {
            display: flex;
            height: calc(100vh - 120px);
            gap: 1px;
            background: #333;
        }
        
        .room-panel {
            flex: 1;
            background: #1a1a1a;
            display: flex;
            flex-direction: column;
            border-radius: 8px 8px 0 0;
            overflow: hidden;
        }
        
        .room-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1rem;
            text-align: center;
            position: relative;
        }
        
        .room-header h2 {
            font-size: 1.2rem;
            margin-bottom: 0.5rem;
        }
        
        .room-status {
            font-size: 0.8rem;
            opacity: 0.9;
        }
        
        .connection-indicator {
            position: absolute;
            top: 10px;
            right: 10px;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #ff4444;
        }
        
        .connection-indicator.connected {
            background: #44ff44;
            box-shadow: 0 0 10px #44ff44;
        }
        
        .transcription-area {
            flex: 1;
            padding: 1rem;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            line-height: 1.6;
        }
        
        .transcription-line {
            margin-bottom: 1rem;
            padding: 0.5rem;
            background: rgba(255,255,255,0.05);
            border-radius: 4px;
            border-left: 3px solid #667eea;
            animation: fadeIn 0.3s ease-in;
        }
        
        .transcription-line.partial {
            opacity: 0.7;
            border-left-color: #ffa500;
        }
        
        .timestamp {
            font-size: 0.7rem;
            color: #888;
            margin-bottom: 0.2rem;
        }
        
        .text {
            font-size: 0.9rem;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .controls {
            position: fixed;
            bottom: 20px;
            right: 20px;
            display: flex;
            gap: 10px;
        }
        
        .control-btn {
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            color: white;
            padding: 10px 15px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.8rem;
            transition: all 0.3s ease;
        }
        
        .control-btn:hover {
            background: rgba(255,255,255,0.2);
        }
        
        /* Responsive design */
        @media (max-width: 1024px) {
            .room-container {
                flex-direction: column;
            }
            .room-panel {
                min-height: 300px;
            }
        }
        
        /* Scrollbar styling */
        .transcription-area::-webkit-scrollbar {
            width: 8px;
        }
        
        .transcription-area::-webkit-scrollbar-track {
            background: rgba(255,255,255,0.1);
        }
        
        .transcription-area::-webkit-scrollbar-thumb {
            background: rgba(255,255,255,0.3);
            border-radius: 4px;
        }
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
    
    <div class="room-container" id="roomContainer">
        <!-- Room panels will be dynamically added here -->
    </div>
    
    <div class="controls">
        <button class="control-btn" onclick="clearAll()">Clear All</button>
        <button class="control-btn" onclick="exportTranscriptions()">Export</button>
        <button class="control-btn" onclick="toggleFullscreen()">Fullscreen</button>
    </div>

    <script>
        const socket = io();
        let sessionStartTime = Date.now();
        let totalTranscriptions = 0;
        let rooms = {};
        
        // Update session timer
        setInterval(() => {
            const elapsed = Date.now() - sessionStartTime;
            const hours = Math.floor(elapsed / 3600000);
            const minutes = Math.floor((elapsed % 3600000) / 60000);
            const seconds = Math.floor((elapsed % 60000) / 1000);
            document.getElementById('session-time').textContent = 
                `Session: ${hours.toString().padStart(2,'0')}:${minutes.toString().padStart(2,'0')}:${seconds.toString().padStart(2,'0')}`;
        }, 1000);
        
        // Socket event handlers
        socket.on('room_connected', function(data) {
            console.log('Room connected:', data);
            createRoomPanel(data.room);
            updateRoomStatus(data.room, 'connected');
        });
        
        socket.on('room_disconnected', function(data) {
            console.log('Room disconnected:', data);
            updateRoomStatus(data.room, 'disconnected');
        });
        
        socket.on('transcription_update', function(data) {
            console.log('Transcription:', data);
            updateTranscription(data);
            
            if (data.type === 'final') {
                totalTranscriptions++;
                document.getElementById('total-transcriptions').textContent = 
                    `Transcriptions: ${totalTranscriptions}`;
            }
        });
        
        function createRoomPanel(roomName) {
            if (rooms[roomName]) return; // Already exists
            
            const container = document.getElementById('roomContainer');
            const panel = document.createElement('div');
            panel.className = 'room-panel';
            panel.id = `room-${roomName.replace(/\\s+/g, '-')}`;
            
            panel.innerHTML = `
                <div class="room-header">
                    <div class="connection-indicator" id="status-${roomName.replace(/\\s+/g, '-')}"></div>
                    <h2>${roomName}</h2>
                    <div class="room-status" id="stats-${roomName.replace(/\\s+/g, '-')}">
                        Waiting for audio...
                    </div>
                </div>
                <div class="transcription-area" id="transcriptions-${roomName.replace(/\\s+/g, '-')}">
                    <div class="transcription-line">
                        <div class="timestamp">Ready</div>
                        <div class="text">Microphone active, waiting for speech...</div>
                    </div>
                </div>
            `;
            
            container.appendChild(panel);
            rooms[roomName] = {
                panel: panel,
                transcriptionArea: panel.querySelector('.transcription-area'),
                lastTranscriptionId: null
            };
            
            // Update room count
            document.getElementById('total-rooms').textContent = 
                `Rooms: ${Object.keys(rooms).length}`;
        }
        
        function updateRoomStatus(roomName, status) {
            const statusElement = document.getElementById(`status-${roomName.replace(/\\s+/g, '-')}`);
            if (statusElement) {
                statusElement.className = `connection-indicator ${status === 'connected' ? 'connected' : ''}`;
            }
        }
        
        function updateTranscription(data) {
            const roomName = data.room;
            const room = rooms[roomName];
            
            if (!room) {
                createRoomPanel(roomName);
                return updateTranscription(data); // Retry after creating panel
            }
            
            // For partial updates, update the last transcription
            if (data.type === 'partial' && room.lastTranscriptionId === data.id) {
                const lastLine = room.transcriptionArea.lastElementChild;
                if (lastLine && lastLine.classList.contains('partial')) {
                    lastLine.querySelector('.text').textContent = data.text;
                    return;
                }
            }
            
            // Create new transcription line
            const line = document.createElement('div');
            line.className = `transcription-line ${data.type}`;
            line.innerHTML = `
                <div class="timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</div>
                <div class="text">${data.text}</div>
            `;
            
            room.transcriptionArea.appendChild(line);
            room.transcriptionArea.scrollTop = room.transcriptionArea.scrollHeight;
            
            if (data.type === 'final') {
                room.lastTranscriptionId = data.id;
            }
            
            // Update room stats
            const statsElement = document.getElementById(`stats-${roomName.replace(/\\s+/g, '-')}`);
            if (statsElement) {
                if (data.type === 'final') {
                    statsElement.textContent = `Last: ${new Date(data.timestamp * 1000).toLocaleTimeString()}`;
                } else {
                    statsElement.textContent = 'Speaking...';
                }
            }
        }
        
        function clearAll() {
            Object.values(rooms).forEach(room => {
                room.transcriptionArea.innerHTML = `
                    <div class="transcription-line">
                        <div class="timestamp">Cleared</div>
                        <div class="text">Transcriptions cleared</div>
                    </div>
                `;
            });
            totalTranscriptions = 0;
            document.getElementById('total-transcriptions').textContent = 'Transcriptions: 0';
        }
        
        function exportTranscriptions() {
            // Create export data
            const exportData = {
                session_start: new Date(sessionStartTime).toISOString(),
                export_time: new Date().toISOString(),
                rooms: {}
            };
            
            Object.keys(rooms).forEach(roomName => {
                const lines = rooms[roomName].transcriptionArea.querySelectorAll('.transcription-line:not(.partial)');
                exportData.rooms[roomName] = Array.from(lines).map(line => ({
                    timestamp: line.querySelector('.timestamp').textContent,
                    text: line.querySelector('.text').textContent
                }));
            });
            
            // Download as JSON
            const blob = new Blob([JSON.stringify(exportData, null, 2)], {type: 'application/json'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `heritage-transcription-${new Date().toISOString().slice(0,19)}.json`;
            a.click();
            URL.revokeObjectURL(url);
        }
        
        function toggleFullscreen() {
            if (document.fullscreenElement) {
                document.exitFullscreen();
            } else {
                document.documentElement.requestFullscreen();
            }
        }
        
        // Initialize with any pre-existing rooms
        socket.emit('get_room_status');
    </script>
</body>
</html>
"""

class CentralHub:
    def __init__(self, websocket_port=9000, web_port=8000):
        self.websocket_port = websocket_port
        self.web_port = web_port
        self.websocket_server = None

    async def handle_room_connection(self, websocket, path):
        """Handle WebSocket connections from room servers"""
        client_address = websocket.remote_address
        logger.info(f"Room server connected from {client_address}")

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.process_room_message(data)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received: {message}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Room server {client_address} disconnected")
        except Exception as e:
            logger.error(f"Error in room connection: {e}")

    async def process_room_message(self, data):
        """Process messages from room servers"""
        message_type = data.get('type')
        room_name = data.get('room')

        if message_type == 'connection':
            connected_rooms[room_name] = {
                'connected_at': data.get('timestamp'),
                'last_seen': time.time(),
                'status': 'connected'
            }
            transcription_history[room_name] = []
            room_stats[room_name] = {'total_transcriptions': 0}

            # Notify web interface
            socketio.emit('room_connected', {'room': room_name})
            logger.info(f"Room '{room_name}' connected")

        elif message_type == 'disconnection':
            if room_name in connected_rooms:
                connected_rooms[room_name]['status'] = 'disconnected'
                socketio.emit('room_disconnected', {'room': room_name})
                logger.info(f"Room '{room_name}' disconnected")

        elif message_type in ['partial', 'final']:
            # Update room last seen
            if room_name in connected_rooms:
                connected_rooms[room_name]['last_seen'] = time.time()

            # Store transcription
            if message_type == 'final':
                transcription_history.setdefault(room_name, []).append(data)
                room_stats.setdefault(room_name, {'total_transcriptions': 0})['total_transcriptions'] += 1

            # Broadcast to web interface
            socketio.emit('transcription_update', data)

            # Log for debugging
            if message_type == 'final':
                logger.info(f"[{room_name}] {data.get('text', '')}")

    def start_websocket_server(self):
        """Start the WebSocket server for room connections"""
        async def run_websocket_server():
            self.websocket_server = await websockets.serve(
                self.handle_room_connection,
                "0.0.0.0",
                self.websocket_port
            )
            logger.info(f"WebSocket server started on port {self.websocket_port}")
            await self.websocket_server.wait_closed()

        # Run WebSocket server in a separate thread
        def start_async_server():
            asyncio.new_event_loop().run_until_complete(run_websocket_server())

        websocket_thread = threading.Thread(target=start_async_server, daemon=True)
        websocket_thread.start()

    def start_web_server(self):
        """Start the Flask web server"""
        @app.route('/')
        def index():
            return render_template_string(DISPLAY_TEMPLATE)

        @socketio.on('get_room_status')
        def handle_room_status_request():
            # Send current room status to newly connected web clients
            for room_name, room_data in connected_rooms.items():
                if room_data['status'] == 'connected':
                    emit('room_connected', {'room': room_name})

        logger.info(f"Starting web server on port {self.web_port}")
        socketio.run(app, host='0.0.0.0', port=self.web_port, debug=False)

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Central transcription hub")
    parser.add_argument("--websocket-port", type=int, default=9000,
                        help="WebSocket port for room connections")
    parser.add_argument("--web-port", type=int, default=8000,
                        help="Web server port for display interface")

    args = parser.parse_args()

    # Create and start central hub
    hub = CentralHub(
        websocket_port=args.websocket_port,
        web_port=args.web_port
    )

    # Start WebSocket server
    hub.start_websocket_server()

    # Start web server (this blocks)
    logger.info("Central Hub starting...")
    logger.info(f"WebSocket endpoint: ws://localhost:{args.websocket_port}")
    logger.info(f"Web interface: http://localhost:{args.web_port}")

    try:
        hub.start_web_server()
    except KeyboardInterrupt:
        logger.info("Central Hub shutting down...")

if __name__ == "__main__":
    main()