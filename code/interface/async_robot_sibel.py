#!/usr/bin/env python3
"""
robot_main.py - ELE495 Asenkron Kuyruk Mimarisi (v1.0+ OpenAI SDK)
Revision 23: Cleaned up syntax, restored defs, fixed Arduino handshake and capture
"""
import client_sender

import os
import asyncio
import json
import uuid
import ast
import logging
import time
from pathlib import Path
from typing import Optional

from openai import OpenAI
import sounddevice as sd
from scipy.io.wavfile import write, read
from scipy.signal import resample
import webrtcvad
import subprocess
import serial
import numpy as np
import re

# === USER CONFIG ==========================================================
CONFIG = {
    "OPENAI_API_KEY": "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",
    "OPENAI_MODEL":    "gpt-4o-mini",
    "WHISPER_MODEL":   "whisper-1",
    "TTS_MODEL":       "tts-1",
    "TTS_VOICE":       "alloy",
    "CAPTURE_RATE":    48000,           # Record at 44.1 kHz
    "PROCESS_RATE":    16000,           # Resample to 16 kHz for Whisper
    "CHUNK_SEC":       5,
    "AUDIO_DEVICE":    1,       #  (USB Composite Device mikrofon)
    "USB_SPEAKER_DEVICE": "plughw:2,0", # UACDemoV1.0 hoparlör
    "SERIAL_PORT":     "/dev/ttyUSB0",
    "BAUDRATE":        115200,
    "ACK_TIMEOUT":     10.0
}

if not CONFIG["OPENAI_API_KEY"]:
    raise RuntimeError("OPENAI_API_KEY is not set.")

# === CLIENT & CONSTANTS ==================================================
client = OpenAI(api_key=CONFIG["OPENAI_API_KEY"])
CAPTURE_RATE = CONFIG["CAPTURE_RATE"]
PROCESS_RATE = CONFIG["PROCESS_RATE"]
CHUNK = CONFIG["CHUNK_SEC"]
TMP_DIR = Path("/tmp/robot_audio")
TMP_DIR.mkdir(exist_ok=True)

sd.default.device = (CONFIG["AUDIO_DEVICE"], None)
ser = serial.Serial(CONFIG["SERIAL_PORT"], CONFIG["BAUDRATE"], timeout=0)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("robot")

# === ARDUINO HELPERS ======================================================

ser = serial.Serial('/dev/ttyUSB0', 115200)

def send_to_arduino(cmd: str, log, duration: Optional[int] = None,angle: Optional[int] = None) -> bool:
    """Sends JSON command and waits for ack."""
    msg = {"cmd": cmd}
    if duration is not None:
        msg["sure"] = duration
    if angle is not None:
        msg["aci"] = angle

    
    # 🟢 Durum metni oluştur
    # VERİ ARAÇ DURUMU
    
    durum_map = {
        "FORWARD": "ileri gidiyor",
        "BACKWARD": "geri gidiyor",
        "LEFT": "sola dönüyor",
        "RIGHT": "sağa dönüyor",
        "STOP": "duruyor"
    }
    komut_turkce = durum_map.get(cmd.upper(), "bilinmeyen komut")
    if duration:
        durum_aciklama = f"Araç {duration} saniye {komut_turkce}"
    elif angle:
        durum_aciklama = f"Araç {angle} derece {komut_turkce}"
    else:
        durum_aciklama = f"Araç {komut_turkce}"

    veri_arac_durumu = {
        "type": "arac_durumu",
        "aracDurumu": durum_aciklama
    }

    # 🟢 Arayüze gönder
    try:
        client_sender.send_json_data(veri_arac_durumu)
    except Exception as e:
        log.error(f"Durum gönderilemedi: {e}")



    js = json.dumps(msg)
    ser.write((js + "\n").encode())
    log.info(f"UART=> {js}")

    start = time.time()
    buf = ''
    while time.time() - start < CONFIG.get("ACK_TIMEOUT", 2.0):
        if ser.in_waiting:
            c = ser.read(1).decode(errors='ignore')
            buf += c
            if c == '\n':
                line = buf.strip()
                buf = ''
                log.info(f"UART<= {line}")
                try:
                    resp = json.loads(line)
                    if resp.get('ack') == cmd:
                        return True
                except json.JSONDecodeError:
                    log.debug(f"Invalid ack JSON: {line}")
    log.error(f"ACK timeout for {cmd}")
    return False


