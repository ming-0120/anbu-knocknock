import { useMemo, useState } from "react";
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
// 기존 App의 모든 기능을 담은 메인 화면 부품<
const MainLayout = () => {
  const rightUsers = useMemo(() => {
  return MOCK_DATA.map((u: any) => ({
    resident_id: u.resident_id ?? u.id,           // ✅ id → resident_id로 매핑
    name: u.name,
    gu: u.gu,
    issue: u.issue,
    lat: u.lat,
    lon: u.lon,
    address_main: u.address_main ?? u.address,    // ✅ address → address_main으로 매핑
    latest_risk_score: u.latest_risk_score ?? u.risk,  // ✅ risk → latest_risk_score로 매핑
    latest_risk_level: u.latest_risk_level ?? null,
    latest_scored_at: u.latest_scored_at ?? null,
  }));
}, []);
  const [selectedGu, setSelectedGu] = useState("서울시");
  const [isRightOpen, setIsRightOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<any>(null);
  const [activeModal, setActiveModal] = useState<"danger" | "info" | null>(null);

  const closeModals = () => {
    setActiveModal(null);
    setSelectedUser(null);
  };

  const handleDetailClick = async (u: any) => {
  // 1) 일단 모달 오픈 (요약 표시)
  setSelectedUser(u);
  setActiveModal("info");

  const residentId = u?.resident_id;
  if (!residentId) return;

  try {
    const res = await fetch(`${API_BASE}/api/dashboard/residents/${residentId}`);    
    if (!res.ok) {
      console.error("detail api failed", res.status);
      return;
    }

    const detail = await res.json();

    // 2) InfoModal이 읽는 형태로 맞춰서 merge
    setSelectedUser((prev: any) => ({
      ...(prev ?? {}),
      ...detail,
      // 위험도 표시(InfoModal은 risk/risk_score만 봄)
      risk_score:
        detail?.risk_score ??
        detail?.latest_risk_score ??
        prev?.risk_score ??
        prev?.latest_risk_score ??
        prev?.risk ??
        null,

      // 특이사항(note)도 issue -> note로 매핑하면 깔끔
      note: detail?.note ?? prev?.note ?? prev?.issue ?? null,

      // InfoModal은 contact.guardian을 보기도 함 -> guardian.phone을 매핑
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
      <SidebarLeft
        users={rightUsers}
        onUserClick={(u) => {
          setSelectedUser(u);
          setActiveModal("danger");
        }}
      />

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
          onDetailClick={handleDetailClick} // ✅ 여기 연결
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
        {/* 모바일 앱 경로 추가 */}
        <Route path="/mobile" element={<MobileApp />} />
        <Route path="/mobile-detail" element={<MobileDetail />} />
        <Route path="/operators/login" element={<OperatorLogin />} />        
      </Routes>
    </BrowserRouter>
  );
}
export default App;