# Live Transcript

A Windows desktop application that transcribes audio playing through a selected Windows playback device. Transcription runs locally using [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper).

The first launch downloads the selected Whisper model, so an internet connection is required once. After the model is downloaded, Faster-Whisper can use the cached model on subsequent launches.

## Requirements

* Windows 10 or Windows 11, 64-bit
* Python 3.11 or newer, 64-bit
* Python installation with Tcl/Tk support
* Internet access for installing dependencies and downloading the Whisper model on the first launch
* A working Windows playback device

> **Recommended:** Use Python 3.11 or 3.12 (64-bit) for the most predictable package compatibility.

## Setup

Run these commands from the project folder in PowerShell:

```powershell
python -m venv .venv

.\.venv\Scripts\python.exe -m pip install --upgrade pip

.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\python.exe Transcript.py
```

The virtual environment keeps the application's Python packages isolated from other projects.

Use the `.venv` Python interpreter for both installing dependencies and running the application.

## Usage

1. Start the application and wait for the Whisper model to finish loading.
2. Select the Windows playback device from the **Playback device** dropdown.
3. Start playing audio through the selected device.
4. Click **Start** to begin capturing and transcribing the system audio.
5. Click **Stop** when you want to stop transcription.
6. Click **Save** to export the timestamped transcript.
7. Click **Clear** to remove the current transcript from the application.

The application captures **Windows system playback audio through loopback**, not microphone input.

Speaker identities are not detected or assigned. The application only produces the transcribed text from the captured audio.

The current Whisper configuration is optimized for **English transcription** using the `small.en` model.

## How It Works

The application uses the following components:

* **Tkinter** — Desktop graphical user interface
* **SoundCard** — Captures Windows playback audio through loopback
* **NumPy** — Converts stereo audio into mono audio
* **Faster-Whisper** — Performs local speech-to-text transcription
* **Python threading** — Keeps audio capture and transcription separate from the GUI
* **Queue** — Transfers captured audio chunks between the capture and transcription threads

The processing flow is:

```text
Windows Playback Device
        ↓
SoundCard Loopback Capture
        ↓
3-second Audio Chunk
        ↓
NumPy Stereo → Mono
        ↓
Thread-safe Queue
        ↓
Faster-Whisper
        ↓
Timestamped Transcript
        ↓
Tkinter GUI
```

## Troubleshooting

### Python is not recognized

If `python` is not recognized, install 64-bit Python and make sure Python is added to PATH.

You can check installed Python versions with:

```powershell
py -0p
```

### Tkinter is unavailable

Make sure your Python installation includes Tcl/Tk.

You can test Tkinter with:

```powershell
python -m tkinter
```

A small Tkinter test window should appear.

### No playback devices appear

Make sure a Windows output/playback device is connected and enabled.

The application obtains the available playback devices when it starts.

### Missing Python packages

Run the dependency installation again using the virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Whisper model cannot load

For the first launch, verify that:

* You have an active internet connection.
* You have sufficient disk space.
* The model download is not being blocked by a firewall or proxy.

After the model is downloaded, subsequent launches can use the cached model.

### Transcription is delayed

The application processes audio in 3-second chunks. On slower CPUs, Whisper may take longer to process a chunk than the duration of the audio itself, which can cause transcription to fall behind real time.

The current configuration uses:

```text
Model: small.en
Device: CPU
Compute type: int8
Chunk size: 3 seconds
```

## Limitations

* Windows only
* Requires access to a Windows playback device
* Does not detect speaker identities
* Currently configured for English transcription
* CPU-based transcription may introduce some latency
* The first launch requires downloading the Whisper model
* Dockerizing the complete application requires additional Windows GUI and audio-loopback considerations
