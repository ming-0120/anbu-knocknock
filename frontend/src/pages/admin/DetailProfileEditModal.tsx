import React from "react";
declare global { interface Window { daum: any } }

type OutingSchedule = { id: string; memo: string; days: Record<"mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun", boolean>; part: "morning" | "afternoon"; startTime: string; endTime: string; };

type Props = {
  isOpen: boolean; onClose: () => void;
  editAddress: string; setEditAddress: (v: string) => void;
  editZipCode: string; setEditZipCode: (v:string)=>void;
  editAddressDetail: string; setEditAddressDetail: (v: string) => void;
  editNote: string; setEditNote: (v: string) => void;
  editSchedules: OutingSchedule[]; addSchedule: () => void; removeSchedule: (id: string) => void; updateSchedule: (id: string, patch: Partial<OutingSchedule>) => void; toggleDay: (id: string, day: any) => void;
  onSave: () => void; displayProfileImg: string; openFilePicker: () => void; fileInputRef: any; onPickImage: any;
  editSensitivity: number | null; setEditSensitivity: (v: number | null) => void;
  editSleepStart: string; setEditSleepStart: (v: string) => void; editSleepEnd: string; setEditSleepEnd: (v: string) => void;
};

const DEFAULT_PROFILE_IMG = "/images/default_profile.png";
const dayKeys = ["mon","tue","wed","thu","fri","sat","sun"] as const;
const dayLabels: Record<typeof dayKeys[number], string> = { mon: "월", tue: "화", wed: "수", thu: "목", fri: "금", sat: "토", sun: "일" };

