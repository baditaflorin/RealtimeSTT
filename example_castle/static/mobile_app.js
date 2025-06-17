document.addEventListener('DOMContentLoaded', () => {
    // --- UI Elements ---
    const roomNameInput = document.getElementById('roomName');
    const hubIpInput = document.getElementById('hubIp');
    const connectButton = document.getElementById('connectBtn');
    const statusDiv = document.getElementById('status');
    const transcriptPreview = document.getElementById('transcript-preview');

    let websocket;
    let isConnected = false;

    // --- Pre-fill Hub IP for convenience ---
    // Uses the same IP you used to access the page.
    hubIpInput.value = window.location.hostname;

    // --- Speech Recognition Setup ---
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        statusDiv.textContent = 'Error: Speech Recognition not supported by this browser.';
        connectButton.disabled = true;
        return;
    }
    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';


    // --- Main Button Logic ---
    connectButton.addEventListener('click', () => {
        if (isConnected) {
            disconnect();
        } else {
            connect();
        }
    });

    function connect() {
        const hubUrl = `wss://${hubIpInput.value}:9000`;
        statusDiv.textContent = `Connecting to ${hubUrl}...`;
        websocket = new WebSocket(hubUrl);

        websocket.onopen = () => {
            isConnected = true;
            statusDiv.textContent = 'Status: Connected & Listening';
            connectButton.textContent = 'Stop Transcribing';
            connectButton.classList.add('recording');
            recognition.start();
        };

        websocket.onclose = () => {
            disconnect('Connection closed.');
        };

        websocket.onerror = () => {
            disconnect('Connection error.');
        };
    }

    function disconnect(message = 'Disconnected') {
        if (recognition) recognition.stop();
        if (websocket) websocket.close();
        isConnected = false;
        statusDiv.textContent = `Status: ${message}`;
        connectButton.textContent = 'Start Transcribing';
        connectButton.classList.remove('recording');
    }


    // --- Handle Speech Recognition Results ---
    recognition.onresult = (event) => {
        let interim_transcript = '';
        let final_transcript = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                final_transcript += event.results[i][0].transcript;
            } else {
                interim_transcript += event.results[i][0].transcript;
            }
        }

        transcriptPreview.textContent = interim_transcript || final_transcript;

        if (final_transcript.trim()) {
            sendToHub('final', final_transcript);
        }
    };

    // Auto-restart recognition to make it continuous
    recognition.onend = () => {
        if (isConnected) {
            recognition.start();
        }
    };

    recognition.onerror = (event) => {
        disconnect(`Speech Error: ${event.error}`);
    };


    // --- Helper to Send Data to Hub ---
    function sendToHub(type, text) {
        if (!isConnected) return;
        const payload = {
            type: type,
            room: roomNameInput.value || 'Mobile Room',
            text: text,
            timestamp: Date.now() / 1000
        };
        websocket.send(JSON.stringify(payload));
    }
});