import asyncio
import io
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

import av
import edge_tts
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel


VOICE = "pt-BR-FranciscaNeural"
VOICE_OPTIONS = {
    "Francisca (pt-BR)": "pt-BR-FranciscaNeural",
    "Thalita (pt-BR)": "pt-BR-ThalitaMultilingualNeural",
    "Raquel (pt-PT)": "pt-PT-RaquelNeural",
    "Ava Multilingual (en-US)": "en-US-AvaMultilingualNeural",
    "Emma Multilingual (en-US)": "en-US-EmmaMultilingualNeural",
}
DEFAULT_HOTWORDS = "Francisca, Francisca Neural, AURELIA"
SAMPLE_RATE = 16000
OUTPUT_RATE = 24000
LIVE_PAUSE_SECONDS = 0.30
LIVE_MAX_SEGMENT_SECONDS = 8


class VoiceChanger:
    def __init__(self, root):
        self.root = root
        self.root.title("AURELIA | Voz Neural")
        self.root.geometry("760x800")
        self.root.minsize(640, 700)
        self.root.configure(bg="#111310")

        self.events = queue.Queue()
        self.model = None
        self.model_lock = threading.Lock()
        self.stream = None
        self.live_input_queue = None
        self.live_phrase_queue = None
        self.recording = False
        self.busy = False
        self.live_mode = False
        self.record_started = 0.0
        self.input_devices = {}
        self.output_devices = {}

        self._configure_style()
        self._build_ui()
        self.refresh_devices()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self._poll_events)
        self.record_button.configure(state="disabled")
        self.status_var.set("Preparando reconhecimento de voz local…")
        threading.Thread(target=self._warm_model, daemon=True).start()

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
            text="Fale ao microfone. A fala será reconhecida e reproduzida pela voz escolhida.",
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
        ttk.Label(devices, text="Voz sintetizada").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=6)
        self.voice_var = tk.StringVar(value="Francisca (pt-BR)")
        self.voice_menu = ttk.Combobox(
            devices, textvariable=self.voice_var, values=list(VOICE_OPTIONS), state="readonly"
        )
        self.voice_menu.grid(row=2, column=1, sticky="ew", pady=6)
        ttk.Label(devices, text="Nomes para reconhecer").grid(row=3, column=0, sticky="w", padx=(0, 12), pady=6)
        self.hotwords_var = tk.StringVar(value=DEFAULT_HOTWORDS)
        ttk.Entry(devices, textvariable=self.hotwords_var).grid(row=3, column=1, sticky="ew", pady=6)
        ttk.Button(devices, text="Atualizar dispositivos", command=self.refresh_devices).grid(
            row=4, column=1, sticky="e", pady=(8, 0)
        )

        ttk.Label(
            outer,
            text="Thalita é pt-BR; Raquel é pt-PT. Ava e Emma são multilíngues en-US e podem soar com sotaque diferente. Para chamadas, escolha CABLE Input aqui e CABLE Output no app da chamada.",
            style="Muted.TLabel", wraplength=650,
        ).pack(anchor="w", pady=(0, 16))

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(0, 10))
        self.record_button = ttk.Button(
            controls, text="Iniciar conversão ao vivo", style="Accent.TButton", command=self.toggle_recording
        )
        self.record_button.pack(side="left")
        self.timer_var = tk.StringVar(value="Fale normalmente; frases são convertidas após uma pausa curta")
        ttk.Label(controls, textvariable=self.timer_var, style="Muted.TLabel").pack(side="left", padx=14)

        ttk.Label(outer, text="Transcrição reconhecida").pack(anchor="w", pady=(8, 6))
        self.transcript = tk.Text(
            outer, height=8, wrap="word", undo=True, bg="#1b1c18", fg="#f0ecdf",
            insertbackground="#e7c985", relief="flat", padx=12, pady=12, font=("Segoe UI", 11),
        )
        self.transcript.pack(fill="both", expand=True)

        self.generate_button = ttk.Button(
            outer, text="Enviar texto editado à voz", style="Accent.TButton", command=self.generate_voice
        )
        self.generate_button.pack(anchor="e", pady=(14, 10))
        ttk.Label(
            outer,
            text="O modo ao vivo converte cada frase após uma pausa curta. A transcrição é local; o texto reconhecido é enviado ao Microsoft Edge TTS. O áudio original do microfone não é enviado.",
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
        output_name = self.output_var.get()
        if output_name not in self.output_devices:
            self.status_var.set("Selecione uma saída de áudio disponível.")
            return
        voice_id = VOICE_OPTIONS.get(self.voice_var.get(), VOICE)
        hotwords = self.hotwords_var.get().strip()
        self.live_input_queue = queue.Queue()
        self.live_phrase_queue = queue.Queue()
        self.record_started = time.monotonic()
        try:
            self.stream = sd.InputStream(
                device=self.input_devices[input_name], samplerate=SAMPLE_RATE, channels=1,
                blocksize=1600, dtype="float32", callback=self._audio_callback,
            )
            self.stream.start()
            self.recording = True
            self.live_mode = True
            output_device = self.output_devices[output_name]
            threading.Thread(
                target=self._segment_live_audio,
                args=(self.live_input_queue, self.live_phrase_queue),
                daemon=True,
            ).start()
            threading.Thread(
                target=self._process_live_phrases,
                args=(self.live_phrase_queue, output_device, voice_id, hotwords),
                daemon=True,
            ).start()
            self.record_button.configure(text="Parar conversão ao vivo")
            self.generate_button.configure(state="disabled")
            self.transcript.configure(state="normal")
            self.transcript.delete("1.0", "end")
            self.status_var.set("Ouvindo. A conversão para Francisca acontece automaticamente entre frases.")
            self._update_timer()
        except Exception as error:
            self.stream = None
            self.status_var.set(f"Falha ao iniciar o microfone: {error}")

    def _audio_callback(self, audio, frames, timing, status):
        if status:
            self.events.put(("status", f"Áudio: {status}"))
        if self.live_input_queue is not None:
            self.live_input_queue.put(audio.copy())

    def _update_timer(self):
        if not self.recording:
            return
        elapsed = time.monotonic() - self.record_started
        self.timer_var.set(f"Ao vivo: {elapsed:04.1f}s")
        self.root.after(100, self._update_timer)

    def stop_recording(self):
        if not self.recording:
            return
        self.recording = False
        stream, self.stream = self.stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        self.live_mode = False
        if self.live_input_queue is not None:
            self.live_input_queue.put(None)
        self.record_button.configure(text="Iniciar conversão ao vivo")
        self.timer_var.set("Finalizando a última frase…")
        self.status_var.set("Parando. As frases já capturadas ainda serão convertidas.")

    def _segment_live_audio(self, audio_queue, phrase_queue):
        pre_roll = []
        phrase = []
        noise_floor = 0.002
        speech_samples = 0
        silence_samples = 0
        phrase_samples = 0
        active = False
        silence_limit = int(SAMPLE_RATE * LIVE_PAUSE_SECONDS)
        segment_limit = int(SAMPLE_RATE * LIVE_MAX_SEGMENT_SECONDS)

        while True:
            block = audio_queue.get()
            if block is None:
                if active and speech_samples >= int(SAMPLE_RATE * 0.25):
                    phrase_queue.put(np.concatenate(phrase).astype(np.float32, copy=False))
                phrase_queue.put(None)
                return

            samples = np.asarray(block, dtype=np.float32).reshape(-1)
            rms = float(np.sqrt(np.mean(samples * samples)))
            threshold = max(0.006, noise_floor * 3.0)

            if not active:
                if rms < threshold:
                    noise_floor = 0.95 * noise_floor + 0.05 * rms
                pre_roll.append(samples)
                if len(pre_roll) > 3:
                    pre_roll.pop(0)
                if rms >= threshold:
                    active = True
                    phrase = pre_roll.copy()
                    phrase_samples = sum(len(part) for part in phrase)
                    speech_samples = len(samples)
                    silence_samples = 0
                continue

            phrase.append(samples)
            phrase_samples += len(samples)
            if rms >= max(0.004, threshold * 0.65):
                speech_samples += len(samples)
                silence_samples = 0
            else:
                silence_samples += len(samples)

            if silence_samples >= silence_limit or phrase_samples >= segment_limit:
                if speech_samples >= int(SAMPLE_RATE * 0.25):
                    phrase_queue.put(np.concatenate(phrase).astype(np.float32, copy=False))
                phrase = []
                pre_roll = []
                speech_samples = 0
                silence_samples = 0
                phrase_samples = 0
                active = False

    def _process_live_phrases(self, phrase_queue, output_device, voice_id=VOICE, hotwords=DEFAULT_HOTWORDS):
        try:
            while True:
                audio = phrase_queue.get()
                if audio is None:
                    break
                try:
                    self.events.put(("live_status", "Reconhecendo a frase…"))
                    segments, _ = self._get_model().transcribe(
                        audio,
                        language="pt",
                        vad_filter=True,
                        beam_size=1,
                        condition_on_previous_text=False,
                        hotwords=hotwords or None,
                    )
                    text = " ".join(segment.text.strip() for segment in segments).strip()
                    if not text:
                        continue
                    self.events.put(("live_transcript", text))
                    self.events.put(("live_status", "Gerando a voz selecionada…"))
                    speech_audio = self._create_speech_samples(text, voice_id)
                    sd.play(speech_audio, samplerate=OUTPUT_RATE, device=output_device, blocking=True)
                    if self.live_mode:
                        self.events.put(("live_status", "Ouvindo a próxima frase…"))
                except Exception as error:
                    self.events.put(("live_error", f"Falha nesta frase; a escuta continua: {error}"))
        finally:
            self.events.put(("live_finished", None))

    def _get_model(self):
        with self.model_lock:
            if self.model is None:
                self.model = WhisperModel("base", device="cpu", compute_type="int8")
            return self.model

    def _warm_model(self):
        try:
            self._get_model()
            self.events.put(("model_ready", None))
        except Exception as error:
            self.events.put(("model_error", f"Não foi possível preparar o reconhecimento: {error}"))

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
        voice_id = VOICE_OPTIONS.get(self.voice_var.get(), VOICE)
        self.busy = True
        self.generate_button.configure(state="disabled")
        self.record_button.configure(state="disabled")
        self.status_var.set("Gerando voz neural…")
        threading.Thread(target=self._synthesize_and_play, args=(text, output_device, voice_id), daemon=True).start()

    def _synthesize_and_play(self, text, output_device, voice_id=VOICE):
        try:
            audio = self._create_speech_samples(text, voice_id)
            self.events.put(("status", "Reproduzindo pela saída selecionada…"))
            sd.play(audio, samplerate=OUTPUT_RATE, device=output_device, blocking=True)
            self.events.put(("done", None))
        except Exception as error:
            self.events.put(("error", f"Falha ao gerar ou reproduzir a voz: {error}"))

    def _create_speech_samples(self, text, voice_id=VOICE):
        async def generate_audio():
            chunks = []
            speech = edge_tts.Communicate(text, voice_id, rate="-8%", pitch="-1Hz")
            async for message in speech.stream():
                if message["type"] == "audio":
                    chunks.append(message["data"])
            return b"".join(chunks)

        encoded_audio = asyncio.run(generate_audio())
        if not encoded_audio:
            raise RuntimeError("O serviço de voz retornou áudio vazio.")

        samples = []
        with av.open(io.BytesIO(encoded_audio)) as container:
            resampler = av.AudioResampler(format="flt", layout="mono", rate=OUTPUT_RATE)
            for frame in container.decode(audio=0):
                for converted in resampler.resample(frame):
                    samples.append(converted.to_ndarray().reshape(-1))
            for converted in resampler.resample(None):
                samples.append(converted.to_ndarray().reshape(-1))
        if not samples:
            raise RuntimeError("Não foi possível decodificar o áudio sintetizado.")
        return np.concatenate(samples).astype(np.float32, copy=False)

    def _poll_events(self):
        try:
            while True:
                event, value = self.events.get_nowait()
                if event == "status":
                    self.status_var.set(value)
                elif event == "live_status":
                    self.status_var.set(value)
                elif event == "live_transcript":
                    self.transcript.configure(state="normal")
                    self.transcript.insert("end", value + "\n")
                    self.transcript.see("end")
                elif event == "live_error":
                    self.status_var.set(value)
                elif event == "model_ready":
                    self.record_button.configure(state="normal")
                    self.status_var.set("Reconhecimento pronto. Selecione o microfone e a saída de voz.")
                elif event == "model_error":
                    self.record_button.configure(state="normal")
                    self.status_var.set(value)
                elif event == "live_finished":
                    self.timer_var.set("Fale normalmente; frases são convertidas após uma pausa curta")
                    self.generate_button.configure(state="normal")
                    if not self.recording:
                        self.status_var.set("Conversão ao vivo encerrada.")
                elif event == "transcript":
                    self.transcript.delete("1.0", "end")
                    self.transcript.insert("1.0", value)
                    self.timer_var.set("Transcrição pronta")
                    self.status_var.set("Transcrição pronta. Corrija o texto e gere a voz na saída escolhida.")
                    self.busy = False
                elif event == "empty":
                    self.timer_var.set("Pronto")
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