import queue
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import numpy as np
import soundcard as sc
from faster_whisper import WhisperModel

RATE = 16000
CHUNK = 3
MODEL_SIZE = "small.en"
DEVICE = "cpu"
COMPUTE = "int8"

class App:
    def __init__(self, root):
        self.root = root
        root.title("Live Transcript")
        root.geometry("1000x700")
        root.minsize(760, 520)

        self.q = queue.Queue(maxsize=10)
        self.stop_event = threading.Event()
        self.running = False
        self.model_ready = False
        self.lines = []
        self.model = None

        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("App.TFrame", background="#f3f5f7")
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure("Header.TFrame", background="#183b43")
        style.configure("HeaderTitle.TLabel", background="#183b43", foreground="#ffffff", font=("Segoe UI", 20, "bold"))
        style.configure("HeaderSubtitle.TLabel", background="#183b43", foreground="#d4e2e2", font=("Segoe UI", 10))
        style.configure("Section.TLabel", background="#f3f5f7", foreground="#183b43", font=("Segoe UI", 10, "bold"))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#66777b", font=("Segoe UI", 9))
        style.configure("Status.TLabel", background="#e6eeee", foreground="#183b43", font=("Segoe UI", 9, "bold"))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 8))
        style.configure("Toolbar.TButton", font=("Segoe UI", 9), padding=(10, 7))

        root.configure(background="#f3f5f7")
        shell = ttk.Frame(root, style="App.TFrame", padding=18)
        shell.pack(fill="both", expand=True)
        shell.rowconfigure(2, weight=1)
        shell.columnconfigure(0, weight=1)

        header = ttk.Frame(shell, style="Header.TFrame", padding=(22, 18))
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        ttk.Label(header, text="Live Transcript", style="HeaderTitle.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Transcribe audio playing through your Windows playback device.",
            style="HeaderSubtitle.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        setup = ttk.Frame(shell, padding=(18, 14), style="Panel.TFrame")
        setup.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        setup.columnconfigure(0, weight=1)
        ttk.Label(setup, text="AUDIO SOURCE", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))

        device_row = ttk.Frame(setup, style="App.TFrame")
        device_row.grid(row=1, column=0, sticky="ew")
        device_row.columnconfigure(0, weight=1)
        self.dev = tk.StringVar()
        self.combo = ttk.Combobox(device_row, textvariable=self.dev, state="readonly")
        self.combo.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.refresh = ttk.Button(device_row, text="Refresh devices", style="Toolbar.TButton", command=self.load_devices)
        self.refresh.grid(row=0, column=1)

        actions = ttk.Frame(setup, style="App.TFrame")
        actions.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self.start = ttk.Button(actions, text="Start transcription", style="Primary.TButton", command=self.start_capture, state="disabled")
        self.start.pack(side="left")
        self.stop = ttk.Button(actions, text="Stop", style="Toolbar.TButton", command=self.stop_capture, state="disabled")
        self.stop.pack(side="left", padx=(8, 0))
        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=12)
        self.save_button = ttk.Button(actions, text="Save transcript", style="Toolbar.TButton", command=self.save, state="disabled")
        self.save_button.pack(side="left")
        self.clear_button = ttk.Button(actions, text="Clear", style="Toolbar.TButton", command=self.clear, state="disabled")
        self.clear_button.pack(side="left", padx=(8, 0))

        transcript = ttk.Frame(shell, padding=16, style="Panel.TFrame")
        transcript.grid(row=2, column=0, sticky="nsew")
        transcript.rowconfigure(1, weight=1)
        transcript.columnconfigure(0, weight=1)
        transcript_header = ttk.Frame(transcript, style="Panel.TFrame")
        transcript_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        transcript_header.columnconfigure(0, weight=1)
        ttk.Label(transcript_header, text="TRANSCRIPT", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.line_count = tk.StringVar(value="0 entries")
        ttk.Label(transcript_header, textvariable=self.line_count, style="Muted.TLabel").grid(row=0, column=1, sticky="e")

        text_frame = ttk.Frame(transcript)
        text_frame.grid(row=1, column=0, sticky="nsew")
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)
        self.text = tk.Text(
            text_frame,
            wrap="word",
            font=("Segoe UI", 11),
            padx=16,
            pady=14,
            background="#ffffff",
            foreground="#25383c",
            insertbackground="#183b43",
            relief="flat",
            state="disabled",
        )
        self.text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.tag_configure("time", foreground="#28766f", font=("Segoe UI", 10, "bold"))

        footer = ttk.Frame(shell, style="App.TFrame")
        footer.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.status = tk.StringVar(value="Loading transcription model...")
        ttk.Label(footer, textvariable=self.status, style="Status.TLabel", padding=(10, 7)).pack(side="left")
        ttk.Label(footer, text="English · Local model · Speaker labels are not inferred", style="Muted.TLabel").pack(side="right")

        self.load_devices()
        threading.Thread(target=self.load_model, daemon=True).start()

    def load_devices(self):
        try:
            previous = self.dev.get()
            names = [speaker.name for speaker in sc.all_speakers()]
            self.combo["values"] = names
            default = sc.default_speaker()
            if previous in names:
                self.dev.set(previous)
            elif default and default.name in names:
                self.dev.set(default.name)
            elif names:
                self.dev.set(names[0])
            else:
                self.dev.set("")
                self.status.set("No playback devices found. Connect an audio device and refresh.")
            if names and self.model_ready and not self.running:
                self.status.set("Ready to transcribe")
            self._update_controls()
        except Exception as error:
            messagebox.showerror("Audio devices", str(error))

    def load_model(self):
        try:
            self.model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE)
            self.root.after(0, self._model_loaded)
        except Exception as error:
            self.root.after(0, self._model_failed, str(error))

    def _model_loaded(self):
        self.model_ready = True
        self.status.set("Ready to transcribe" if self.dev.get() else "No playback devices found. Connect an audio device and refresh.")
        self._update_controls()

    def _model_failed(self, message):
        self.status.set("Model error: " + message)
        messagebox.showerror("Whisper model", message)

    def _update_controls(self):
        can_start = self.model_ready and bool(self.dev.get()) and not self.running
        self.start.config(state="normal" if can_start else "disabled")
        self.refresh.config(state="disabled" if self.running else "normal")
        self.combo.config(state="disabled" if self.running else "readonly")
        has_lines = bool(self.lines)
        self.save_button.config(state="normal" if has_lines else "disabled")
        self.clear_button.config(state="normal" if has_lines else "disabled")

    def capture(self):
        try:
            speaker = next(speaker for speaker in sc.all_speakers() if speaker.name == self.dev.get())
            microphone = sc.get_microphone(id=str(speaker.name), include_loopback=True)
            with microphone.recorder(samplerate=RATE, channels=2) as recorder:
                while not self.stop_event.is_set():
                    audio = recorder.record(numframes=RATE * CHUNK)
                    mono = np.mean(audio, axis=1).astype(np.float32)
                    try:
                        self.q.put(mono, timeout=0.5)
                    except queue.Full:
                        pass
        except Exception as error:
            self.root.after(0, self._capture_failed, str(error))

    def _capture_failed(self, message):
        self.status.set("Capture error: " + message)
        self.stop_capture()

    def transcribe(self):
        while not self.stop_event.is_set() or not self.q.empty():
            try:
                audio = self.q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                segments, _ = self.model.transcribe(
                    audio,
                    beam_size=1,
                    vad_filter=True,
                    language="en",
                    condition_on_previous_text=False,
                    temperature=0,
                )
                text = " ".join(segment.text.strip() for segment in segments).strip()
                if text:
                    stamp = datetime.now().strftime("%H:%M:%S")
                    self.lines.append((stamp, text))
                    self.root.after(0, self.add_line, stamp, text)
            except Exception as error:
                self.root.after(0, self._transcription_failed, str(error))

    def _transcription_failed(self, message):
        self.status.set("Transcription error: " + message)

    def add_line(self, stamp, text):
        self.text.config(state="normal")
        self.text.insert("end", f"[{stamp}] ", "time")
        self.text.insert("end", text + "\n\n")
        self.text.see("end")
        self.text.config(state="disabled")
        self.line_count.set(f"{len(self.lines)} entr{'y' if len(self.lines) == 1 else 'ies'}")
        self._update_controls()
        self.status.set("Listening and transcribing")

    def start_capture(self):
        if self.running:
            return
        if not self.dev.get():
            messagebox.showwarning("Audio source", "Select a playback device first.")
            return
        self.running = True
        self.stop_event.clear()
        self.stop.config(state="normal")
        self._update_controls()
        threading.Thread(target=self.capture, daemon=True).start()
        threading.Thread(target=self.transcribe, daemon=True).start()
        self.status.set("Listening for audio...")

    def stop_capture(self):
        if not self.running:
            return
        self.running = False
        self.stop_event.set()
        self.stop.config(state="disabled")
        self._update_controls()
        self.status.set("Stopped")

    def clear(self):
        if not self.lines:
            return
        if not messagebox.askyesno("Clear transcript", "Remove all transcript entries?"):
            return
        self.lines.clear()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")
        self.line_count.set("0 entries")
        self._update_controls()

    def save(self):
        if not self.lines:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text transcript", "*.txt"), ("Markdown", "*.md")],
            title="Save transcript",
        )
        if path:
            with open(path, "w", encoding="utf-8") as output:
                for stamp, text in self.lines:
                    output.write(f"[{stamp}] {text}\n")
            messagebox.showinfo("Transcript saved", f"Saved to:\n{path}")

if __name__=="__main__":
    r=tk.Tk(); a=App(r); r.mainloop()
