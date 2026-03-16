import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { WS_BASE } from '../../config';
type Task = { task_id: number; resident_id: number; alert_id: number; operator_id: number; name: string; gu: string; address_main: string; phone: string; guardian_phone: string; lat: number; lon: number; risk_score: number; last_activity: string; status: string; profile_image_url?: string; reason_codes?: any; summary?: string; };

const MobileApp = () => {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [operatorLocation, setOperatorLocation] = useState<{ lat: number; lon: number } | null>(null);
  const [operatorId, setOperatorId] = useState<number | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("operator_token");
    if (!token) { navigate("/operators/login", { replace: true }); return; }
    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      setOperatorId(payload.operator_id);
      loadTasks(token);
    } catch (err) { console.error("token parse fail", err); }
  }, [navigate]);

  useEffect(() => {
    const token = localStorage.getItem("operator_token");
    if (!token) return;
    const interval = setInterval(() => {
      fetch("/api/operators/heartbeat", { method: "POST", headers: { "Authorization": `Bearer ${token}` } });
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadTasks = async (token: string) => {
    try {
      const res = await fetch("/api/operator-tasks", { headers: { Authorization: `Bearer ${token}` } });
      if (res.status === 401) { localStorage.removeItem("operator_token"); navigate("/operators/login", { replace: true }); return; }
      if (!res.ok) throw new Error("API error");
      const data = await res.json();
      if (Array.isArray(data)) {
        const parsed = data.map((t) => {
          let summary = "";
          if (t.reason_codes) {
            try { const rc = typeof t.reason_codes === "string" ? JSON.parse(t.reason_codes) : t.reason_codes; summary = rc.summary || ""; } 
            catch { summary = ""; }
          }
          return { ...t, summary };
        });
        setTasks(parsed);
      }
    } catch (err) { console.error("task load fail", err); } 
    finally { setLoading(false); }
  };

  useEffect(() => {
    if (!operatorId) return;
    const ws = new WebSocket(`${WS_BASE}/ws/worker/${operatorId}`);
    ws.onopen = () => console.log("worker socket connected");
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "NEW_TASK") {
          const token = localStorage.getItem("operator_token");
          if (token) loadTasks(token);
        }
      } catch (err) { console.error("socket parse error", err); }
    };
    ws.onclose = () => console.log("worker socket closed");
    return () => ws.close();
  }, [operatorId]);

  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => setOperatorLocation({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      (err) => console.error("위치 권한 거부", err)
    );
  }, []);

  if (loading) {
    return (
      <div style={container}>
        <header style={header}><strong>담당 업무</strong></header>
        <div style={{ padding: 20, textAlign: "center", color: "#666" }}>불러오는 중...</div>
      </div>
    );
  }

  return (
    <div style={container}>
      <header style={header}>
        <strong>담당 업무</strong>
      </header>

      <section style={section}>
        {tasks.length === 0 && (
          <div style={{ padding: 20, textAlign: "center", color: "#666" }}>할당된 업무가 없습니다.</div>
        )}

        {tasks.map((task) => (
          <div key={task.task_id} style={card}>
            <div style={{ flex: 1 }}>
              <div style={name}>{task.name}</div>
              <div style={sub}>{task.gu} | {task.address_main}</div>
            </div>
            <button style={btn} onClick={() => navigate("/mobile-detail", { state: { task, operatorLocation } })}>
              상세
            </button>
          </div>
        ))}
      </section>
    </div>
  );
};

// --- Styles ---
const container: React.CSSProperties = { maxWidth: "480px", margin: "0 auto", minHeight: "100vh", background: "#f8f9fa", boxSizing: "border-box", fontFamily: "sans-serif" };
const header: React.CSSProperties = { padding: "16px", textAlign: "center", background: "#ffffff", borderBottom: "1px solid #e5e7eb", fontSize: "16px", color: "#111827", position: "sticky", top: 0, zIndex: 10, boxSizing: "border-box" };
const section: React.CSSProperties = { padding: "16px", boxSizing: "border-box" };
const card: React.CSSProperties = { display: "flex", alignItems: "center", background: "#ffffff", borderRadius: "8px", border: "1px solid #e5e7eb", padding: "16px", marginBottom: "12px", boxSizing: "border-box" };
const name: React.CSSProperties = { fontSize: "16px", fontWeight: 700, color: "#111827", marginBottom: "4px" };
const sub: React.CSSProperties = { fontSize: "13px", color: "#6b7280" };
const btn: React.CSSProperties = { background: "#ffffff", color: "#374151", border: "1px solid #d1d5db", borderRadius: "6px", padding: "8px 16px", fontSize: "13px", fontWeight: 600, cursor: "pointer", flexShrink: 0, boxSizing: "border-box" };

export default MobileApp;