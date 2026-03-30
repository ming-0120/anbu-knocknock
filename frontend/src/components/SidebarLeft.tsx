import React, { useMemo, useState } from "react";

interface SidebarLeftProps {
  users: any[];
  onUserClick: (user: any) => void;
  onSimulateSuccess: (targetId: number) => void; // ✅ 추가: 시뮬레이션 성공 알림용
}

const SidebarLeft = ({ users, onUserClick, onSimulateSuccess }: SidebarLeftProps) => {
  const [levelFilter, setLevelFilter] = useState("all");
  const [guFilter, setGuFilter] = useState("all");
  const [scoreFilter, setScoreFilter] = useState(0);
  const [inactiveFilter, setInactiveFilter] = useState(0);

  // 구 목록 생성
  const guList = useMemo(() => {
    const set = new Set<string>();
    users.forEach((u) => {
      if (u.gu) set.add(u.gu);
    });
    return Array.from(set).sort();
  }, [users]);

  const filteredUsers = useMemo(() => {
    let result = users.filter((u) => u.risk_level && u.risk_level !== "normal");

    if (levelFilter !== "all") {
      result = result.filter((u) => u.risk_level === levelFilter);
    }
    if (guFilter !== "all") {
      result = result.filter((u) => u.gu === guFilter);
    }
    if (scoreFilter > 0) {
      result = result.filter((u) => (u.risk_score ?? 0) >= scoreFilter);
    }
    if (inactiveFilter > 0) {
      const now = Date.now();
      result = result.filter((u) => {
        if (!u.last_activity) return true;
        const last = new Date(u.last_activity).getTime();
        const diffHours = (now - last) / (1000 * 60 * 60);
        return diffHours >= inactiveFilter;
      });
    }

    result.sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0));
    return result;
  }, [users, levelFilter, guFilter, scoreFilter, inactiveFilter]);

  return (
    <aside style={sidebarContainer}>
      <h2 style={{ fontSize: "18px", fontWeight: 700, color: "#111827", marginBottom: "20px" }}>
        🌐 서울시 통합 관제
      </h2>
      
      {/* 🔴 시뮬레이션 버튼 섹션 */}
      <div style={{ marginBottom: "16px" }}>
        <button
          onClick={async () => {
            const res = await fetch("/api/simulate/anomaly", { method: "POST" });
            if (res.ok) {
              const data = await res.json();
              onSimulateSuccess(data.resident_id); 
            }
          }}
          style={{
            width: "100%",
            padding: "10px",
            backgroundColor: "#ef4444",
            color: "white",
            border: "none",
            borderRadius: "8px",
            fontWeight: 700,
            cursor: "pointer",
            boxShadow: "0 4px 6px -1px rgba(239, 68, 68, 0.3)"
          }}
        >
          🚨 이상 상황 시나리오 가동
        </button>
      </div>

      <div style={filterSection}>
        <div style={filterGroup}>
          <div style={filterLabel}>위험 레벨</div>
          <div style={buttonRow}>
            {["all", "emergency", "alert", "watch"].map((lv) => (
              <button
                key={lv}
                onClick={() => setLevelFilter(lv)}
                style={filterButton(levelFilter === lv)}
              >
                {lv}
              </button>
            ))}
          </div>
        </div>

        <div style={filterGroup}>
          <div style={filterLabel}>지역</div>
          <select
            value={guFilter}
            onChange={(e) => setGuFilter(e.target.value)}
            style={selectStyle}
          >
            <option value="all">전체</option>
            {guList.map((gu) => (
              <option key={gu}>{gu}</option>
            ))}
          </select>
        </div>

        <div style={filterGroup}>
          <div style={filterLabel}>위험 점수</div>
          <div style={buttonRow}>
            {[0, 0.7, 0.8, 0.9].map((s) => (
              <button
                key={s}
                onClick={() => setScoreFilter(s)}
                style={filterButton(scoreFilter === s)}
              >
                {s === 0 ? "전체" : `${s}+`}
              </button>
            ))}
          </div>
        </div>

        <div style={filterGroup}>
          <div style={filterLabel}>활동 없음</div>
          <div style={buttonRow}>
            {[0, 6, 12, 24].map((h) => (
              <button
                key={h}
                onClick={() => setInactiveFilter(h)}
                style={filterButton(inactiveFilter === h)}
              >
                {h === 0 ? "전체" : `${h}h`}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div style={dangerSection}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
          <span style={pulsingDot}></span>
          <span style={{ fontSize: "14px", fontWeight: 700, color: "#b91c1c" }}>
            실시간 고위험군 ({filteredUsers.length})
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {filteredUsers.map((user, i) => (
            <div
              key={`${user.resident_id}-${i}`}
              onClick={() => onUserClick(user)}
              style={cardStyle(user.risk_score)}
            >
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <strong style={{ fontSize: "14px" }}>{user.name}</strong>
                <span style={{ fontSize: "12px", color: "#6b7280" }}>{user.gu}</span>
              </div>
              <div style={{ fontSize: "12px", color: "#4b5563" }}>
                {user.reason ?? user.risk_level}
              </div>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
};

/* Styles (생략 없이 유지) */
const sidebarContainer: React.CSSProperties = { width: "340px", borderRight: "1px solid #e5e7eb", padding: "24px", backgroundColor: "#ffffff", flexShrink: 0, overflowY: "auto" };
const filterSection: React.CSSProperties = { marginBottom: "24px", display: "flex", flexDirection: "column", gap: "16px" };
const filterGroup: React.CSSProperties = { display: "flex", flexDirection: "column", gap: "6px" };
const filterLabel: React.CSSProperties = { fontSize: "12px", fontWeight: 600, color: "#6b7280" };
const buttonRow: React.CSSProperties = { display: "flex", gap: "6px", flexWrap: "wrap" };
const filterButton = (active: boolean): React.CSSProperties => ({ padding: "4px 8px", fontSize: "12px", borderRadius: "6px", border: "1px solid #e5e7eb", background: active ? "#111827" : "#ffffff", color: active ? "#ffffff" : "#374151", cursor: "pointer" });
const selectStyle: React.CSSProperties = { padding: "6px", fontSize: "12px", borderRadius: "6px", border: "1px solid #e5e7eb" };
const dangerSection: React.CSSProperties = { borderTop: "1px solid #f3f4f6", paddingTop: "20px" };
const pulsingDot: React.CSSProperties = { width: "8px", height: "8px", backgroundColor: "#ef4444", borderRadius: "50%", boxShadow: "0 0 0 3px rgba(239, 68, 68, 0.2)" };
const cardStyle = (score?: number | null): React.CSSProperties => {
  let borderLeftColor = "#10b981";
  if (typeof score === "number") {
    const pct = score * 100;
    if (pct >= 70) borderLeftColor = "#ef4444";
    else if (pct >= 50) borderLeftColor = "#f59e0b";
  }
  return { padding: "14px", backgroundColor: "#ffffff", border: "1px solid #e5e7eb", borderLeft: `4px solid ${borderLeftColor}`, borderRadius: "8px", cursor: "pointer", boxShadow: "0 1px 2px rgba(0,0,0,0.05)" };
};

export default SidebarLeft;