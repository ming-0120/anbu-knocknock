import asyncio
import edge_tts
import os

dialogs = [
"""
상담사: 안녕하세요 어르신 안부 확인 전화 드렸습니다.
어르신: 네 안녕하세요.
상담사: 오늘 건강 상태는 어떠세요?
어르신: 괜찮아요. 조금 피곤하긴 한데 큰 문제는 없어요.
""",

"""
상담사: 안녕하세요 어르신 오늘 날씨가 많이 추워졌습니다.
어르신: 네 그래서 오늘은 집에만 있었어요.
상담사: 외출은 안 하셨군요.
어르신: 네 오늘은 안 나갔습니다.
""",

"""
상담사: 안녕하세요 어르신 약은 잘 드시고 계신가요?
어르신: 네 아침에 먹었습니다.
상담사: 최근에 어지럽거나 불편한 곳은 없으세요?
어르신: 가끔 허리가 조금 아파요.
""",

"""
상담사: 안녕하세요 어르신 오늘 식사는 하셨나요?
어르신: 네 아침에 죽 먹었습니다.
상담사: 요즘 잠은 잘 주무세요?
어르신: 가끔 새벽에 깨긴 하는데 괜찮아요.
""",

"""
상담사: 안녕하세요 어르신 안부 확인 전화입니다.
어르신: 네 반갑습니다.
상담사: 오늘 컨디션은 어떠세요?
어르신: 괜찮은 편이에요.
"""
]

VOICE = "ko-KR-SunHiNeural"

os.makedirs("recordings", exist_ok=True)

async def main():

    for i, text in enumerate(dialogs, 1):

        path = f"recordings/call{i}.wav"

        tts = edge_tts.Communicate(
            text,
            VOICE
        )

        await tts.save(path)

        print("created:", path)

asyncio.run(main())