#!/usr/bin/env python3
"""
robot_main.py — ELE 495 Asenkron Kuyruk Mimarisi (v1.0+ OpenAI SDK)
Revision 23: Cleaned up syntax, restored defs, fixed Arduino handshake and capture
"""
import client_sender         # Custom module to send data (e.g., to a UI or logging server)

import asyncio               # For asynchronous programming and concurrent tasks
import json                  # To parse and generate JSON data
import uuid                  # For generating unique identifiers (e.g., for temp files)
import ast                   # For safely evaluating Python literals (e.g., parsed JSON from string)
import logging               # For structured logging and debugging
import time                  # Time-based functions (sleep, timestamps)
from pathlib import Path     # Object-oriented file path manipulation
from typing import Optional  # Type hinting: allows declaring values that may be None

from openai import OpenAI    # OpenAI SDK client (Whisper, ChatGPT, TTS APIs)
import sounddevice as sd     # Access system audio input/output for recording
import soundfile as sf       # Read and write audio files (like WAV)
from scipy.io.wavfile import write, read  # Functions for handling WAV files
from scipy.signal import resample         # Resample audio signals to a different sample rate
from resemblyzer import VoiceEncoder, preprocess_wav  # For speaker embedding and preprocessing
import webrtcvad             # Voice Activity Detection from WebRTC (detects if speech is present)
import subprocess            # Run system shell commands (e.g., play audio with aplay)
import serial                # Serial communication with devices (e.g., Arduino via USB)
import numpy as np           # Numerical operations, especially on audio arrays
import re                    # Regular expressions for string pattern matching and cleaning


# === USER CONFIG ==========================================================
CONFIG = {
     # Your OpenAI API key for accessing GPT, Whisper, and TTS services
    "OPENAI_API_KEY": # "sk-...",
    "OPENAI_MODEL":    "gpt-4o-mini", # GPT model used for command parsing (lightweight version of GPT-4o)
    "WHISPER_MODEL":   "whisper-1", # Whisper model name for speech-to-text conversion
    "TTS_MODEL":       "tts-1",    # Text-to-speech model used to generate spoken responses
    "TTS_VOICE":       "alloy",     # TTS voice name (e.g., Alloy, Echo, Fable, etc.)
    "CAPTURE_RATE":    48000,           # Record at 44.1 kHz
    "PROCESS_RATE":    16000,           # Resample to 16 kHz for Whisper
    "CHUNK_SEC":       7,               # Maximum recording duration per utterance (in seconds)
    "AUDIO_DEVICE":    1,       #  (USB 2.0 Device microphne)
    "USB_SPEAKER_DEVICE": "plughw:2,0", # UACDemoV1.0 speaker
    "SERIAL_PORT":     "/dev/ttyUSB0",  # Serial port for communication with Arduino
    "BAUDRATE":        115200,          # Baud rate for serial communication (must match Arduino side)
    "ACK_TIMEOUT":     20.0,            # Timeout (in seconds) to wait for ACK message from Arduino
     "VAD_MODE":        2,              # WebRTC VAD sensitivity mode (0: most sensitive, 3: least sensitive)
    "VAD_SILENCE_MS":  800              # Duration of silence (in ms) before stopping audio recording
}

# Check if the OpenAI API key is provided, otherwise raise an error
if not CONFIG["OPENAI_API_KEY"]:
    raise RuntimeError("OPENAI_API_KEY is not set.")

# === CLIENT & CONSTANTS ==================================================

# Initialize the OpenAI client using the provided API key
client = OpenAI(api_key=CONFIG["OPENAI_API_KEY"])

# Extract configuration values for easier access
CAPTURE_RATE = CONFIG["CAPTURE_RATE"]     # Microphone recording rate (Hz)
PROCESS_RATE = CONFIG["PROCESS_RATE"]     # Processing rate for Whisper (Hz)
CHUNK = CONFIG["CHUNK_SEC"]               # Duration of each audio recording chunk (in seconds)

# Create a temporary directory for storing audio files
TMP_DIR = Path("/tmp/robot_audio")
TMP_DIR.mkdir(exist_ok=True)              # Create the directory if it doesn't already exist

