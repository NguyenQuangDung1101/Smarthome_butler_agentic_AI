import collections
import numpy as np
import sounddevice as sd
import webrtcvad
from faster_whisper import WhisperModel
import warnings
import asyncio
import edge_tts
from playsound import playsound

warnings.filterwarnings("ignore", category=UserWarning)


# =========================
# Config
# =========================
SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_DURATION_MS = 30          # 10, 20, or 30 for webrtcvad
VAD_AGGRESSIVENESS = 3          # 0 = less strict, 3 = more strict
START_TRIGGER_FRAMES = 15       # speech frames needed to start recording
END_TRIGGER_FRAMES = 120        # silence frames needed to stop recording
MAX_RECORD_SECONDS = 40         # safety limit (in seconds)
WHISPER_MODEL_SIZE = "base"     # tiny, base, small, medium, large-v2, large-v3


# =========================
# English (US)
# =========================
# en-US-AvaNeural           # young
# en-US-MichelleNeural      # deep female
# en-US-JennyNeural         # friday
# en-US-AndrewMultilingualNeural            # damnnnn shit Ryan Gosling =)))
# en-US-SteffanNeural       # deep male

# =========================
# English (UK)
# =========================
# en-GB-ThomasNeural        # young ielts listening 1
# en-GB-RyanNeural          # deep ielts listening 2
# en-GB-SoniaNeural         # female ielts listening 3

TTS_VOICE = "en-GB-RyanNeural"


# =========================
# Load models once
# =========================
vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)

stt_model = WhisperModel(
    WHISPER_MODEL_SIZE,
    compute_type="int8"
)


# =========================
# TTS
# =========================
async def _tts_async(text: str, output_file: str = "tts_output.mp3") -> None:
    communicate = edge_tts.Communicate(text, TTS_VOICE)
    await communicate.save(output_file)

def text_to_speech(text: str) -> None:
    if not text.strip():
        return
    output_file = "tts_output.mp3"
    asyncio.run(_tts_async(text, output_file))
    playsound(output_file)


# =========================
# STT: receive audio array, not file path
# audio: int16 numpy array, shape (n,) or (n, 1)
# =========================
def speech_to_text(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> str:
    if audio.ndim > 1:
        audio = audio.squeeze()

    if audio.dtype != np.int16:
        audio = audio.astype(np.int16)

    audio_float32 = audio.astype(np.float32) / 32768.0

    segments, _ = stt_model.transcribe(
        audio_float32,
        language="en",
        beam_size=5
    )

    text_parts = [seg.text.strip() for seg in segments if seg.text.strip()]
    return " ".join(text_parts).strip()


# =========================
# Listen until voice starts, then record until silence
# Return int16 numpy array
# =========================
def listen_for_speech(
    sample_rate: int = SAMPLE_RATE,
    frame_duration_ms: int = FRAME_DURATION_MS,
    max_record_seconds: int = MAX_RECORD_SECONDS,
) -> np.ndarray:
    frame_size = int(sample_rate * frame_duration_ms / 1000)
    bytes_per_frame = frame_size * 2  # int16 = 2 bytes
    max_frames = int(max_record_seconds * 1000 / frame_duration_ms)

    pre_speech_buffer = collections.deque(maxlen=10)
    recorded_frames = []

    speech_count = 0
    silence_count = 0
    triggered = False
    total_frames = 0

    print("Waiting for speech...")

    with sd.InputStream(
        samplerate=sample_rate,
        channels=CHANNELS,
        dtype="int16",
        blocksize=frame_size
    ) as stream:
        while True:
            audio_chunk, _ = stream.read(frame_size)   # shape: (frame_size, 1)
            frame = audio_chunk[:, 0].copy()          # shape: (frame_size,)
            frame_bytes = frame.tobytes()

            if len(frame_bytes) != bytes_per_frame:
                continue

            is_speech = vad.is_speech(frame_bytes, sample_rate)

            if not triggered:
                pre_speech_buffer.append(frame)

                if is_speech:
                    speech_count += 1
                else:
                    speech_count = 0

                # print(speech_count)
                
                if speech_count >= START_TRIGGER_FRAMES:
                    triggered = True
                    print("Speech detected. Recording...")
                    recorded_frames.extend(list(pre_speech_buffer))
                    pre_speech_buffer.clear()
            else:
                recorded_frames.append(frame)
                total_frames += 1

                if is_speech:
                    silence_count = 0
                else:
                    silence_count += 1
                if silence_count >= END_TRIGGER_FRAMES:
                    print("Silence detected. Stop recording.")
                    break
                if total_frames >= max_frames:
                    print("Max recording time reached.")
                    break

    if not recorded_frames:
        return np.array([], dtype=np.int16)

    return np.concatenate(recorded_frames).astype(np.int16)



def listen_and_repeat() -> str:
    audio = listen_for_speech()

    if audio.size == 0:
        print("No speech captured.")
        return ""

    print("Transcribing...")
    text = speech_to_text(audio)

    if not text:
        print("No speech recognized.")
        text_to_speech("I did not catch that.")
        return ""

    print("You said:", text)
    text_to_speech(text)
    return text


if __name__ == "__main__":
    listen_and_repeat()