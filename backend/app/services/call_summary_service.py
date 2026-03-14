import os
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")

client = OpenAI(api_key=OPENAI_API_KEY)

async def summarize_call_text(stt_text: str):

    prompt = f"""
다음 독거노인 안부 확인 통화 내용을
1~2문장으로 요약하라.

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