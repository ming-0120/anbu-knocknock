const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function postHighRisk(body: any) {
  const res = await fetch(`${BASE}/api/dashboard/high-risk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(String(res.status));
  return res.json();
}

export async function postMapSummary(body: any) {
  const res = await fetch(`${BASE}/api/dashboard/map-summary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(String(res.status));
  return res.json();
}

export async function postGuResidents(body: any) {
  const res = await fetch(`${BASE}/api/dashboard/gu-residents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(String(res.status));
  return res.json();
}
export type HighRiskReq = {
  window_minutes?: number
  limit?: number
  min_level?: "normal" | "watch" | "alert" | "emergency"
}

export async function getHighRisk(body: HighRiskReq) {
  const res = await fetch("/api/dashboard/high-risk", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    throw new Error(`high-risk API error: ${res.status}`)
  }

  return res.json()
}