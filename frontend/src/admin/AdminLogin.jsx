import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAdminAuth } from "./AuthContext";

export default function AdminLogin() {
  const { login } = useAdminAuth();
  const navigate = useNavigate();
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [showPass, setShowPass] = useState(false);
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
    <div className="da-login-wrap" data-testid="admin-login-page">
      {/* COLUNA ESQUERDA — imagem Donatelo */}
      <aside className="da-login-hero" aria-hidden="true">
        <div
          className="da-login-hero__img"
          style={{ backgroundImage: `url(${process.env.PUBLIC_URL || ""}/assets/donatelo.jpg)` }}
        />
        <div className="da-login-hero__overlay" />
        <div className="da-login-hero__bottom">
          <span className="da-login-pill" data-testid="admin-login-pill">
            <span className="da-login-pill__dot" />
            ACESSO RESTRITO
          </span>
          <p className="da-login-quote">
            <em>
              O conhecimento é como uma escada: quanto mais alto você sobe,<br />
              mais <span className="da-login-quote__hl">ampla é sua visão</span>.
            </em>
          </p>
        </div>
      </aside>

      {/* COLUNA DIREITA — formulário */}
      <main className="da-login-side">
        <form
          className="da-login-card"
          onSubmit={submit}
          data-testid="admin-login-form"
          autoComplete="on"
        >
          <div className="da-login-logo">
            <div className="da-avatar" aria-hidden="true">D</div>
            <div>
              <div className="da-login-brand">Donas</div>
              <div className="da-login-sub">PAINEL ADMINISTRATIVO</div>
            </div>
          </div>

          <div className="da-login-head">
            <h1 className="da-login-title">Acessar painel</h1>
            <p className="da-login-desc">Digite suas credenciais para continuar.</p>
          </div>

          <label className="da-label" htmlFor="adm-user">USUÁRIO</label>
          <input
            id="adm-user"
            className="da-input"
            value={u}
            onChange={(e) => setU(e.target.value)}
            placeholder=""
            data-testid="admin-login-username"
            autoComplete="username"
            required
          />

          <label className="da-label" htmlFor="adm-pass">SENHA</label>
          <div className="da-input-wrap">
            <input
              id="adm-pass"
              className="da-input"
              type={showPass ? "text" : "password"}
              value={p}
              onChange={(e) => setP(e.target.value)}
              placeholder=""
              data-testid="admin-login-password"
              autoComplete="current-password"
              required
            />
            <button
              type="button"
              className="da-input-eye"
              onClick={() => setShowPass((s) => !s)}
              aria-label={showPass ? "Ocultar senha" : "Mostrar senha"}
              data-testid="admin-login-toggle-password"
              tabIndex={-1}
            >
              {showPass ? (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20C5 20 1 12 1 12a21.77 21.77 0 0 1 5.06-5.94" />
                  <path d="M9.9 4.24A10.94 10.94 0 0 1 12 4c7 0 11 8 11 8a21.83 21.83 0 0 1-3.17 4.19" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              ) : (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              )}
            </button>
          </div>

          {err && (
            <div className="da-login-err" data-testid="admin-login-error">
              {err}
            </div>
          )}

          <button
            className="da-login-btn"
            disabled={loading}
            data-testid="admin-login-submit"
          >
            <span>{loading ? "Entrando..." : "Entrar"}</span>
            {!loading && <span className="da-login-btn__arrow">→</span>}
          </button>

          <div className="da-login-foot">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <span>Conexão segura · Apenas administradores autorizados.</span>
          </div>
        </form>
      </main>
    </div>
  );
}
