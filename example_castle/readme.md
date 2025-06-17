# Heritage Building Transcription System Setup Guide

## ⚠️ **Important Notes**

### Multiprocessing Protection
RealtimeSTT uses multiprocessing, so **all Python scripts must include** the `if __name__ == '__main__':` protection. This is already included in the provided scripts.

### macOS Microphone Permissions
On macOS, you'll need to grant microphone permissions to Terminal or your Python IDE when first running the transcription.

### SSL/HTTPS Security
The system now runs with SSL/HTTPS encryption for secure communications. Self-signed certificates are included for immediate use.

## 📋 **System Requirements**

### Central Hub Machine
- **CPU**: 4+ cores (any modern processor)
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 50GB+ for transcription storage
- **Network**: Ethernet + WiFi capabilities
- **OS**: macOS, Linux, or Windows

### Room Laptops (per room)
- **CPU**: 6+ cores (M1 Pro/Max, Ryzen 5 5600U, i5-1240P)
- **RAM**: 16GB minimum for real-time transcription
- **Storage**: 20GB+ for models and cache
- **Audio**: Built-in mic or USB audio interface
- **Network**: WiFi 6 or Ethernet capability
- **OS**: macOS, Linux (Windows with WSL)

### Mobile Devices (NEW)
- **Requirements**: Any modern smartphone/tablet with:
    - Chrome, Safari, or Edge browser
    - Working microphone
    - WiFi connection to local network
    - Web Speech API support (most modern browsers)

## 🔧 **Installation Steps**

### 1. Install Dependencies

#### On All Machines:
```bash
# Install Python 3.9+ and pip
python3 --version  # Should be 3.9+

# Create virtual environment
python3 -m venv heritage-transcription
source heritage-transcription/bin/activate  # On Windows: heritage-transcription\\Scripts\\activate

# Install required packages
pip install --upgrade pip
pip install RealtimeSTT
pip install websockets
pip install flask flask-socketio
pip install numpy scipy torch torchaudio
```

#### macOS Additional Setup:
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install audio dependencies
brew install portaudio ffmpeg
```

#### Linux Additional Setup:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3-dev portaudio19-dev ffmpeg espeak espeak-data libespeak1 libespeak-dev

# CentOS/RHEL
sudo yum install python3-devel portaudio-devel ffmpeg espeak espeak-devel
```

### 2. Pre-Download Models (NEW - Recommended)
Use the included download script to cache models before deployment:
```bash
python3 download_models.py

# This will download:
# - Whisper models (base, small)
# - Silero VAD models (standard and ONNX versions)
# Models are cached in ~/.cache/
```

### 3. SSL Certificate Setup (NEW)
The system includes self-signed SSL certificates for secure communication:
- `cert.pem` - SSL certificate
- `key.pem` - Private key

To generate your own certificates:
```bash
# Generate a self-signed certificate valid for 1 year
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

### 4. Network Configuration

#### Router Setup (Offline Network)
```bash
# Example configuration for isolated heritage building network
Network Name: HeritageTranscription
IP Range: 192.168.100.0/24 (or any private range)
Gateway: 192.168.100.1
DHCP Range: 192.168.100.10 - 192.168.100.50

# The system will auto-detect local IP addresses
# No need to configure static IPs unless preferred
```

#### Firewall Rules
```bash
# Allow WebSocket traffic on port 9000 (now WSS)
# Allow Web interface on port 8000 (now HTTPS)
# Allow SSH for remote management (optional)
```

## 🚀 **Deployment Instructions**

### 1. Set Up Central Hub

#### Create project directory:
```bash
mkdir heritage-transcription-hub
cd heritage-transcription-hub

# Copy all required files:
# - central_hub.py
# - room_stream.py
# - cert.pem
# - key.pem
# - start_system.sh
# - download_models.py
# - templates/mobile.html (create templates directory)
# - static/mobile_app.js (create static directory)
```

#### Start Central Hub:
```bash
source heritage-transcription/bin/activate
python central_hub.py --websocket-port 9000 --web-port 8000

# Or simply use the deployment script:
./start_system.sh hub
```

#### Access interfaces:
- **Main Dashboard**: `https://[HUB_IP]:8000` (accept self-signed cert warning)
- **Mobile Client**: `https://[HUB_IP]:8000/mobile`
- The system will display the correct URLs when starting