# Set default audio input device for sounddevice
sd.default.device = (CONFIG["AUDIO_DEVICE"], None)  # Only set input device (leave output as default)

# Open serial communication with Arduino
ser = serial.Serial(CONFIG["SERIAL_PORT"], CONFIG["BAUDRATE"], timeout=0)

# Set up logging format and level
logging.basicConfig(
    level=logging.INFO,                  # Log info level and above
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",  # Log format with timestamp
    datefmt="%H:%M:%S"                   # Time format (HH:MM:SS)
)

# Create a logger named "robot"
logger = logging.getLogger("robot")

# === SPEAKER ID ==========================================================
# Initialize the Resemblyzer voice encoder
voice_encoder = VoiceEncoder()

# Load previously saved speaker embeddings from a .npy file
voiceprints = np.load("voiceprints.npy", allow_pickle=True).item()

# Global flag to track if energy is too low for processing
energy_low = 0

def identify_speaker(wav_path: Path, threshold=0.75) ->  Optional[str]:
    # === Wav length and energy control
    # Load the audio file and calculate duration and energy
    audio, sr = sf.read(str(wav_path))
    duration_sec = len(audio) / sr
    energy = np.mean(audio ** 2)

    global energy_low
    energy_low=0 # Reset low energy flag

    # Reject if the audio is too short
    if duration_sec < 0.3:
        print("Ses çok kısa, tanıma iptal.")
        return None

     # Reject if the audio energy is too low
    if energy < 0.001:
        print("Ses çok sessiz, tanıma iptal.")
        energy_low=1
        return None

    # === Resemblyzer ===
    # Preprocess and embed the audio using Resemblyzer
    wav = preprocess_wav(str(wav_path))
    embed = voice_encoder.embed_utterance(wav)

    # Variables to store the best and second-best match
    best = {"name": None, "score": -1}
    second_best = {"name": None, "score": -1}

    # Compare the embedding to all saved voiceprints
    for name, ref in voiceprints.items():
        score = np.dot(embed, ref)# Cosine similarity
        if score > best["score"]:
            second_best = best.copy()
            best = {"name": name, "score": score}
        elif score > second_best["score"]:
            second_best = {"name": name, "score": score}

    print(f"Best: {best} | Second Best: {second_best}")

    # === Threshold checks ===
    # Reject if the best match score is too low
    if best["score"] < threshold:
        print("Skor düşük, tanıma iptal.")
        return None

    # Reject if best and second best are too close in score
    if (best["score"] - second_best["score"]) < 0.005:
        print("En iyi ve ikinci en iyi skor çok yakın, tanıma iptal.")
        return None

     # Return the identified speaker name
    return best["name"]
    
# === ARDUINO HELPERS ======================================================

# Initialize serial communication with Arduino on port /dev/ttyUSB0 at 115200 baud
ser = serial.Serial('/dev/ttyUSB0', 115200)

# Function to send a command to Arduino and wait for acknowledgment (ACK)
def send_to_arduino(cmd: str, log, duration: Optional[int] = None,angle: Optional[int] = None) -> bool:
    """Sends JSON command and waits for ack."""
    # Construct the base JSON message
    msg = {"cmd": cmd}
    if duration is not None:
        msg["sure"] = duration # Include duration if specified
    if angle is not None:
        msg["aci"] = angle # Include angle if specified

    # Create a status message in Turkish for UI display
    durum_map = {
        "FORWARD": "ileri gidiyor",
        "BACKWARD": "geri gidiyor",
        "LEFT": "sola dönüyor",
        "RIGHT": "sağa dönüyor",
        "STOP": "duruyor"
    }
    komut_turkce = durum_map.get(cmd.upper(), "bilinmeyen komut")

    # Construct status explanation depending on parameters
    if duration:
        durum_aciklama = f"Araç {duration} saniye {komut_turkce}"
    elif angle:
        durum_aciklama = f"Araç {angle} derece {komut_turkce}"
    else:
        durum_aciklama = f"Araç {komut_turkce}"

    # JSON data to send to client interface (for visualization)
    veri_arac_durumu = {
        "type": "arac_durumu",
        "aracDurumu": durum_aciklama
    }

    # Try to send the status to the interface
    try:
        client_sender.send_json_data(veri_arac_durumu)
    except Exception as e:
        log.error(f"Durum gönderilemedi: {e}")

    # Send JSON command to Arduino via UART
    js = json.dumps(msg)
    ser.write((js + "\n").encode())
    log.info(f"UART=> {js}")

    # Wait for acknowledgment (ack) from Arduino
    start = time.time()
    buf = ''
    while time.time() - start < CONFIG.get("ACK_TIMEOUT", 2.0):
        if ser.in_waiting:
            c = ser.read(1).decode(errors='ignore') # Read one byte at a time
            buf += c
            if c == '\n':
                line = buf.strip()
                buf = ''
                log.info(f"UART<= {line}")
                try:
                    resp = json.loads(line)
                    if resp.get('ack') == cmd: # Match acknowledgment
                        return True
                except json.JSONDecodeError:
                    log.debug(f"Invalid ack JSON: {line}")
    # If timeout expires without valid ACK                
    log.error(f"ACK timeout for {cmd}")
    return False

