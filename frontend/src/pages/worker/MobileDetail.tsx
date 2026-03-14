import { useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import type { CSSProperties } from "react";
import CallModal from "../../components/call/callModal";
// 💡 age, gender 등을 받을 수 있도록 타입 확장
type TaskType = {
  task_id: number; resident_id: number; alert_id: number; operator_id: number;
  name: string; gu: string; address_main: string; phone: string;
  guardian_phone?: string; lat: number; lon: number; risk_score: number;
  last_activity: string; profile_image_url?: string; reason_codes?: any;
  age?: number; gender?: string; // 백엔드 추가 요청 필요
};

// 💡 마이너스 시간 방지 로직 추가
function getElapsedText(lastActivity: string) {
  const now = new Date().getTime();
  const last = new Date(lastActivity).getTime();
  const diffMin = Math.floor((now - last) / 60000);

  if (diffMin < 0) return "방금 전"; // 미래 시간이나 타임존 오류 시 예외 처리
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

  if (!task) return <div style={{ padding: "20px" }}>데이터 없음</div>;

  const rc = task.reason_codes;
  const riskLevel = getRiskLevel(task.risk_score);
  const riskColor = task.risk_score >= 0.8 ? "#ef4444" : task.risk_score >= 0.6 ? "#f59e0b" : task.risk_score >= 0.3 ? "#eab308" : "#10b981";
  const [showCallModal, setShowCallModal] = useState(false);
  const formatTime = (t: string) => {
    const d = new Date(t);
    return d.toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  };
  const [callTarget, setCallTarget] = useState<"resident" | "guardian" | null>(null);
  function openMap() { window.open(`https://map.kakao.com/link/map/${task.lat},${task.lon}`); }
  function callResident() {
  setCallTarget("resident");
  setShowCallModal(true);
}
  function callGuardian() {
  setCallTarget("guardian");
  setShowCallModal(true);
}
  function callEmergency() { window.location.href = `tel:119`; }

  async function saveRecord() {
    if (!result) { alert("처리 결과를 선택해주세요."); return; }
    const res = await fetch(`/api/alert-actions/${task.alert_id}/close`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ operator_id: task.operator_id, result: result, memo: memo || null })
    });
    if (res.ok) { alert("저장되었습니다."); navigate(-1); }
  }

  return (
    <div style={container}>
      {/* 고정 헤더 */}
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
        
        {/* 💡 1. 어르신 정보 (나이, 성별 추가) */}
        <div style={card}>
          <div style={sectionTitle}>대상자 기본 정보</div>
          <div style={userRow}>
            <img src={task.profile_image_url || "/images/default-profile.png"} style={profile} alt="profile" />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: "16px", fontWeight: 700, color: "#111827", marginBottom: "4px" }}>
                {task.name} <span style={{ fontSize: "13px", color: "#6b7280", fontWeight: 500 }}>
                  ({task.age ? `${task.age}세` : "나이 미상"} / {task.gender || "성별 미상"})
                </span>
              </div>
              <div style={{ fontSize: "14px", color: "#374151", marginBottom: "4px", fontWeight: 600 }}>📞 {task.phone}</div>
              <div style={{ fontSize: "13px", color: "#6b7280", lineHeight: 1.4 }}>🏠 {task.address_main}</div>
            </div>
          </div>
        </div>

        {/* 💡 2. AI 분석 요약 (JSON 데이터 100% 활용) */}
        <div style={card}>
          <div style={sectionTitle}>AI 위험 감지 리포트</div>
          
          <div style={aiBox}>
            <strong style={{ color: "#1e293b", display: "block", marginBottom: "4px" }}>감지 내용</strong>
            {rc?.summary || "특이사항 요약 정보가 없습니다."}
          </div>

          <div style={infoGrid}>
            <div style={infoGridItem}>
              <div style={infoLabel}>마지막 활동</div>
              <div style={infoVal}>{formatTime(task.last_activity)}</div>
            </div>
            <div style={infoGridItem}>
              <div style={infoLabel}>분석 기준일</div>
              <div style={infoVal}>{rc?.context?.target_date || "-"}</div>
            </div>
            <div style={infoGridItem}>
              <div style={infoLabel}>설정 민감도</div>
              <div style={infoVal}>{rc?.weights?.sensitivity ? `Level ${rc.weights.sensitivity}` : "기본"}</div>
            </div>
            <div style={infoGridItem}>
              <div style={infoLabel}>기저질환 가중치</div>
              <div style={{ ...infoVal, color: rc?.weights?.alpha_disease > 1 ? "#ef4444" : "#111827" }}>
                {rc?.weights?.alpha_disease || 1.0}
              </div>
            </div>
          </div>
        </div>

        <div style={card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
            <div style={sectionTitle}>현장 위치</div>
            <button style={mapBtn} onClick={openMap}>지도 앱 열기</button>
          </div>
        </div>

        <div style={card}>
          <div style={sectionTitle}>현장 조치 결과 등록</div>
          <div style={radioGroup}>
            <label style={radioLabel}><input type="radio" value="ok" checked={result === "ok"} onChange={(e) => setResult(e.target.value)} /> 정상 (이상 없음)</label>
            <label style={radioLabel}><input type="radio" value="wrong_alarm" checked={result === "wrong_alarm"} onChange={(e) => setResult(e.target.value)} /> 기기 오탐 (수리 필요)</label>
            <label style={radioLabel}><input type="radio" value="needs_help" checked={result === "needs_help"} onChange={(e) => setResult(e.target.value)} /> 도움 필요 (복지 연계)</label>
            <label style={radioLabel}><input type="radio" value="emergency" checked={result === "emergency"} onChange={(e) => setResult(e.target.value)} /> 응급 상황 (119 이송)</label>
          </div>
          <textarea placeholder="현장 조치 내용 및 어르신 상태를 상세히 기록해주세요." value={memo} onChange={(e) => setMemo(e.target.value)} style={memoStyle} />
          <button style={saveBtn} onClick={saveRecord}>결과 저장 및 보고</button>
        </div>
      </div>

      <div style={bottomBar}>
        <button style={callBtn} onClick={callResident}>본인 통화</button>
        <button style={guardianBtn} onClick={callGuardian}>보호자</button>
        <button style={emergencyBtn} onClick={callEmergency}>119 신고</button>
      </div>
      {showCallModal && (
        <CallModal
          residentId={task.resident_id}
          operatorId={1}
          onClose={() => setShowCallModal(false)}
        />
    )}
    </div>
  );
}