### 2. Set Up Room Laptops

#### On each room laptop:
```bash
mkdir heritage-room-transcription
cd heritage-room-transcription
# Copy room_stream.py to this directory

source heritage-transcription/bin/activate

# Test audio input
python3 -c "import pyaudio; print('Audio devices:', [pyaudio.PyAudio().get_device_info_by_index(i)['name'] for i in range(pyaudio.PyAudio().get_device_count())])"
```

#### Start room transcription:
```bash
# The system will auto-detect the hub IP and use secure WebSocket (WSS)
# Room 1 (Hall A)
./start_system.sh room "Hall A" base

# Room 2 (Conference Room)
./start_system.sh room "Conference Room" base

# Room 3 (Workshop)
./start_system.sh room "Workshop" small

# If connecting to a specific hub IP:
./start_system.sh room "Hall A" base 192.168.23.231
```

### 3. Mobile Device Setup (NEW)

#### Quick Setup:
1. Connect mobile device to the same network as the hub
2. Open browser and navigate to: `https://[HUB_IP]:8000/mobile`
3. Accept the self-signed certificate warning
4. Enter a room name (e.g., "Mobile Tour Guide")
5. Hub IP is auto-filled with the current server
6. Tap "Start Transcribing"

#### Mobile Features:
- Uses browser's built-in speech recognition (no app install needed)
- Real-time transcription preview
- Automatic reconnection handling
- Works on iOS Safari, Android Chrome, and modern mobile browsers

## 🎛️ **Configuration Options**

### RealtimeSTT Settings (Adjust in room_stream.py)
```python
# For noisy heritage building environments
silero_sensitivity=0.4        # Lower = less sensitive to noise
webrtc_sensitivity=2          # 1-3, lower = less sensitive

# For quiet, echoey spaces
silero_sensitivity=0.7        # Higher = more sensitive
webrtc_sensitivity=3          # Higher = more sensitive
post_speech_silence_duration=1.5  # Longer pause before stopping

# For rapid conversation
min_gap_between_recordings=0.1     # Very quick response
post_speech_silence_duration=0.8   # Shorter pause
```

### Model Selection Guide
```python
# Performance vs Accuracy trade-off
models = {
    "tiny":   {"size": "39 MB",  "speed": "32x real-time", "quality": "Basic"},
    "base":   {"size": "142 MB", "speed": "16x real-time", "quality": "Good"},
    "small":  {"size": "466 MB", "speed": "6x real-time",  "quality": "Better"},
    "medium": {"size": "1.5 GB", "speed": "2x real-time",  "quality": "High"},
    "large":  {"size": "2.9 GB", "speed": "1x real-time",  "quality": "Highest"}
}
```

## 🔍 **Testing & Validation**

### 1. Network Connectivity Test
```bash
# Check system status to see current IP
./start_system.sh status

# From room laptop, test central hub connection (now HTTPS)
ping [HUB_IP_FROM_STATUS]
curl -k https://[HUB_IP_FROM_STATUS]:8000  # -k flag for self-signed cert
```

### 2. Audio Input Test
```bash
# Test microphone on room laptop
python3 -c "
import pyaudio
import wave
print('Recording 5 seconds of audio...')
# Record and play back to verify audio input
"
```

### 3. SSL Certificate Test
```bash
# Check certificate details
openssl x509 -in cert.pem -text -noout

# Test secure WebSocket connection
python3 -c "
import websockets
import ssl
import asyncio

async def test():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    uri = 'wss://localhost:9000'
    async with websockets.connect(uri, ssl=ssl_context) as ws:
        print('SSL connection successful!')

asyncio.run(test())
"
```

### 4. Mobile Client Test
1. Open `https://[HUB_IP]:8000/mobile` on phone
2. Accept certificate warning
3. Grant microphone permissions when prompted
4. Start transcribing and verify text appears on main dashboard

### 5. End-to-End Test
```bash
# Start central hub
./start_system.sh hub
# Note the HTTPS URLs shown

# In another terminal, start room server
./start_system.sh room "Test Room"

# On mobile device, access https://[HUB_IP]:8000/mobile
# Start mobile transcription

# Speak into microphone/phone
# Check web interface at https://[HUB_IP]:8000
# Verify transcriptions from both sources appear
```

