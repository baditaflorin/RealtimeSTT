# Heritage Building Transcription System Setup Guide

## ⚠️ **Important Notes**

### Multiprocessing Protection
RealtimeSTT uses multiprocessing, so **all Python scripts must include** the `if __name__ == '__main__':` protection. This is already included in the provided scripts.

### macOS Microphone Permissions
On macOS, you'll need to grant microphone permissions to Terminal or your Python IDE when first running the transcription.

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

### 2. Download Whisper Models (Optional - Auto-downloaded on first use)
```bash
# Pre-download models to avoid first-run delays
python3 -c "
from faster_whisper import WhisperModel
print('Downloading base model...')
WhisperModel('base', device='cpu', compute_type='int8')
print('Downloading small model...')
WhisperModel('small', device='cpu', compute_type='int8')
print('Models downloaded successfully!')
"
```

### 3. Network Configuration

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
# Allow WebSocket traffic on port 9000
# Allow Web interface on port 8000
# Allow SSH for remote management (optional)
```

## 🚀 **Deployment Instructions**

### 1. Set Up Central Hub

#### Create project directory:
```bash
mkdir heritage-transcription-hub
cd heritage-transcription-hub

# Save the central_hub.py script
# Save the room_stream.py script
```

#### Start Central Hub:
```bash
source heritage-transcription/bin/activate
python central_hub.py --websocket-port 9000 --web-port 8000

# Or simply use the deployment script:
./start_system.sh hub
```

#### Access web interface:
- The system will display the correct URLs when starting
- Example: `http://192.168.23.231:8000` (your actual IP will be shown)
- Should see empty room panels waiting for connections

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
# The system will auto-detect the hub IP
# Room 1 (Hall A)
./start_system.sh room "Hall A" base

# Room 2 (Conference Room)
./start_system.sh room "Conference Room" base

# Room 3 (Workshop)
./start_system.sh room "Workshop" small

# If connecting to a specific hub IP:
./start_system.sh room "Hall A" base 192.168.23.231
```

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

# From room laptop, test central hub connection
ping [HUB_IP_FROM_STATUS]
curl -I http://[HUB_IP_FROM_STATUS]:8000
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

### 3. End-to-End Test
```bash
# Start central hub
./start_system.sh hub
# Note the IP address and web interface URL shown

# In another terminal, start room server
./start_system.sh room "Test Room"

# Speak into microphone
# Check web interface at the URL shown when hub started
# Verify transcription appears in real-time
```

## 🚨 **Troubleshooting Guide**

### Common Issues & Solutions

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

#### "Connection refused to central hub"
```bash
# Check if central hub is running
netstat -an | grep 9000

# Check firewall settings
sudo ufw allow 9000  # Linux
# macOS: System Preferences > Security & Privacy > Firewall
```

#### "Poor transcription quality"
```bash
# Check microphone levels
# Increase model size: --model small or --model medium
# Adjust RealtimeSTT sensitivity settings
# Verify room acoustics (minimize echo)
```

#### "High CPU usage"
```bash
# Use smaller model: --model tiny or --model base
# Reduce threads in RealtimeSTT configuration
# Close unnecessary applications
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
```

## 📊 **Expected Performance**

### Typical Resource Usage (per room laptop)
- **CPU**: 15-40% (depending on model size)
- **RAM**: 2-6GB (depending on model)
- **Network**: <1 Mbps (text-only transmission)
- **Storage**: 500MB-3GB (model files)

### Latency Expectations
- **Voice Activity Detection**: <100ms
- **Transcription Processing**: 0.5-2 seconds
- **Network Transmission**: <50ms local network
- **Total End-to-End**: 1-3 seconds

### Battery Life (MacBook Pro)
- **With power adapter**: Unlimited operation
- **Battery only**: 6-10 hours (depending on model and usage)
- **Optimization**: Use base model, reduce screen brightness

## 💾 **Data Backup & Export**

### Automatic Backup
The system automatically saves:
- Real-time transcription logs in JSON format
- Local backup files if network connection fails
- Session export capability via web interface

### Manual Export
```bash
# Export all transcriptions (replace IP with your hub IP)
curl http://[HUB_IP]:8000/export > session_export.json

# Or use the "Export" button in web interface
```

This completes your heritage building transcription system setup. The system will now capture, transcribe, and display speech from multiple rooms in real-time, working completely offline once configured.