# Function to read a line from Arduino if available
def read_from_arduino(log) -> Optional[str]:
    """Reads line if available."""
    if ser.in_waiting:
        line = ser.readline().decode().strip()
        log.info(f"UART<= {line}")
        return line
    return None


# === RESAMPLE HELPER ======================================================

# Function to resample a WAV file to a different sample rate (e.g., from 48kHz to 16kHz)
def resample_wav(input_path: Path, orig_rate: int, target_rate: int) -> Path:
    # Read the original WAV file (returns sample rate and audio data)
    rate, data = read(str(input_path))

    # If the sample rate is already the target rate, return the original file
    if rate == target_rate:
        return input_path

    # Calculate the duration of the original audio (in seconds)    
    duration = data.shape[0] / rate

    # Compute the new number of samples needed at the target rate
    new_length = int(duration * target_rate)

    # Resample the audio to the new length and convert to 16-bit integers
    data_resampled = resample(data, new_length).astype(np.int16)

    # Generate a new filename indicating the new sample rate
    new_path = input_path.with_name(f"{input_path.stem}_{target_rate}hz.wav")

    # Write the resampled audio to the new WAV file
    write(str(new_path), target_rate, data_resampled)

     # Return the path to the new resampled file
    return new_path

# === AUDIO CAPTURE =======================================================

# Function to record audio until silence is detected using WebRTC VAD
def record_until_silence(log) -> Path:

    # Initialize WebRTC voice activity detector with configured sensitivity
    vad = webrtcvad.Vad(CONFIG["VAD_MODE"])

    # Set the sample rate and frame properties
    sample_rate = CAPTURE_RATE # Audio input rate (e.g., 48000 Hz)
    frame_duration = 30        # Frame size in milliseconds
    frame_len = int(sample_rate * frame_duration / 1000) # Number of samples per frame
    silence_threshold = CONFIG["VAD_SILENCE_MS"] # Max silence before stopping (e.g., 800 ms)
    silence_count = 0 # Counter for consecutive silent frames

    raw_frames = [] # Buffer to collect audio frames

    # Open the audio input stream using sounddevice
    stream = sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16', device=CONFIG["AUDIO_DEVICE"])
    with stream:
        while True:
            # Read a single frame from the microphone
            audio_chunk, _ = stream.read(frame_len)
            raw_frames.append(audio_chunk.copy())

            # Check if this frame contains speech
            is_speech = vad.is_speech(audio_chunk.tobytes(), sample_rate)
            if not is_speech:
                # Increment silence counter if no speech is detected
                silence_count += frame_duration
                if silence_count > silence_threshold:
                    break # Stop recording after enough silence
            else:
                silence_count = 0  # Reset counter on speech

    # Concatenate all recorded audio frames into a single array
    raw_audio = np.concatenate(raw_frames, axis=0)

    # Create a temporary WAV file to store the recorded audio
    wav_path = TMP_DIR / f"raw_{uuid.uuid4().hex}.wav"
    write(str(wav_path), sample_rate, raw_audio)

    # Log the recording duration and path
    log.info(f"[Recorder] Saved {wav_path} ({len(raw_audio)/sample_rate:.2f}s)")

    # Resample the audio to the processing sample rate (e.g., 16000 Hz) and return the path
    return resample_wav(wav_path, sample_rate, PROCESS_RATE)

