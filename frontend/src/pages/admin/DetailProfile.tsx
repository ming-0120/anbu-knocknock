import React, { useEffect, useMemo, useRef, useState } from "react";

import { useLocation, useNavigate } from "react-router-dom";

import DetailProfileEditModal from "./DetailProfileEditModal";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";



async function getHourlyFeatures(residentId: number) {

  const res = await fetch(`/api/hourly-features/${residentId}`)

  if (!res.ok) throw new Error("API error")

  return res.json()

}



/** =========================

 * 독거기간 계산 유틸

 * ========================= */

function calcLivingAlonePeriod(livingAloneSince?: string | null): { years: number; months: number } | null {

  if (!livingAloneSince) return null;

  const start = new Date(livingAloneSince);

  if (Number.isNaN(start.getTime())) return null;

  const today = new Date();

  let years = today.getFullYear() - start.getFullYear();

  let months = today.getMonth() - start.getMonth();

  let days = today.getDate() - start.getDate();



  if (days < 0) {

    const prevMonthLastDay = new Date(today.getFullYear(), today.getMonth(), 0).getDate();

    months -= 1;

    days += prevMonthLastDay;

  }

  if (months < 0) { months += 12; years -= 1; }

  if (years < 0) return null;

  return { years, months };

}



function schedulesToDaysOfWeek(editSchedules: OutingSchedule[]) {

  return {

    routine: {

      outings: editSchedules.map((s) => ({

        type: "regular",

        label: s.memo,

        days: Object.entries(s.days).filter(([_, v]) => v).map(([k]) => k.toUpperCase()),

        schedule: [{ start: s.startTime, end: s.endTime }]

      }))

    }

  }

}



function formatLivingAlonePeriod(livingAloneSince?: string | null): string {

  const p = calcLivingAlonePeriod(livingAloneSince);

  if (!p) return "-";

  return `${p.years}년 ${p.months}개월`;

}



/** =========================

 * 타입 정의

 * ========================= */

type ChartPoint = { n: string | number; v: number };

type OutingSchedule = { id: string; memo: string; days: Record<"mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun", boolean>; part: "morning" | "afternoon"; startTime: string; endTime: string; };

type UserDetail = {

  resident_id?: number | string; disease_label?: string | null; name: string; age?: number; gender?: string;

  address?: string; address_main?: string; address_detail?: string; note?: string;

  diseases?: string | null; medications?: string | null; living_alone_since?: string | null;

  contact?: { guardian?: string; guardian_phone?: string }; manager?: { name?: string; phone?: string };

  profile_image_url?: string | null; sensitivity_weight?: number | null; sleep_start?: string | null; sleep_end?: string | null;

  chartData?: ChartPoint[]; outingSchedules?: OutingSchedule[]; days_of_week?: any;

};



const API_BASE = "http://localhost:8000";



type ResidentDetailResponse = {

  resident_id: number; name: string; phone: string | null; address_main: string | null; address_detail: string | null;

  birth_date: string | null; age: number | null; gender: string | null; note: string | null; profile_image_url: string | null;

  diseases?: string | null; disease_label?: string | null; medications?: string | null; living_alone_since?: string | null;

  settings: null | { sensitivity_weight: number | null; sleep_start: string | null; sleep_end: string | null; no_activity_threshold_min?: number | null; emergency_sms_enabled?: boolean | null; days_of_week?: any; };

  guardian: null | { guardian_id: number; name: string; phone: string | null; guardian_type?: string | null; is_primary: boolean; priority: number | null; };

};



async function updateResidentDetail(

  residentId: string | number,

  payload: { note?:string; address_main?: string; address_detail?: string; sensitivity_weight?: number | null; sleep_start?: string | null; sleep_end?: string | null; days_of_week?: any; profileImageFile?: File | null; }

): Promise<void> {

  const fd = new FormData();

  if (payload.address_main !== undefined) fd.append("address_main", payload.address_main);

  if (payload.address_detail !== undefined) fd.append("address_detail", payload.address_detail);

  if (payload.note !== undefined) fd.append("note", payload.note);

  if (payload.sensitivity_weight !== undefined) fd.append("sensitivity_weight", String(payload.sensitivity_weight ?? ""));

  if (payload.sleep_start !== undefined) fd.append("sleep_start", payload.sleep_start ?? "");

  if (payload.sleep_end !== undefined) fd.append("sleep_end", payload.sleep_end ?? "");

  if (payload.days_of_week !== undefined) fd.append("days_of_week", JSON.stringify(payload.days_of_week));

  if (payload.profileImageFile) fd.append("profile_image", payload.profileImageFile);



  const res = await fetch(`/api/dashboard/residents/${residentId}`, { method: "PUT", body: fd });

  if (!res.ok) throw new Error(`PUT resident update failed: ${res.status}`);

}



