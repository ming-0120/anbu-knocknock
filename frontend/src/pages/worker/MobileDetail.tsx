import { useLocation, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import type { CSSProperties } from "react";
import CallModal from "../../components/call/callModal";

type TaskType = {
  task_id: number; resident_id: number; alert_id: number; operator_id: number;
  name: string; gu: string; address_main: string; phone: string;
  guardian_phone?: string; lat: number; lon: number; risk_score: number;
  last_activity: string; profile_image_url?: string; reason_codes?: any;
  age?: number; gender?: string; summary?:string;
};

function getElapsedText(lastActivity: string) {
  const now = new Date().getTime();
  const last = new Date(lastActivity).getTime();
  const diffMin = Math.floor((now - last) / 60000);
  if (diffMin < 0) return "방금 전";
  if (diffMin < 60) return `${diffMin}분`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}시간`;
  const diffDay = Math.floor(diffHour / 24);
  return `${diffDay}일`;
}

function getRiskLevel(score: number) {
  if (score >= 0.8) return "응급";
  if (score >= 0.6) return "위험";
  if (score >= 0.3) return "주의";
  return "정상";
}

export default function MobileDetail() {
  const location = useLocation();
  const navigate = useNavigate();
  const task = location.state?.task as TaskType;

  const [memo, setMemo] = useState("");
  const [result, setResult] = useState("");
  const [summary, setSummary] = useState("");
  const [showCallModal, setShowCallModal] = useState(false);
  const [callTarget, setCallTarget] = useState<"resident" | "guardian" | null>(null);

  // ✅ 성별에 따른 이미지 결정 로직
  const displayProfileImg = () => {
    if (task?.profile_image_url) return task.profile_image_url;
    const g = task?.gender?.toLowerCase();
    if (g === "female" || g === "여성" || g === "여") {
      return "/images/female-profile.png";
    }
    return "/images/male-profile.png";
  };

  useEffect(() => {
    if (!task) return;
    async function loadSummary() {
      try {
        const callRes = await fetch(`/api/call/latest/${task.resident_id}`);
        const callData = await callRes.json();
        if (!callData?.call_id) return;
        const sumRes = await fetch(`/api/call/summary/${callData.call_id}`);
        const sumData = await sumRes.json();
        setSummary(sumData.summary || "");
      } catch (e) {
        console.error("summary load fail", e);
      }
    }
    loadSummary();
  }, [task]);

  if (!task) return <div style={{ padding: "20px" }}>데이터 없음</div>;

  // const rc = task.reason_codes;
  const riskLevel = getRiskLevel(task.risk_score);
  const riskColor = task.risk_score >= 0.8 ? "#ef4444" : task.risk_score >= 0.6 ? "#f59e0b" : task.risk_score >= 0.3 ? "#eab308" : "#10b981";

  function openMap() { window.open(`https://map.kakao.com/?q=${task.lat},${task.lon}`); }
  function callResident() { setCallTarget("resident"); setShowCallModal(true); }
  function callGuardian() { setCallTarget("guardian"); setShowCallModal(true); }
  function callEmergency() { window.location.href = `tel:119`; }

  async function saveRecord() {
    if (!result) { alert("처리 결과를 선택해주세요."); return; }
    const taskTypeMap: Record<string, string> = { ok: "정상", wrong_alarm: "오탐", needs_help: "도움 필요", emergency: "응급" };
    const task_type = taskTypeMap[result] || "UNKNOWN";
    const res = await fetch(`/api/alert-actions/${task.alert_id}/close`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ operator_id: task.operator_id, result, task_type, description: memo || null }),
    });
    if (res.ok) { alert("저장되었습니다."); navigate(-1); }
  }

  return (
    <div style={container}>
      <div style={{ ...stickyHeader, borderBottomColor: riskColor }}>
        <div style={headerTop}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <button onClick={() => navigate(-1)} style={backBtn}>←</button>
            <div style={name}>{task.name}</div>
          </div>
          <div style={{ ...badge, backgroundColor: riskColor }}>{riskLevel}</div>
        </div>
        <div style={headerInfo}>
          <div style={{ display: "flex", gap: "24px" }}>
            <div><div style={label}>위험 점수</div><div style={{ ...score, color: riskColor }}>{(task.risk_score * 100).toFixed(0)}%</div></div>
            <div><div style={label}>미확인 시간</div><div style={score}>{getElapsedText(task.last_activity)}</div></div>
          </div>
        </div>
      </div>

      <div style={content}>
        <div style={card}>
          <div style={sectionTitle}>대상자 기본 정보</div>
          <div style={userRow}>
            {/* ✅ 수정된 이미지 경로 적용 */}
            <img src={displayProfileImg()} style={profile} alt="profile" />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: "16px", fontWeight: 700 }}>
                {task.name} <span style={{ fontSize: "13px", color: "#6b7280" }}>({task.age ? `${task.age}세` : "65 세"} / {task.gender || "(남)"})</span>
              </div>
              <div style={{ fontSize: "14px", marginTop: "4px" }}>📞 {task.phone}</div>
              <div style={{ fontSize: "13px", color: "#6b7280" }}>🏠 {task.address_main}</div>
            </div>
          </div>
        </div>       
        <div style={card}><div style={sectionTitle}>최근 통화 AI 요약</div><div style={aiBox}>{summary || "최근 통화 요약이 없습니다."}</div></div>
        <div style={card}><div style={{ display: "flex", justifyContent: "space-between" }}><div style={sectionTitle}>현장 위치</div><button style={mapBtn} onClick={openMap}>지도 앱 열기</button></div></div>

        <div style={card}>
          <div style={sectionTitle}>현장 조치 결과 등록</div>
          <div style={radioGroup}>
            {["ok", "wrong_alarm", "needs_help", "emergency"].map((val) => (
              <label key={val} style={radioLabel}>
                <input type="radio" value={val} checked={result === val} onChange={(e) => setResult(e.target.value)} />
                {val === "ok" ? "정상" : val === "wrong_alarm" ? "오탐" : val === "needs_help" ? "도움 필요" : "응급 상황"}
              </label>
            ))}
          </div>
          <textarea placeholder="현장 조치 내용 기록" value={memo} onChange={(e) => setMemo(e.target.value)} style={memoStyle} />
          <button style={saveBtn} onClick={saveRecord}>결과 저장</button>
        </div>
      </div>

      <div style={bottomBar}>
        <button style={callBtn} onClick={callResident}>본인 통화</button>
        <button style={guardianBtn} onClick={callGuardian}>보호자</button>
        <button style={emergencyBtn} onClick={callEmergency}>119 신고</button>
      </div>

      {showCallModal && <CallModal residentId={task.resident_id} operatorId={1} onClose={() => setShowCallModal(false)} />}
    </div>
  );
}