# Asynchronous loop to capture audio and enqueue it if the vehicle is active
async def capture_loop(raw_q: asyncio.Queue):
    while True:
        # If the vehicle is not active, wait and skip capturing
        if not client_sender.is_arac_aktif():
            await asyncio.sleep(0.5)
            continue
        # Record and enqueue audio using a background thread    
        wav = await asyncio.to_thread(record_until_silence, logger)
        await raw_q.put(wav) # Put the recorded file path into the queue


# === OPENAI HELPERS =======================================================
#Promps to help OpenAI interpret the commands
def SYS_PROMPT() -> str:
    return (
        "Aşağıdaki Türkçe komutu JSON listeye çevir.\n"
        "- 'ileri' → FORWARD, 'geri' → BACKWARD, 'sola' → LEFT, 'sağa' → RIGHT, 'dur' → STOP.\n"
        "Ek veriler: 'sure' (saniye), 'kosul' (engel), 'açı' (derece).\n\n"
        "Çıktı bir JSON liste olmalı. Her komut ayrı bir sözlük nesnesi içinde olmalı.\n\n"

        "Eğer kullanıcıdan gelen cümle anlamlı bir Türkçe ifadeyse ama bu robotun tanıdığı bir komut değilse: (örneğin: 'zıpla', 'uç', 'yüz', 'çay demle', 'elbise giy', 'kahve koy','yemek ye', 'dans et','duş al','onu getir','dök','renk tespiti yap','araba, uçar mısın','araba, uç','araba, renk tespiti yap') gibi emir içeren kelimeler ise \n"
        "→ [{'komut': 'gecersiz', 'girdi': 'kullanıcının söylediği komut'}]\n\n"
        "Eğer kullanıcıdan geriye dön/geriye döner misin/geriye döner misiniz gibi bir komut gelirse 180 derece sağa dön "
        "Eğer komutlar: 'İki kere sağa dön', 'İki defa sola dön' şeklindeyse istenen eylemi belirtilen sayı kadar tekrarla"
        "Eğer sana 'içebilir misin?' gibi bir cğmle kurmaya çalırken yanlış telaffuz edip 'içer bilir misin?' gibi bir cümle kurarsam onu 'içebilir misin?' olarak yorumla"
        "Eğer sana '3 saniye ileri git' gibi bir cümle kuruyorsam ve bu cümleyi ses alırken yanlışlıkla '3 saniyelere ileri git' gibi anladıysan bu komutu '3 saniye ileri git' olarak yorumla "
        "Eğer kullanıcıdan gelen metin\n"
        "- saçma sapan, anlam bozan, küfürlü ya da uydurma kelimeler içeriyorsa\n"
        "- Whisper çıktısı alakasız ve komut dışı ise (örneğin: 'afiyet olsun', 'altyazı mk', 'gözlükten selam', 'tamam canım')\n"
        "- ya da kullanıcı hiç konuşmadıysa / ses boşsa\n"
        "→ [{'komut': 'imkansiz'}]\n\n"
        
        " Örnekler:\n"
        "Kullanıcı: 'ileri git' → [{'komut': 'FORWARD']\n"
        "Kullanıcı: 'ileri gider misin?' → [{'komut': 'FORWARD']\n"
        "Kullanıcı: 'ileri gidebilir misin?' → [{'komut': 'FORWARD']\n"
        "Kullanıcı: '2 saniye ileri git' → [{'komut': 'FORWARD', 'sure': 2}]\n"
        "Kullanıcı: '2 saniye ileri gider misin?' → [{'komut': 'FORWARD', 'sure': 2}]\n"
        "Kullanıcı: '2 saniye ileri gidebilir misin?' → [{'komut': 'FORWARD', 'sure': 2}]\n"
        "Kullanıcı: 'geri git' → [{'komut': 'BACKWARD'}]\n"
        "Kullanıcı: 'geri gider misin?' → [{'komut': 'BACKWARD'}]\n"
        "Kullanıcı: 'geri gidebilir misin?' → [{'komut': 'BACKWARD'}]\n"
        "Kullanıcı: 'geriye gidebilir misin?' → [{'komut': 'BACKWARD'}]\n"
        "Kullanıcı: 'geriye gider misin?' → [{'komut': 'BACKWARD'}]\n"
        "Kullanıcı: 'geri git' → [{'komut': 'BACKWARD'}]\n"
        "Kullanıcı: 'geriye dön' → [{'komut': 'right', 'aci':180}]\n"
        "Kullanıcı: 'geriye döner misin' → [{'komut': 'right', 'aci':180}]\n"
        "Kullanıcı: 'geriye dönebilir misin?' → [{'komut': 'right', 'aci':180}]\n"
        "Kullanıcı: 'sağa dön' → [{'komut': 'right'}]\n"
        "Kullanıcı: 'sağa döner misin?' → [{'komut': 'right'}]\n"
        "Kullanıcı: 'sağa dönebilir misiniz?' → [{'komut': 'right'}]\n"
        "Kullanıcı: 'sola dön' → [{'komut': 'left'}]\n"
        "Kullanıcı: 'sola döner misin?' → [{'komut': 'left'}]\n"
        "Kullanıcı: 'sola dönebilir misin?' → [{'komut': 'left'}]\n"

        "Kullanıcı: 'zıpla' → [{'komut': 'gecersiz', 'girdi': 'zıpla'}]\n"
        "Kullanıcı: 'uç' → [{'komut': 'gecersiz', 'girdi': 'uç'}]\n"
        "Kullanıcı: 'uçar mısın?' → [{'komut': 'gecersiz', 'girdi': 'uç'}]\n"
        "Kullanıcı: 'uçabilir misin?' → [{'komut': 'gecersiz', 'girdi': 'uç'}]\n"
        "Kullanıcı: 'meyve suyu içer misin?' → [{'komut': 'gecersiz', 'girdi': 'meyve suyu iç'}]\n"
        "Kullanıcı: 'renk tespiti yap' → [{'komut': 'gecersiz', 'girdi': 'renk tespiti yap'}]\n"
        "Kullanıcı: 'araba,renk tespiti yap' → [{'komut': 'gecersiz', 'girdi': 'renk tespiti yap'}]\n"
        "Kullanıcı: 'dans et' → [{'komut': 'gecersiz', 'girdi': 'dans et'}]\n"
        "Kullanıcı: 'dans eder misin?' → [{'komut': 'gecersiz', 'girdi': 'dans et'}]\n"
        "Kullanıcı: 'pizza yap' → [{'komut': 'gecersiz', 'girdi': 'yemek yap'}]\n"
        "Kullanıcı: 'su iç' → [{'komut': 'gecersiz', 'girdi': 'su iç'}]\n"
        "Kullanıcı: 'araba, yüzer misin?' → [{'komut': 'gecersiz', 'girdi': 'yüz'}]\n"
        "Kullanıcı: 'araba afiyet olsun' → [{'komut': 'imkansiz'}]\n"
        "Kullanıcı: hiç konuşmadı (sessizlik) → [{'komut': 'imkansiz'}]\n"
        
        
    )

