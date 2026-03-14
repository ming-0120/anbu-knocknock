import os
from openai import OpenAI

# 환경 변수에서 API 설정 읽기
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

client = OpenAI(api_key=OPENAI_API_KEY)


def generate_stt_text(audio_path: str):

    with open(audio_path, "rb") as audio_file:

        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=audio_file
        )

    return transcript.text


def summarize_call_text(stt_text: str):

    prompt = f"""
다음 독거노인 안부 확인 통화 내용을 1~2문장으로 요약하라.

통화 내용:
{stt_text}
"""

    res = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    return res.choices[0].message.content.strip()


def main():

    audio_path = "call.wav"   # 테스트할 녹음 파일

    print("1. STT 실행 중...\n")

    stt_text = generate_stt_text(audio_path)

    print("STT 결과:\n")
    print(stt_text)

    print("\n2. 요약 생성 중...\n")

    summary = summarize_call_text(stt_text)

    print("요약 결과:\n")
    print(summary)


if __name__ == "__main__":
    main()