def read_from_arduino(log) -> Optional[str]:
    """Reads line if available."""
    if ser.in_waiting:
        line = ser.readline().decode().strip()
        log.info(f"UART<= {line}")
        return line
    return None


# === RESAMPLE HELPER ======================================================

def resample_wav(input_path: Path, orig_rate: int, target_rate: int) -> Path:
    rate, data = read(str(input_path))
    if rate == target_rate:
        return input_path
    duration = data.shape[0] / rate
    new_length = int(duration * target_rate)
    data_resampled = resample(data, new_length).astype(np.int16)
    new_path = input_path.with_name(f"{input_path.stem}_{target_rate}hz.wav")
    write(str(new_path), target_rate, data_resampled)
    return new_path

# === AUDIO CAPTURE =======================================================

def capture_raw(log) -> Path:
    raw_path = TMP_DIR / f"raw_{uuid.uuid4().hex}.wav"
    logger.info(f"[Recorder] Recording {CHUNK}s @ {CAPTURE_RATE}Hz to {raw_path}")
    rec = sd.rec(int(CAPTURE_RATE * CHUNK), samplerate=CAPTURE_RATE,
                 channels=1, dtype='int16', device=CONFIG["AUDIO_DEVICE"])
    sd.wait()
    write(str(raw_path), CAPTURE_RATE, rec)
    proc_path = resample_wav(raw_path, CAPTURE_RATE, PROCESS_RATE)
    rate, data = read(str(proc_path))

    # Güvenli RMS hesaplama
    try:
        if data.size == 0:
            rms = 0.0
        else:
            data = data.astype(np.float32)
            max_val = np.iinfo(data.dtype).max if np.issubdtype(data.dtype, np.integer) else 1.0
            normalized = data / (max_val ** 2)
            normalized = normalized[~np.isnan(normalized)]
            normalized = normalized[normalized >= 0]
            if normalized.size == 0:
                rms = 0.0
            else:
                rms = np.sqrt(normalized.mean())
    except Exception as e:
        logger.warning(f"[Recorder] RMS hesaplanırken hata: {e}")
        rms = 0.0

    logger.info(f"[Recorder] Saved {proc_path} | RMS: {rms:.5f}")
    return proc_path


async def capture_loop(raw_q: asyncio.Queue):
    while True:
        # Araç aktif mi kontrol et
        if not client_sender.is_arac_aktif():
            await asyncio.sleep(0.5)  # Araç kapalıysa bekle
            continue
            
        wav = await asyncio.to_thread(capture_raw, logger)
        await raw_q.put(wav)

# === OPENAI HELPERS =======================================================

def SYS_PROMPT() -> str:
    return (
        "Aşağıdaki Türkçe komutu JSON listeye çevir.\n"
        "- 'ileri' → FORWARD, 'geri' → BACKWARD, 'sola' → LEFT, 'sağa' → RIGHT, 'dur' → STOP.\n"
        "Ek veriler: 'sure' (saniye), 'kosul' (engel), 'açı' (derece).\n\n"
        "Çıktı bir JSON liste olmalı. Her komut ayrı bir sözlük nesnesi içinde olmalı.\n\n"

        "Eğer kullanıcıdan gelen cümle anlamlı bir Türkçe ifadeyse ama bu robotun tanıdığı bir komut değilse: (örneğin: 'zıpla', 'uç', 'yüz', 'çay demle', 'elbise giy', 'kahve koy','yemek ye', 'dans et','duş al','namaz kıl','onu getir','dök') gibi emir içeren kelimeler ise \n"
        "→ [{'komut': 'gecersiz', 'girdi': 'kullanıcının söylediği komut'}]\n\n"
        

        "Eğer kullanıcıdan gelen metin\n"
        "- saçma sapan, anlam bozan, küfürlü ya da uydurma kelimeler içeriyorsa\n"
        "- Whisper çıktısı alakasız ve komut dışı ise (örneğin: 'afiyet olsun', 'altyazı mk', 'gözlükten selam', 'tamam canım')\n"
        "- ya da kullanıcı hiç konuşmadıysa / ses boşsa\n"
        "→ [{'komut': 'imkansiz'}]\n\n"

        " Örnekler:\n"
        "Kullanıcı: '2 saniye ileri git' → [{'komut': 'forward', 'sure': 2}]\n"
        "Kullanıcı: 'sağa dön' → [{'komut': 'right'}]\n"
        "Kullanıcı: 'zıpla' → [{'komut': 'gecersiz', 'girdi': 'zıpla'}]\n"
        "Kullanıcı: 'araba afiyet olsun' → [{'komut': 'imkansiz'}]\n"
        "Kullanıcı: hiç konuşmadı (sessizlik) → [{'komut': 'imkansiz'}]\n"
    )