# ASYNC: Run Whisper STT (Speech-to-Text) on a given WAV file
async def stt_whisper(wav: Path) -> str:
    logger.info(f"[STT] Whisper on {wav}")

    # Define sync function to call Whisper transcription API
    def sync():
        with open(wav, 'rb') as f:
            return client.audio.transcriptions.create(
                model=CONFIG["WHISPER_MODEL"], file=f, language="tr" # Whisper model name and Turkish language
            ).text

    # Run sync function in background thread (non-blocking)        
    text = await asyncio.to_thread(sync)
    logger.info(f"[STT] {text}")
    return text

# ASYNC: Run GPT model to parse transcribed text into command JSON
async def openai_llm(text: str) -> list:
    logger.info(f"[LLM] {text}")

    # Define sync function to query OpenAI ChatCompletion API
    def sync():
        return client.chat.completions.create(
            model=CONFIG["OPENAI_MODEL"], temperature=0.0, # GPT model name and Deterministic output
            messages=[{"role":"system","content":SYS_PROMPT()}, # System prompt with rules
                      {"role":"user","content":text}] # User's input (from STT)
        )

    # Call LLM API in background thread    
    resp = await asyncio.to_thread(sync)

    # Remove markdown formatting (like ```json) from response
    raw = re.sub(r"```[\w]*\n|```", "", resp.choices[0].message.content).strip()
    logger.debug(f"[LLM raw response] {raw}")
    logger.info(f"[LLM] got: {raw}")

    # Try parsing the LLM's response as Python literal (usually a list of dicts)
    try:
        return ast.literal_eval(raw)
    except:
        logger.error("LLM parse failed")
        return []

