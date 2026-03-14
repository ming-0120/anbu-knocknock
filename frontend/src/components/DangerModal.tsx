import React, { useEffect, useMemo, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

// API 호출 함수 (기존과 동일)
async function getHourlyFeatures(residentId: number) {
  const res = await fetch(`/api/hourly-features/${residentId}`);
  if (!res.ok) throw new Error("API error");
  return res.json();
}
function isOnline(lastSeen?: string) {
  console.log(lastSeen)
  if (!lastSeen) return false;

  const last = new Date(lastSeen).getTime();
  const now = Date.now();

  return now - last < 120000; // 2분
}
type ChartPoint = { hour: string; motion: number; };
type Operator = { operators_id: number; name: string; distance?: number; last_seen?: string;};
type DangerUser = {
  resident_id?: number | null;
  note? :string;
  name?: string;
  gu?: string;
  age?: number;
  gender?: string;
  lat?: number;
  lon?: number;
  address_main?: string;
  address_detail?: string;
  disease_label?: string;
  phone?: string;
  guardian_phone?: string;
  risk_score?: number;
  risk_level?: string;
};

type Props = {
  user: DangerUser | null;
  onClose: () => void;
  onAssigned?: (residentId: number) => void;
};

const DangerModal: React.FC<Props> = ({ user, onClose, onAssigned }) => {
  const [chartData, setChartData] = useState<ChartPoint[]>([]);
  const [showManagers, setShowManagers] = useState(false);
  const [selectedManager, setSelectedManager] = useState<number | null>(null);
  const [operators, setOperators] = useState<Operator[]>([]);
  const [assignedOperatorName, setAssignedOperatorName] = useState<string | null>(null);

  // Body 스크롤 방지
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "unset";
    };
  }, []);

  // 차트 데이터 로드
  useEffect(() => {
    if (!user || user.resident_id == null) return;
    async function loadChart() {
      try {
        const data = await getHourlyFeatures(Number(user?.resident_id));
        const formatted = (data ?? []).map((d: any) => ({
          hour: new Date(d.hour).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" }),
          motion: d.motion
        }));
        setChartData(formatted);
      } catch (e) {
        console.error("차트 로드 실패", e);
      }
    }
    loadChart();
  }, [user]);

  // 근처 담당자 로드
  useEffect(() => {
  if (!showManagers) return;
  if (!user || user.lat == null || user.lon == null) return;
  async function loadOperators() {
    const res = await fetch(
      `/api/operators/nearby?lat=${user?.lat}&lon=${user?.lon}&radius=3`
    );

    const data = await res.json();
    setOperators(data.operators ?? []);
  }

  loadOperators();

}, [showManagers, user]);

