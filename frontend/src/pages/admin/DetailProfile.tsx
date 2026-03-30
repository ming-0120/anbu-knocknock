import React, { useEffect, useMemo, useRef, useState } from "react";
import { API_BASE } from '../../config';
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

/** 매핑 및 유틸 함수 생략 **/
const diseaseMap: Record<string, string> = { none: "없음", diabetes: "당뇨", hypertension: "고혈압", depression: "우울증", alcoholism: "알코올 의존" };
const medicationMap: Record<string, string> = { none: "복용 약 없음", metformin: "메트포르민", amlodipine: "암로디핀", sertraline: "설트랄린" };
function formatLivingAlonePeriod(livingAloneSince?: string | null): string {
  if (!livingAloneSince) return "-";
  const start = new Date(livingAloneSince);
  if (Number.isNaN(start.getTime())) return "-";
  const today = new Date();
  let years = today.getFullYear() - start.getFullYear();
  let months = today.getMonth() - start.getMonth();
  if (months < 0) { months += 12; years -= 1; }
  return `${years}년 ${months}개월`;
}

type ChartPoint = { hour: string; motion: number };
type OutingSchedule = { id: string; memo: string; days: Record<string, boolean>; part: "morning" | "afternoon"; startTime: string; endTime: string; };
type UserDetail = {
  resident_id?: number | string; name: string; age?: number; gender?: string;
  address?: string; address_main?: string; address_detail?: string; note?: string;
  diseases?: string | null; medications?: string | null; living_alone_since?: string | null;
  contact?: { guardian?: string; guardian_phone?: string }; profile_image_url?: string | null;
  chartData?: ChartPoint[]; recent_history: any[]; phone?: string | null;
  sensitivity_weight?: number | null; sleep_start?: string; sleep_end?: string; outingSchedules?: OutingSchedule[];
};

const DEFAULT_PROFILE_IMG = "/images/default-profile3.png";

const DetailProfile = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const initialUser = (location.state?.user ?? {}) as Partial<UserDetail>;
  const selectedGu = location.state?.selectedGu;

  const [userInfo, setUserInfo] = useState<UserDetail>(() => ({
    name: initialUser.name ?? "", age: initialUser.age, gender: initialUser.gender, resident_id: initialUser.resident_id,
    profile_image_url: initialUser.profile_image_url ?? null, chartData: [], recent_history: [],
    note: initialUser.note ?? "", address_main: initialUser.address_main ?? "", address_detail: initialUser.address_detail ?? "", phone: initialUser.phone ?? null,
  }));

  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editAddress, setEditAddress] = useState("");
  const [editAddressDetail, setEditAddressDetail] = useState("");
  const [editZipCode, setEditZipCode] = useState("");
  const [editNote, setEditNote] = useState("");
  const [editSensitivity, setEditSensitivity] = useState<number | null>(null);
  const [editSleepStart, setEditSleepStart] = useState("21:00");
  const [editSleepEnd, setEditSleepEnd] = useState("07:00");
  const [editSchedules, setEditSchedules] = useState<OutingSchedule[]>([]);
  const [profilePreviewUrl, setProfilePreviewUrl] = useState<string | null>(null);
  const [profileFile, setProfileFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const formatTime = (t?: string) => {
    if (!t) return "";
    return t.slice(0, 5); // "22:00:00" → "22:00"
  };
  useEffect(() => {
    const rid = userInfo.resident_id;
    if (!rid) return;
    (async () => {
      try {
        const res = await fetch(`/api/dashboard/residents/${rid}`);
        const fresh = await res.json();
        const filteredHistory = (fresh.recent_history ?? []).filter((h: any) => h.description && h.description !== "내용 없음" && h.description !== "요약 없음");
        setUserInfo(prev => ({ ...prev, ...fresh, recent_history: filteredHistory }));
        setEditAddress(fresh.address_main ?? "");
        setEditAddressDetail(fresh.address_detail ?? "");
        setEditNote(fresh.note ?? "");
        setEditSchedules(
          parseSchedules(fresh.settings?.days_of_week)
        );
         // 🔥 추가 (핵심)
      setEditSleepStart(formatTime(fresh.settings?.sleep_start) || "21:00");
      setEditSleepEnd(formatTime(fresh.settings?.sleep_end) || "07:00");
        const chartRes = await fetch(`/api/hourly-features/${rid}`);
        const chartData = await chartRes.json();
        setUserInfo(prev => ({ ...prev, chartData }));
      } catch (e) { console.error(e); }
    })();
  }, [userInfo.resident_id]);

  const displayProfileImg = useMemo(() => {
    if (profilePreviewUrl) return profilePreviewUrl;
    if (userInfo.profile_image_url) return API_BASE + userInfo.profile_image_url;
    return userInfo.gender?.toLowerCase() === 'female' ? '/images/female-profile.png' : '/images/male-profile.png';
  }, [profilePreviewUrl, userInfo.profile_image_url, userInfo.gender]);
const parseSchedules = (data: any): OutingSchedule[] => {
  if (!data?.routine?.outings) return [];

  return data.routine.outings.map((o: any) => {
    const daysObj: any = {
      mon: false, tue: false, wed: false,
      thu: false, fri: false, sat: false, sun: false
    };

    (o.days || []).forEach((d: string) => {
      const key = d.toLowerCase();
      daysObj[key] = true;
    });

    return {
      id: crypto.randomUUID(),
      memo: o.label || "",
      days: daysObj,
      part: "morning",
      startTime: o.schedule?.[0]?.start || "09:00",
      endTime: o.schedule?.[0]?.end || "12:00"
    };
  });
};
  const openFilePicker = () => fileInputRef.current?.click();
  const onPickImage = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) { setProfileFile(f); setProfilePreviewUrl(URL.createObjectURL(f)); }
  };
  const addSchedule = () => setEditSchedules(prev => [...prev, { id: crypto.randomUUID(), memo: "", days: {}, part: "morning", startTime: "09:00", endTime: "12:00" }]);
  const removeSchedule = (id: string) => setEditSchedules(prev => prev.filter(s => s.id !== id));
  const updateSchedule = (id: string, patch: any) => setEditSchedules(prev => prev.map(s => s.id === id ? { ...s, ...patch } : s));
  const toggleDay = (id: string, day: string) => setEditSchedules(prev => prev.map(s => s.id === id ? { ...s, days: { ...s.days, [day]: !s.days[day] } } : s));