const DEFAULT_PROFILE_IMG = "/images/default-profile.png";

const dayKeys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;



function newSchedule(): OutingSchedule {

  return { id: crypto.randomUUID(), memo: "", days: { mon: false, tue: false, wed: false, thu: false, fri: false, sat: false, sun: false }, part: "morning", startTime: "09:00", endTime: "12:00" };

}



function parseRoutineToSchedules(days_of_week: any) {

  const outings = days_of_week?.routine?.outings ?? [];

  return outings.map((o: any) => {

    const sched = o.schedule?.[0] ?? {};

    const dayObj: Record<"mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun", boolean> = { mon:false, tue:false, wed:false, thu:false, fri:false, sat:false, sun:false };

    (o.days ?? []).forEach((d:string)=>{ const key = d.toLowerCase() as keyof typeof dayObj; dayObj[key] = true; });

    const start = sched.start ?? "09:00"; const end = sched.end ?? "10:00";

    const hour = Number(start.split(":")[0]);

    return { id: crypto.randomUUID(), memo: o.label ?? "", days: dayObj, part: hour < 12 ? "morning" : "afternoon", startTime: start, endTime: end };

  });

}



async function fetchResidentDetail(residentId: number | string): Promise<ResidentDetailResponse> {

  const ridNum = typeof residentId === "number" ? residentId : Number(residentId);

  if (!Number.isFinite(ridNum)) throw new Error("Invalid residentId");

  const res = await fetch(`/api/dashboard/residents/${ridNum}`);

  if (!res.ok) throw new Error(String(res.status));

  return res.json();

}



