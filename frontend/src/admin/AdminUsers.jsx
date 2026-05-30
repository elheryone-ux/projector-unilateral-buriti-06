import React, { useEffect, useState, useCallback } from "react";
import { Users, Plus, Trash2, X, Eye, EyeOff } from "lucide-react";
import { usersApi } from "./api";

const fmtDate = (iso) => {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }); }
  catch { return iso; }
};

function Avatar({ name }) {
  const letter = (name || "?").charAt(0).toUpperCase();
  // gradiente fixo por letra (consistente)
  const palette = [
    ["#7c3aed", "#ec4899"], ["#10b981", "#3b82f6"], ["#f59e0b", "#ef4444"],
    ["#0ea5e9", "#6366f1"], ["#f97316", "#a855f7"], ["#14b8a6", "#84cc16"],
  ];
  const idx = letter.charCodeAt(0) % palette.length;
  const [c1, c2] = palette[idx];
  return (
    <div className="usr-avatar" style={{ background: `linear-gradient(135deg, ${c1} 0%, ${c2} 100%)` }}>
      {letter}
    </div>
  );
}

function RoleBadge({ role }) {
  const isRoot = role === "root";
  return (
    <span className={`usr-badge ${isRoot ? "is-root" : "is-admin"}`} data-testid={`role-${role}`}>
      {isRoot ? "ROOT" : "ADMIN"}
    </span>
  );
}

function CreateModal({ onClose, onCreated }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [role, setRole] = useState("admin");
  const [showPwd, setShowPwd] = useState(false);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    if (!username.trim() || !password) { setErr("Preencha usuário e senha."); return; }
    if (password.length < 4) { setErr("Senha deve ter ao menos 4 caracteres."); return; }
    if (password !== confirm) { setErr("As senhas não coincidem."); return; }
    setLoading(true);
    try {
      await usersApi.create({ username: username.trim(), password, role });
      onCreated();
    } catch (e2) {
      setErr(e2?.response?.data?.detail || "Erro ao criar administrador.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="da-modal-overlay" onClick={onClose} data-testid="create-admin-modal">
      <div className="da-modal usr-modal" onClick={(e) => e.stopPropagation()}>
        <div className="da-modal-head">
          <div className="da-modal-title">Novo administrador</div>
          <button type="button" onClick={onClose} className="da-icon-btn" data-testid="close-create-modal">
            <X size={18} />
          </button>
        </div>
        <form onSubmit={submit} className="usr-form">
          <label>
            <span>Nome de usuário</span>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value.toLowerCase().replace(/[^a-z0-9._-]/g, ""))}
              placeholder="ex: maria.silva"
              autoFocus
              data-testid="input-new-username"
            />
            <small>Apenas letras minúsculas, números, ponto, hífen e underline.</small>
          </label>

          <label>
            <span>Senha</span>
            <div className="usr-input-wrap">
              <input
                type={showPwd ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="ao menos 4 caracteres"
                data-testid="input-new-password"
              />
              <button type="button" onClick={() => setShowPwd((v) => !v)} className="usr-eye" aria-label="Mostrar senha">
                {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </label>

          <label>
            <span>Confirmar senha</span>
            <input
              type={showPwd ? "text" : "password"}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="repita a senha"
              data-testid="input-confirm-password"
            />
          </label>

          <label>
            <span>Papel (permissão)</span>
            <select value={role} onChange={(e) => setRole(e.target.value)} data-testid="select-role">
              <option value="admin">Admin — gerencia inscrições</option>
              <option value="root">Root — acesso total (pode gerenciar admins)</option>
            </select>
          </label>

          {err && <div className="usr-err" data-testid="form-error">{err}</div>}

          <div className="usr-actions">
            <button type="button" className="da-btn da-btn-ghost" onClick={onClose}>Cancelar</button>
            <button type="submit" className="da-btn da-btn-primary" disabled={loading} data-testid="submit-new-admin">
              {loading ? "Criando…" : "Criar administrador"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function AdminUsers() {
  const [data, setData] = useState({ items: [], total: 0, current: "" });
  const [loading, setLoading] = useState(true);
  const [openModal, setOpenModal] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setData(await usersApi.list()); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async (u) => {
    if (u.username === data.current) {
      alert("Você não pode excluir o usuário com o qual está logado.");
      return;
    }
    if (!window.confirm(`Excluir o administrador "${u.username}"? Esta ação não pode ser desfeita.`)) return;
    try {
      await usersApi.remove(u.username);
      await load();
    } catch (e) {
      alert(e?.response?.data?.detail || "Erro ao excluir.");
    }
  };

  return (
    <div className="da-page" data-testid="admin-users">
      <header className="da-page-head">
        <div>
          <h1 className="da-page-title">Usuários</h1>
          <p className="da-page-sub">Administradores com acesso ao painel.</p>
        </div>
      </header>

      {/* KPI */}
      <div className="da-card usr-kpi" data-testid="usr-kpi-total">
        <div className="usr-kpi-head">
          <span className="usr-kpi-label">ADMINISTRADORES</span>
          <span className="usr-kpi-ic"><Users size={18} /></span>
        </div>
        <div className="usr-kpi-value">{loading ? "…" : data.total}</div>
        <div className="usr-kpi-sub">com acesso ao painel</div>
        <div className="usr-kpi-bar" />
      </div>

      {/* Lista */}
      <div className="da-card usr-list">
        <div className="usr-list-head">
          <h2 className="da-card-title" style={{ margin: 0 }}>Lista de administradores</h2>
          <button
            type="button"
            className="da-btn da-btn-primary"
            onClick={() => setOpenModal(true)}
            data-testid="btn-new-admin"
          >
            <Plus size={14} /> Novo administrador
          </button>
        </div>

        <div className="usr-thead">
          <div>USUÁRIO</div>
          <div>PAPEL</div>
          <div>CRIADO EM</div>
          <div style={{ textAlign: "right" }}>AÇÕES</div>
        </div>
        <div className="usr-tbody">
          {loading && <div className="da-empty">Carregando…</div>}
          {!loading && data.items.length === 0 && (
            <div className="da-empty">Nenhum administrador cadastrado.</div>
          )}
          {!loading && data.items.map((u) => (
            <div className="usr-row" key={u.username} data-testid={`usr-row-${u.username}`}>
              <div className="usr-cell-user">
                <Avatar name={u.username} />
                <span className="usr-name">{u.username}</span>
                {u.username === data.current && (
                  <span className="usr-you-tag">você</span>
                )}
              </div>
              <div><RoleBadge role={u.role} /></div>
              <div className="usr-date">{fmtDate(u.created_at)}</div>
              <div style={{ textAlign: "right" }}>
                <button
                  type="button"
                  className="ds-btn-trash"
                  onClick={() => handleDelete(u)}
                  disabled={u.username === data.current}
                  data-testid={`btn-delete-${u.username}`}
                  title={u.username === data.current ? "Não é possível excluir você mesmo" : "Excluir"}
                  aria-label="Excluir"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {openModal && (
        <CreateModal
          onClose={() => setOpenModal(false)}
          onCreated={() => { setOpenModal(false); load(); }}
        />
      )}
    </div>
  );
}
