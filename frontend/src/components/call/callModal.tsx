import { useEffect, useRef, useState } from "react";

type Props = {
  residentId: number;
  operatorId: number;
  onClose: () => void;
};

const CallModal = ({ residentId, operatorId, onClose }: Props) => {

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const timerRef = useRef<any>(null);

  const [callId, setCallId] = useState<number | null>(null);

  const [callStartedAt, setCallStartedAt] = useState<number | null>(null);
  const [duration, setDuration] = useState(0);
  const [callEnded, setCallEnded] = useState(false);
  const [connecting, setConnecting] = useState(false);

  const [summary, setSummary] = useState<string | null>(null);

  // 🔵 통화 시작
  const startCall = async () => {

    setConnecting(true);

    const res = await fetch("/api/call/start", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        resident_id: residentId,
        operator_id: operatorId
      })
    });

    const data = await res.json();
    setCallId(data.call_id);

    await new Promise(r => setTimeout(r, 800));

    if (data.recording_url) {

      const audio = new Audio(data.recording_url);
      audioRef.current = audio;

      try {
        await audio.play();
      } catch (e) {
        console.warn("audio play blocked", e);
      }

      // 🔥 오디오 끝나면 자동 종료
      audio.onended = () => {
        endCall();
      };
    }

    setConnecting(false);

    const start = Date.now();
    setCallStartedAt(start);

    timerRef.current = setInterval(() => {
      setDuration(Math.floor((Date.now() - start) / 1000));
    }, 1000);
  };

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      audioRef.current?.pause();
    };
  }, []);

  // 🔥 summary retry 함수 (핵심)
  const getSummaryWithRetry = async (callId: number) => {

    for (let i = 0; i < 5; i++) {

      const res = await fetch("/api/call/summary", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          call_id: callId
        })
      });

      const data = await res.json();

      // 성공
      if (!data.error) {
        return data.summary;
      }

      // 실패 → 대기 후 재시도
      await new Promise(r => setTimeout(r, 500));
    }

    return "요약 생성 실패";
  };

  // 🔥 통화 종료 + 자동 요약
  const endCall = async () => {

    if (!callId) return;

    if (timerRef.current) clearInterval(timerRef.current);

    audioRef.current?.pause();

    // 1. 통화 종료
    await fetch("/api/call/end", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        call_id: callId,
        duration_sec: duration,
        outcome: "connected"
      })
    });

    setCallEnded(true);

    // 2. 요약 생성 (retry 기반)
    try {
      const summary = await getSummaryWithRetry(callId);
      setSummary(summary);
    } catch (e) {
      console.error("summary error", e);
      setSummary("요약 생성 중 오류 발생");
    }
  };

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`;
  };

  return (
    <>
      <div className="callModal">

        {/* 🔵 통화 시작 전 */}
        {!callStartedAt && (
          <div className="callBody">
            <h2>통화를 시작하시겠습니까?</h2>

            <button className="startBtn" onClick={startCall}>
              통화 시작
            </button>
          </div>
        )}

        {/* 🔵 연결중 */}
        {callStartedAt && connecting && (
          <div className="callBody">
            <h2>연결 중...</h2>
          </div>
        )}

        {/* 🔵 통화중 */}
        {callStartedAt && !connecting && !callEnded && (
          <div className="callBody">

            <h2>통화 중...</h2>

            <div className="timer">
              {formatTime(duration)}
            </div>

            <button className="endBtn" onClick={endCall}>
              통화 종료
            </button>

          </div>
        )}

        {/* 🔵 요약 결과 */}
        {callEnded && summary && (
          <div className="callBody">

            <h3>요약 결과</h3>

            <p className="summaryBox">{summary}</p>

            <button
              className="closeBtn"
              onClick={() => {
                onClose();
                window.location.reload();
              }}
            >
              닫기
            </button>

          </div>
        )}

        {/* 🔵 요약 생성 중 */}
        {callEnded && !summary && (
          <div className="callBody">
            <h3>요약 생성 중...</h3>
          </div>
        )}

      </div>

      <style>{`
        .callModal {
          position: fixed;
          left: 0;
          right: 0;
          bottom: 0;
          background: #fff;
          border-top-left-radius: 18px;
          border-top-right-radius: 18px;
          padding: 24px 20px 30px;
          box-shadow: 0 -4px 16px rgba(0,0,0,0.08);
          z-index: 2000;
        }

        .callBody {
          text-align: center;
        }

        h2, h3 {
          margin-bottom: 16px;
          font-weight: 600;
          color: #222;
        }

        .timer {
          font-size: 42px;
          font-weight: 700;
          margin: 28px 0 36px;
          letter-spacing: 2px;
        }

        button {
          width: 100%;
          height: 46px;
          border: none;
          border-radius: 10px;
          font-size: 15px;
          font-weight: 600;
          cursor: pointer;
        }

        .startBtn {
          background: #4caf50;
          color: white;
        }

        .endBtn {
          background: #ff4d4f;
          color: white;
        }

        .closeBtn {
          background: #555;
          color: white;
        }

        .summaryBox {
          background: #f6f7fb;
          padding: 14px;
          border-radius: 10px;
          margin-bottom: 16px;
          font-size: 14px;
          line-height: 1.6;
        }
      `}</style>
    </>
  );
};

export default CallModal;