const DetailProfile = () => {

  const location = useLocation();

  const navigate = useNavigate();

  const initialUser = (location.state?.user ?? {}) as Partial<UserDetail>;



  const [userInfo, setUserInfo] = useState<UserDetail>(() => ({

    name: initialUser.name ?? "", age: initialUser.age, gender: initialUser.gender, address: initialUser.address, note: initialUser.note,

    diseases: initialUser.diseases ?? null, medications: initialUser.medications ?? null, living_alone_since: initialUser.living_alone_since ?? null,

    contact: initialUser.contact, manager: initialUser.manager, resident_id: initialUser.resident_id, profile_image_url: initialUser.profile_image_url ?? null,

    chartData: initialUser.chartData ?? [], sensitivity_weight: initialUser.sensitivity_weight ?? null, sleep_start: initialUser.sleep_start ?? "21:00",

    sleep_end: initialUser.sleep_end ?? "07:00", outingSchedules: initialUser.outingSchedules ?? [], address_main: initialUser.address_main ?? "", address_detail: initialUser.address_detail ?? "",

  }));




  const [editAddress, setEditAddress] = useState("");

  const [editAddressDetail, setEditAddressDetail] = useState("");

  const [editZipCode, setEditZipCode] = useState("");

  const [editNote, setEditNote] = useState("");

  const [editSensitivity, setEditSensitivity] = useState<number | null>(null);

  const [editSleepStart, setEditSleepStart] = useState("21:00");

  const [editSleepEnd, setEditSleepEnd] = useState("07:00");

  const [editSchedules, setEditSchedules] = useState<OutingSchedule[]>([]);

  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  const [daysOfWeek, setDaysOfWeek] = useState<any>(null);

  const [profilePreviewUrl, setProfilePreviewUrl] = useState<string | null>(null);

  const [profileFile, setProfileFile] = useState<File | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

 

  useEffect(() => {

    const rid = userInfo.resident_id;

    if (rid === undefined || rid === null || rid === "") return;

    (async () => {

      const fresh = await fetchResidentDetail(rid);

      const address = [fresh.address_main, fresh.address_detail].filter((v) => typeof v === "string" && v.trim()).join(" ");

      setUserInfo((prev) => ({

        ...prev, resident_id: fresh.resident_id, name: fresh.name, age: fresh.age ?? prev.age, gender: fresh.gender ?? prev.gender,

        disease_label: fresh.disease_label ?? prev.disease_label ?? null, address: address || "-", note: fresh.note ?? prev.note ?? "-",

        diseases: fresh.diseases ?? prev.diseases ?? null, medications: fresh.medications ?? prev.medications ?? null, living_alone_since: fresh.living_alone_since ?? prev.living_alone_since ?? null,

        profile_image_url: fresh.profile_image_url ?? prev.profile_image_url ?? null,

        contact: { ...(prev.contact ?? {}), guardian: fresh.guardian?.name ?? "-", guardian_phone: fresh.guardian?.phone ?? "", },

        sensitivity_weight: fresh.settings?.sensitivity_weight ?? null, sleep_start: fresh.settings?.sleep_start ?? "21:00", sleep_end: fresh.settings?.sleep_end ?? "07:00",

        outingSchedules: parseRoutineToSchedules(fresh.settings?.days_of_week),

      }));

      setDaysOfWeek(fresh.settings?.days_of_week ?? null);

    })().catch(() => {});

  }, [userInfo.resident_id]);



  useEffect(() => { if (!daysOfWeek) return; const parsed = parseRoutineToSchedules(daysOfWeek); setEditSchedules(parsed); }, [daysOfWeek]);



  useEffect(() => {

    const rid = userInfo.resident_id;

    if (!rid) return;

    async function loadChart() {

      try { const data = await getHourlyFeatures(Number(rid)); setUserInfo(prev => ({ ...prev, chartData: data })); }

      catch (e) { console.error("chart load fail", e); }

    }

    loadChart();

  }, [userInfo.resident_id]);



  useEffect(() => {

    if (!isEditModalOpen) return;

    setEditAddress(userInfo.address_main ?? ""); setEditAddressDetail(userInfo.address_detail ?? "");

    setEditNote(userInfo.note ?? ""); setEditSensitivity(userInfo.sensitivity_weight ?? null);

    setEditSleepStart(userInfo.sleep_start ?? "21:00"); setEditSleepEnd(userInfo.sleep_end ?? "07:00");

    setProfilePreviewUrl(null); setProfileFile(null);

  }, [isEditModalOpen, userInfo]);



  const displayProfileImg = useMemo(() => {

    if (profilePreviewUrl) return profilePreviewUrl;

    if (userInfo.profile_image_url) return API_BASE + userInfo.profile_image_url;

    return DEFAULT_PROFILE_IMG;

  }, [profilePreviewUrl, userInfo.profile_image_url]);



  if (!userInfo.name) return <div style={{ padding: "20px" }}>데이터가 없습니다.</div>;



  const openFilePicker = () => fileInputRef.current?.click();

  const onPickImage: React.ChangeEventHandler<HTMLInputElement> = (e) => {

    const f = e.target.files?.[0];

    if (!f) return;

    if (!f.type.startsWith("image/")) { alert("이미지 파일만 업로드할 수 있습니다."); e.target.value = ""; return; }

    const url = URL.createObjectURL(f); setProfileFile(f); setProfilePreviewUrl(url);

  };



  const toggleDay = (schedId: string, day: (typeof dayKeys)[number]) => { setEditSchedules((prev) => prev.map((s) => s.id === schedId ? { ...s, days: { ...s.days, [day]: !s.days[day] } } : s)); };

  const updateSchedule = (schedId: string, patch: Partial<OutingSchedule>) => { setEditSchedules((prev) => prev.map((s) => (s.id === schedId ? { ...s, ...patch } : s))); };

  const addSchedule = () => setEditSchedules((prev) => [...prev, newSchedule()]);

  const removeSchedule = (schedId: string) => setEditSchedules((prev) => prev.filter((s) => s.id !== schedId));



  const onSave = async () => {

    const ok = window.confirm("수정하시겠습니까?");

    if (!ok) return;

    const rid = userInfo.resident_id;

    if (rid === undefined || rid === null || rid === "") { alert("resident_id가 없어 저장할 수 없습니다."); return; }

    try {

      const daysOfWeekJson = schedulesToDaysOfWeek(editSchedules);

      await updateResidentDetail(rid, { address_main: editAddress, address_detail: editAddressDetail, note: editNote, sensitivity_weight: editSensitivity, sleep_start: editSleepStart, sleep_end: editSleepEnd, days_of_week: daysOfWeekJson, profileImageFile: profileFile });

      alert("저장되었습니다.");

      setUserInfo((prev) => ({ ...prev, address_main: editAddress, address_detail: editAddressDetail, address: `${editAddress} ${editAddressDetail}`.trim(), note: editNote, sensitivity_weight: editSensitivity, sleep_start: editSleepStart, sleep_end: editSleepEnd, outingSchedules: editSchedules }));

      setIsEditModalOpen(false);

      try {

        const fresh = await fetchResidentDetail(rid);

        const address = [fresh.address_main, fresh.address_detail].filter((v) => typeof v === "string" && v.trim()).join(" ");

        setUserInfo((prev) => ({

          ...prev, resident_id: fresh.resident_id, name: fresh.name, age: fresh.age ?? prev.age, gender: fresh.gender ?? prev.gender, address: address || prev.address || "-",

          contact: { ...(prev.contact ?? {}), guardian: fresh.guardian?.name ?? prev.contact?.guardian ?? "-", guardian_phone: fresh.guardian?.phone ?? prev.contact?.guardian_phone ?? "", },

          sensitivity_weight: fresh.settings?.sensitivity_weight ?? prev.sensitivity_weight ?? null, sleep_start: fresh.settings?.sleep_start ?? prev.sleep_start ?? "21:00", sleep_end: fresh.settings?.sleep_end ?? prev.sleep_end ?? "07:00",

          diseases: fresh.diseases ?? prev.diseases ?? null, medications: fresh.medications ?? prev.medications ?? null, living_alone_since: fresh.living_alone_since ?? prev.living_alone_since ?? null,

        }));

      } catch {}

    } catch (e) { alert("저장 실패"); }

  };



  const formattedChart = (userInfo.chartData ?? []).map((d:any) => ({

    hour: new Date(d.hour).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" }), motion: d.motion

  }));

  return (
    <div style={pageStyle}>
      <header style={headerStyle}>
        <div>
          <h2 style={{ margin: 0, fontSize: "24px", fontWeight: 800, color: "#1e293b" }}>
            {userInfo.name} <span style={{ fontSize: "18px", color: "#64748b", fontWeight: 500 }}>({userInfo.age}세, {userInfo.gender})</span>
          </h2>
          <div style={statusBadgeStyle}><span style={pulseDotStyle}></span> 정상 작동 중</div>
        </div>
        <button onClick={() => navigate("/dashboard")} style={btnGhost}>대시보드로 돌아가기</button>
      </header>

      <div style={topProfileGridStyle}>
        <div style={avatarCardStyle}>
          <img src={displayProfileImg} alt="profile" style={avatarImgStyle} />
        </div>
        <div style={infoGridCardStyle}>
          <div style={infoGridStyle}>
            <InfoItem label="질병" value={userInfo.disease_label} isTag />
            <InfoItem label="복용약" value={userInfo.medications} isTag color="#f0f9ff" textColor="#0369a1" />
            <InfoItem label="비상연락망" value={`${userInfo.contact?.guardian || "-"} (${userInfo.contact?.guardian_phone || "-"})`} />
            <InfoItem label="독거기간" value={formatLivingAlonePeriod(userInfo.living_alone_since)} subValue={`시작: ${userInfo.living_alone_since || "-"}`} />
            <div style={{ gridColumn: "span 2", borderTop: "1px solid #f1f5f9", paddingTop: "16px" }}>
              <div style={labelStyle}>메모</div>
              <div style={{ fontSize: "14px", color: "#475569" }}>{userInfo.note || "없음"}</div>
            </div>
          </div>
        </div>
      </div>

      <div style={bottomGridStyle}>
        <section style={cardStyle}>
          <div style={sectionHeaderStyle}>활동량 추이</div>
          <div style={{ height: 280, marginTop: "20px" }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={formattedChart}>
                <defs>
                  <linearGradient id="colorMotion" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9"/>
                <XAxis dataKey="hour" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip />
                <Area type="monotone" dataKey="motion" stroke="#3b82f6" strokeWidth={3} fill="url(#colorMotion)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section style={cardStyle}>
          <div style={sectionHeaderStyle}>최근 이력</div>
          <div style={logItemStyle}>
            <div style={{ fontWeight: 700 }}>02/10(화) <span style={{ color: "#3b82f6" }}>[전화]</span></div>
            <div style={{ fontSize: "14px", marginTop: "8px" }}>
              "최근 <span style={{ color: "#ef4444", fontWeight: 700 }}>어지러움증 호소</span> 증상 확인."
            </div>
          </div>
        </section>
      </div>

      <div style={{ display: "flex", justifyContent: "center", marginTop: "20px" }}>
        <button onClick={() => setIsEditModalOpen(true)} style={btnPrimary}>정보 수정하기</button>
      </div>

      {/* 모달 에러 해결: 모든 필수 Props 전달 */}
      <DetailProfileEditModal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        onSave={onSave}
        editAddress={editAddress} setEditAddress={setEditAddress}
        editZipCode={editZipCode} setEditZipCode={setEditZipCode}
        editAddressDetail={editAddressDetail} setEditAddressDetail={setEditAddressDetail}
        editNote={editNote} setEditNote={setEditNote}
        editSchedules={editSchedules}
        addSchedule={addSchedule} 
        removeSchedule={removeSchedule} 
        updateSchedule={updateSchedule} 
        toggleDay={toggleDay} 
        displayProfileImg={displayProfileImg} openFilePicker={openFilePicker} fileInputRef={fileInputRef} onPickImage={onPickImage}
        editSensitivity={editSensitivity} setEditSensitivity={setEditSensitivity}
        editSleepStart={editSleepStart} setEditSleepStart={setEditSleepStart}
        editSleepEnd={editSleepEnd} setEditSleepEnd={setEditSleepEnd}
      />
    </div>
  );
};

// ... 이하 기존 스타일(CSS-in-JS)은 동일 ...
const InfoItem = ({ label, value, isTag, color, textColor, subValue }: any) => (
  <div>
    <div style={labelStyle}>{label}</div>
    {isTag ? (
      <span style={{ display: 'inline-block', padding: '4px 10px', borderRadius: '6px', backgroundColor: color || '#f1f5f9', color: textColor || '#475569', fontSize: '13px', fontWeight: 600, marginTop: '4px' }}>{value || "-"}</span>
    ) : (
      <div style={{ fontSize: "15px", fontWeight: 600, color: "#1e293b", marginTop: "4px" }}>{value || "-"}{subValue && <div style={{ fontSize: '12px', color: '#94a3b8', fontWeight: 400 }}>{subValue}</div>}</div>
    )}
  </div>
);

const pageStyle: React.CSSProperties = { padding: "40px", backgroundColor: "#f0f7ff", minHeight: "100vh", fontFamily: "Pretendard" };
const headerStyle: React.CSSProperties = { display: "flex", justifyContent: "space-between", marginBottom: "32px" };
const topProfileGridStyle: React.CSSProperties = { display: "grid", gridTemplateColumns: "240px 1fr", gap: "24px", marginBottom: "24px" };
const avatarCardStyle: React.CSSProperties = { background: "#fff", borderRadius: "20px", padding: "20px", display: "flex", justifyContent: "center", alignItems: "center", boxShadow: "0 10px 25px rgba(0,0,0,0.05)" };
const avatarImgStyle: React.CSSProperties = { width: "160px", height: "160px", borderRadius: "50%", objectFit: "cover" };
const infoGridCardStyle: React.CSSProperties = { background: "#fff", borderRadius: "20px", padding: "32px", boxShadow: "0 10px 25px rgba(0,0,0,0.05)" };
const infoGridStyle: React.CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" };
const labelStyle: React.CSSProperties = { fontSize: "12px", fontWeight: 600, color: "#94a3b8", marginBottom: "4px" };
const bottomGridStyle: React.CSSProperties = { display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: "24px" };
const cardStyle: React.CSSProperties = { background: "#fff", borderRadius: "20px", padding: "28px", boxShadow: "0 10px 25px rgba(0,0,0,0.05)" };
const sectionHeaderStyle: React.CSSProperties = { fontWeight: 800, fontSize: "18px", color: "#1e293b" };
const statusBadgeStyle: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', padding: '6px 12px', backgroundColor: '#ecfdf5', color: '#059669', borderRadius: '20px', fontSize: '13px', fontWeight: 600, marginTop: '10px' };
const pulseDotStyle: React.CSSProperties = { width: '8px', height: '8px', backgroundColor: '#10b981', borderRadius: '50%', marginRight: '8px' };
const logItemStyle: React.CSSProperties = { marginTop: "20px", padding: "20px", borderRadius: "16px", backgroundColor: "#f8fafc" };
const btnPrimary: React.CSSProperties = { padding: "14px 32px", borderRadius: "12px", border: "none", background: "#2563eb", color: "#fff", fontWeight: 700, cursor: "pointer" };
const btnGhost: React.CSSProperties = { padding: "10px 20px", borderRadius: "10px", border: "1px solid #e2e8f0", background: "#fff", color: "#64748b", fontWeight: 600, cursor: "pointer" };

export default DetailProfile;