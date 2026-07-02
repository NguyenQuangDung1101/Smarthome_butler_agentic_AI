# B.E.O.N Smart Home Assistant

B.E.O.N is an intelligent smart home assistant built using an **Agentic AI architecture**. It allows users to control and monitor smart home devices through text, voice, manual controls, and automated schedules. 

## Main Techniques

* **Agentic AI and LLM:** Understands natural-language requests, performs multi-step reasoning, and selects appropriate tools or device actions.
* **Tool Calling:** Connects the AI agent with functions such as device control, notes, weather, time, and scheduling.
* **Hierarchical Agent Architecture:** Separates direct user interaction from background schedule and event processing.
* **Hardware-in-the-Loop:** Sends commands to real ESP32 devices and receives actual sensor and actuator states.
* **React and Vite:** Provide the web dashboard and user interface.
* **Flask and Python:** Handle backend APIs, AI processing, sessions, device communication, and scheduling.
* **TCP/JSON Communication:** Transfers control commands and device states between the backend and ESP32 nodes.
* **Voice Interaction:** Uses speech-to-text and text-to-speech for voice-based communication.

## Run the Project

### Installation

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

Install Ollama, then pull the cloud model:

```bash
ollama pull gemma4:31b-cloud
```

### 1. Start the backend

```bash
python app.py
```

The backend runs at:

```text
http://localhost:5000
```

### 2. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open the printed Vite URL

### 3. Expose the backend with Ngrok

```bash
ngrok http 5000
```

Use the generated Ngrok URL as the backend API URL for remote access.