export default function DetailProfileEditModal({    
  isOpen, onClose, editAddress, setEditAddress, editAddressDetail, setEditAddressDetail, editZipCode, setEditZipCode, editNote, setEditNote,
  editSchedules, addSchedule, removeSchedule, updateSchedule, toggleDay, onSave, displayProfileImg, openFilePicker, fileInputRef, onPickImage,
  editSensitivity, setEditSensitivity, editSleepStart, setEditSleepStart, editSleepEnd, setEditSleepEnd,
}: Props) {

  const openAddressSearch = () => {
    if (!window.daum || !window.daum.Postcode) { alert("주소 검색 스크립트가 로드되지 않았습니다."); return; }
    new window.daum.Postcode({
      oncomplete: function (data:any) {
        let addr = data.userSelectedType === "R" ? data.roadAddress : data.jibunAddress;
        setEditZipCode(data.zonecode);
        setEditAddress(addr);
        const detailInput = document.getElementById("detailAddressInput");
        if (detailInput) { (detailInput as HTMLInputElement).focus(); }
      }
    }).open();
  };

  if (!isOpen) return null;

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={modalStyle} onClick={(e) => e.stopPropagation()}>
        
        {/* Header */}
        <div style={modalHeaderStyle}>
          <div style={{ fontSize: "16px", fontWeight: 700, color: "#111827" }}>대상자 정보 수정</div>
          <button onClick={onClose} style={btnLink}>✕</button>
        </div>
        
        {/* Body */}
        <div style={modalBodyStyle}>                        
          <div style={{ display: "flex", gap: "20px", marginBottom: "20px" }}>
            
            <div style={modalPhotoWrap}>
              <img src={displayProfileImg} alt="profile-edit" style={profileEditImgStyle} onError={(e) => { const img = e.currentTarget; if (img.src.endsWith(DEFAULT_PROFILE_IMG)) return; img.src = DEFAULT_PROFILE_IMG; }} />
              <div style={{ marginTop: "12px", width: "100%", display: "flex", justifyContent: "center" }}>
                <button type="button" onClick={openFilePicker} style={btnSmallOutline}>사진 변경</button>
                <input ref={fileInputRef} type="file" accept="image/*" onChange={onPickImage} style={{ display: "none" }} />
              </div>
            </div>

            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "16px" }}>
              <div style={formRow}>
                <label style={labelStyle}>거주지 주소</label>
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  <div style={{ display: "flex", gap: "8px" }}>
                    <input value={editZipCode} readOnly style={{ ...inputStyle, width: "120px", backgroundColor: "#f9fafb" }} placeholder="우편번호" />
                    <button type="button" onClick={openAddressSearch} style={btnSmallOutline}>주소 검색</button>
                  </div>
                  <input value={editAddress} readOnly style={{ ...inputStyle, backgroundColor: "#f9fafb" }} placeholder="도로명 주소" />
                  <input id="detailAddressInput" value={editAddressDetail} onChange={(e)=>setEditAddressDetail(e.target.value)} style={inputStyle} placeholder="상세 주소 (동/호수 등)" />
                </div>
              </div>

              <div style={formRow}>
                <label style={labelStyle}>건강상태 및 특이사항 메모</label>
                <input value={editNote} onChange={(e) => setEditNote(e.target.value)} style={inputStyle} placeholder="담당자 참고용 특이사항을 입력하세요." />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px" }}>
                <div style={formRow}>
                  <label style={labelStyle}>센서 민감도</label>
                  <input
                    type="number"      // 숫자 전용 입력창으로 변경
                    step="0.1"        // 0.1 단위로 증감 허용
                    value={editSensitivity ?? ""}
                    onChange={(e) => {
                      const v = e.target.value;
                      // 빈 값일 경우 null 처리, 아닐 경우 실수(float)로 변환
                      setEditSensitivity(v === "" ? null : parseFloat(v));
                    }}
                    style={inputStyle}
                    placeholder="1.0"
                  />
                </div>
                <div style={formRow}>
                  <label style={labelStyle}>수면 시작 시간</label>
                  <input type="time" value={editSleepStart} onChange={(e) => setEditSleepStart(e.target.value)} style={inputStyle} />
                </div>
                <div style={formRow}>
                  <label style={labelStyle}>수면 종료 시간</label>
                  <input type="time" value={editSleepEnd} onChange={(e) => setEditSleepEnd(e.target.value)} style={inputStyle} />
                </div>
              </div>
            </div>
          </div>

          {/* 생활 패턴(스케줄) */}
          <div style={boxStyle}>
            <div style={boxHeaderStyle}>
              <div style={{ fontWeight: 600, color: "#111827", fontSize: "14px" }}>정기 외출 스케줄 관리</div>
              <button type="button" onClick={addSchedule} style={btnSmallPrimary}>+ 스케줄 추가</button>
            </div>

            {editSchedules.length === 0 ? (
              <div style={{ padding: "20px", fontSize: "13px", color: "#9ca3af", textAlign: "center" }}>등록된 정기 외출 스케줄이 없습니다.</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px", padding: "16px" }}>
                {editSchedules.map((s) => (
                  <div key={s.id} style={scheduleCardStyle}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", marginBottom: "12px" }}>
                      <input value={s.memo} onChange={(e) => updateSchedule(s.id, { memo: e.target.value })} style={{ ...inputStyle, flex: 1 }} placeholder="외출 목적 (예: 병원 방문, 노인정)" />
                      <button type="button" onClick={() => removeSchedule(s.id)} style={btnDangerSmall}>삭제</button>
                    </div>

                    <div style={{ display: "flex", flexWrap: "wrap", gap: "16px", alignItems: "center" }}>
                      <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                        <span style={miniLabel}>반복 요일</span>
                        <div style={{ display: "flex", gap: "6px" }}>
                          {dayKeys.map((d) => (
                            <label key={d} style={checkPillStyle(s.days[d])}>
                              <input type="checkbox" checked={s.days[d]} onChange={() => toggleDay(s.id, d)} style={{ display: "none" }} />
                              {dayLabels[d]}
                            </label>
                          ))}
                        </div>
                      </div>

                      <div style={{ width: "1px", height: "20px", backgroundColor: "#e5e7eb" }}></div>

                      <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                        <span style={miniLabel}>시간대</span>
                        <select value={s.part} onChange={(e) => updateSchedule(s.id, { part: e.target.value as any })} style={selectStyle}>
                          <option value="morning">오전</option>
                          <option value="afternoon">오후</option>
                        </select>
                      </div>

                      <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                        <span style={miniLabel}>외출 시간</span>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <input type="time" value={s.startTime} onChange={(e) => updateSchedule(s.id, { startTime: e.target.value })} style={timeStyle} />
                          <span style={{ color: "#9ca3af" }}>~</span>
                          <input type="time" value={s.endTime} onChange={(e) => updateSchedule(s.id, { endTime: e.target.value })} style={timeStyle} />
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        
        {/* Footer */}
        <div style={modalFooterStyle}>
          <button onClick={onClose} style={btnGhost}>취소</button>
          <button onClick={onSave} style={btnPrimary}>변경사항 저장</button>
        </div>
      </div>                       
    </div>
  );
}

/** =========================
 * 🎨 Modern SaaS 모달 스타일
 * ========================= */
const overlayStyle: React.CSSProperties = { position: "fixed", top: 0, left: 0, width: "100%", height: "100%", backgroundColor: "rgba(17, 24, 39, 0.5)", display: "flex", justifyContent: "center", alignItems: "center", zIndex: 2000, padding: "14px", backdropFilter: "blur(2px)" };
const modalStyle: React.CSSProperties = { backgroundColor: "#ffffff", width: "860px", maxWidth: "100%", maxHeight: "90vh", overflow: "hidden", borderRadius: "12px", boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)", display: "flex", flexDirection: "column" };

const modalHeaderStyle: React.CSSProperties = { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px 24px", background: "#ffffff", borderBottom: "1px solid #f3f4f6" };
const btnLink: React.CSSProperties = { border: "none", background: "transparent", cursor: "pointer", fontSize: "18px", color: "#9ca3af", padding: "4px" };

const modalBodyStyle: React.CSSProperties = { padding: "24px", maxHeight: "calc(90vh - 140px)", overflowY: "auto", backgroundColor: "#f9fafb" };
const modalPhotoWrap: React.CSSProperties = { width: "160px", minWidth: "160px", display: "flex", flexDirection: "column", alignItems: "center" };
const profileEditImgStyle: React.CSSProperties = { width: "140px", height: "140px", objectFit: "cover", borderRadius: "50%", border: "1px solid #e5e7eb", backgroundColor: "#ffffff" };

const formRow: React.CSSProperties = { display: "flex", flexDirection: "column", gap: "8px" };
const labelStyle: React.CSSProperties = { fontSize: "13px", fontWeight: 600, color: "#374151" };
const inputStyle: React.CSSProperties = { height: "40px", borderRadius: "8px", border: "1px solid #d1d5db", padding: "0 12px", outline: "none", fontSize: "14px", color: "#111827", transition: "border-color 0.2s", backgroundColor: "#ffffff" };
const selectStyle: React.CSSProperties = { height: "36px", borderRadius: "8px", border: "1px solid #d1d5db", padding: "0 10px", fontSize: "13px", backgroundColor: "#ffffff", color: "#111827", outline: "none" };
const timeStyle: React.CSSProperties = { height: "36px", borderRadius: "8px", border: "1px solid #d1d5db", padding: "0 10px", fontSize: "13px", backgroundColor: "#ffffff", color: "#111827", outline: "none" };

const boxStyle: React.CSSProperties = { border: "1px solid #e5e7eb", borderRadius: "10px", background: "#ffffff", overflow: "hidden" };
const boxHeaderStyle: React.CSSProperties = { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px 20px", borderBottom: "1px solid #e5e7eb", background: "#f9fafb" };
const scheduleCardStyle: React.CSSProperties = { border: "1px solid #e5e7eb", borderRadius: "8px", padding: "16px", background: "#ffffff", boxShadow: "0 1px 2px 0 rgba(0, 0, 0, 0.05)" };

const miniLabel: React.CSSProperties = { fontSize: "13px", fontWeight: 600, color: "#6b7280" };
const checkPillStyle = (active: boolean): React.CSSProperties => ({
  padding: "6px 12px", borderRadius: "6px", fontSize: "13px", fontWeight: 600, cursor: "pointer", userSelect: "none", transition: "all 0.2s",
  border: active ? "1px solid #bfdbfe" : "1px solid #d1d5db",
  background: active ? "#eff6ff" : "#ffffff",
  color: active ? "#2563eb" : "#4b5563",
});

const btnSmallOutline: React.CSSProperties = { padding: "8px 12px", borderRadius: "6px", border: "1px solid #d1d5db", background: "#ffffff", cursor: "pointer", fontWeight: 600, fontSize: "13px", color: "#374151" };
const btnSmallPrimary: React.CSSProperties = { padding: "6px 12px", borderRadius: "6px", border: "none", background: "#eff6ff", color: "#2563eb", cursor: "pointer", fontWeight: 600, fontSize: "13px" };
const btnDangerSmall: React.CSSProperties = { padding: "8px 12px", borderRadius: "6px", border: "1px solid #fecaca", background: "#fef2f2", cursor: "pointer", fontWeight: 600, fontSize: "13px", color: "#dc2626" };

const btnPrimary: React.CSSProperties = { flex: 1, padding: "12px", borderRadius: "8px", border: "none", background: "#2563eb", color: "#ffffff", fontWeight: 600, cursor: "pointer", fontSize: "14px" };
const btnGhost: React.CSSProperties = { flex: 1, padding: "12px", borderRadius: "8px", border: "1px solid #d1d5db", background: "#ffffff", color: "#374151", fontWeight: 600, cursor: "pointer", fontSize: "14px" };

const modalFooterStyle: React.CSSProperties = { display: "flex", justifyContent: "space-between", gap: "12px", padding: "16px 24px", borderTop: "1px solid #f3f4f6", background: "#ffffff" };