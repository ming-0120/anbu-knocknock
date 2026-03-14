import { useEffect, useRef, useState } from "react";

type Props = {
  residentId: number;
  operatorId: number;
  onClose: () => void;
};

const CallModal = ({ residentId, operatorId, onClose }: Props) => {

  const audioRef = useRef<HTMLAudioElement | null>(null);

  const [recordingUrl, setRecordingUrl] = useState<string | null>(null);
  const [callStartedAt, setCallStartedAt] = useState<number | null>(null);
  const [duration, setDuration] = useState(0);
  const [callEnded, setCallEnded] = useState(false);

  const [note, setNote] = useState("");
  const [summary, setSummary] = useState<string | null>(null);

  const timerRef = useRef<any>(null);


  useEffect(() => {

    async function startCall() {

      const res = await fetch("/api/calls/start", {
        method: "POST"
      });

      const data = await res.json();

      setRecordingUrl(data.recording_url);

      const audio = new Audio(data.recording_url);

      audioRef.current = audio;

      audio.play();

      const start = Date.now();
      setCallStartedAt(start);

      timerRef.current = setInterval(() => {
        setDuration(Math.floor((Date.now() - start) / 1000));
      }, 1000);
    }

    startCall();

    return () => {
      clearInterval(timerRef.current);
    };

  }, []);


  const endCall = async () => {

    clearInterval(timerRef.current);

    audioRef.current?.pause();

    setCallEnded(true);

    const res = await fetch("/api/calls/end", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        resident_id: residentId,
        operator_id: operatorId,
        duration_sec: duration,
        recording_url: recordingUrl
      })
    });

    const data = await res.json();

    return data.call_id;
  };


  const handleGenerateSummary = async () => {

    const callId = await endCall();

    const res = await fetch("/api/calls", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        call_id: callId,
        text: note
      })
    });

    const data = await res.json();

    setSummary(data.summary);
  };


  const formatTime = (sec: number) => {

    const m = Math.floor(sec / 60);
    const s = sec % 60;

    return `${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`;
  };


  return (
    <>
      <div className="callModal">

        {!callEnded && (

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

        {callEnded && !summary && (

          <div className="callBody">

            <h3>상담 내용 입력</h3>

            <textarea
              value={note}
              onChange={(e)=>setNote(e.target.value)}
              placeholder="통화 내용을 입력하세요"
            />

            <button className="summaryBtn" onClick={handleGenerateSummary}>
              요약 생성
            </button>

          </div>
        )}

        {summary && (

          <div className="callBody">

            <h3>요약 결과</h3>

            <p className="summaryBox">{summary}</p>

            <button className="closeBtn" onClick={onClose}>
              닫기
            </button>   

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

        textarea {
          width: 100%;
          height: 130px;

          border: 1px solid #ddd;
          border-radius: 10px;

          padding: 12px;
          font-size: 14px;

          resize: none;
          margin-bottom: 16px;
        }

        textarea:focus {
          outline: none;
          border-color: #4c7cf0;
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

        .endBtn {
          background: #ff4d4f;
          color: white;
        }

        .summaryBtn {
          background: #4c7cf0;
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