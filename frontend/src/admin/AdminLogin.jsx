import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAdminAuth } from "./AuthContext";

export default function AdminLogin() {
  const { login } = useAdminAuth();
  const navigate = useNavigate();
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await login(u.trim(), p);
      navigate("/donaspainel", { replace: true });
    } catch (e) {
      const d = e?.response?.data?.detail;
      setErr(typeof d === "string" ? d : "Não foi possível entrar.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="da-login-wrap">
      <form className="da-login-card" onSubmit={submit} data-testid="admin-login-form">
        <div className="da-login-logo">
          <div className="da-avatar">D</div>
          <div>
            <div className="da-login-title">Donas</div>
            <div className="da-login-sub">PAINEL ADMINISTRATIVO</div>
          </div>
        </div>

        <label className="da-label" htmlFor="adm-user">Usuário</label>
        <input
          id="adm-user"
          className="da-input"
          value={u}
          onChange={(e) => setU(e.target.value)}
          placeholder="usuário"
          data-testid="admin-login-username"
          autoComplete="username"
          required
        />

        <label className="da-label" htmlFor="adm-pass">Senha</label>
        <input
          id="adm-pass"
          className="da-input"
          type="password"
          value={p}
          onChange={(e) => setP(e.target.value)}
          placeholder="••••••••"
          data-testid="admin-login-password"
          autoComplete="current-password"
          required
        />

        {err && <div className="da-login-err" data-testid="admin-login-error">{err}</div>}

        <button className="da-login-btn" disabled={loading} data-testid="admin-login-submit">
          {loading ? "Entrando..." : "Entrar"}
        </button>

        <div className="da-login-foot">Acesso restrito • Donas</div>
      </form>
    </div>
  );
}
