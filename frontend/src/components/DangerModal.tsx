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
import { WS_BASE } from '../config';

// API 호출 함수
async function getHourlyFeatures(residentId: number) {
  const res = await fetch(`/api/hourly-features/${residentId}`);
  if (!res.ok) throw new Error("API error");
  return res.json();
}

function isOnline(lastSeen?: string) {  
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
  reason_codes?: any; 
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
    return () => { document.body.style.overflow = "unset"; };
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
      } catch (e) { console.error("차트 로드 실패", e); }
    }
    loadChart();
  }, [user]);

  // 근처 담당자 로드
  useEffect(() => {
    if (!showManagers || !user?.lat || !user?.lon) return;
    async function loadOperators() {
      const res = await fetch(`/api/operators/nearby?lat=${user?.lat}&lon=${user?.lon}&radius=3`);
      const data = await res.json();
      setOperators(data.operators ?? []);
    }
    loadOperators();
  }, [showManagers, user]);

  // WebSocket 연결
  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/ws/operators`)
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === "operator_update") {
        setOperators(prev => prev.map(o => o.operators_id === Number(data.operator_id) ? { ...o, last_seen: data.last_seen } : o))
      }
    }
    return () => ws.close()
  }, [])

  // 데이터 가공 (에러 수정 완료)
  const safe = useMemo(() => {
    if (!user) return null;
    const risk = typeof user.risk_score === "number"
      ? Math.round(user.risk_score <= 1 ? user.risk_score * 100 : user.risk_score)
      : "-";
    const address = [user.address_main, user.address_detail].filter(Boolean).join(" ");
    
    let reason = user.reason_codes;
    if (typeof reason === 'string') {
      try { reason = JSON.parse(reason); } catch(e) { reason = null; }
    }

    return {
      name: user.name ?? "-",
      age: user.age ?? "-",
      note: user.note ?? "-",
      gender: user.gender ?? "-",
      address: address || "-",
      risk,
      riskLevel: user.risk_level ?? "Extreme",
      summary: reason?.summary || "실시간 활동 이상 정지 감지",
      mode: reason?.mode || "Simulation Mode",
      phone: user.phone ?? "-", // ✨ 에러 해결 핵심: phone 추가
      guardian: user.guardian_phone ?? "-" // ✨ 에러 해결 핵심: guardian 추가
    };
  }, [user]);

  // 세련된 관제 아이콘 (SVG)
  const AlertIcon = () => (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
      <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  );

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
        
        {/* 전문 관제 헤더 */}
        <div style={headerStyle}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={pulseIconBox}>
               <AlertIcon />
            </div>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span style={{ fontWeight: 800, color: "#ffffff", fontSize: "16px", letterSpacing: "-0.3px" }}>위급 상황 관제 시스템</span>
              <span style={{ fontSize: "11px", color: "rgba(255,255,255,0.7)" }}>REAL-TIME EMERGENCY MONITORING</span>
            </div>
          </div>
          <button type="button" onClick={onClose} style={closeBtnStyle}>✕</button>
        </div>

        <div style={bodyStyle}>
          
          {/* 대상자 정보 카드 */}
          <div style={infoCard}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
              <div>
                <div style={{ fontSize: "18px", fontWeight: 800, color: "#1e293b" }}>{safe.name}</div>
                <div style={{ fontSize: "13px", color: "#64748b" }}>{safe.age}세 · {safe.gender} | {safe.address}</div>
              </div>
              <div style={riskBadge}>{safe.risk}% {safe.riskLevel}</div>
            </div>
            <div style={{ display: "flex", gap: "12px", fontSize: "13px", paddingTop: "10px", borderTop: "1px solid #f1f5f9" }}>
              <a href={`tel:${safe.phone}`} style={linkStyle}>📞 본인: {safe.phone}</a>
              <span style={{color: '#e2e8f0'}}>|</span>
              <a href={`tel:${safe.guardian}`} style={linkStyle}>🏠 보호자: {safe.guardian}</a>
            </div>
          </div>

          {/* 활동 데이터 차트 */}
          <div style={chartSection}>
            <div style={sectionTitle}>실시간 활동 지표 (Motion Data)</div>
            <div style={chartBox}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 10, left: -25, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="hour" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }} />
                  <Line type="monotone" dataKey="motion" stroke="#dc2626" strokeWidth={3} dot={{ r: 3, fill: "#dc2626", strokeWidth: 2, stroke: "#fff" }} activeDot={{ r: 6 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* AI 분석 리포트 */}
          <div style={summaryBoxStyle}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
              <span style={{ fontSize: "12px", fontWeight: 800, color: "#991b1b" }}>ANALYSIS REPORT</span>
            </div>
            <div style={{ color: "#450a0a", fontSize: "14px", fontWeight: 700, lineHeight: "1.5" }}>
              {safe.summary}
            </div>
            <div style={{ fontSize: "11px", color: "#991b1b", marginTop: "6px", opacity: 0.8 }}>
              Mode: {safe.mode} / Risk Score: {safe.risk}%
            </div>
          </div>

          {/* 담당자 지정 영역 */}
          <div style={managerSection}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
              <div style={sectionTitle}>근거리 출동 가능 인력</div>
              {!showManagers && !selectedManager && (
                <button style={btnSmallPrimary} onClick={() => { setOperators([]); setShowManagers(true); }}>주변 검색</button>
              )}
            </div>

            {showManagers && !selectedManager && (
              <div style={tableWrapper}>
                <table style={dataTable}>
                  <thead style={tableHeader}>
                    <tr>
                      <th style={thStyle}>이름</th>
                      <th style={thStyle}>상태</th>
                      <th style={thStyle}>거리</th>
                      <th style={thStyle}>명령</th>
                    </tr>
                  </thead>
                  <tbody>
                    {operators.map((m) => (
                      <tr key={m.operators_id} style={trStyle}>
                        <td style={{ ...tdStyle, fontWeight: 600 }}>{m.name}</td>
                        <td style={tdStyle}>
                          <span style={{ color: isOnline(m.last_seen) ? "#10b981" : "#94a3b8", marginRight: "4px" }}>●</span>
                          {isOnline(m.last_seen) ? "온라인" : "오프라인"}
                        </td>
                        <td style={tdStyle}>{m.distance?.toFixed(1)}km</td>
                        <td style={tdStyle}>
                          <button style={btnAssign} onClick={() => {
                            if (!confirm(`${m.name} 님에게 배정하시겠습니까? `)) return;
                            setSelectedManager(m.operators_id);
                            setAssignedOperatorName(m.name);
                            setShowManagers(false);
                          }}>배정</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {selectedManager && assignedOperatorName && (
              <div style={assignedCard}>
                <div style={{ fontSize: "13px", color: "#1e40af", marginBottom: "4px" }}>배정 완료</div>
                <div style={{ fontSize: "17px", fontWeight: 800, color: "#1e3a8a", marginBottom: "12px" }}>
                   {assignedOperatorName} 님
                </div>
                <div style={{ display: "flex", gap: "8px" }}>
                  <button style={btnGhost} onClick={() => { setSelectedManager(null); setAssignedOperatorName(null); setShowManagers(true); }}>재배정</button>
                  <button style={btnSolidPrimary} onClick={async () => {
                    try {
                      await assignTask(user.resident_id!, selectedManager);
                      alert("배정을 마쳤습니다.");
                      onAssigned?.(user.resident_id!); onClose();
                    } catch (err) { alert("연동 실패"); }
                  }}>닫기</button>
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
// 🎨 스타일 정의
// ==========================================

const overlayStyle: React.CSSProperties = {
  position: "fixed", top: 0, left: 0, width: "100vw", height: "100vh",
  backgroundColor: "rgba(15, 23, 42, 0.7)", display: "flex", justifyContent: "center", alignItems: "center", zIndex: 9999,
  backdropFilter: "blur(4px)"
};

const modalContainer: React.CSSProperties = {
  width: "480px", height: "85vh", maxHeight: "820px",
  backgroundColor: "#ffffff", borderRadius: "24px", boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
  display: "flex", flexDirection: "column", overflow: "hidden", border: "1px solid #dc2626"
};

const headerStyle: React.CSSProperties = {
  padding: "20px 24px", display: "flex", justifyContent: "space-between", alignItems: "center",
  backgroundColor: "#dc2626", color: "white"
};

const pulseIconBox: React.CSSProperties = {
  backgroundColor: "rgba(255,255,255,0.2)", padding: "8px", borderRadius: "12px", color: "white", display: "flex", alignItems: "center"
};

const closeBtnStyle: React.CSSProperties = {
  background: "none", border: "none", fontSize: "20px", color: "white", cursor: "pointer", opacity: 0.8
};

const bodyStyle: React.CSSProperties = { 
  padding: "24px", display: "flex", flexDirection: "column", flex: 1, overflowY: "auto", gap: "18px" 
};

const infoCard: React.CSSProperties = {
  backgroundColor: "#f8fafc", padding: "20px", borderRadius: "16px", border: "1px solid #e2e8f0"
};

const riskBadge: React.CSSProperties = {
  backgroundColor: "#dc2626", color: "white", padding: "6px 12px", borderRadius: "10px", fontSize: "12px", fontWeight: 800
};

const sectionTitle: React.CSSProperties = { fontSize: "11px", fontWeight: 800, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "1px" };
const chartSection: React.CSSProperties = { width: "100%" };
const chartBox: React.CSSProperties = { width: "100%", height: "140px", marginTop: "10px" };

const summaryBoxStyle: React.CSSProperties = {
  backgroundColor: "#fef2f2", padding: "18px", borderRadius: "16px", borderLeft: "6px solid #dc2626"
};

const managerSection: React.CSSProperties = { display: "flex", flexDirection: "column", flex: 1, minHeight: 0 };
const tableWrapper: React.CSSProperties = { flex: 1, overflowY: "auto", borderRadius: "12px", border: "1px solid #e2e8f0", backgroundColor: "white" };
const dataTable: React.CSSProperties = { width: "100%", borderCollapse: "collapse", fontSize: "13px" };
const tableHeader: React.CSSProperties = { position: "sticky", top: 0, backgroundColor: "#f8fafc", zIndex: 1 };
const thStyle: React.CSSProperties = { padding: "12px", borderBottom: "1px solid #e2e8f0", color: "#64748b", textAlign: "left", fontWeight: 600 };
const trStyle: React.CSSProperties = { borderBottom: "1px solid #f1f5f9" };
const tdStyle: React.CSSProperties = { padding: "12px", color: "#1e293b" };

const btnSmallPrimary: React.CSSProperties = { padding: "6px 14px", backgroundColor: "#f1f5f9", color: "#475569", border: "1px solid #e2e8f0", borderRadius: "8px", fontSize: "12px", fontWeight: 700, cursor: "pointer" };
const btnAssign: React.CSSProperties = { padding: "6px 12px", backgroundColor: "#0f172a", color: "white", border: "none", borderRadius: "6px", fontSize: "12px", cursor: "pointer" };
const assignedCard: React.CSSProperties = { padding: "20px", backgroundColor: "#eff6ff", borderRadius: "16px", border: "1px solid #bfdbfe", textAlign: "center" };
const btnGhost: React.CSSProperties = { flex: 1, padding: "12px", backgroundColor: "white", color: "#64748b", border: "1px solid #e2e8f0", borderRadius: "10px", fontWeight: 600, cursor: "pointer" };
const btnSolidPrimary: React.CSSProperties = { flex: 1, padding: "12px", backgroundColor: "#1e40af", color: "white", border: "none", borderRadius: "10px", fontWeight: 600, cursor: "pointer" };
const linkStyle: React.CSSProperties = { color: "#2563eb", textDecoration: "none", fontWeight: 700 };

export default DangerModal;