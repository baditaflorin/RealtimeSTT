#!/bin/bash
# Heritage Building Transcription System Startup Script

set -e

# Configuration
VENV_NAME="heritage-transcription"
HUB_WS_PORT="9000"
HUB_WEB_PORT="8000"

# Auto-detect local IP address
get_local_ip() {
    # Try different methods to get local IP
    local ip=""

    # Method 1: Use route to find default interface IP
    if command -v ip &> /dev/null; then
        ip=$(ip route get 8.8.8.8 2>/dev/null | grep -oP 'src \K\S+' | head -1)
    fi

    # Method 2: Use ifconfig (macOS/BSD)
    if [ -z "$ip" ] && command -v ifconfig &> /dev/null; then
        ip=$(ifconfig | grep -E "inet ([0-9]{1,3}\.){3}[0-9]{1,3}" | grep -v "127.0.0.1" | awk '{print $2}' | head -1 | sed 's/addr://')
    fi

    # Method 3: Use hostname (fallback)
    if [ -z "$ip" ] && command -v hostname &> /dev/null; then
        ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    fi

    # Method 4: Python fallback
    if [ -z "$ip" ]; then
        ip=$(python3 -c "
import socket
try:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(('8.8.8.8', 80))
        print(s.getsockname()[0])
except:
    print('localhost')
" 2>/dev/null)
    fi

    echo "${ip:-localhost}"
}

HUB_IP=$(get_local_ip)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if virtual environment exists
check_venv() {
    if [ ! -d "$VENV_NAME" ]; then
        log_error "Virtual environment '$VENV_NAME' not found!"
        log_info "Please run the installation script first."
        exit 1
    fi
}

# Activate virtual environment
activate_venv() {
    source $VENV_NAME/bin/activate
    log_success "Virtual environment activated"
}

# Start central hub
start_hub() {
    local current_ip=$(get_local_ip)

    log_info "Starting Central Hub..."
    log_info "Auto-detected IP: $current_ip"
    check_venv
    activate_venv

    if lsof -i:$HUB_WS_PORT &> /dev/null; then
        log_warning "Port $HUB_WS_PORT already in use. Hub may already be running."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    log_info "WebSocket server will start on port $HUB_WS_PORT"
    log_info "Web interface will be available at:"
    log_info "  Local:    http://localhost:$HUB_WEB_PORT"
    log_info "  Network:  http://$current_ip:$HUB_WEB_PORT"
    log_info ""
    log_info "Room laptops should connect to: $current_ip"
    log_info "Press Ctrl+C to stop the hub"

    python central_hub.py --websocket-port $HUB_WS_PORT --web-port $HUB_WEB_PORT
}

# Start room transcription
start_room() {
    local room_name="$1"
    local model="${2:-base}"
    local custom_hub_ip="$3"
    local hub_ip="${custom_hub_ip:-$HUB_IP}"
    local hub_url="ws://$hub_ip:$HUB_WS_PORT"

    if [ -z "$room_name" ]; then
        log_error "Room name is required!"
        echo "Usage: $0 room <room_name> [model] [hub_ip]"
        echo "Example: $0 room \"Hall A\" base"
        echo "Example: $0 room \"Hall A\" base 192.168.1.100"
        exit 1
    fi

    log_info "Starting room transcription for: $room_name"
    log_info "Using model: $model"
    log_info "Connecting to hub: $hub_url"

    check_venv
    activate_venv

    # Check if hub is reachable
    if ping -c 1 "$hub_ip" &> /dev/null; then
        log_success "Hub is reachable at $hub_ip"
    else
        log_warning "Hub not reachable at $hub_ip. Starting in offline mode."
        log_warning "Transcriptions will be saved locally only."
    fi

    # Test microphone
    log_info "Testing microphone access..."
    python3 -c "
import pyaudio
try:
    p = pyaudio.PyAudio()
    info = p.get_default_input_device_info()
    print(f'Using microphone: {info[\"name\"]}')
    p.terminate()
except Exception as e:
    print(f'Microphone test failed: {e}')
    exit(1)
" || exit 1

    log_success "Microphone test passed"
    log_info "Starting transcription... Speak into the microphone."
    log_info "Press Ctrl+C to stop"

    python room_stream.py --room "$room_name" --hub-url "$hub_url" --model "$model"
}

# Installation function
install() {
    log_info "Installing Heritage Building Transcription System..."

    # Check Python version
    python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    if [[ $(echo "$python_version >= 3.9" | bc -l) -eq 0 ]]; then
        log_error "Python 3.9+ required. Found: $python_version"
        exit 1
    fi

    log_success "Python version: $python_version"

    # Create virtual environment
    if [ ! -d "$VENV_NAME" ]; then
        log_info "Creating virtual environment..."
        python3 -m venv $VENV_NAME
    fi

    activate_venv

    # Upgrade pip
    log_info "Upgrading pip..."
    pip install --upgrade pip

    # Install dependencies
    log_info "Installing Python packages..."
    pip install RealtimeSTT websockets flask flask-socketio numpy scipy torch torchaudio

    # Install system dependencies based on OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            log_info "Installing macOS dependencies..."
            brew install portaudio ffmpeg || log_warning "Failed to install some dependencies"
        else
            log_warning "Homebrew not found. Please install manually: portaudio, ffmpeg"
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v apt &> /dev/null; then
            log_info "Installing Linux dependencies..."
            sudo apt update
            sudo apt install -y python3-dev portaudio19-dev ffmpeg espeak espeak-data libespeak1 libespeak-dev
        elif command -v yum &> /dev/null; then
            log_info "Installing Linux dependencies..."
            sudo yum install -y python3-devel portaudio-devel ffmpeg espeak espeak-devel
        else
            log_warning "Unknown package manager. Please install manually: portaudio19-dev, ffmpeg, espeak"
        fi
    fi

    # Pre-download common models
    log_info "Pre-downloading Whisper models..."
    python3 -c "
from faster_whisper import WhisperModel
print('Downloading base model...')
model = WhisperModel('base', device='cpu', compute_type='int8')
print('Downloading small model...')
model = WhisperModel('small', device='cpu', compute_type='int8')
print('Models downloaded successfully!')
" || log_warning "Model pre-download failed, but they'll download automatically on first use"

    log_success "Installation complete!"
    log_info "To start the system:"
    log_info "  Central Hub: $0 hub"
    log_info "  Room Laptop: $0 room \"Room Name\""
}

# Test system
test() {
    log_info "Testing system components..."

    check_venv
    activate_venv

    # Test Python imports
    log_info "Testing Python dependencies..."
    python3 -c "
import RealtimeSTT
import websockets
import flask
import torch
print('All imports successful!')
" || exit 1

    # Test audio
    log_info "Testing audio system..."
    python3 -c "
import pyaudio
p = pyaudio.PyAudio()
print(f'Audio devices found: {p.get_device_count()}')
default_input = p.get_default_input_device_info()
print(f'Default input: {default_input[\"name\"]}')
p.terminate()
" || exit 1

    # Test RealtimeSTT
    log_info "Testing RealtimeSTT initialization..."
    python3 -c "
from RealtimeSTT import AudioToTextRecorder
try:
    # Test initialization (don't start, just create)
    recorder = AudioToTextRecorder(use_microphone=False)
    print('RealtimeSTT initialized successfully!')
    recorder.shutdown()
except Exception as e:
    print(f'RealtimeSTT initialization failed: {e}')
    exit(1)
" || exit 1

    log_success "All tests passed!"
}

# Display system status
status() {
    local current_ip=$(get_local_ip)

    log_info "Heritage Building Transcription System Status"
    echo "============================================="
    echo "Local IP Address: $current_ip"
    echo "Hub URL: ws://$current_ip:$HUB_WS_PORT"
    echo "Web Interface: http://$current_ip:$HUB_WEB_PORT"
    echo ""

    # Check if hub is running
    if lsof -i:$HUB_WS_PORT &> /dev/null; then
        log_success "Central Hub: RUNNING (port $HUB_WS_PORT)"
    else
        log_warning "Central Hub: NOT RUNNING"
    fi

    # Check if web interface is running
    if lsof -i:$HUB_WEB_PORT &> /dev/null; then
        log_success "Web Interface: RUNNING (port $HUB_WEB_PORT)"
    else
        log_warning "Web Interface: NOT RUNNING"
    fi

    # Check virtual environment
    if [ -d "$VENV_NAME" ]; then
        log_success "Virtual Environment: Available"
    else
        log_error "Virtual Environment: NOT FOUND"
    fi

    echo "============================================="
}

# Main script logic
case "${1:-}" in
    "hub")
        start_hub
        ;;
    "room")
        start_room "$2" "$3" "$4"
        ;;
    "install")
        install
        ;;
    "test")
        test
        ;;
    "status")
        status
        ;;
    *)
        echo "Heritage Building Transcription System"
        echo "======================================"
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  install                     Install system and dependencies"
        echo "  hub                         Start central hub server"
        echo "  room <name> [model]         Start room transcription"
        echo "  test                        Test system components"
        echo "  status                      Show system status"
        echo ""
        echo "Examples:"
        echo "  $0 install                  # First-time setup"
        echo "  $0 hub                      # Start central hub"
        echo "  $0 room \"Hall A\"            # Start transcription for Hall A"
        echo "  $0 room \"Workshop\" small    # Use small model for Workshop"
        echo ""
        echo "Models: tiny, base, small, medium, large"
        echo "Network: Hub at $HUB_IP:$HUB_WS_PORT"
        exit 1
        ;;
esac