// --- Styles ---
const container: CSSProperties = { display: "flex", flexDirection: "column", height: "100vh", background: "#f1f5f9", boxSizing: "border-box", fontFamily: "sans-serif", maxWidth: "480px", margin: "0 auto" };
const stickyHeader: CSSProperties = { flexShrink: 0, background: "#ffffff", padding: "16px 20px", borderBottomWidth: "3px", borderBottomStyle: "solid", zIndex: 10, boxSizing: "border-box" };
const headerTop: CSSProperties = { display: "flex", justifyContent: "space-between", alignItems: "center" };
const backBtn: CSSProperties = { background: "none", border: "none", fontSize: "18px", color: "#111827", cursor: "pointer", padding: "0 14px 0 0" };
const headerInfo: CSSProperties = { marginTop: "16px", background: "#f8fafc", padding: "14px", borderRadius: "8px", border: "1px solid #f1f5f9" };
const name: CSSProperties = { fontSize: "18px", fontWeight: 700, color: "#111827" };
const label: CSSProperties = { fontSize: "12px", color: "#64748b", marginBottom: "4px" };
const score: CSSProperties = { fontSize: "16px", fontWeight: 700, color: "#111827" };
const badge: CSSProperties = { padding: "4px 10px", borderRadius: "6px", fontSize: "13px", fontWeight: 600, color: "#fff" };

const content: CSSProperties = { flex: 1, overflowY: "auto", padding: "16px", boxSizing: "border-box" };
const card: CSSProperties = { background: "#ffffff", borderRadius: "10px", padding: "20px", marginBottom: "16px", border: "1px solid #e2e8f0", boxShadow: "0 1px 2px rgba(0,0,0,0.03)", boxSizing: "border-box" };
const sectionTitle: CSSProperties = { fontWeight: 700, fontSize: "15px", color: "#0f172a", marginBottom: "16px" };
const userRow: CSSProperties = { display: "flex", gap: "16px", alignItems: "center" };
const profile: CSSProperties = { width: "64px", height: "64px", borderRadius: "10px", objectFit: "cover", border: "1px solid #e2e8f0" };

const aiBox: CSSProperties = { background: "#f8fafc", padding: "14px", borderRadius: "8px", marginBottom: "16px", fontSize: "14px", color: "#334155", border: "1px solid #e2e8f0", lineHeight: 1.5 };

// 💡 새로운 2x2 Grid 스타일
const infoGrid: CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" };
const infoGridItem: CSSProperties = { display: "flex", flexDirection: "column", gap: "4px", padding: "10px", background: "#f8fafc", borderRadius: "6px", border: "1px solid #f1f5f9" };
const infoLabel: CSSProperties = { fontSize: "12px", color: "#64748b" };
const infoVal: CSSProperties = { fontSize: "14px", color: "#0f172a", fontWeight: 600 };

const mapBtn: CSSProperties = { background: "#ffffff", color: "#2563eb", border: "1px solid #bfdbfe", padding: "6px 12px", borderRadius: "6px", fontSize: "13px", fontWeight: 600, cursor: "pointer" };

const radioGroup: CSSProperties = { display: "flex", flexDirection: "column", gap: "10px", marginBottom: "16px" };
const radioLabel: CSSProperties = { display: "flex", alignItems: "center", gap: "10px", fontSize: "14px", color: "#334155", cursor: "pointer", padding: "8px 0" };
const memoStyle: CSSProperties = { width: "100%", height: "90px", borderRadius: "8px", border: "1px solid #cbd5e1", padding: "12px", marginBottom: "16px", fontSize: "14px", boxSizing: "border-box", outline: "none", resize: "none" };
const saveBtn: CSSProperties = { width: "100%", padding: "14px", borderRadius: "8px", background: "#334155", color: "#ffffff", border: "none", fontWeight: 600, fontSize: "15px", cursor: "pointer" };

const bottomBar: CSSProperties = { flexShrink: 0, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px", padding: "12px 16px", background: "#ffffff", borderTop: "1px solid #e2e8f0", boxSizing: "border-box", paddingBottom: "max(12px, env(safe-area-inset-bottom))" };
const callBtn: CSSProperties = { padding: "14px 0", borderRadius: "8px", border: "1px solid #cbd5e1", background: "#ffffff", color: "#334155", fontWeight: 600, fontSize: "14px", cursor: "pointer" };
const guardianBtn: CSSProperties = { padding: "14px 0", borderRadius: "8px", background: "#10b981", color: "#ffffff", border: "none", fontWeight: 600, fontSize: "14px", cursor: "pointer" };
const emergencyBtn: CSSProperties = { padding: "14px 0", borderRadius: "8px", background: "#ef4444", color: "#ffffff", border: "none", fontWeight: 600, fontSize: "14px", cursor: "pointer" };