const container: CSSProperties = { display: "flex", flexDirection: "column", height: "100vh", background: "#f1f5f9", maxWidth: "480px", margin: "0 auto" };
const stickyHeader: CSSProperties = { background: "#fff", padding: "16px", borderBottomWidth: "3px", borderBottomStyle: "solid" };
const headerTop: CSSProperties = { display: "flex", justifyContent: "space-between" };
const backBtn: CSSProperties = { background: "none", border: "none", fontSize: "18px", cursor: "pointer" };
const headerInfo: CSSProperties = { marginTop: "10px" };
const name: CSSProperties = { fontSize: "18px", fontWeight: 700 };
const label: CSSProperties = { fontSize: "12px", color: "#64748b" };
const score: CSSProperties = { fontSize: "16px", fontWeight: 700 };
const badge: CSSProperties = { padding: "4px 10px", borderRadius: "6px", color: "#fff" };
const content: CSSProperties = { flex: 1, overflowY: "auto", padding: "16px" };
const card: CSSProperties = { background: "#fff", borderRadius: "10px", padding: "20px", marginBottom: "16px" };
const sectionTitle: CSSProperties = { fontWeight: 700, marginBottom: "10px" };
const userRow: CSSProperties = { display: "flex", gap: "16px" };
const profile: CSSProperties = { width: "64px", height: "64px", borderRadius: "10px", objectFit: "cover" };
const aiBox: CSSProperties = { background: "#f8fafc", padding: "14px", borderRadius: "8px", whiteSpace: "pre-line" };
const mapBtn: CSSProperties = { border: "1px solid #bfdbfe", padding: "6px 12px", borderRadius: "6px" };
const radioGroup: CSSProperties = { display: "flex", flexDirection: "column", gap: "10px" };
const radioLabel: CSSProperties = { display: "flex", gap: "8px" };
const memoStyle: CSSProperties = { width: "100%", height: "90px", marginTop: "10px", padding: "8px" };
const saveBtn: CSSProperties = { marginTop: "10px", width: "100%", padding: "12px", background: "#334155", color: "#fff", border: "none" };
const bottomBar: CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px", padding: "12px", background: "#fff" };
const callBtn: CSSProperties = { padding: "12px", border: "1px solid #cbd5e1" };
const guardianBtn: CSSProperties = { padding: "12px", background: "#10b981", color: "#fff", border: "none" };
const emergencyBtn: CSSProperties = { padding: "12px", background: "#ef4444", color: "#fff", border: "none" };