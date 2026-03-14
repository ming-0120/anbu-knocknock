import React, { useMemo, useState } from "react";

// ... (기존 타입 정의 부분은 동일하게 유지) ...
type RiskLevel = "normal" | "watch" | "alert" | "emergency" | "danger";
type UserRow = { resident_id: number; name: string; gu: string; address_main?: string; issue?: string; latest_risk_level?: RiskLevel | null; latest_risk_score?: number | null; latest_scored_at?: string | null; scoreText?: string; };
interface SidebarRightProps { guName: string; users: UserRow[]; onClose: () => void; onDetailClick: (user: UserRow) => void; }
type ScoreFilter = "all" | "high" | "medium";
type SortType = "risk_desc" | "recent" | "name";

const SidebarRight = ({ guName, users, onClose, onDetailClick }: SidebarRightProps) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [dangerOnly, setDangerOnly] = useState(false);
  const [scoreFilter, setScoreFilter] = useState<ScoreFilter>("all");
  const [sortType, setSortType] = useState<SortType>("risk_desc");

  // ... (기존 guUsers useMemo 로직 동일하게 유지) ...
  const guUsers = useMemo(() => {
    const term = searchTerm.trim();
    let list = users
      .filter((u) => u.gu === guName)
      .filter((u) => !term || (u.name ?? "").includes(term))
      .filter((u) => !dangerOnly || u.latest_risk_level === "alert" || u.latest_risk_level === "emergency")
      .filter((u) => {
        if (scoreFilter === "all") return true;
        if (u.latest_risk_score == null) return false;

        const pct = u.latest_risk_score * 100;

        if (scoreFilter === "high") return pct >= 70;
        if (scoreFilter === "medium") return pct >= 40;

        return true;
      });

    list.sort((a, b) => {
      if (sortType === "risk_desc") return (b.latest_risk_score ?? 0) - (a.latest_risk_score ?? 0);
      if (sortType === "recent") return new Date(b.latest_scored_at ?? 0).getTime() - new Date(a.latest_scored_at ?? 0).getTime();
      if (sortType === "name") return (a.name ?? "").localeCompare(b.name ?? "");
      return 0;
    });
    return list;
  }, [users, guName, searchTerm, dangerOnly, scoreFilter, sortType]);

  return (
    <aside style={sidebarStyle}>
      <div style={headerStyle}>
        <h2 style={{ fontSize: "18px", fontWeight: 700, color: "#111827", margin: 0 }}>{guName} 현황</h2>
        <button onClick={onClose} style={closeBtnStyle}>✕</button>
      </div>

      <input type="text" placeholder="이름으로 검색..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} style={inputStyle} />

      <div style={filterSection}>
        <button style={dangerButton(dangerOnly)} onClick={() => setDangerOnly(!dangerOnly)}>
          {dangerOnly ? "🔴 고위험군 필터 해제" : "🚨 고위험군만 보기"}
        </button>
      </div>

      {/* 💡 상하 배치로 변경하여 좁은 느낌 해결 */}
      <div style={{ display: "flex", flexDirection: "column", gap: "14px", marginBottom: "20px" }}>
        <div>
          <div style={sectionTitle}>위험도 필터</div>
          <div style={pillContainer}>
            <button style={pill(scoreFilter === "all")} onClick={() => setScoreFilter("all")}>전체</button>
            <button style={pill(scoreFilter === "medium")} onClick={() => setScoreFilter("medium")}>40% 이상</button>
            <button style={pill(scoreFilter === "high")} onClick={() => setScoreFilter("high")}>70% 이상</button>
          </div>
        </div>
        <div>
          <div style={sectionTitle}>정렬 기준</div>
          <select value={sortType} onChange={(e) => setSortType(e.target.value as SortType)} style={selectStyle}>
            <option value="risk_desc">위험도 높은순</option>
            <option value="recent">최근 분석순</option>
            <option value="name">이름순</option>
          </select>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "10px", paddingRight: "4px" }}>
        {guUsers.map((user) => {
          const scoreStr = user.latest_risk_score != null
            ? `${(Math.max(0, Math.min(1, user.latest_risk_score)) * 100).toFixed(0)}%`
            : "-";
          const issueText = user.issue && user.issue.trim().length > 0 ? user.issue : `위험도: ${scoreStr}`;

          return (
            <div key={user.resident_id} style={cardStyle(user.latest_risk_score)}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <strong style={{ color: "#111827", fontSize: "14px" }}>{user.name}</strong>
                <button onClick={() => onDetailClick(user)} style={smallBtnStyle}>상세보기</button>
              </div>
              <p style={{ fontSize: "12px", color: "#6b7280", margin: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {issueText}
              </p>
            </div>
          );
        })}
        {guUsers.length === 0 && <div style={{ textAlign: "center", color: "#9ca3af", marginTop: "20px", fontSize: "13px" }}>검색 결과가 없습니다.</div>}
      </div>
    </aside>
  );
};

