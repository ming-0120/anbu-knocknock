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
  reason_codes?: any;
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

    const riskPct = rawRisk !== null && Number.isFinite(rawRisk) ? (rawRisk <= 1 ? Math.round(rawRisk * 100) : Math.round(rawRisk)) : null;

    const addressFromParts = [user.address_main, user.address_detail].filter((v) => typeof v === "string" && v.trim()).join(" ");
    const address = (typeof user.address === "string" && user.address.trim() && user.address) || (addressFromParts.trim() ? addressFromParts : "-");

    let aiSummary = "";
    if (user.reason_codes) {
      try {
        const rc = typeof user.reason_codes === "string" ? JSON.parse(user.reason_codes) : user.reason_codes;
        aiSummary = rc.summary || rc.reason || "";
      } catch (e) {}
    }

    let note = "-";
    if (typeof user.note === "string" && user.note.trim()) {
      note = user.note;
    } else if (aiSummary) {
      note = `[AI 분석] ${aiSummary}`;
    } else {
      note = riskPct !== null && riskPct >= 70 ? "활동 이상 징후가 실시간 감지되었습니다." : "기록된 특이사항이 없습니다.";
    }

    const selfPhone = (typeof user.contact?.self === "string" && user.contact.self.trim() ? user.contact.self : null) || (typeof user.phone === "string" && user.phone.trim() ? user.phone : null) || "-";
    const guardianPhone = (typeof user.contact?.guardian === "string" && user.contact.guardian.trim() ? user.contact.guardian : null) || (typeof (user as any).guardian_phone === "string" && (user as any).guardian_phone.trim() ? (user as any).guardian_phone : "-");

    const riskLabel = riskPct === null ? "-" : riskPct >= 75 ? "위급" : riskPct >= 50 ? "경고" : riskPct >= 25 ? "주의" : "안전";

    return { name, age, gender, riskPct, riskLabel, address, note, selfPhone, guardianPhone };
  }, [user]);

  const isEmergency = safe.riskPct !== null && safe.riskPct >= 70;

  const handleAction = () => {
    const rid = (user as any)?.resident_id;
    if (!rid) return;
    if (isEmergency) {
      onShowDanger?.({ ...user, resident_id: rid });
    } else {
      navigate("/detail", { state: { user: { ...user, resident_id: rid }, selectedGu } });
      onClose();
    }
  };

  // 세련된 관제 아이콘 (SVG)
  const AlertIcon = () => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
      <line x1="12" y1="9" x2="12" y2="13"/>
      <line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  );

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div 
        style={{ ...modalContainer, ...(isEmergency ? emergencyContainerStyle : {}) }} 
        onClick={(e) => e.stopPropagation()}
      >
        
        {/* Header - 전문적인 딥 레드 테마 */}
        <div style={{ ...headerStyle, ...(isEmergency ? emergencyHeaderStyle : {}) }}>
          <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
            <div style={{ ...avatarStyle, ...(isEmergency ? emergencyAvatarStyle : {}) }}>
              {isEmergency ? <AlertIcon /> : (safe.name !== "-" ? safe.name.slice(0, 1) : "?")}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ fontSize: "19px", fontWeight: 800, color: isEmergency ? "#ffffff" : "#111827", letterSpacing: "-0.5px" }}>
                  {safe.name}
                </span>
                <span style={{ fontSize: "14px", color: isEmergency ? "rgba(255,255,255,0.8)" : "#6b7280" }}>
                  {safe.age}세 · {safe.gender}
                </span>
                <span style={{ 
                  ...pillBase, 
                  backgroundColor: isEmergency ? "rgba(255,255,255,0.2)" : (safe.riskPct && safe.riskPct >= 40 ? "#fffbeb" : "#f3f4f6"),
                  color: isEmergency ? "#ffffff" : (safe.riskPct && safe.riskPct >= 40 ? "#b45309" : "#4b5563"),
                  border: isEmergency ? "1px solid rgba(255,255,255,0.3)" : "none"
                }}>
                  {safe.riskPct}% · {safe.riskLabel}
                </span>
              </div>
              <div style={{ fontSize: "13px", color: isEmergency ? "rgba(255,255,255,0.7)" : "#4b5563" }}>{safe.address}</div>
            </div>
          </div>
          <button onClick={onClose} style={{ ...closeBtnStyle, color: isEmergency ? "#ffffff" : "#9ca3af" }}>✕</button>
        </div>

        {/* Body */}
        <div style={bodyStyle}>
          
          {isEmergency && (
            <div style={emergencyBannerStyle}>
              <span style={{ marginRight: "6px" }}>⚠️</span>
              <strong>시스템 알림:</strong> 이상 패턴 감지로 인한 긴급 관제가 활성화되었습니다.
            </div>
          )}

          <div style={infoCard}>
            <div style={sectionTitle}>특이사항 분석</div>
            <div style={{ fontSize: "15px", color: isEmergency ? "#111827" : "#374151", lineHeight: 1.6, fontWeight: isEmergency ? 600 : 400 }}>
              {safe.note}
            </div>
          </div>

          <div style={infoCard}>
            <div style={sectionTitle}>비상 연락망</div>
            <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <div style={contactRow}>
                <span style={contactLabel}>대상자</span>
                <a href={`tel:${safe.selfPhone}`} style={isEmergency ? contactValueEmergency : contactValueNormal}>{safe.selfPhone}</a>
              </div>
              <div style={contactRow}>
                <span style={contactLabel}>보호자</span>
                <a href={`tel:${safe.guardianPhone}`} style={isEmergency ? contactValueEmergency : contactValueNormal}>{safe.guardianPhone}</a>
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: "12px", marginTop: "10px" }}>
            <button onClick={onClose} style={btnGhost}>닫기</button>
            <button
              onClick={handleAction}
              className={isEmergency ? "emergency-pulse" : ""}
              style={isEmergency ? btnEmergencyStyle : btnPrimary}
            >
              {isEmergency ? "실시간 긴급 조치 실행" : "상세 분석 데이터"}
            </button>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes emergency-glow {
          0% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.5); transform: scale(1); }
          50% { box-shadow: 0 0 20px 5px rgba(220, 38, 38, 0); transform: scale(1.01); }
          100% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); transform: scale(1); }
        }
        .emergency-pulse {
          animation: emergency-glow 2s infinite ease-in-out;
        }
      `}</style>
    </div>
  );
};

// --- Styles ---
const overlayStyle: React.CSSProperties = { position: "fixed", top: 0, left: 0, width: "100vw", height: "100vh", backgroundColor: "rgba(15, 23, 42, 0.65)", display: "flex", justifyContent: "center", alignItems: "center", zIndex: 9999, backdropFilter: "blur(3px)" };
const modalContainer: React.CSSProperties = { width: "450px", backgroundColor: "#ffffff", borderRadius: "24px", boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.3)", display: "flex", flexDirection: "column", overflow: "hidden", transition: "all 0.4s cubic-bezier(0.4, 0, 0.2, 1)" };
const headerStyle: React.CSSProperties = { padding: "28px 24px", borderBottom: "1px solid #f1f5f9", display: "flex", justifyContent: "space-between", alignItems: "center" };
const avatarStyle: React.CSSProperties = { width: "52px", height: "52px", borderRadius: "16px", backgroundColor: "#f8fafc", color: "#64748b", display: "flex", justifyContent: "center", alignItems: "center", fontSize: "18px", fontWeight: "bold" };
const closeBtnStyle: React.CSSProperties = { background: "none", border: "none", fontSize: "22px", cursor: "pointer", opacity: 0.6 };
const pillBase: React.CSSProperties = { padding: "3px 10px", borderRadius: "8px", fontSize: "11px", fontWeight: 800, textTransform: "uppercase" };

const bodyStyle: React.CSSProperties = { padding: "24px", display: "flex", flexDirection: "column", gap: "20px" };
const infoCard: React.CSSProperties = { backgroundColor: "#f8fafc", padding: "20px", borderRadius: "16px", border: "1px solid #e2e8f0" };
const sectionTitle: React.CSSProperties = { fontSize: "11px", fontWeight: 800, color: "#94a3b8", textTransform: "uppercase", marginBottom: "12px", letterSpacing: "0.1em" };
const contactRow: React.CSSProperties = { display: "flex", alignItems: "center" };
const contactLabel: React.CSSProperties = { width: "80px", color: "#64748b", fontSize: "13px", fontWeight: 500 };
const contactValueNormal: React.CSSProperties = { color: "#2563eb", fontWeight: 700, fontSize: "15px", textDecoration: "none" };
const contactValueEmergency: React.CSSProperties = { color: "#dc2626", fontWeight: 800, fontSize: "16px", textDecoration: "none" };

const btnGhost: React.CSSProperties = { flex: 1, padding: "16px", backgroundColor: "#ffffff", color: "#64748b", border: "1px solid #e2e8f0", borderRadius: "14px", fontSize: "15px", fontWeight: 600, cursor: "pointer" };
const btnPrimary: React.CSSProperties = { flex: 2, padding: "16px", backgroundColor: "#0f172a", color: "#ffffff", border: "none", borderRadius: "14px", fontSize: "15px", fontWeight: 600, cursor: "pointer" };

// --- Professional Emergency 스타일 ---
const emergencyContainerStyle: React.CSSProperties = { border: "2px solid #dc2626", boxShadow: "0 0 40px rgba(220, 38, 38, 0.15)" };
const emergencyHeaderStyle: React.CSSProperties = { backgroundColor: "#dc2626", borderBottom: "none" };
const emergencyAvatarStyle: React.CSSProperties = { backgroundColor: "rgba(255,255,255,0.2)", color: "#ffffff", borderRadius: "14px" };
const emergencyBannerStyle: React.CSSProperties = { backgroundColor: "#fef2f2", color: "#991b1b", padding: "14px", borderRadius: "12px", textAlign: "center", fontWeight: 600, fontSize: "14px", border: "1px solid #fee2e2" };
const btnEmergencyStyle: React.CSSProperties = { flex: 2, padding: "16px", backgroundColor: "#dc2626", color: "#ffffff", border: "none", borderRadius: "14px", fontSize: "16px", fontWeight: 800, cursor: "pointer" };

export default InfoModal;