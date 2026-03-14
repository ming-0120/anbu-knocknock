import React, { useMemo } from "react";
import { useNavigate } from "react-router-dom";

type InfoUser = {
  resident_id?: number;
  name?: string;
  age?: number | string;
  gender?: string;
  issue?: string;
  latest_risk_score?: number;
  risk?: number;
  risk_score?: number;
  address?: string;
  address_main?: string;
  address_detail?: string;
  note?: string;
  reason_codes?: string[];
  contact?: { self?: string; guardian?: string };
  phone?: string; 
};

interface InfoModalProps {
  user: InfoUser | null;
  selectedGu: string;
  onClose: () => void;
  onShowDanger?: (user: InfoUser) => void;
}

const InfoModal: React.FC<InfoModalProps> = ({ user, selectedGu, onClose, onShowDanger }) => {
  const navigate = useNavigate();
  if (!user) return null;

  const safe = useMemo(() => {
    const name = typeof user.name === "string" && user.name.trim() ? user.name : "-";
    const age = typeof user.age === "number" || (typeof user.age === "string" && user.age.trim()) ? user.age : "-";
    const gender = typeof user.gender === "string" && user.gender.trim() ? user.gender : "-";

    const rawRisk =
      typeof user.risk === "number" ? user.risk :
      typeof user.risk_score === "number" ? user.risk_score :
      typeof (user as any).latest_risk_score === "number" ? (user as any).latest_risk_score : null;

    const riskIsNumber = rawRisk !== null && Number.isFinite(rawRisk);
    const riskPct = riskIsNumber ? (rawRisk <= 1 ? Math.round(rawRisk * 100) : Math.round(rawRisk)) : null;

    const addressFromParts = [user.address_main, user.address_detail].filter((v) => typeof v === "string" && v.trim()).join(" ");
    const address = (typeof user.address === "string" && user.address.trim() && user.address) || (addressFromParts.trim() ? addressFromParts : "-");

    // 💡 [수정된 부분] 특이사항(note) 추출 로직 세분화
    let aiSummary = "";
    if (user.reason_codes) {
      try {
        const rc = typeof user.reason_codes === "string" ? JSON.parse(user.reason_codes) : user.reason_codes;
        aiSummary = rc.summary || rc.reason || "";
      } catch (e) {}
    }

    let note = "-";
    const rawIssue = (user as any).issue || "";

    if (typeof user.note === "string" && user.note.trim()) {
      note = user.note; // 1순위: 관리자가 직접 작성한 메모
    } else if (aiSummary) {
      note = `💡 [AI 감지] ${aiSummary}`;
    } else if (typeof rawIssue === "string" && rawIssue.trim() && !rawIssue.includes("score=")) {
      note = rawIssue; 
    } else {
      note = riskPct !== null && riskPct >= 70 
        ? "⚠️ 활동 이상 징후가 감지되었습니다." 
        : "기록된 특이사항이 없습니다.";
    }

    const selfPhone = (typeof user.contact?.self === "string" && user.contact.self.trim() ? user.contact.self : null) || (typeof user.phone === "string" && user.phone.trim() ? user.phone : null) || "-";
    const guardianPhone = (typeof user.contact?.guardian === "string" && user.contact.guardian.trim() ? user.contact.guardian : null) || (typeof (user as any).guardian_phone === "string" && (user as any).guardian_phone.trim() ? (user as any).guardian_phone : "-");

    const riskLabel = riskPct === null ? "-" : riskPct >= 70 ? "위험" : riskPct >= 40 ? "주의" : "안전";

    return { name, age, gender, riskPct, riskLabel, address, note, selfPhone, guardianPhone };
  }, [user]);

  const handleGoDetail = () => {
    const rid = (user as any)?.resident_id;
    if (!rid) { alert("상세 페이지를 열 수 없습니다."); return; }
    navigate("/detail", { state: { user: { ...user, resident_id: rid }, selectedGu } });
    onClose();
  };

  const handleShowDanger = () => {
    if (!onShowDanger) return;
    const rid = (user as any)?.resident_id;
    if (!rid) { alert("조치 모달을 열 수 없습니다."); return; }
    onShowDanger({ ...user, resident_id: rid });
  };

  const riskStyle = safe.riskPct !== null && safe.riskPct >= 70 ? pillDanger : safe.riskPct !== null && safe.riskPct >= 40 ? pillWarning : pillSafe;

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={modalContainer} onClick={(e) => e.stopPropagation()}>
        
        {/* Header */}
        <div style={headerStyle}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div style={avatarStyle}>
              {safe.name !== "-" ? safe.name.slice(0, 1) : "?"}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontSize: "16px", fontWeight: 700, color: "#111827" }}>{safe.name}</span>
                <span style={{ fontSize: "13px", color: "#6b7280" }}>{safe.age}세 · {safe.gender}</span>
                <span style={{ ...pillBase, ...riskStyle }}>
                  {safe.riskPct !== null ? `${safe.riskPct}%` : "-"} · {safe.riskLabel}
                </span>
              </div>
              <div style={{ fontSize: "13px", color: "#4b5563" }}>{safe.address}</div>
            </div>
          </div>
          <button onClick={onClose} style={closeBtnStyle}>✕</button>
        </div>

        {/* Body */}
        <div style={bodyStyle}>
          <div style={infoCard}>
            <div style={sectionTitle}>특이사항</div>
            <div style={{ fontSize: "14px", color: "#374151", lineHeight: 1.5 }}>{safe.note}</div>
          </div>

          <div style={infoCard}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "12px" }}>
              <div style={sectionTitle}>비상 연락처</div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <div style={contactRow}>
                <span style={contactLabel}>본인</span>
                <span style={contactValue}>{safe.selfPhone}</span>
              </div>
              <div style={contactRow}>
                <span style={contactLabel}>보호자</span>
                <span style={contactValue}>{safe.guardianPhone}</span>
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: "10px", marginTop: "10px" }}>
            <button onClick={onClose} style={btnGhost}>닫기</button>
            <button
              onClick={() => { (safe.riskPct !== null && safe.riskPct >= 70) ? handleShowDanger() : handleGoDetail() }}
              style={safe.riskPct !== null && safe.riskPct >= 70 ? btnDanger : btnPrimary}
            >
              {safe.riskPct !== null && safe.riskPct >= 70 ? "긴급 조치하기" : "상세보기"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// --- Styles ---
const overlayStyle: React.CSSProperties = { position: "fixed", top: 0, left: 0, width: "100vw", height: "100vh", backgroundColor: "rgba(17, 24, 39, 0.4)", display: "flex", justifyContent: "center", alignItems: "center", zIndex: 9999 };
const modalContainer: React.CSSProperties = { width: "420px", backgroundColor: "#ffffff", borderRadius: "12px", boxShadow: "0 20px 25px -5px rgba(0,0,0,0.1)", display: "flex", flexDirection: "column", overflow: "hidden" };
const headerStyle: React.CSSProperties = { padding: "20px", borderBottom: "1px solid #f3f4f6", display: "flex", justifyContent: "space-between", alignItems: "flex-start", backgroundColor: "#ffffff" };
const avatarStyle: React.CSSProperties = { width: "40px", height: "40px", borderRadius: "50%", backgroundColor: "#e5e7eb", color: "#4b5563", display: "flex", justifyContent: "center", alignItems: "center", fontSize: "16px", fontWeight: "bold" };
const closeBtnStyle: React.CSSProperties = { background: "none", border: "none", fontSize: "18px", color: "#9ca3af", cursor: "pointer", padding: "4px" };
const pillBase: React.CSSProperties = { padding: "2px 8px", borderRadius: "12px", fontSize: "11px", fontWeight: 600 };
const pillDanger: React.CSSProperties = { backgroundColor: "#fee2e2", color: "#b91c1c" };
const pillWarning: React.CSSProperties = { backgroundColor: "#fef3c7", color: "#b45309" };
const pillSafe: React.CSSProperties = { backgroundColor: "#f3f4f6", color: "#4b5563" };
const bodyStyle: React.CSSProperties = { padding: "20px", display: "flex", flexDirection: "column", gap: "16px" };
const infoCard: React.CSSProperties = { backgroundColor: "#f9fafb", padding: "16px", borderRadius: "8px", border: "1px solid #f3f4f6" };
const sectionTitle: React.CSSProperties = { fontSize: "13px", fontWeight: 700, color: "#6b7280", marginBottom: "8px" };
const contactRow: React.CSSProperties = { display: "flex", alignItems: "center", fontSize: "14px" };
const contactLabel: React.CSSProperties = { width: "60px", color: "#6b7280", fontSize: "13px" };
const contactValue: React.CSSProperties = { color: "#111827", fontWeight: 500 };
const btnGhost: React.CSSProperties = { flex: 1, padding: "12px", backgroundColor: "#ffffff", color: "#374151", border: "1px solid #d1d5db", borderRadius: "8px", fontSize: "14px", fontWeight: 600, cursor: "pointer" };
const btnPrimary: React.CSSProperties = { flex: 1, padding: "12px", backgroundColor: "#2563eb", color: "#ffffff", border: "none", borderRadius: "8px", fontSize: "14px", fontWeight: 600, cursor: "pointer" };
const btnDanger: React.CSSProperties = { flex: 1, padding: "12px", backgroundColor: "#ef4444", color: "#ffffff", border: "none", borderRadius: "8px", fontSize: "14px", fontWeight: 600, cursor: "pointer", boxShadow: "0 4px 6px -1px rgba(239, 68, 68, 0.3)" };

export default InfoModal;