# ASYNC: Use OpenAI TTS to synthesize voice response from command(s)
async def openai_tts(cmds) -> Path:
    # If direct text is given (example: "Sistem hazır" -> System is ready)
    if isinstance(cmds, str):
        utter = cmds
    else:
        # Otherwise, format a list of command dictionaries into natural language
        def format_command(cmd: dict) -> str:
            k = cmd.get("komut", "").lower()
            s = cmd.get("sure")
            a = cmd.get("aci") or cmd.get("açı")
            kosul = cmd.get("kosul")
            girdi = cmd.get("girdi", "")

            if k == "forward":
                if s:
                    return f"{s} saniye boyunca ileri gidiyorum"
                elif kosul:
                    return f"{kosul} olana kadar ileri gidiyorum"
                else:
                    return "İleri gidiyorum"
            elif k == "backward":
                if s:
                    return f"{s} saniye boyunca geri gidiyorum"
                elif kosul:
                    return f"{kosul} olana kadar geri gidiyorum"
                else:
                    return "Geri gidiyorum"
            elif k == "left":
                if a:
                    return f"{a} derece sola dönüyorum"
                else:
                    return "Sola dönüyorum"
            elif k == "right":
                if a:
                    if a == 180 :
                         return "Geriye dönüyorum"
                    else:
                         return f"{a} derece sağa dönüyorum"
                else:
                    return "Sağa dönüyorum"
            elif k == "stop":
                if s:
                    return f"{s} saniye boyunca duruyorum"
                else:    
                    return "Duruyorum"
            elif k == "gecersiz":
                return f"'{girdi}' komutunu anlayamadım"
            elif k == "imkansiz":
                return "Bunu gerçekleştiremiyorum"
            else:
                return f"{k} komutunu uyguluyorum"

         # Join all formatted commands with "ve" (and)
        utter = " ve ".join(format_command(c) for c in cmds)

    logger.info(f"[TTS] {utter}")

    # Define sync TTS API call
    def sync():
        return client.audio.speech.create(
            model=CONFIG["TTS_MODEL"],  # TTS model name
            voice=CONFIG["TTS_VOICE"], # Voice selection (e.g., Alloy)
            input=utter,  # Final text to synthesize
            response_format="wav"  # Output format
        )

    # Call TTS API in background thread
    res = await asyncio.to_thread(sync)

    # Read audio bytes from response
    data = getattr(res, 'audio', res.read())

    # Write synthesized audio to temporary WAV file
    wav = TMP_DIR / f"tts_{uuid.uuid4().hex}.wav"
    wav.write_bytes(data)

    return wav # Return path to the TTS audio file

# === VAD & UTILITY ========================================================

# Function to determine if a WAV file contains speech using WebRTC VAD
def is_speech(wav: Path) -> bool:

    # Read WAV file to get sample rate and raw audio data
    rate, data = read(str(wav))

    # Initialize WebRTC Voice Activity Detector with mode 2 (medium sensitivity)
    vad = webrtcvad.Vad(2)

    # Convert audio data to raw bytes for VAD processing
    frames = data.tobytes()

    # Define the size of each frame (30 ms) in bytes (16-bit samples = 2 bytes/sample)
    win = int(rate * 30 / 1000) * 2

    # Iterate through the audio data in chunks of 30 ms
    for i in range(0, len(frames), win):
        chunk = frames[i:i+win]

        # If the final chunk is too short, break the loop
        if len(chunk) < win: break

        # If VAD detects speech in this chunk, return True
        if vad.is_speech(chunk, rate): return True
    return False

