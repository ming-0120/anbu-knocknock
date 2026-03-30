import whisper
import tempfile
import requests

model = whisper.load_model("base")

def download_audio(url: str) -> str:
    """
    recording_url에서 audio 다운로드 후
    임시 파일로 저장
    """

    res = requests.get(url)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".m4a")
    tmp.write(res.content)
    tmp.close()

    return tmp.name


def speech_to_text(recording_url: str) -> str:
    """
    녹음 파일 → STT
    """

    audio_path = download_audio(recording_url)

    result = model.transcribe(audio_path)

    return result["text"]