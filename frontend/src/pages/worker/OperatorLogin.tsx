import { useState } from "react";
import { useNavigate } from "react-router-dom";

const OperatorLogin = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const login = async () => {
    if (!email || !password) {
      alert("이메일과 비밀번호를 입력해주세요.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/operators/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      if (!res.ok) { alert("로그인 실패"); setLoading(false); return; }
      const data = await res.json();
      if (!data.access_token) { alert("토큰 없음"); setLoading(false); return; }
      
      localStorage.setItem("operator_token", data.access_token);
      navigate("/mobile", { replace: true });
    } catch (err) {
      console.error("login error", err);
      alert("로그인 오류");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={container}>
      <div style={loginBox}>
        <div style={logoArea}>
          <h2 style={logo}>안부 톡톡</h2>
          <p style={sub}>현장 요원 시스템</p>
        </div>

        <div style={form}>
          <input
            style={input}
            placeholder="이메일"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            style={input}
            type="password"
            placeholder="비밀번호"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") login();
            }}
          />
          <button style={button} onClick={login} disabled={loading}>
            {loading ? "로그인 중..." : "로그인"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default OperatorLogin;

// --- Styles ---
const container: React.CSSProperties = { height: "100vh", display: "flex", justifyContent: "center", alignItems: "center", background: "#f1f5f9", boxSizing: "border-box", fontFamily: "sans-serif" };
const loginBox: React.CSSProperties = { width: "100%", maxWidth: "360px", padding: "40px 24px", background: "#ffffff", borderRadius: "12px", border: "1px solid #e2e8f0", boxShadow: "0 4px 6px -1px rgba(0,0,0,0.05)", boxSizing: "border-box" };
const logoArea: React.CSSProperties = { textAlign: "center", marginBottom: "32px" };
const logo: React.CSSProperties = { margin: 0, fontSize: "22px", fontWeight: 700, color: "#1e293b" };
const sub: React.CSSProperties = { margin: "6px 0 0 0", fontSize: "14px", color: "#64748b" };
const form: React.CSSProperties = { display: "flex", flexDirection: "column", gap: "12px" };
const input: React.CSSProperties = { width: "100%", padding: "12px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "15px", outline: "none", boxSizing: "border-box" };
const button: React.CSSProperties = { width: "100%", marginTop: "8px", padding: "14px", borderRadius: "6px", border: "none", background: "#334155", color: "#ffffff", fontSize: "15px", fontWeight: 600, cursor: "pointer", boxSizing: "border-box" };