// --- Styles ---
// --- Styles ---
const sidebarStyle: React.CSSProperties = { 
  width: "380px", // 💡 약간 넓힘 (360px -> 380px)
  boxSizing: "border-box", // 💡 핵심: 패딩이 너비를 초과하지 않도록 고정
  borderLeft: "1px solid #e5e7eb", 
  padding: "24px", 
  display: "flex", 
  flexDirection: "column", 
  backgroundColor: "#ffffff", 
  flexShrink: 0,
  marginRight:"24px"
};

const headerStyle: React.CSSProperties = { 
  display: "flex", 
  justifyContent: "space-between", 
  alignItems: "center", 
  marginBottom: "20px",
  width: "100%" // 부모 영역을 넘어가지 않도록 확실히 제한
};
const closeBtnStyle: React.CSSProperties = { 
  border: "none", 
  background: "#f3f4f6", // 연한 회색 배경을 넣어 버튼 영역을 명확히 함
  width: "32px",         // 고정 너비
  height: "32px",        // 고정 높이
  borderRadius: "50%",   // 동그란 모양
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  fontSize: "14px", 
  fontWeight: "bold",
  color: "#6b7280", 
  cursor: "pointer",
  padding: 0,            // 브라우저 기본 패딩 제거
  flexShrink: 0          // ★ 공간이 좁아져도 절대 찌그러지지 않음
};
const inputStyle: React.CSSProperties = { padding: "10px 12px", marginBottom: "16px", border: "1px solid #d1d5db", borderRadius: "8px", fontSize: "14px", backgroundColor: "#f9fafb", width: "100%", boxSizing: "border-box" }; // 💡 boxSizing 추가

const filterSection: React.CSSProperties = { marginBottom: "16px" };
const sectionTitle: React.CSSProperties = { fontSize: "12px", fontWeight: 600, color: "#6b7280", marginBottom: "8px" };

const selectStyle: React.CSSProperties = { 
  width: "100%", 
  padding: "8px 10px", 
  borderRadius: "6px", 
  border: "1px solid #d1d5db", 
  fontSize: "13px", 
  backgroundColor: "#ffffff", 
  color: "#374151",
  boxSizing: "border-box" // 💡 boxSizing 추가
};

const pillContainer: React.CSSProperties = { display: "flex", gap: "8px" };

const pill = (active: boolean): React.CSSProperties => ({
  flex: 1, padding: "8px 0", borderRadius: "6px", fontSize: "12px", fontWeight: 600, cursor: "pointer", textAlign: "center",
  border: active ? "1px solid #bfdbfe" : "1px solid #e5e7eb",
  background: active ? "#eff6ff" : "#ffffff",
  color: active ? "#2563eb" : "#6b7280",
  boxSizing: "border-box"
});

const dangerButton = (active: boolean): React.CSSProperties => ({
  width: "100%", padding: "12px", borderRadius: "8px", cursor: "pointer", fontSize: "13px", fontWeight: 600, transition: "all 0.2s",
  border: active ? "1px solid #fca5a5" : "1px solid #e5e7eb",
  background: active ? "#fef2f2" : "#ffffff",
  color: active ? "#b91c1c" : "#374151",
  boxSizing: "border-box"
});

const cardStyle = (score?: number | null): React.CSSProperties => {

  let borderLeft = "#10b981";
  let bg = "#ffffff";

  if (typeof score === "number") {

    const normalized = Math.max(0, Math.min(1, score));
    const pct = normalized * 100;

    if (pct >= 70) {
      borderLeft = "#ef4444";
      bg = "#fef2f2";
    } 
    else if (pct >= 40) {
      borderLeft = "#f59e0b";
      bg = "#fffbeb";
    }
  }

  return {
    padding: "16px",
    border: "1px solid #e5e7eb",
    borderLeft: `4px solid ${borderLeft}`,
    borderRadius: "8px",
    backgroundColor: bg,
    boxShadow: "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
    boxSizing: "border-box",
    marginBottom: "10px"
  };
};

const smallBtnStyle: React.CSSProperties = {
  fontSize: "11px", fontWeight: 600, cursor: "pointer", padding: "6px 10px", borderRadius: "4px",
  backgroundColor: "#ffffff", border: "1px solid #d1d5db", color: "#374151"
};
export default SidebarRight;