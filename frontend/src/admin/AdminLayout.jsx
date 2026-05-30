import React, { useState } from "react";
import { NavLink, Outlet, useNavigate, Navigate } from "react-router-dom";
import {
  LayoutDashboard, FileText, Users, Settings, ChevronLeft, ChevronRight, LogOut,
} from "lucide-react";
import { useAdminAuth } from "./AuthContext";

const NAV = [
  { to: "/donaspainel", end: true, label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
  { to: "/donaspainel/inscricoes", label: "Inscrições", icon: FileText, testid: "nav-inscricoes" },
  { to: "/donaspainel/usuarios", label: "Usuários", icon: Users, testid: "nav-usuarios" },
  { to: "/donaspainel/configuracoes", label: "Configurações", icon: Settings, testid: "nav-config" },
];

export default function AdminLayout() {
  const { user, logout } = useAdminAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);

  if (user === undefined) {
    return <div className="da-fullload">Carregando…</div>;
  }
  if (user === null) {
    return <Navigate to="/donaspainel/login" replace />;
  }

  const doLogout = async () => {
    await logout();
    navigate("/donaspainel/login", { replace: true });
  };

  return (
    <div className={`da-shell ${collapsed ? "is-collapsed" : ""}`}>
      <aside className="da-side" data-testid="admin-sidebar">
        <div className="da-side-head">
          <div className="da-avatar">D</div>
          {!collapsed && (
            <div className="da-side-brand">
              <div className="da-side-name">Donas</div>
              <div className="da-side-tag">PAINEL</div>
            </div>
          )}
          <button
            type="button"
            className="da-collapse-btn"
            onClick={() => setCollapsed((c) => !c)}
            aria-label="Recolher menu"
            data-testid="sidebar-collapse-btn"
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>

        <nav className="da-nav">
          {NAV.map((it) => {
            const Icon = it.icon;
            return (
              <NavLink
                key={it.to}
                to={it.to}
                end={it.end}
                className={({ isActive }) => "da-nav-item" + (isActive ? " is-active" : "")}
                data-testid={it.testid}
              >
                <Icon size={18} />
                {!collapsed && <span>{it.label}</span>}
              </NavLink>
            );
          })}
        </nav>

        <div className="da-side-foot">
          {!collapsed && (
            <div className="da-userbox" data-testid="admin-user-box">
              <div className="da-avatar da-avatar-sm">D</div>
              <div>
                <div className="da-user-name">{user.display_name || user.username}</div>
                <div className="da-user-role">Administrador</div>
              </div>
            </div>
          )}
          <button
            type="button"
            onClick={doLogout}
            className="da-logout-btn"
            data-testid="admin-logout-btn"
          >
            <LogOut size={16} />
            {!collapsed && <span>Sair</span>}
          </button>
        </div>
      </aside>

      <main className="da-main">
        <Outlet />
      </main>
    </div>
  );
}
