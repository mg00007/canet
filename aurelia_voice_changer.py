import asyncio
import os
import queue
import subprocess
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk

import edge_tts
import imageio_ffmpeg
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel


VOICE = "pt-BR-FranciscaNeural"
SAMPLE_RATE = 16000
OUTPUT_RATE = 24000
MAX_RECORD_SECONDS = 25


class VoiceChanger:
    def __init__(self, root):
        self.root = root
        self.root.title("AURELIA | Voz Neural")
        self.root.geometry("720x720")
        self.root.minsize(620, 640)
        self.root.configure(bg="#111310")

        self.events = queue.Queue()
        self.model = None
        self.stream = None
        self.audio_chunks = []
        self.recording = False
        self.busy = False
        self.record_started = 0.0
        self.input_devices = {}
        self.output_devices = {}

        self._configure_style()
        self._build_ui()
        self.refresh_devices()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self._poll_events)

    def _configure_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#111310")
        style.configure("TLabel", background="#111310", foreground="#eee9dc", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"), foreground="#e7c985")
        style.configure("Muted.TLabel", foreground="#aba999", font=("Segoe UI", 9))
        style.configure("TLabelframe", background="#111310", foreground="#ddc58e")
        style.configure("TLabelframe.Label", background="#111310", foreground="#ddc58e", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", padding=(12, 9), font=("Segoe UI", 10))
        style.configure("Accent.TButton", background="#c5a464", foreground="#17150f", font=("Segoe UI", 11, "bold"))
        style.map("Accent.TButton", background=[("active", "#ddbd7a"), ("disabled", "#62583e")])
        style.configure("TCombobox", fieldbackground="#24251f", background="#24251f", foreground="#eee9dc", padding=6)

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=24)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="AURELIA", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Fale ao microfone. Sua mensagem será sintetizada com a voz pt-BR-FranciscaNeural.",
            style="Muted.TLabel", wraplength=650,
        ).pack(anchor="w", pady=(3, 18))

        devices = ttk.LabelFrame(outer, text="Dispositivos de áudio", padding=14)
        devices.pack(fill="x", pady=(0, 16))
        devices.columnconfigure(1, weight=1)
        ttk.Label(devices, text="Microfone").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=6)
        self.input_var = tk.StringVar()
        self.input_menu = ttk.Combobox(devices, textvariable=self.input_var, state="readonly")
        self.input_menu.grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Label(devices, text="Saída da voz").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=6)
        self.output_var = tk.StringVar()
        self.output_menu = ttk.Combobox(devices, textvariable=self.output_var, state="readonly")
        self.output_menu.grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Button(devices, text="Atualizar dispositivos", command=self.refresh_devices).grid(
            row=2, column=1, sticky="e", pady=(8, 0)
        )

        ttk.Label(
            outer,
            text="Para usar em uma chamada: selecione CABLE Input como saída aqui e CABLE Output como microfone no aplicativo da chamada.",
            style="Muted.TLabel", wraplength=650,
        ).pack(anchor="w", pady=(0, 16))

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(0, 10))
        self.record_button = ttk.Button(
            controls, text="Iniciar gravação", style="Accent.TButton", command=self.toggle_recording
        )
        self.record_button.pack(side="left")
        self.timer_var = tk.StringVar(value=f"Até {MAX_RECORD_SECONDS} segundos por trecho")
        ttk.Label(controls, textvariable=self.timer_var, style="Muted.TLabel").pack(side="left", padx=14)

        ttk.Label(outer, text="Transcrição (edite antes de sintetizar, se necessário)").pack(anchor="w", pady=(8, 6))
        self.transcript = tk.Text(
            outer, height=8, wrap="word", undo=True, bg="#1b1c18", fg="#f0ecdf",
            insertbackground="#e7c985", relief="flat", padx=12, pady=12, font=("Segoe UI", 11),
        )
        self.transcript.pack(fill="both", expand=True)

        self.generate_button = ttk.Button(
            outer, text="Gerar voz e enviar à saída", style="Accent.TButton", command=self.generate_voice
        )
        self.generate_button.pack(anchor="e", pady=(14, 10))
        ttk.Label(
            outer,
            text="A transcrição é feita localmente. O texto editado é enviado ao Microsoft Edge TTS para gerar a voz; o áudio original do microfone não é enviado.",
            style="Muted.TLabel", wraplength=650,
        ).pack(anchor="w", pady=(0, 10))
        self.status_var = tk.StringVar(value="Pronto. Selecione o microfone e a saída.")
        ttk.Label(outer, textvariable=self.status_var, foreground="#e7c985", wraplength=650).pack(anchor="w")

    def refresh_devices(self):
        try:
            devices = sd.query_devices()
            default_input, default_output = sd.default.device
            self.input_devices = {
                f"{index}: {device['name']}": index
                for index, device in enumerate(devices)
                if device["max_input_channels"] > 0
            }
            self.output_devices = {
                f"{index}: {device['name']}": index
                for index, device in enumerate(devices)
                if device["max_output_channels"] > 0
            }
            input_names = list(self.input_devices)
            output_names = list(self.output_devices)
            self.input_menu["values"] = input_names
            self.output_menu["values"] = output_names
            if input_names:
                selected = next(
                    (name for name, index in self.input_devices.items() if index == default_input), input_names[0]
                )
                self.input_var.set(selected)
            if output_names:
                cable = next((name for name in output_names if "cable input" in name.lower()), None)
                selected = cable or next(
                    (name for name, index in self.output_devices.items() if index == default_output), output_names[0]
                )
                self.output_var.set(selected)
                if not cable:
                    self.status_var.set("VB-CABLE não encontrado. Instale-o para enviar a voz a outros aplicativos.")
        except Exception as error:
            self.status_var.set(f"Não foi possível consultar o áudio: {error}")

    def toggle_recording(self):
        if self.busy:
            return
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        input_name = self.input_var.get()
        if input_name not in self.input_devices:
            self.status_var.set("Selecione um microfone disponível.")
            return
        self.audio_chunks = []
        self.record_started = time.monotonic()
        try:
            self.stream = sd.InputStream(
                device=self.input_devices[input_name], samplerate=SAMPLE_RATE, channels=1,
                dtype="float32", callback=self._audio_callback,
            )
            self.stream.start()
            self.recording = True
            self.record_button.configure(text="Parar e transcrever")
            self.status_var.set("Gravando. Clique para parar e converter sua fala.")
            self._update_timer()
        except Exception as error:
            self.stream = None
            self.status_var.set(f"Falha ao iniciar o microfone: {error}")

    def _audio_callback(self, audio, frames, timing, status):
        if status:
            self.events.put(("status", f"Áudio: {status}"))
        self.audio_chunks.append(audio.copy())

    def _update_timer(self):
        if not self.recording:
            return
        elapsed = time.monotonic() - self.record_started
        self.timer_var.set(f"Gravando: {elapsed:04.1f} / {MAX_RECORD_SECONDS}s")
        if elapsed >= MAX_RECORD_SECONDS:
            self.stop_recording()
            return
        self.root.after(100, self._update_timer)

    def stop_recording(self):
        if not self.recording:
            return
        self.recording = False
        stream, self.stream = self.stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        self.record_button.configure(text="Iniciar gravação")
        self.timer_var.set("Transcrevendo localmente…")
        if not self.audio_chunks:
            self.timer_var.set(f"Até {MAX_RECORD_SECONDS} segundos por trecho")
            self.status_var.set("Nenhum áudio capturado. Verifique o microfone selecionado.")
            return
        self.busy = True
        audio = np.concatenate(self.audio_chunks, axis=0).reshape(-1)
        self.audio_chunks = []
        threading.Thread(target=self._transcribe, args=(audio,), daemon=True).start()

    def _transcribe(self, audio):
        try:
            self.events.put(("status", "Carregando reconhecimento local; a primeira execução baixa o modelo…"))
            if self.model is None:
                self.model = WhisperModel("base", device="cpu", compute_type="int8")
            segments, _ = self.model.transcribe(audio, language="pt", vad_filter=True, beam_size=3)
            text = " ".join(segment.text.strip() for segment in segments).strip()
            if text:
                self.events.put(("transcript", text))
            else:
                self.events.put(("empty", None))
        except Exception as error:
            self.events.put(("error", f"Erro ao transcrever: {error}"))

    def generate_voice(self):
        if self.busy or self.recording:
            return
        text = self.transcript.get("1.0", "end-1c").strip()
        if not text:
            self.status_var.set("Grave uma frase ou digite o texto que deseja sintetizar.")
            return
        output_name = self.output_var.get()
        if output_name not in self.output_devices:
            self.status_var.set("Selecione uma saída de áudio disponível.")
            return
        output_device = self.output_devices[output_name]
        self.busy = True
        self.generate_button.configure(state="disabled")
        self.record_button.configure(state="disabled")
        self.status_var.set("Gerando voz neural…")
        threading.Thread(target=self._synthesize_and_play, args=(text, output_device), daemon=True).start()

    def _synthesize_and_play(self, text, output_device):
        mp3_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temporary:
                mp3_path = temporary.name
            speech = edge_tts.Communicate(text, VOICE, rate="-8%", pitch="-1Hz")
            asyncio.run(speech.save(mp3_path))
            decoded = subprocess.run(
                [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", mp3_path,
                 "-f", "f32le", "-ac", "1", "-ar", str(OUTPUT_RATE), "pipe:1"],
                check=True, capture_output=True,
            )
            audio = np.frombuffer(decoded.stdout, dtype=np.float32).copy()
            if not audio.size:
                raise RuntimeError("O serviço de voz retornou áudio vazio.")
            self.events.put(("status", "Reproduzindo pela saída selecionada…"))
            sd.play(audio, samplerate=OUTPUT_RATE, device=output_device, blocking=True)
            self.events.put(("done", None))
        except Exception as error:
            self.events.put(("error", f"Falha ao gerar ou reproduzir a voz: {error}"))
        finally:
            if mp3_path and os.path.exists(mp3_path):
                os.unlink(mp3_path)

    def _poll_events(self):
        try:
            while True:
                event, value = self.events.get_nowait()
                if event == "status":
                    self.status_var.set(value)
                elif event == "transcript":
                    self.transcript.delete("1.0", "end")
                    self.transcript.insert("1.0", value)
                    self.timer_var.set(f"Até {MAX_RECORD_SECONDS} segundos por trecho")
                    self.status_var.set("Transcrição pronta. Corrija o texto e gere a voz na saída escolhida.")
                    self.busy = False
                elif event == "empty":
                    self.timer_var.set(f"Até {MAX_RECORD_SECONDS} segundos por trecho")
                    self.status_var.set("Não reconheci fala neste trecho. Tente novamente ou digite o texto.")
                    self.busy = False
                elif event == "error":
                    self.status_var.set(value)
                    self.busy = False
                elif event == "done":
                    self.status_var.set("Pronto. O áudio sintetizado foi enviado à saída selecionada.")
                    self.busy = False
                if not self.busy:
                    self.generate_button.configure(state="normal")
                    self.record_button.configure(state="normal")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def close(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    VoiceChanger(root)
    root.mainloop()


if __name__ == "__main__":
    main()