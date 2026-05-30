import React, { useEffect, useMemo, useState } from "react";
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Legend,
} from "recharts";
import {
  Eye, FileText, DollarSign, Copy, Download, Trash2, RotateCcw, MapPin, Activity,
  Smartphone, Monitor, X, Search, BookOpen, UserPlus, ClipboardList, CreditCard, LayoutDashboard,
} from "lucide-react";
import { dashboardApi } from "./api";

// ---- helpers ----
const fmtBRL = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(v || 0));
const fmtNum = (v) => new Intl.NumberFormat("pt-BR").format(Number(v || 0));

const FUNNEL_COLORS = {
  acessos: "#7c3aed",
  inscricoes: "#10b981",
  pix_gerado: "#f59e0b",
  pix_copiado: "#ec4899",
  pix_baixado: "#38bdf8",
};

const FUNNEL_ICONS = {
  acessos: Eye,
  inscricoes: FileText,
  pix_gerado: DollarSign,
  pix_copiado: Copy,
  pix_baixado: Download,
};

const RELATIVE = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const m = Math.floor(diffMs / 60000);
  if (m < 1) return "agora";
  if (m < 60) return `${m} min atrás`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} h atrás`;
  const dDays = Math.floor(h / 24);
  return `${dDays} d atrás`;
};

// ---- KPI Card ----
function KpiCard({ label, value, sub, icon: Icon, accent, testid, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="da-kpi"
      style={{ "--accent": accent }}
      data-testid={testid}
    >
      <div className="da-kpi-top">
        <span className="da-kpi-label">{label}</span>
        <span className="da-kpi-icon"><Icon size={18} /></span>
      </div>
      <div className="da-kpi-value">{value}</div>
      <div className="da-kpi-sub">{sub}</div>
      <div className="da-kpi-bar" />
    </button>
  );
}

// ---- Funnel step row (barra horizontal proporcional, estilo funil real) ----
function FunnelStep({ step, color, max, prevValue }) {
  const Icon = FUNNEL_ICONS[step.key] || Eye;
  const widthPct = max > 0 ? Math.max((step.value / max) * 100, 6) : 6;
  // Conversão desta etapa em relação à anterior
  const conv = prevValue > 0 ? Math.round((step.value / prevValue) * 1000) / 10 : null;
  const dropped = prevValue != null ? Math.max(prevValue - step.value, 0) : 0;
  const isTop = step.key === "acessos";
  return (
    <div className="fn-row" style={{ "--c": color }} data-testid={`funnel-step-${step.key}`}>
      <div className="fn-row-head">
        <div className="fn-row-icon"><Icon size={16} /></div>
        <div className="fn-row-label">{step.label}</div>
        <div className="fn-row-value">{fmtNum(step.value)}</div>
      </div>
      <div className="fn-bar-wrap">
        <div className="fn-bar" style={{ width: widthPct + "%" }} />
      </div>
      <div className="fn-row-meta">
        {isTop ? (
          <span className="fn-chip fn-chip-mute">Topo do funil</span>
        ) : (
          <span className={`fn-chip ${conv >= 50 ? "fn-chip-pos" : conv > 0 ? "fn-chip-neutral" : "fn-chip-neg"}`}>
            {conv != null ? `${conv}% conversão` : "—"}
          </span>
        )}
        {dropped > 0 && (
          <span className="fn-drop">{fmtNum(dropped)} {dropped === 1 ? "saiu" : "saíram"}</span>
        )}
      </div>
    </div>
  );
}

// ---- Realtime event ----
const EVT_ICON = {
  access: Eye,
  inscription_started: UserPlus,
  edital_access: BookOpen,
  inscription_form: ClipboardList,
  pay_screen: CreditCard,
  central_access: LayoutDashboard,
  registration: FileText,
  pix_generated: DollarSign,
  pix_copied: Copy,
  pix_downloaded: Download,
};
const EVT_COLOR = {
  access: "#7c3aed",
  inscription_started: "#06b6d4",   // ciano
  edital_access: "#a855f7",         // roxo lavanda
  inscription_form: "#0ea5e9",      // azul céu
  pay_screen: "#f97316",            // laranja
  central_access: "#64748b",        // cinza-azulado
  registration: "#10b981",          // verde
  pix_generated: "#f59e0b",         // amarelo/laranja
  pix_copied: "#ec4899",            // rosa
  pix_downloaded: "#38bdf8",        // azul claro
};

function EventRow({ ev }) {
  const Icon = EVT_ICON[ev.type] || Activity;
  // Adiciona ícone do dispositivo quando aplicável
  const Device = ev.device === "Mobile" ? Smartphone : Monitor;
  const hasDevice = ev.type === "access" && ev.device;
  return (
    <div className="da-event" data-testid={`event-${ev.id}`}>
      <div className="da-event-ic" style={{ background: (EVT_COLOR[ev.type] || "#7c3aed") + "22", color: EVT_COLOR[ev.type] || "#7c3aed" }}>
        <Icon size={16} />
      </div>
      <div className="da-event-body">
        <div className="da-event-title">
          {ev.title}
          {hasDevice && (
            <span className="da-event-device" title={ev.device}>
              <Device size={11} /> {ev.device}
            </span>
          )}
        </div>
        <div className="da-event-sub">{ev.subtitle}</div>
      </div>
      <div className="da-event-time">{RELATIVE(ev.created_at)}</div>
    </div>
  );
}

// ---- Access list modal ----
function AccessesModal({ open, onClose }) {
  const [data, setData] = useState({ items: [], total: 0 });
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    let active = true;
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const d = await dashboardApi.accessList(q);
        if (active) setData(d);
      } finally {
        if (active) setLoading(false);
      }
    }, 200);
    return () => { active = false; clearTimeout(t); };
  }, [q, open]);

  if (!open) return null;
  return (
    <div className="da-modal-overlay" onClick={onClose} data-testid="accesses-modal">
      <div className="da-modal" onClick={(e) => e.stopPropagation()}>
        <div className="da-modal-head">
          <div>
            <div className="da-modal-title">Acessos ao site</div>
            <div className="da-modal-sub">{fmtNum(data.total)} visitas registradas</div>
          </div>
          <button type="button" onClick={onClose} className="da-icon-btn" data-testid="close-accesses-modal">
            <X size={18} />
          </button>
        </div>

        <div className="da-modal-search">
          <Search size={16} />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar por IP, cidade, UF ou dispositivo…"
            data-testid="accesses-search-input"
          />
        </div>

        <div className="da-modal-table">
          <div className="da-modal-thead">
            <div>DATA / HORA</div>
            <div>IP</div>
            <div>LOCALIZAÇÃO</div>
            <div className="da-tr-right">DISPOSITIVO</div>
          </div>
          <div className="da-modal-tbody">
            {loading && <div className="da-empty">Carregando…</div>}
            {!loading && data.items.length === 0 && <div className="da-empty">Nenhum acesso encontrado.</div>}
            {!loading && data.items.map((a) => (
              <div className="da-modal-row" key={a.id || (a.ip + a.created_at)}>
                <div>{new Date(a.created_at).toLocaleString("pt-BR")}</div>
                <div className="da-ip">{a.ip}</div>
                <div>{a.city}{a.region && a.region !== "—" ? "/" + a.region : ""}</div>
                <div className="da-tr-right">
                  <span className={`da-pill ${a.device === "Mobile" ? "is-mobile" : "is-desktop"}`}>
                    {a.device === "Mobile" ? <Smartphone size={12} /> : <Monitor size={12} />}
                    {a.device?.toUpperCase()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---- Main Dashboard ----
export default function AdminDashboard() {
  const [kpis, setKpis] = useState(null);
  const [funnel, setFunnel] = useState(null);
  const [locs, setLocs] = useState({ items: [] });
  const [act, setAct] = useState({ labels: [], acessos: [], inscricoes: [] });
  const [events, setEvents] = useState({ items: [] });
  const [accessesOpen, setAccessesOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const loadAll = async () => {
    setRefreshing(true);
    try {
      const [k, f, l, a, e] = await Promise.all([
        dashboardApi.kpis(),
        dashboardApi.funnel(),
        dashboardApi.locations(),
        dashboardApi.activity7(),
        dashboardApi.realtime(),
      ]);
      setKpis(k); setFunnel(f); setLocs(l); setAct(a); setEvents(e);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadAll();
    const iv = setInterval(loadAll, 60000); // refresh AO VIVO a cada 60s
    return () => clearInterval(iv);
  }, []);

  const onReset = async () => {
    if (!window.confirm("Tem certeza que deseja ZERAR todos os KPIs? Esta ação não pode ser desfeita.")) return;
    await dashboardApi.resetKpis();
    await loadAll();
  };

  const pieData = useMemo(() => {
    if (!funnel) return [];
    return funnel.steps.map((s) => ({
      name: s.label, value: s.value, key: s.key, color: FUNNEL_COLORS[s.key] || "#7c3aed",
    }));
  }, [funnel]);

  const lineData = useMemo(() => {
    return act.labels.map((lab, i) => ({
      day: lab, Acessos: act.acessos[i] || 0, Inscrições: act.inscricoes[i] || 0,
    }));
  }, [act]);

  const maxLoc = Math.max(1, ...locs.items.map((l) => l.count));

  if (!kpis || !funnel) {
    return <div className="da-fullload">Carregando dashboard…</div>;
  }

  return (
    <div className="da-page" data-testid="admin-dashboard">
      <header className="da-page-head">
        <div>
          <h1 className="da-page-title">Dashboard</h1>
          <p className="da-page-sub">Visão geral em tempo real do site Donas.</p>
        </div>
        <div className="da-page-actions">
          <button type="button" onClick={onReset} className="da-btn da-btn-danger" data-testid="btn-reset-kpis">
            <Trash2 size={14} /> Zerar KPIs
          </button>
          <button type="button" onClick={loadAll} className="da-btn da-btn-ghost" data-testid="btn-refresh">
            <RotateCcw size={14} className={refreshing ? "da-spin" : ""} /> Atualizar
          </button>
        </div>
      </header>

      {/* KPIs */}
      <section className="da-kpi-grid">
        <KpiCard
          label="ACESSOS" icon={Eye} accent="#7c3aed"
          value={fmtNum(kpis.acessos)} sub="Usuários únicos  →"
          onClick={() => setAccessesOpen(true)} testid="kpi-acessos"
        />
        <KpiCard
          label="TOTAL DE INSCRIÇÕES" icon={FileText} accent="#3b82f6"
          value={fmtNum(kpis.total_inscricoes)} sub="Candidatos cadastrados"
          testid="kpi-inscricoes"
        />
        <KpiCard
          label="VALOR TOTAL GERADO" icon={DollarSign} accent="#10b981"
          value={fmtBRL(kpis.valor_total_gerado)} sub={`${kpis.pix_gerados_count} PIX gerado(s)`}
          testid="kpi-valor-gerado"
        />
        <KpiCard
          label="PIX COPIADOS" icon={Copy} accent="#f59e0b"
          value={fmtBRL(kpis.valor_pix_copiados)} sub={`${kpis.pix_copiados_count} pix copiados`}
          testid="kpi-pix-copiados"
        />
        <KpiCard
          label="PIX BAIXADOS" icon={Download} accent="#ec4899"
          value={fmtBRL(kpis.valor_pix_baixados)} sub={`${kpis.pix_baixados_count} comprovantes baixados`}
          testid="kpi-pix-baixados"
        />
      </section>

      {/* Funnel + Locations */}
      <section className="da-grid-2">
        <div className="da-card fn-card" data-testid="funnel-card">
          <div className="da-card-head">
            <div>
              <h2 className="da-card-title">Funil de conversão</h2>
              <p className="da-card-sub">Da visita ao pagamento — acompanhe onde cada candidato parou.</p>
            </div>
          </div>

          <div className="fn-steps">
            {funnel.steps.slice(0, 5).map((s, i, arr) => (
              <FunnelStep
                key={s.key}
                step={s}
                color={FUNNEL_COLORS[s.key]}
                max={arr[0].value || 1}
                prevValue={i === 0 ? null : arr[i - 1].value}
              />
            ))}
          </div>

          <div className="fn-rates" data-testid="funnel-rates">
            <div className="fn-rate">
              <div className="fn-rate-val">{funnel.rates.insc_to_pix}<span>%</span></div>
              <div className="fn-rate-lbl">Inscrição → PIX gerado</div>
            </div>
            <div className="fn-rate">
              <div className="fn-rate-val">{funnel.rates.pix_to_baixados}<span>%</span></div>
              <div className="fn-rate-lbl">PIX gerado → baixado</div>
            </div>
            <div className="fn-rate fn-rate-hero">
              <div className="fn-rate-val">{funnel.rates.geral}<span>%</span></div>
              <div className="fn-rate-lbl">Conversão geral</div>
            </div>
          </div>
        </div>

        <div className="da-card" data-testid="locations-card">
          <div className="da-card-head">
            <div>
              <h2 className="da-card-title">Top localizações</h2>
              <p className="da-card-sub">De onde vêm os visitantes</p>
            </div>
          </div>
          <div className="da-locs">
            {locs.items.length === 0 && <div className="da-empty">Sem dados ainda.</div>}
            {locs.items.map((l, i) => (
              <div className="da-loc-row" key={i} data-testid={`loc-${i}`}>
                <MapPin size={14} className="da-loc-pin" />
                <div className="da-loc-name">
                  <div className="da-loc-city">{l.city}</div>
                  <div className="da-loc-region">{l.region}</div>
                </div>
                <div className="da-loc-bar">
                  <div className="da-loc-fill" style={{ width: (l.count / maxLoc) * 100 + "%" }} />
                </div>
                <div className="da-loc-count">{l.count}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 7d chart + Realtime */}
      <section className="da-grid-2">
        <div className="da-card" data-testid="activity-card">
          <div className="da-card-head">
            <div>
              <h2 className="da-card-title">Atividade dos últimos 7 dias</h2>
              <p className="da-card-sub">Acessos × Inscrições por dia</p>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={lineData} margin={{ left: -20, right: 10, top: 10, bottom: 0 }}>
              <defs>
                <linearGradient id="ac" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="#7c3aed" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#7c3aed" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="in" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#eee5fb" vertical={false} />
              <XAxis dataKey="day" stroke="#7a6c95" tick={{ fontSize: 11 }} />
              <YAxis stroke="#7a6c95" tick={{ fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: "#1a1330", border: "1px solid #3a2e5c", borderRadius: 8, color: "#fff" }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area type="monotone" dataKey="Acessos" stroke="#7c3aed" fill="url(#ac)" strokeWidth={2} />
              <Area type="monotone" dataKey="Inscrições" stroke="#10b981" fill="url(#in)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="da-card" data-testid="realtime-card">
          <div className="da-card-head">
            <div>
              <h2 className="da-card-title">Atividade em tempo real</h2>
              <p className="da-card-sub">Últimos eventos no portal</p>
            </div>
            <span className="da-live"><span className="da-live-dot" /> AO VIVO</span>
          </div>
          <div className="da-events">
            {events.items.length === 0 && <div className="da-empty">Nenhum evento ainda.</div>}
            {events.items.map((ev) => <EventRow key={ev.id} ev={ev} />)}
          </div>
        </div>
      </section>

      <AccessesModal open={accessesOpen} onClose={() => setAccessesOpen(false)} />
    </div>
  );
}