useEffect(() => {
  const ws = new WebSocket("ws://localhost:8000/ws/operators")

  ws.onmessage = (event) => {

  const data = JSON.parse(event.data)
  console.log("WS DATA", data)

  if (data.type === "operator_update") {

    setOperators(prev => {

      const exists = prev.find(o => o.operators_id === Number(data.operator_id))

      if (!exists) return prev

      return prev.map(o =>
        o.operators_id === Number(data.operator_id)
          ? { ...o, last_seen: data.last_seen }
          : o
      )

    })

  }

}
  return () => ws.close()
}, [])

  const safe = useMemo(() => {
    if (!user) return null;
    const risk = typeof user.risk_score === "number"
      ? Math.round(user.risk_score <= 1 ? user.risk_score * 100 : user.risk_score)
      : "-";
    const address = [user.address_main, user.address_detail].filter(Boolean).join(" ");

    return {
      name: user.name ?? "-",
      age: user.age ?? "-",
      note: user.note ?? "-",
      gender: user.gender ?? "-",
      address: address || "-",
      disease: user.disease_label ?? "-",
      phone: user.phone ?? "-",
      guardian: user.guardian_phone ?? "-",
      risk,
      riskLevel: user.risk_level ?? "Extreme"
    };
  }, [user]);

  async function assignTask(residentId: number, operatorId: number) {
    const res = await fetch("/api/operator-tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resident_id: residentId,
        operator_id: operatorId,
        task_type: "risk_check",
        description: "위험 알림 대응"
      })
    });
    if (!res.ok) throw new Error("assign fail");
    return res.json();
  }

  if (!user || !safe) return null;

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={modalContainer} onClick={(e) => e.stopPropagation()}>
        
        {/* 모던하고 깔끔한 헤더 */}
        <div style={headerStyle}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ display: "inline-block", width: "8px", height: "8px", borderRadius: "50%", backgroundColor: "#ef4444" }}></span>
            <span style={{ fontWeight: 600, color: "#111827", fontSize: "15px" }}>위급 상황 알림</span>
          </div>
          <button type="button" onClick={onClose} style={closeBtnStyle}>✕</button>
        </div>

        {/* 바디 (Flex Layout 적용) */}
        <div style={bodyStyle}>
          
          {/* 대상자 정보 카드 */}
          <div style={infoCard}>
            <div style={cardHeader}>
              <span style={{ fontSize: "16px", fontWeight: 700, color: "#111827" }}>
                {safe.name} <span style={{ fontSize: "13px", color: "#6b7280", fontWeight: 400 }}>({safe.age}세/{safe.gender})</span>
              </span>
              <span style={riskBadge}>{safe.risk}% ({safe.riskLevel})</span>
            </div>
            <div style={infoRow}>
              <span style={infoLabel}>주소</span>
              <span style={infoValue}>{safe.address}</span>
            </div>
            <div style={infoRow}>
              <span style={infoLabel}>특이사항</span>
              <span style={infoValue}>{safe.note}</span>
            </div>
            <div style={{...infoRow, marginTop: "8px", paddingTop: "8px", borderTop: "1px dashed #e5e7eb"}}>
              <span style={infoLabel}>연락처</span>
              <div style={{ display: "flex", gap: "12px" }}>
                <a href={`tel:${safe.phone}`} style={linkStyle}>본인: {safe.phone}</a>
                <span style={{ color: "#d1d5db" }}>|</span>
                <a href={`tel:${safe.guardian}`} style={linkStyle}>보호자: {safe.guardian}</a>
              </div>
            </div>
          </div>

          {/* 활동 데이터 차트 */}
          <div style={chartSection}>
            <div style={sectionTitle}>최근 활동 타임라인</div>
            <div style={chartBox}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 10, left: -25, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                  <XAxis dataKey="hour" tick={{ fontSize: 11, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' }} />
                  <Line type="monotone" dataKey="motion" stroke="#ef4444" strokeWidth={2} dot={{ r: 3, fill: "#ef4444" }} activeDot={{ r: 5 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 담당자 지정 영역 (플렉스 컨테이너 안에서 스크롤 작동) */}
          <div style={managerSection}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <div style={sectionTitle}>현장 담당자 배정</div>
              {!showManagers && !selectedManager && (
                <button
                  style={btnSmallPrimary}
                  onClick={() => {
                    setOperators([]);
                    setShowManagers(true);
                  }}
                >
                주변 담당자 찾기
                </button>
              )}
            </div>

            {/* 스크롤 영역 */}
            {showManagers && !selectedManager && (
              <div style={tableWrapper}>
                <table style={dataTable}>
                  <thead style={tableHeader}>
                    <tr>
                      <th style={thStyle}>이름</th>
                      <th style={thStyle}>상태</th>
                      <th style={thStyle}>거리</th>
                      <th style={thStyle}>작업</th>
                    </tr>
                  </thead>
                  <tbody>
                    {operators.map((m) => (
                      <tr key={m.operators_id} style={trStyle}>
                        <td style={tdStyle}>{m.name}</td>
                        <td style={tdStyle}>
                          {isOnline(m.last_seen) ? (
                            <>
                              <span style={{ color: "#10b981", fontSize: "14px", marginRight: "4px" }}>•</span>
                              온라인
                            </>
                          ) : (
                            <>
                              <span style={{ color: "#9ca3af", fontSize: "14px", marginRight: "4px" }}>•</span>
                              비접속
                            </>
                          )}
                        </td>
                        <td style={tdStyle}>{m.distance != null ? `${m.distance.toFixed(1)}km` : "-"}</td>
                        <td style={tdStyle}>
                          <button style={btnAssign} onClick={() => {
                            if (!confirm(`${m.name}님을 담당자로 배정하시겠습니까?`)) return;
                            setSelectedManager(m.operators_id);
                            setAssignedOperatorName(m.name);
                            setShowManagers(false);
                          }}>배정</button>
                        </td>
                      </tr>
                    ))}
                    {operators.length === 0 && (
                      <tr><td colSpan={4} style={{...tdStyle, textAlign: "center", padding: "20px", color: "#6b7280"}}>조회된 담당자가 없습니다.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* 담당자 배정 완료 카드 */}
            {selectedManager && assignedOperatorName && (
              <div style={assignedCard}>
                <div style={{ color: "#4b5563", marginBottom: "4px" }}>배정된 담당자</div>
                <div style={{ fontSize: "16px", fontWeight: 600, color: "#111827", marginBottom: "12px" }}>
                  {assignedOperatorName}
                </div>
                <div style={{ display: "flex", gap: "8px" }}>
                  <button style={btnGhost} onClick={() => { setSelectedManager(null); setAssignedOperatorName(null); setShowManagers(true); }}>
                    재지정
                  </button>
                  <button style={btnSolidPrimary} onClick={async () => {
                    if (!selectedManager || !user?.resident_id) return;
                    try {
                      await assignTask(user.resident_id, selectedManager);
                      alert("배정 처리가 완료되었습니다.");
                      onAssigned?.(user.resident_id);
                      onClose();
                    } catch (err) { alert("처리 실패"); }
                  }}>
                    완료 및 전파
                  </button>
                </div>
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
};

// ==========================================
// 🎨 모던 SaaS 스타일 (Modern SaaS UI)
// ==========================================

const overlayStyle: React.CSSProperties = {
  position: "fixed", top: 0, left: 0, width: "100vw", height: "100vh",
  backgroundColor: "rgba(17, 24, 39, 0.4)", // 부드러운 반투명 어두운 배경
  display: "flex", justifyContent: "center", alignItems: "center", zIndex: 9999,
};

// ★ 전체 모달: 깔끔한 라운드 처리, 부드러운 그림자, 높이 고정
const modalContainer: React.CSSProperties = {
  width: "460px", 
  height: "80vh", // 최대 높이 제한
  maxHeight: "750px",
  backgroundColor: "#ffffff", 
  borderRadius: "12px", // 부드러운 모서리
  boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)", // 고급스러운 그림자
  display: "flex", 
  flexDirection: "column",
  overflow: "hidden" 
};

const headerStyle: React.CSSProperties = {
  padding: "16px 20px",
  borderBottom: "1px solid #f3f4f6", // 아주 연한 선
  display: "flex", justifyContent: "space-between", alignItems: "center",
  backgroundColor: "#ffffff"
};

const closeBtnStyle: React.CSSProperties = {
  background: "none", border: "none", fontSize: "18px", color: "#9ca3af", cursor: "pointer", padding: "4px"
};

// 바디: 내부 요소들을 위아래로 띄워줌 (gap 사용)
const bodyStyle: React.CSSProperties = { 
  padding: "20px", 
  display: "flex", 
  flexDirection: "column",
  flex: 1, 
  overflow: "hidden", 
  gap: "20px" // 요소 사이 간격을 일정하게 유지
};

const infoCard: React.CSSProperties = {
  backgroundColor: "#f9fafb", // 연한 회색 배경
  padding: "16px", 
  borderRadius: "8px", 
  border: "1px solid #f3f4f6",
  flexShrink: 0
};

const cardHeader: React.CSSProperties = {
  display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px"
};

const riskBadge: React.CSSProperties = {
  backgroundColor: "#fee2e2", color: "#b91c1c", padding: "4px 8px", borderRadius: "6px", fontSize: "12px", fontWeight: 600
};

const infoRow: React.CSSProperties = { display: "flex", marginBottom: "6px", fontSize: "13px" };
const infoLabel: React.CSSProperties = { width: "60px", color: "#6b7280", flexShrink: 0 };
const infoValue: React.CSSProperties = { color: "#374151", fontWeight: 500 };
const linkStyle: React.CSSProperties = { color: "#2563eb", textDecoration: "none", fontWeight: 500 };

const chartSection: React.CSSProperties = { flexShrink: 0 };
const sectionTitle: React.CSSProperties = { fontSize: "14px", fontWeight: 600, color: "#111827", marginBottom: "10px" };
const chartBox: React.CSSProperties = { width: "100%", height: "130px" };

// ★ 담당자 영역: flex: 1 설정으로 남는 공간을 모두 차지하게 함
const managerSection: React.CSSProperties = {
  display: "flex", flexDirection: "column", flex: 1, minHeight: 0 
};

// ★ 표 감싸는 영역: 여기서만 스크롤 바 생성
const tableWrapper: React.CSSProperties = {
  flex: 1, 
  overflowY: "auto", 
  border: "1px solid #e5e7eb",
  borderRadius: "8px",
  backgroundColor: "#ffffff"
};

const dataTable: React.CSSProperties = { width: "100%", borderCollapse: "collapse", fontSize: "13px", textAlign: "left" };
const tableHeader: React.CSSProperties = { position: "sticky", top: 0, backgroundColor: "#f9fafb", zIndex: 1 };
const thStyle: React.CSSProperties = { padding: "10px 12px", borderBottom: "1px solid #e5e7eb", color: "#6b7280", fontWeight: 500 };
const trStyle: React.CSSProperties = { borderBottom: "1px solid #f3f4f6" };
const tdStyle: React.CSSProperties = { padding: "10px 12px", color: "#374151" };

const btnSmallPrimary: React.CSSProperties = {
  padding: "6px 12px", backgroundColor: "#eff6ff", color: "#2563eb", border: "1px solid #bfdbfe", borderRadius: "6px", fontSize: "12px", fontWeight: 600, cursor: "pointer"
};

const btnAssign: React.CSSProperties = {
  padding: "4px 10px", backgroundColor: "#ffffff", color: "#374151", border: "1px solid #d1d5db", borderRadius: "4px", fontSize: "12px", cursor: "pointer"
};

const assignedCard: React.CSSProperties = {
  padding: "16px", border: "1px solid #bfdbfe", backgroundColor: "#eff6ff", borderRadius: "8px", textAlign: "center"
};

const btnGhost: React.CSSProperties = {
  flex: 1, padding: "10px", backgroundColor: "#ffffff", color: "#374151", border: "1px solid #d1d5db", borderRadius: "6px", fontSize: "13px", fontWeight: 500, cursor: "pointer"
};
const btnSolidPrimary: React.CSSProperties = {
  flex: 1, padding: "10px", backgroundColor: "#2563eb", color: "#ffffff", border: "none", borderRadius: "6px", fontSize: "13px", fontWeight: 500, cursor: "pointer"
};

export default DangerModal;