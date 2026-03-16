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

  const location = useLocation();

  const closeModals = () => {
    setActiveModal(null);
    setSelectedUser(null);
  };

  useEffect(() => {
    if (location.state?.selectedGu) {
      setSelectedGu(location.state.selectedGu);
      setIsRightOpen(true);
    }

    if (location.state?.user) {
      setSelectedUser(location.state.user);
      setActiveModal("info");
    }
  }, [location.state]);

  /**
   * 🔴 Dashboard 데이터 로드 함수
   */
  const loadDashboard = async () => {
    const [hr, ms] = await Promise.all([
      postHighRisk({ window_minutes: 60, limit: 50 }),
      postMapSummary({ window_minutes: 60 }),
    ]);

    setHighRiskUsers(hr.items ?? []);
    setMapSummary(ms.items ?? []);
  };

  /**
   * 초기 로딩 + 30초 polling
   */
  useEffect(() => {
    let alive = true;

    loadDashboard().catch(console.error);

    const t = window.setInterval(() => {
      loadDashboard().catch(console.error);
    }, 30000);

    return () => {
      alive = false;
      window.clearInterval(t);
    };
  }, []);

  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/ws/dashboard`);

    ws.onopen = () => {
      console.log("dashboard websocket connected");
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === "task_complete") {
        toast(`${data.resident_gu} ${data.resident_name} 업무가 처리되었습니다`);
        loadDashboard();
      }

      if (data.type === "task_assigned") {
        toast("새로운 업무가 배정되었습니다");
        loadDashboard();
      }
    };

    ws.onerror = (err) => {
      console.error("WebSocket error", err);
    };

    ws.onclose = () => {
      console.log("dashboard websocket closed");
    };

    return () => ws.close();
  }, []);

  /**
   * 구 선택 시 우측 데이터 로드
   */
  useEffect(() => {
    if (!isRightOpen) return;
    if (!selectedGu || selectedGu === "서울시") return;

    let alive = true;

    (async () => {
      const res = await postGuResidents({
        gu: selectedGu,
        limit: 500,
        include_latest_score: true,
      });

      if (!alive) return;

      setGuUsers(res.items ?? []);
    })().catch(console.error);

    return () => {
      alive = false;
    };
  }, [selectedGu, isRightOpen]);

  /**
   * SidebarLeft 데이터
   */
  const leftUsers = useMemo(() => {
    return highRiskUsers.map((x) => ({
      ...x,
      id: x.resident_id,
      status:
        x.risk_level === "danger" ||
        x.risk_level === "emergency" ||
        x.risk_level === "alert"
          ? "danger"
          : "normal",
      issue:
        x.reason_codes?.reason ??
        `score=${Number(x.risk_score).toFixed(2)}`,
    }));
  }, [highRiskUsers]);

  /**
   * SidebarRight 데이터
   */
  const rightUsers = useMemo(() => {
    const byId = new Map<number, any>();
    const dupIds: number[] = [];

    for (const x of guUsers) {
      const id = Number(x.resident_id);
      if (!Number.isFinite(id)) continue;

      const prev = byId.get(id);

      if (!prev) {
        byId.set(id, x);
        continue;
      }

      dupIds.push(id);

      const prevT = prev.latest_scored_at
        ? Date.parse(prev.latest_scored_at)
        : -Infinity;

      const curT = x.latest_scored_at
        ? Date.parse(x.latest_scored_at)
        : -Infinity;

      if (curT >= prevT) byId.set(id, x);
    }

    if (dupIds.length > 0) {
      const uniq = Array.from(new Set(dupIds));
      console.warn("[Dashboard] Duplicate resident_id:", uniq);
    }

    return Array.from(byId.values()).map((x) => {
      const s = x.latest_risk_score;
      const level = (x.latest_risk_level ?? "normal") as RiskLevel;

      const status: "danger" | "normal" =
        level === "danger" ||
        level === "emergency" ||
        level === "alert"
          ? "danger"
          : "normal";

      const pct = typeof s === "number" ? Math.round(s * 100) : null;

      return {
        ...x,
        status,
        issue: pct != null ? `위험도 : ${pct}%` : "위험도 : -",
        scoreText: typeof s === "number" ? s.toFixed(2) : "-",
      };
    });
  }, [guUsers]);

  return (
    <>
      {/* 💡 Toast 알림창 스타일 모던하게 변경 */}
      <Toaster
        position="bottom-center"
        toastOptions={{
          style: {
            background: "#374151",
            color: "#ffffff",
            borderRadius: "8px",
            fontSize: "14px",
            fontWeight: 500,
            padding: "12px 16px",
            boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
          },
        }}
      />

      <div
        style={{
          display: "flex",
          width: "100vw",
          height: "100%",
          overflow: "hidden",
          backgroundColor: "#f9fafb",
        }}
      >
        <SidebarLeft
          users={leftUsers}
          onUserClick={(u) => {
            setSelectedUser(u);
            setActiveModal("info");
          }}
        />

        {/* 💡 수정된 부분: mapData prop으로 mapSummary 전달 */}
        <MapView
          mapData={mapSummary}
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
            onDetailClick={(u) => {
              setSelectedUser(u);
              setActiveModal("info");
            }}
          />
        )}

        {activeModal === "danger" && (
          <DangerModal
            user={selectedUser}
            onClose={closeModals}
            onAssigned={(rid) => {
              setHighRiskUsers((prev) =>
                prev.filter((u) => u.resident_id !== rid)
              );
            }}
          />
        )}

        {activeModal === "info" && (
          <InfoModal
            user={selectedUser}
            selectedGu={selectedGu}
            onClose={() => setActiveModal(null)}
            onShowDanger={(u) => {
              setSelectedUser(u);
              setActiveModal("danger");
            }}
          />
        )}
      </div>
    </>
  );
}