## 🚨 **Troubleshooting Guide**

### Common Issues & Solutions

#### "SSL Certificate Warning in Browser"
```bash
# This is expected with self-signed certificates
# Click "Advanced" and "Proceed to site" (Chrome)
# Or "Show Details" and "visit this website" (Safari)
# For production, use Let's Encrypt or proper certificates
```

#### "Mobile Speech Recognition Not Working"
```bash
# Check browser compatibility:
# - iOS: Use Safari 14.5+
# - Android: Use Chrome 25+
# - Grant microphone permissions when prompted
# - Ensure HTTPS connection (required for Web Speech API)
```

#### "WSS Connection Failed"
```bash
# Verify SSL certificates are in place
ls cert.pem key.pem

# Check if using correct protocol (wss:// not ws://)
# Ensure firewall allows port 9000
# Try connecting with certificate verification disabled
```

#### "No module named 'RealtimeSTT'"
```bash
pip install RealtimeSTT
# If fails, try: pip install --upgrade setuptools wheel
```

#### "PortAudio not found"
```bash
# macOS: brew install portaudio
# Ubuntu: sudo apt install portaudio19-dev
# Windows: pip install pyaudio-binary
```

#### "Models not loading quickly"
```bash
# Pre-download models using the provided script
python3 download_models.py

# This caches models in ~/.cache/huggingface/hub/
# and ~/.cache/torch/hub/
```

### Performance Monitoring
```bash
# Monitor resource usage
htop  # Linux/macOS
# Activity Monitor on macOS
# Task Manager on Windows

# Check network traffic
netstat -i  # Network interface statistics
iftop       # Real-time network monitoring

# Monitor HTTPS connections
netstat -an | grep 8000  # Check web connections
netstat -an | grep 9000  # Check WebSocket connections
```

## 📊 **Expected Performance**

### Typical Resource Usage (per room laptop)
- **CPU**: 15-40% (depending on model size)
- **RAM**: 2-6GB (depending on model)
- **Network**: <1 Mbps (text-only transmission)
- **Storage**: 500MB-3GB (model files)

### Mobile Client Performance
- **CPU Usage**: Minimal (uses browser's native speech API)
- **Network**: <100 Kbps per device
- **Battery Impact**: Low-moderate (similar to video call)
- **Accuracy**: Depends on browser implementation and ambient noise

### Latency Expectations
- **Voice Activity Detection**: <100ms
- **Transcription Processing**: 0.5-2 seconds
- **Network Transmission**: <50ms local network
- **Mobile Speech Recognition**: 0.5-1 second
- **Total End-to-End**: 1-3 seconds

## 💾 **Data Backup & Export**

### Automatic Backup
The system automatically saves:
- Real-time transcription logs in JSON format
- Local backup files if network connection fails
- Session export capability via web interface

### Manual Export
```bash
# Export all transcriptions via HTTPS (note the -k flag for self-signed cert)
curl -k https://[HUB_IP]:8000/export > session_export.json

# Or use the "Export" button in web interface
```

### Data Format
```json
{
  "session_start": "2025-06-17T10:00:00Z",
  "export_time": "2025-06-17T14:30:00Z",
  "rooms": {
    "Hall A": [
      {
        "timestamp": "10:15:23",
        "text": "Welcome to the heritage building tour..."
      }
    ],
    "Mobile Tour Guide": [
      {
        "timestamp": "10:16:45", 
        "text": "And here we see the original architecture..."
      }
    ]
  }
}
```

## 🔒 **Security Considerations**

### SSL/TLS Encryption
- All web traffic uses HTTPS
- All WebSocket connections use WSS
- Self-signed certificates included for immediate use
- For production, replace with proper certificates

### Network Isolation
- System designed for offline/isolated networks
- No internet connectivity required after setup
- All processing happens locally

### Mobile Security
- No data stored on mobile devices
- Microphone permissions required only during use
- All transcriptions sent directly to hub

This completes your enhanced heritage building transcription system setup with SSL security and mobile device support!

```bash
codexgigantus --ignore-file chatgpt.txt --ignore-dir heritage-transcription >chatgpt.txt
```