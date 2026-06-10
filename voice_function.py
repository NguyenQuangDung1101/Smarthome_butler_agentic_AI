import collections
import io
import numpy as np
import sounddevice as sd
import webrtcvad
import av
from faster_whisper import WhisperModel
import warnings
import asyncio
import edge_tts

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
# en-GB-RyanNeural          # deep ielts listening 2    ///top1///
# en-GB-SoniaNeural         # female ielts listening 3

TTS_VOICE = "en-GB-RyanNeural"


# =========================
# Load models once
# =========================
vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)

stt_model = WhisperModel(
    WHISPER_MODEL_SIZE,
    device="cpu", 
    compute_type="float32"
)


# =========================
# TTS
# =========================
async def _tts_collect(text: str, stop_event=None) -> bytes:
    """Stream audio bytes from edge_tts into memory."""
    communicate = edge_tts.Communicate(text, TTS_VOICE)
    chunks = []
    async for chunk in communicate.stream():
        if stop_event is not None and stop_event.is_set():
            break
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)

def _play_audio_bytes(mp3_bytes: bytes, stop_event=None) -> None:
    """Decode mp3 bytes with av and play directly via sounddevice."""
    if stop_event is not None and stop_event.is_set():
        return

    buf = io.BytesIO(mp3_bytes)
    container = av.open(buf)
    audio_stream = container.streams.audio[0]
    sample_rate = audio_stream.codec_context.sample_rate or 44100

    resampler = av.AudioResampler(format="fltp", layout="stereo", rate=sample_rate)
    out_frames = []

    for frame in container.decode(audio_stream):
        if stop_event is not None and stop_event.is_set():
            container.close()
            return
        for rf in resampler.resample(frame):
            out_frames.append(rf.to_ndarray().T)   # (samples, 2) float32
    for rf in resampler.resample(None):            # flush resampler
        out_frames.append(rf.to_ndarray().T)

    container.close()

    if out_frames:
        audio = np.concatenate(out_frames, axis=0)
        audio = np.ascontiguousarray(audio)
        chunk_size = max(1, int(sample_rate * 0.1))
        try:
            with sd.OutputStream(
                samplerate=sample_rate,
                channels=audio.shape[1],
                dtype=audio.dtype
            ) as stream:
                for start in range(0, len(audio), chunk_size):
                    if stop_event is not None and stop_event.is_set():
                        sd.stop()
                        break
                    stream.write(np.ascontiguousarray(audio[start:start + chunk_size]))
        finally:
            if stop_event is not None and stop_event.is_set():
                sd.stop()

def text_to_speech(text: str, stop_event=None) -> None:
    text = text.replace('*', '')
    if not text.strip():
        return
    mp3_data = asyncio.run(_tts_collect(text, stop_event=stop_event))
    if mp3_data and not (stop_event is not None and stop_event.is_set()):
        _play_audio_bytes(mp3_data, stop_event=stop_event)


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
    stop_event=None,        # optional threading.Event – set it to abort early
    state_callback=None,
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
    if state_callback is not None:
        state_callback("speech_wait")

    with sd.InputStream(
        samplerate=sample_rate,
        channels=CHANNELS,
        dtype="int16",
        blocksize=frame_size
    ) as stream:
        while True:
            if stop_event is not None and stop_event.is_set():
                break
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
                    if state_callback is not None:
                        state_callback("listening")
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