async def stt_whisper(wav: Path) -> str:
    logger.info(f"[STT] Whisper on {wav}")
    def sync():
        with open(wav, 'rb') as f:
            return client.audio.transcriptions.create(
                model=CONFIG["WHISPER_MODEL"], file=f, language="tr"
            ).text
    text = await asyncio.to_thread(sync)
    logger.info(f"[STT] {text}")
    return text

async def openai_llm(text: str) -> list:
    logger.info(f"[LLM] {text}")
    def sync():
        return client.chat.completions.create(
            model=CONFIG["OPENAI_MODEL"], temperature=0.0,
            messages=[{"role":"system","content":SYS_PROMPT()},
                      {"role":"user","content":text}]
        )
    resp = await asyncio.to_thread(sync)
    raw = re.sub(r"```[\w]*\n|```", "", resp.choices[0].message.content).strip()
    logger.debug(f"[LLM raw response] {raw}")
    logger.info(f"[LLM] got: {raw}")
    try:
        return ast.literal_eval(raw)
    except:
        logger.error("LLM parse failed")
        return []

async def openai_tts(cmds) -> Path:
    # Eğer doğrudan metin verildiyse (örnek: "Sistem hazır")
    if isinstance(cmds, str):
        utter = cmds
    else:
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
                    return f"{a} derece sağa dönüyorum"
                else:
                    return "Sağa dönüyorum"
            elif k == "stop":
                return "Duruyorum"
            elif k == "gecersiz":
                return f"'{girdi}' komutunu anlayamadım"
            elif k == "imkansiz":
                return "Bunu gerçekleştiremiyorum"
            else:
                return f"{k} komutunu uyguluyorum"

        # Her komutu doğal Türkçe'ye çevir
        utter = " ve ".join(format_command(c) for c in cmds)

    logger.info(f"[TTS] {utter}")

    def sync():
        return client.audio.speech.create(
            model=CONFIG["TTS_MODEL"],
            voice=CONFIG["TTS_VOICE"],
            input=utter,
            response_format="wav"
        )

    res = await asyncio.to_thread(sync)
    data = getattr(res, 'audio', res.read())
    wav = TMP_DIR / f"tts_{uuid.uuid4().hex}.wav"
    wav.write_bytes(data)
    return wav



# === VAD & UTILITY ========================================================

def is_speech(wav: Path) -> bool:
    rate, data = read(str(wav))
    vad = webrtcvad.Vad(2)
    frames = data.tobytes()
    win = int(rate * 30 / 1000) * 2
    for i in range(0, len(frames), win):
        chunk = frames[i:i+win]
        if len(chunk) < win: break
        if vad.is_speech(chunk, rate): return True
    return False

# === PLAYBACK =============================================================

async def play_wav(wav: Path):
    logger.info(f"[Play] {wav}")
    subprocess.run(["aplay","-D",CONFIG["USB_SPEAKER_DEVICE"],str(wav)])

# === PIPELINE TASKS =======================================================

async def vad_task(q_raw: asyncio.Queue, q_stt: asyncio.Queue):
    logger.info("[VAD Task] start")
    while True:
        wav = await q_raw.get()
        
        # Araç aktif mi kontrol et
        if not client_sender.is_arac_aktif():
            logger.info("[VAD Task] Araç pasif - ses işlenmiyor")
            q_raw.task_done()
            continue
            
        if await asyncio.to_thread(is_speech, wav):
            await q_stt.put(wav)
        q_raw.task_done()