# === PLAYBACK =============================================================

async def play_wav(wav: Path):
    logger.info(f"[Play] {wav}")
    subprocess.run(["aplay","-D",CONFIG["USB_SPEAKER_DEVICE"],str(wav)])

# === PIPELINE TASKS =======================================================

# Task 1: Voice Activity Detection (VAD) and speaker identification
async def vad_task(q_raw: asyncio.Queue, q_stt: asyncio.Queue):
    logger.info("[VAD Task] start")
    while True:
        wav = await q_raw.get()

        # 1) Skip if the vehicle is not active
        if not client_sender.is_arac_aktif():
            logger.info("[VAD Task] Araç pasif - ses işlenmiyor")
            q_raw.task_done()
            continue

        # 2) Check if there is speech in the audio
        if await asyncio.to_thread(is_speech, wav):

            # Identify the speaker in a background thread
            speaker = await asyncio.to_thread(identify_speaker, wav)

            if speaker:
                logger.info(f"[VAD] Konuşan kişi tanındı: {speaker}")
                await q_stt.put(wav)
            elif not energy_low:
                logger.info("[VAD] Tanımadığım kişi konuştu, komut işlenmeyecek.")
                unknown_wav = await openai_tts("Konuşan kişi tanınmıyor.")
                await play_wav(unknown_wav)

        q_raw.task_done()

# Task 2: Speech-to-Text (STT)
async def stt_task(q_stt: asyncio.Queue, q_llm: asyncio.Queue):
    logger.info("[STT Task] start")
    while True:
        wav = await q_stt.get()
        text = await stt_whisper(wav) # Transcribe speech
        await q_llm.put(text)  # Pass transcription to LLM
        q_stt.task_done()

# Task 3: Natural Language Understanding (LLM)
async def llm_task(q_llm: asyncio.Queue, q_cmd: asyncio.Queue):
    logger.info("[LLM Task] start")
    while True:
        text = await q_llm.get()
        logger.info(f"[LLM Task] Transcribed text: {text}")
        try:
            cmds = await openai_llm(text) # Parse command from user text
            logger.info(f"[LLM Task] Parsed cmds: {cmds}")
        except Exception as e:
            logger.error(f"[LLM Task] HATA: {e}")
            cmds = []

       # Send parsed command details to the client interface
        veri_diger = {
            "type": "durum",
            "sesliKomut": text,
            "yorumlananKomutlar": cmds,
            "gecmis": [
                {
                    "zaman": time.strftime("%H:%M:%S"),
                    "komut": c.get("komut", "bilinmiyor"),
                    "aciklama": "Yorumlandı"
                } for c in cmds
            ] if cmds else []
        }

        try:
            client_sender.send_json_data(veri_diger)
        except Exception as e:
            logger.error(f"Veri gönderilemedi: {e}")


        await q_cmd.put(cmds) # Pass command to speaker task
        q_llm.task_done()

