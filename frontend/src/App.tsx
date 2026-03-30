import { useEffect, useMemo, useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import SidebarLeft from "./components/SidebarLeft";
import SidebarRight from "./components/SidebarRight";
import MapView from "./components/MapView";
import DangerModal from "./components/DangerModal";
import InfoModal from "./components/InfoModal";
import { MOCK_DATA } from "./data/mockData";
import DetailProfile from "./pages/admin/DetailProfile";
import MobileApp from "./pages/worker/MobileApp";
import MobileDetail from "./pages/worker/MobileDetail";
import Dashboard from "./pages/admin/Dashboard";
import OperatorLogin from "./pages/worker/OperatorLogin"; 
import { API_BASE } from './config';
import toast, { Toaster } from "react-hot-toast";

// 메인 레이아웃 컴포넌트
const MainLayout = () => {
  const [selectedGu, setSelectedGu] = useState("서울시");
  const [isRightOpen, setIsRightOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<any>(null);
  const [activeModal, setActiveModal] = useState<"danger" | "info" | null>(null);

  // ✅ 실시간 데이터를 관리하기 위한 상태 추가
  const [highRiskUsers, setHighRiskUsers] = useState<any[]>([]);
  const [simulatedId, setSimulatedId] = useState<number | null>(null);

  const closeModals = () => {
    setActiveModal(null);
    setSelectedUser(null);
  };

  // ✅ 데이터 로드 함수 (Dashboard 로직 이식)
  const loadHighRiskData = async (isInitial = false) => {
    try {
      if (isInitial) {
        setHighRiskUsers([]); // 초기에 비워둠
        return [];
      }
      const res = await fetch(`${API_BASE}/api/dashboard/high-risk?window_minutes=60&limit=50`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ window_minutes: 60, limit: 50 })
      });
      const data = await res.json();
      const items = data.items ?? [];
      setHighRiskUsers(items);
      return items;
    } catch (e) {
      console.error(e);
      return [];
    }
  };

  // 초기 로딩
  useEffect(() => {
    loadHighRiskData(true);
  }, []);

  // ✅ SidebarLeft에 전달할 유저 데이터 가공
  const leftUsers = useMemo(() => {
    let display = highRiskUsers;
    if (simulatedId !== null) {
      display = highRiskUsers.filter(u => (u.resident_id ?? u.id) === simulatedId);
    }
    return display.map((x) => ({
      ...x,
      id: x.resident_id,
      status: ["danger", "emergency", "alert"].includes(x.risk_level) ? "danger" : "normal",
      issue: x.reason_codes?.reason ?? `위험 점수: ${Number(x.risk_score).toFixed(2)}`,
    }));
  }, [highRiskUsers, simulatedId]);

  // SidebarRight용 데이터 (Mock 또는 전체 데이터)
  const rightUsers = useMemo(() => {
    return MOCK_DATA.map((u: any) => ({
      resident_id: u.resident_id ?? u.id,
      name: u.name,
      gu: u.gu,
      issue: u.issue,
      lat: u.lat,
      lon: u.lon,
      address_main: u.address_main ?? u.address,
      latest_risk_score: u.latest_risk_score ?? u.risk,
      latest_risk_level: u.latest_risk_level ?? null,
      latest_scored_at: u.latest_scored_at ?? null,
    }));
  }, []);

  const handleDetailClick = async (u: any) => {
    setSelectedUser(u);
    setActiveModal("info");
    const residentId = u?.resident_id;
    if (!residentId) return;

    try {
      const res = await fetch(`${API_BASE}/api/dashboard/residents/${residentId}`);    
      if (!res.ok) return;
      const detail = await res.json();
      setSelectedUser((prev: any) => ({
        ...(prev ?? {}),
        ...detail,
        risk_score: detail?.risk_score ?? detail?.latest_risk_score ?? prev?.risk_score ?? null,
        note: detail?.note ?? prev?.note ?? prev?.issue ?? null,
        contact: {
          self: detail?.phone ?? prev?.phone ?? prev?.contact?.self,
          guardian: detail?.guardian?.phone ?? prev?.contact?.guardian,
        },
      }));
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div style={{ display: "flex", width: "100vw", height: "100vh", overflow: "hidden" }}>
      {/* 💡 알림창 위치 설정 */}
      <Toaster position="top-center" />

      <SidebarLeft
        users={leftUsers} // ✅ 가공된 실시간 데이터 전달
        onUserClick={(u) => {
          setSelectedUser(u);
          setActiveModal("info");
        }}
        // ✅ 에러 해결: 누락되었던 필수 Props 추가
        onSimulateSuccess={async (targetId: number) => {
          await new Promise(resolve => setTimeout(resolve, 500)); // DB 반영 대기
          const freshUsers = await loadHighRiskData(false);
          setSimulatedId(targetId);
          toast.error("🚨 긴급! 실시간 이상 징후가 감지되었습니다.");

          const targetUser = freshUsers.find((u: any) => (u.resident_id ?? u.id) === targetId);
          if (targetUser) {
            handleDetailClick(targetUser); // 자동으로 상세 모달 오픈
            if (targetUser.gu) {
              setSelectedGu(targetUser.gu);
              setIsRightOpen(true);
            }
          }
        }}
      />

      {simulatedId && (
        <button 
          onClick={() => setSimulatedId(null)}
          style={{ position: 'fixed', bottom: '20px', left: '360px', zIndex: 100, padding: '10px 20px', backgroundColor: '#1f2937', color: 'white', border: 'none', borderRadius: '30px', cursor: 'pointer', fontWeight: 700 }}
        >
          🔄 전체 관제 모드 복구
        </button>
      )}

      <MapView
        onGuClick={(name) => {
          setSelectedGu(name);
          setIsRightOpen(true);
        }}
      />

      {isRightOpen && (
        <SidebarRight
          guName={selectedGu}
          users={rightUsers}
          onClose={() => setIsRightOpen(false)}
          onDetailClick={handleDetailClick}
        />
      )}

      {activeModal === "danger" && <DangerModal user={selectedUser} onClose={closeModals} />}
      {activeModal === "info" && (
        <InfoModal
          user={selectedUser}
          selectedGu={selectedGu}
          onClose={closeModals}
          onShowDanger={() => setActiveModal("danger")}
        />
      )}
    </div>
  );
};

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />} />
        <Route path="/detail" element={<DetailProfile />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/mobile" element={<MobileApp />} />
        <Route path="/mobile-detail" element={<MobileDetail />} />
        <Route path="/operators/login" element={<OperatorLogin />} />        
      </Routes>
    </BrowserRouter>
  );
}
export default App;