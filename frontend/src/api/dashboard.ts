import { API_BASE } from '../config';

export async function postHighRisk(body: any) {
  const res = await fetch(`${API_BASE}/api/dashboard/high-risk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(String(res.status));
  return res.json();
}

export async function postMapSummary(body: any) {
  const res = await fetch(`${API_BASE}/api/dashboard/map-summary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(String(res.status));
  return res.json();
}

export async function postGuResidents(body: any) {
  const res = await fetch(`${API_BASE}/api/dashboard/gu-residents`, {
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