# Task 4: TTS feedback and Arduino command dispatch
async def speaker_task(q_cmd: asyncio.Queue, q_ard: asyncio.Queue):
    logger.info("[Speaker Task] start")
    while True:
        cmds = await q_cmd.get()

        # Skip if the vehicle is not active
        if not client_sender.is_arac_aktif():
            logger.info("[Speaker Task] Araç pasif - komut işlenmiyor")
            q_cmd.task_done()
            continue

        # Inner function to process each command
        async def handle_command(c):
            cmd = c.get("komut") or c.get("cmd")
            dur = c.get("sure")
            ang = c.get("aci") or c.get("açı")

            if cmd == "gecersiz":

                # Generate natural rejection sentence based on the verb ending
                girdi = c.get("girdi", "").strip().lower()

                # Inflect simple verb endings
                if girdi.endswith("la"):
                    cumle = f"Ben bir arabayım, {girdi[:-1]}yamam"
                elif girdi.endswith("le"):
                    cumle = f"Ben bir arabayım, {girdi[:-1]}yemem"
                elif girdi.endswith("a"):
                    cumle = f"Ben bir arabayım, {girdi}mam"
                elif girdi.endswith("e"):
                    cumle = f"Ben bir arabayım, {girdi}mem"
                elif girdi.endswith("et"):  
                    cumle = f"Ben bir arabayım, {girdi[:-2]}edemem"
                elif girdi.endswith("yap"):
                    cumle = f"Ben bir arabayım, {girdi}amam"
                elif girdi.endswith("uç"):
                    cumle = f"Ben bir arabayım, {girdi}amam"  
                elif girdi.endswith("yüz"):
                    cumle = f"Ben bir arabayım, {girdi}emem"  
                elif girdi.endswith("kıl"):
                    cumle = f"Ben bir arabayım, {girdi}amam" 
                elif girdi.endswith("mısın?"):
                    kelime = girdi[:-7]
                    if kelime.endswith("ar"):
                        cumle = f"Ben bir arabayım, {kelime[:-2]}amam"
                elif girdi.endswith("misin?"):
                    kelime = girdi[:-7]
                    if kelime.endswith("er"):
                        cumle = f"Ben bir arabayım, {kelime[:-2]}emem"
                    elif kelime.endswith("bilir"):    
                        bilir_eki=kelime[:-5]
                        if bilir_eki.endswith("e"):
                            cumle = f"Ben bir arabayım, {bilir_eki[:-1]}emem"
                        elif bilir_eki.endswith("a"):
                            cumle = f"Ben bir arabayım, {bilir_eki[:-1]}amam"
                else:
                    cumle = f"Ben bir arabayım, {girdi} yapamam"
                wav = await openai_tts(cumle)
                await play_wav(wav)

            elif cmd == "imkansiz":
                pass # No TTS for impossible commands

            else:
                await send_and_speak(cmd, dur, ang)

        # Inner function: speak the command and send to Arduino
        async def send_and_speak(cmd, dur, ang):
            cmd_obj = {"komut": cmd}
            if dur is not None:
                cmd_obj["sure"] = dur
            if ang is not None:
                cmd_obj["aci"] = ang

            # Lowercase letters can be used for TTS (to make Turkish apear more natural)
            wav = await openai_tts([cmd_obj])
            await play_wav(wav)

            # Use uppercase when sending to arduino
            await asyncio.to_thread(send_to_arduino, cmd.upper(), logger, dur, ang)

        if not cmds:
            logger.warning("[Speaker Task] Boş komut geldi, konuşma yapılmayacak.")

        for c in cmds:
            await handle_command(c)

        q_cmd.task_done()



# === MAIN LOOP ============================================================

# Entry point for the asynchronous system
async def main():
    # Wait for Arduino to send "ready" status
    logger.info("Waiting for Arduino ready...")
    start = time.time()
    while time.time() - start < CONFIG["ACK_TIMEOUT"]:
        line = read_from_arduino(logger)
        if line:
            try:
                msg = json.loads(line)
                if msg.get("status") == "ready":
                    logger.info("Arduino is ready. Starting main loop.")
                    # ready notice
                    try:
                        # Inform user that system is ready
                        ready_wav = await openai_tts("Sistem hazır. Lütfen aracı aktif hale getirin.")
                        await play_wav(ready_wav)
                    except Exception as e:
                        logger.error(f"Ready notice failed: {e}")
                    break
            except json.JSONDecodeError:
                pass # Ignore malformed lines

     # Create task queues
    raw_q = asyncio.Queue() # Raw audio
    stt_q = asyncio.Queue() # Speech-to-text
    llm_q = asyncio.Queue() # LLM interpretation
    cmd_q = asyncio.Queue() # Commands


    # Start capture loop and pipeline tasks
    asyncio.create_task(capture_loop(raw_q))
    tasks = [
        asyncio.create_task(vad_task(raw_q, stt_q)),
        asyncio.create_task(stt_task(stt_q, llm_q)),
        asyncio.create_task(llm_task(llm_q, cmd_q)),
        asyncio.create_task(speaker_task(cmd_q, None))
    ]

    # Wait for all tasks to run forever (until cancelled)
    await asyncio.gather(*tasks)

# Run the main loop if this script is executed directly
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
