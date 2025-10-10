import pyaudio
from vosk import Model, KaldiRecognizer

# Bạn cần truyền đường dẫn tuyệt đối bằng cách thêm 'r'
model = Model(r"C:/Users/quang/Desktop/Research/smart_house/voice_prompt/vosk_eng_model")
recognizer = KaldiRecognizer(model, 16000)

mic = pyaudio.PyAudio()
stream = mic.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8192)
stream.start_stream()

while True:
    data = stream.read(4096)
    # if len(data) == 0:
    #     break
    if recognizer.AcceptWaveform(data):
        text = recognizer.Result()
        print(text)