const convertSchedules = (schedules: OutingSchedule[]) => {
  return {
    routine: {
      outings: schedules.map(s => ({
        days: Object.entries(s.days || {})
          .filter(([_, v]) => v)
          .map(([k]) => k.toUpperCase()),

        type: "regular",

        label: s.memo || "",

        schedule: [
          {
            start: s.startTime,
            end: s.endTime
          }
        ]
      }))
    }
  };
};
  const onSave = async () => {
  try {
    console.log("address_main:", editAddress);
    console.log("address_detail:", editAddressDetail);
    console.log("editSchedules:", editSchedules);

    const fd = new FormData();

    // ✅ 주소 / 메모
    fd.append("address_main", editAddress || "");
    fd.append("address_detail", editAddressDetail || "");
    fd.append("note", editNote || "");

    // ✅ 🔥 스케줄 변환 후 저장
    const routineData = convertSchedules(editSchedules);
    fd.append("days_of_week", JSON.stringify(routineData));

    // ✅ 추가 설정값
    if (editSensitivity !== null) {
      fd.append("sensitivity_weight", String(editSensitivity));
    }

    if (editSleepStart) {
      fd.append("sleep_start", editSleepStart);
    }

    if (editSleepEnd) {
      fd.append("sleep_end", editSleepEnd);
    }

    // ✅ 프로필 이미지
    if (profileFile) {
      fd.append("profile_image", profileFile);
    }

    const res = await fetch(`/api/dashboard/residents/${userInfo.resident_id}`, {
      method: "PUT",
      body: fd
    });

    if (!res.ok) {
      const text = await res.text();
      console.error("서버 에러:", text);
      alert("저장 실패");
      return;
    }

    alert("저장되었습니다.");
    setIsEditModalOpen(false);
    window.location.reload();

  } catch (e) {
    console.error(e);
    alert("저장 실패");
  }
};

  const formattedChart = (userInfo.chartData ?? []).map((d: any) => ({
    hour: new Date(d.hour).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" }), motion: d.motion
  }));

  const hasValidHistory = userInfo.recent_history && userInfo.recent_history.length > 0;

  return (
    <div style={pageContainerStyle}>
      <header style={compactHeaderStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <h2 style={{ margin: 0, fontSize: "20px", fontWeight: 800, color: "#1e293b" }}>{userInfo.name} <span style={{ fontSize: "15px", color: "#64748b", fontWeight: 500 }}>({userInfo.age}세, {userInfo.gender})</span></h2>
          <div style={statusBadgeStyle}><span style={pulseDotStyle}></span> 정상 작동 중</div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button onClick={() => setIsEditModalOpen(true)} style={btnPrimarySmall}>정보 수정</button>
          <button onClick={() => navigate("/dashboard", { state: { selectedGu } })} style={btnGhostSmall}>닫기</button>
        </div>
      </header>

      {/* 💡 비율 조정: 프로필 320px 확장, 중앙 그래프 영역 minmax 설정 */}
      <div style={{ 
        ...dashboardGridStyle, 
        gridTemplateColumns: hasValidHistory ? "320px minmax(0, 1fr) 300px" : "320px minmax(0, 1fr)" 
      }}>
        
        {/* 1열: 프로필 정보 (확장됨) */}
        <aside style={sidePanelStyle}>
          <div style={avatarCircleStyle}><img src={displayProfileImg} alt="profile" style={avatarImgSmallStyle} /></div>
          <div style={infoStackStyle}>
            <CompactInfoItem label="질병" value={diseaseMap[userInfo.diseases ?? ""] ?? userInfo.diseases} isTag />
            <CompactInfoItem label="복용약" value={medicationMap[userInfo.medications ?? ""] ?? userInfo.medications} isTag />
            <CompactInfoItem label="연락처" value={userInfo.phone} />
            <CompactInfoItem label="비상연락망" value={`${userInfo.contact?.guardian || "-"} \n ${userInfo.contact?.guardian_phone || "-"}`} />
            <CompactInfoItem label="독거기간" value={formatLivingAlonePeriod(userInfo.living_alone_since)} />
            <div style={memoBoxStyle}><div style={miniLabelStyle}>메모</div><div style={memoTextStyle}>{userInfo.note || "기록 없음"}</div></div>
          </div>
        </aside>

        {/* 2열: 활동량 추이 그래프 (비율 감소) */}
        <main style={mainContentStyle}>
          <section style={chartCardStyle}>
            <div style={cardHeaderStyle}>24시간 활동 추이</div>
            <div style={chartContainerArea}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={formattedChart} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs><linearGradient id="colorMotion" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2} /><stop offset="95%" stopColor="#3b82f6" stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" /><XAxis dataKey="hour" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} /><YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} /><Tooltip /><Area type="monotone" dataKey="motion" stroke="#3b82f6" strokeWidth={3} fill="url(#colorMotion)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </section>
        </main>

        {/* 3열: 최근 이력 */}
        {hasValidHistory && (
          <aside style={historyPanelStyle}>
            <div style={cardHeaderStyle}>최근 상담 및 이상 이력</div>
            <div style={historyListStyle}>
              {userInfo.recent_history.map((item, idx) => <HistoryLogItem key={idx} item={item} />)}
            </div>
          </aside>
        )}
      </div>

      <DetailProfileEditModal
        isOpen={isEditModalOpen} onClose={() => setIsEditModalOpen(false)} onSave={onSave}
        editAddress={editAddress} setEditAddress={setEditAddress} editZipCode={editZipCode} setEditZipCode={setEditZipCode}
        editAddressDetail={editAddressDetail} setEditAddressDetail={setEditAddressDetail} editNote={editNote} setEditNote={setEditNote}        
        editSensitivity={editSensitivity} setEditSensitivity={setEditSensitivity} editSleepStart={editSleepStart} setEditSleepStart={setEditSleepStart}
        editSleepEnd={editSleepEnd} setEditSleepEnd={setEditSleepEnd} editSchedules={editSchedules} addSchedule={addSchedule}
        removeSchedule={removeSchedule} updateSchedule={updateSchedule} toggleDay={toggleDay} displayProfileImg={displayProfileImg}
        openFilePicker={openFilePicker} fileInputRef={fileInputRef} onPickImage={onPickImage}
      />
    </div>
  );  
};

