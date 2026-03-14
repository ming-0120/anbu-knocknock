export const overlayStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  backgroundColor: "rgba(15, 23, 42, 0.55)",
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  zIndex: 1100,
  padding: 16,
};

export const modalStyle: React.CSSProperties = {
  width: 560,
  maxWidth: "100%",
  background: "#fff",
  borderRadius: 16,
  border: "1px solid #e5e7eb",
  boxShadow: "0 18px 60px rgba(0,0,0,0.22)",
  overflow: "hidden",
};

export const headerStyle: React.CSSProperties = {
  padding: "14px 16px",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  background: "#ffffff",
  borderBottom: "1px solid #eef2f7",
};

export const avatarStyle: React.CSSProperties = {
  width: 44,
  height: 44,
  borderRadius: 14,
  background: "#f3f4f6",
  border: "1px solid #e5e7eb",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontWeight: 800,
  color: "#111827",
};

export const titleStyle: React.CSSProperties = {
  fontSize: 16,
  fontWeight: 900,
  color: "#111827",
};

export const subtleText: React.CSSProperties = {
  fontSize: 12.5,
  color: "#6b7280",
};

export const iconBtnStyle: React.CSSProperties = {
  border: "1px solid #e5e7eb",
  background: "#fff",
  width: 34,
  height: 34,
  borderRadius: 10,
  cursor: "pointer",
  color: "#111827",
  lineHeight: "32px",
  fontWeight: 800,
};

export const bodyStyle: React.CSSProperties = {
  padding: 16,
};

export const sectionStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 8,
};

export const sectionTitleStyle: React.CSSProperties = {
  fontSize: 12.5,
  fontWeight: 900,
  color: "#111827",
};

export const sectionContentStyle: React.CSSProperties = {
  fontSize: 13.5,
  color: "#111827",
  lineHeight: 1.55,
  background: "#f9fafb",
  border: "1px solid #eef2f7",
  borderRadius: 12,
  padding: "10px 12px",
  whiteSpace: "pre-wrap",
};

export const dividerStyle: React.CSSProperties = {
  height: 1,
  background: "#eef2f7",
  margin: "14px 0",
};

export const contactGridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  gap: 10,
};

export const contactCardStyle: React.CSSProperties = {
  border: "1px solid #eef2f7",
  background: "#fff",
  borderRadius: 12,
  padding: 12,
};

export const contactLabelStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 800,
  color: "#6b7280",
};

export const contactValueStyle: React.CSSProperties = {
  marginTop: 6,
  fontSize: 14,
  fontWeight: 900,
  color: "#111827",
};

export const btnPrimary: React.CSSProperties = {
  padding: "10px 14px",
  borderRadius: 12,
  border: "1px solid #111827",
  background: "#111827",
  color: "#fff",
  fontWeight: 900,
  cursor: "pointer",
};

export const btnGhost: React.CSSProperties = {
  padding: "10px 14px",
  borderRadius: 12,
  border: "1px solid #e5e7eb",
  background: "#fff",
  color: "#111827",
  fontWeight: 800,
  cursor: "pointer",
};

export const pillBase: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  padding: "4px 10px",
  borderRadius: 999,
  fontSize: 12,
  fontWeight: 900,
};

export const pillLow = {
  background: "#ecfdf5",
  color: "#065f46",
};

export const pillWarn = {
  background: "#fffbeb",
  color: "#92400e",
};

export const pillHigh = {
  background: "#fef2f2",
  color: "#991b1b",
};

export const pillNeutral = {
  background: "#f3f4f6",
  color: "#111827",
};
export const hintText = { fontSize: 12, color: "#6b7280", };

export const chartContainer: React.CSSProperties = {
  width: "100%",
  height: 160,
  border: "1px solid #eef2f7",
  borderRadius: 12,
  padding: 10,
  background: "#ffffff",
};