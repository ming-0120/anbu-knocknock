from openai import OpenAI

client = OpenAI()

def summarize_text(text: str) -> str:

    prompt = f"""
다음은 상담 통화 내용이다.

{text}

다음 형식으로 요약하라.

1 상담 내용
2 건강 상태
3 위험 여부
"""

    res = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return res.choices[0].message.content