const CompactInfoItem = ({ label, value, isTag }: any) => (
  <div style={{ marginBottom: '16px' }}>
    <div style={miniLabelStyle}>{label}</div>
    {isTag ? <span style={tagStyle}>{value || "-"}</span> : <div style={valueStyle}>{value || "-"}</div>}
  </div>
);

const HistoryLogItem = ({ item }: any) => {
  const dateText = new Date(item.created_at).toLocaleDateString();
  return (
    <div style={historyItemStyle}>
      <div style={historyHeadStyle}><span style={dateBadgeStyle}>{dateText}</span><span style={{ color: item.type === "call" ? "#3b82f6" : "#10b981", fontWeight: 700 }}>[{item.title}]</span></div>
      <div style={historyBodyStyle}>{item.description}</div>
    </div>
  );
};

// --- 스타일 정의 ---
const pageContainerStyle: React.CSSProperties = { 
  height: "100vh", width: "100vw", boxSizing: "border-box", padding: "24px", 
  backgroundColor: "#f4f9ff", display: "flex", flexDirection: "column", overflow: "hidden", 
  position: "fixed", top: 0, left: 0 
};

const compactHeaderStyle: React.CSSProperties = { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", flexShrink: 0 };

const dashboardGridStyle: React.CSSProperties = { 
  display: "grid", gap: "20px", flex: 1, height: "calc(100% - 60px)", 
  width: "100%", boxSizing: "border-box", overflow: "hidden" 
};

const sidePanelStyle: React.CSSProperties = { background: "#fff", borderRadius: "24px", padding: "32px", display: "flex", flexDirection: "column", boxShadow: "0 4px 20px rgba(0,0,0,0.03)", overflowY: "auto", minWidth: 0 };
const mainContentStyle: React.CSSProperties = { display: "flex", flexDirection: "column", minWidth: 0, height: "100%", overflow: "hidden" };
const chartCardStyle: React.CSSProperties = { background: "#fff", borderRadius: "24px", padding: "24px", flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" };
const chartContainerArea: React.CSSProperties = { flex: 1, minHeight: 0, width: "100%" }; 

const historyPanelStyle: React.CSSProperties = { background: "#fff", borderRadius: "24px", padding: "24px", display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 };
const historyListStyle: React.CSSProperties = { marginTop: "12px", overflowY: "auto", flex: 1 };

const avatarCircleStyle: React.CSSProperties = { width: "120px", height: "120px", borderRadius: "50%", overflow: "hidden", margin: "0 auto 24px", border: "4px solid #f0f7ff", flexShrink: 0 };
const avatarImgSmallStyle: React.CSSProperties = { width: "100%", height: "100%", objectFit: "cover" };
const infoStackStyle: React.CSSProperties = { borderTop: "1px solid #f1f5f9", paddingTop: "24px", flex: 1 };
const miniLabelStyle: React.CSSProperties = { fontSize: "11px", fontWeight: 700, color: "#94a3b8", marginBottom: "4px", textTransform: 'uppercase' };
const tagStyle: React.CSSProperties = { display: 'inline-block', padding: '4px 10px', borderRadius: '8px', backgroundColor: '#eff6ff', color: '#1e40af', fontSize: '12px', fontWeight: 600 };
const valueStyle: React.CSSProperties = { fontSize: "15px", fontWeight: 600, color: "#334155", whiteSpace: 'pre-line', lineHeight: 1.4 };
const memoBoxStyle: React.CSSProperties = { marginTop: "16px", padding: "16px", backgroundColor: "#f8fafc", borderRadius: "16px" };
const memoTextStyle: React.CSSProperties = { fontSize: "13px", color: "#64748b", lineHeight: 1.5 };
const cardHeaderStyle: React.CSSProperties = { fontSize: "16px", fontWeight: 800, color: "#1e293b" };
const historyItemStyle: React.CSSProperties = { marginBottom: "16px", paddingBottom: "16px", borderBottom: "1px solid #f1f5f9" };
const dateBadgeStyle: React.CSSProperties = { fontSize: '11px', color: '#94a3b8', marginRight: '8px' };
const historyHeadStyle: React.CSSProperties = { display: 'flex', alignItems: 'center', marginBottom: '4px', fontSize: '13px' };
const historyBodyStyle: React.CSSProperties = { fontSize: '13px', color: '#475569', lineHeight: 1.5 };

const statusBadgeStyle: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', padding: '5px 12px', backgroundColor: '#ecfdf5', color: '#059669', borderRadius: '20px', fontSize: '12px', fontWeight: 600 };
const pulseDotStyle: React.CSSProperties = { width: '6px', height: '6px', backgroundColor: '#10b981', borderRadius: '50%', marginRight: '8px' };
const btnPrimarySmall: React.CSSProperties = { padding: "10px 18px", borderRadius: "10px", border: "none", background: "#2563eb", color: "#fff", fontWeight: 700, fontSize: '13px', cursor: "pointer" };
const btnGhostSmall: React.CSSProperties = { padding: "10px 18px", borderRadius: "10px", border: "1px solid #e2e8f0", background: "#fff", color: "#64748b", fontWeight: 600, fontSize: '13px', cursor: "pointer" };

export default DetailProfile;