async def stt_task(q_stt: asyncio.Queue, q_llm: asyncio.Queue):
    logger.info("[STT Task] start")
    while True:
        wav = await q_stt.get()
        text = await stt_whisper(wav)
        await q_llm.put(text)
        q_stt.task_done()

async def llm_task(q_llm: asyncio.Queue, q_cmd: asyncio.Queue):
    logger.info("[LLM Task] start")
    while True:
        text = await q_llm.get()
        logger.info(f"[LLM Task] Transcribed text: {text}")
        try:
            cmds = await openai_llm(text)
            logger.info(f"[LLM Task] Parsed cmds: {cmds}")
        except Exception as e:
            logger.error(f"[LLM Task] HATA: {e}")
            cmds = []

        # Mevcut veri gönderme ve komut kuyruğu
        # İlk komutun durumunu alalım
        # VERİ DİĞER 

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



        await q_cmd.put(cmds)
        q_llm.task_done()


async def speaker_task(q_cmd: asyncio.Queue, q_ard: asyncio.Queue):
    logger.info("[Speaker Task] start")
    while True:
        cmds = await q_cmd.get()

        # Araç aktif mi kontrol et
        if not client_sender.is_arac_aktif():
            logger.info("[Speaker Task] Araç pasif - komut işlenmiyor")
            q_cmd.task_done()
            continue

        # Mevcut komut işleme kodları buraya gelecek...
        # (Önceki handle_command ve send_and_speak fonksiyonları aynı kalacak)

        async def handle_command(c):
            cmd = c.get("komut") or c.get("cmd")
            dur = c.get("sure")
            ang = c.get("aci") or c.get("açı")

            if cmd == "gecersiz":
                girdi = c.get("girdi", "").strip().lower()

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
                else:
                    cumle = f"Ben bir arabayım, {girdi} yapamam"

                wav = await openai_tts(cumle)
                await play_wav(wav)

            elif cmd == "imkansiz":
                pass

            else:
                await send_and_speak(cmd, dur, ang)

        async def send_and_speak(cmd, dur, ang):
            cmd_obj = {"komut": cmd}
            if dur is not None:
                cmd_obj["sure"] = dur
            if ang is not None:
                cmd_obj["aci"] = ang

            wav = await openai_tts([cmd_obj])
            await play_wav(wav)

            await asyncio.to_thread(send_to_arduino, cmd.upper(), logger, dur, ang)

        if not cmds:
            logger.warning("[Speaker Task] Boş komut geldi, konuşma yapılmayacak.")

        for c in cmds:
            await handle_command(c)

        q_cmd.task_done()


# === MAIN LOOP ============================================================

async def main():
    # Arduino handshake
    logger.info("Waiting for Arduino ready...")
    start = time.time()
    while time.time() - start < CONFIG["ACK_TIMEOUT"]:
        line = read_from_arduino(logger)
        if line:
            try:
                msg = json.loads(line)
                if msg.get("status") == "ready":
                    logger.info("Arduino is ready. Starting main loop.")
                    
                    # Sistem hazır mesajı - ama araç henüz aktif değil
                    try:
                        ready_wav = await openai_tts("Sistem hazır. Lütfen aracı aktif hale getirin.")
                        await play_wav(ready_wav)
                    except Exception as e:
                        logger.error(f"Ready notice failed: {e}")
                    break
            except json.JSONDecodeError:
                pass

    # Pipeline başlat
    raw_q = asyncio.Queue()
    stt_q = asyncio.Queue()
    llm_q = asyncio.Queue()
    cmd_q = asyncio.Queue()

    asyncio.create_task(capture_loop(raw_q))
    tasks = [
        asyncio.create_task(vad_task(raw_q, stt_q)),
        asyncio.create_task(stt_task(stt_q, llm_q)),
        asyncio.create_task(llm_task(llm_q, cmd_q)),
        asyncio.create_task(speaker_task(cmd_q, None))
    ]
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")

