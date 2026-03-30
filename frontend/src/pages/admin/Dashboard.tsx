import { useEffect, useMemo, useState } from "react";
import SidebarLeft from "../../components/SidebarLeft";
import SidebarRight from "../../components/SidebarRight";
import MapView from "../../components/MapView";
import DangerModal from "../../components/DangerModal";
import InfoModal from "../../components/InfoModal";
import { postGuResidents, postHighRisk, postMapSummary } from "../../api/dashboard";
import { useLocation } from "react-router-dom";
import toast, { Toaster } from "react-hot-toast";
import { WS_BASE } from '../../config';

type RiskLevel = "normal" | "watch" | "alert" | "emergency" | "danger";

export default function Dashboard() {
  const [selectedGu, setSelectedGu] = useState<string>("서울시");
  const [isRightOpen, setIsRightOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<any>(null);
  const [activeModal, setActiveModal] = useState<"danger" | "info" | null>(null);
  const [highRiskUsers, setHighRiskUsers] = useState<any[]>([]);
  const [mapSummary, setMapSummary] = useState<any[]>([]);
  const [guUsers, setGuUsers] = useState<any[]>([]);
  const [simulatedId, setSimulatedId] = useState<number | null>(null);
  
  const location = useLocation();

  const closeModals = () => { setActiveModal(null); setSelectedUser(null); };

  const fetchGuData = async (guName: string) => {
    const res = await postGuResidents({ gu: guName, limit: 500, include_latest_score: true });
    setGuUsers(res.items ?? []);
  };

  /**
   * 🔴 데이터 로드 함수
   */
  const loadDashboard = async (isInitial = false) => {
    const [ms] = await Promise.all([
      postMapSummary({ window_minutes: 60 }),
    ]);
    setMapSummary(ms.items ?? []);

    // 초기 진입 시에는 빈 상태 유지
    if (!isInitial) {
      const hr = await postHighRisk({ window_minutes: 60, limit: 50 });
      setHighRiskUsers(hr.items ?? []);
      return hr.items ?? [];
    }
    return [];
  };

  useEffect(() => {
    loadDashboard(true).catch(console.error);
    const t = window.setInterval(() => {
      loadDashboard(simulatedId === null).catch(console.error);
    }, 30000);
    return () => window.clearInterval(t);
  }, [simulatedId]);

  useEffect(() => {
    if (!isRightOpen || !selectedGu || selectedGu === "서울시") return;
    fetchGuData(selectedGu).catch(console.error);
  }, [selectedGu, isRightOpen]);

  const leftUsers = useMemo(() => {
    let display = highRiskUsers;
    if (simulatedId !== null) {
      display = highRiskUsers.filter(u => u.resident_id === simulatedId);
    }
    return display.map((x) => ({
      ...x,
      id: x.resident_id,
      status: ["danger", "emergency", "alert"].includes(x.risk_level) ? "danger" : "normal",
      issue: x.reason_codes?.reason ?? `위험도: ${Number(x.risk_score).toFixed(2)}`,
    }));
  }, [highRiskUsers, simulatedId]);

  const rightUsers = useMemo(() => {
    const byId = new Map<number, any>();
    for (const x of guUsers) {
      const id = Number(x.resident_id);
      if (!Number.isFinite(id)) continue;
      const prev = byId.get(id);
      if (!prev || (x.latest_scored_at && Date.parse(x.latest_scored_at) >= Date.parse(prev.latest_scored_at))) {
        byId.set(id, x);
      }
    }
    return Array.from(byId.values()).map((x) => {
      const s = x.latest_risk_score;
      const status = ["danger", "emergency", "alert"].includes(x.latest_risk_level) ? "danger" : "normal";
      return { ...x, status, issue: s ? `위험도 : ${Math.round(s * 100)}%` : "위험도 : -", scoreText: s?.toFixed(2) ?? "-" };
    });
  }, [guUsers]);

  return (
    <>
      <Toaster position="top-center" toastOptions={{
        style: { background: "#ef4444", color: "#fff", borderRadius: "12px", fontSize: "18px", fontWeight: 700, padding: "20px 30px", marginTop: "80px" }
      }} />

      <div style={{ display: "flex", width: "100vw", height: "100%", overflow: "hidden", backgroundColor: "#f9fafb" }}>        
        <SidebarLeft
          users={leftUsers}
          onUserClick={(u) => { setSelectedUser(u); setActiveModal("info"); }}
          onSimulateSuccess={async (targetId) => {
            const hrResponse = await postHighRisk({ window_minutes: 61, limit: 50 });
            const freshItems = hrResponse.items ?? [];
            
            setHighRiskUsers(freshItems);
            setSimulatedId(targetId);

            toast.error("🚨 긴급! 실시간 이상 징후가 감지되었습니다.");

            const targetUser = freshItems.find((u: any) => u.resident_id === targetId);
            if (targetUser) {
              setSelectedUser({
                ...targetUser,
                id: targetUser.resident_id,
                issue: targetUser.reason_codes?.reason ?? "이상 징후 발생"
              });
              setActiveModal("info");
              
              if (targetUser.gu) {
                setSelectedGu(targetUser.gu);
                setIsRightOpen(true);
                await fetchGuData(targetUser.gu);
              }
            }
          }}
        />

        {simulatedId && (
          <button onClick={() => setSimulatedId(null)} style={resetButtonStyle}>
            🔄 전체 관제 모드로 복구
          </button>
        )}

        <MapView mapData={mapSummary} onGuClick={(name) => { setSelectedGu(name); setIsRightOpen(true); }} />

        {isRightOpen && (
          <SidebarRight guName={selectedGu} users={rightUsers} onClose={() => setIsRightOpen(false)} onDetailClick={(u) => { setSelectedUser(u); setActiveModal("info"); }} />
        )}

        {activeModal === "danger" && (
          <DangerModal user={selectedUser} onClose={closeModals} onAssigned={(rid) => { 
            setHighRiskUsers(prev => prev.filter(u => u.resident_id !== rid));
            if (simulatedId === rid) setSimulatedId(null);
          }} />
        )}

        {activeModal === "info" && (
          <InfoModal user={selectedUser} selectedGu={selectedGu} onClose={() => setActiveModal(null)} onShowDanger={(u) => { setSelectedUser(u); setActiveModal("danger"); }} />
        )}
      </div>
    </>
  );
}

const resetButtonStyle: React.CSSProperties = { position: 'fixed', bottom: '30px', left: '360px', zIndex: 100, padding: '12px 24px', backgroundColor: '#1f2937', color: 'white', border: 'none', borderRadius: '30px', cursor: 'pointer', fontWeight: 700, boxShadow: '0 4px 12px rgba(0,0,0,0.3)' };