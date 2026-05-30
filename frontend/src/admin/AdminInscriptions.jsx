import React, { useEffect, useMemo, useState, useCallback } from "react";
import {
  Eye, FileText, DollarSign, Copy, Download, Trash2, RotateCcw, X, Search,
  Smartphone, Monitor, ClipboardList, User2, GraduationCap, Accessibility,
  Wallet, ChevronDown,
} from "lucide-react";
import { inscriptionsApi, dashboardApi } from "./api";

const fmtBRL = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(v || 0));
const fmtNum = (v) => new Intl.NumberFormat("pt-BR").format(Number(v || 0));
const fmtDate = (iso) => {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }); }
  catch { return iso; }
};

const STATUS_OPTIONS = [
  { value: "all", label: "Todos os status" },
  { value: "Aguardando pagamento", label: "Aguardando pagamento" },
  { value: "PIX gerado", label: "PIX gerado" },
  { value: "PIX copiado", label: "PIX copiado" },
  { value: "PIX baixado", label: "PIX baixado" },
];

const STATUS_CLASS = {
  "Aguardando pagamento": "ds-aguardando",
  "PIX gerado": "ds-gerado",
  "PIX copiado": "ds-copiado",
  "PIX baixado": "ds-baixado",
};

function KpiCard({ label, value, sub, icon: Icon, accent, testid }) {
  return (
    <div className="da-kpi" style={{ "--accent": accent, cursor: "default" }} data-testid={testid}>
      <div className="da-kpi-top">
        <span className="da-kpi-label">{label}</span>
        <span className="da-kpi-icon"><Icon size={18} /></span>
      </div>
      <div className="da-kpi-value">{value}</div>
      <div className="da-kpi-sub">{sub}</div>
      <div className="da-kpi-bar" />
    </div>
  );
}

function StatusBadge({ status }) {
  const cls = STATUS_CLASS[status] || "ds-aguardando";
  return <span className={`ds-status ${cls}`} data-testid={`status-${(status || "").replace(/\s+/g, "-").toLowerCase()}`}>{status || "—"}</span>;
}

function DetailRow({ label, value, mono = false }) {
  return (
    <div className="ds-detail-row">
      <div className="ds-detail-label">{label}</div>
      <div className={"ds-detail-value" + (mono ? " ds-mono" : "")}>{value || "—"}</div>
    </div>
  );
}

function DetailSection({ title, icon: Icon, color, children }) {
  return (
    <div className="ds-section">
      <div className="ds-section-head" style={{ color }}>
        <Icon size={16} />
        <span>{title}</span>
      </div>
      <div className="ds-section-grid">{children}</div>
    </div>
  );
}

function DetailsModal({ id, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    inscriptionsApi
      .get(id)
      .then((d) => { if (active) setData(d); })
      .catch(() => { if (active) setData(null); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id]);

  return (
    <div className="da-modal-overlay" onClick={onClose} data-testid="inscription-details-modal">
      <div className="da-modal ds-modal" onClick={(e) => e.stopPropagation()}>
        <div className="da-modal-head">
          <div className="da-modal-title">Detalhes do candidato</div>
          <button type="button" onClick={onClose} className="da-icon-btn" data-testid="close-details-modal">
            <X size={18} />
          </button>
        </div>

        <div className="ds-modal-body">
          {loading && <div className="da-empty">Carregando…</div>}
          {!loading && !data && <div className="da-empty">Inscrição não encontrada.</div>}
          {!loading && data && (
            <>
              <DetailSection title="DADOS DA INSCRIÇÃO" icon={ClipboardList} color="#2563eb">
                <DetailRow label="Número de inscrição" value={data.inscription_number} mono />
                <DetailRow label="Status" value={<StatusBadge status={data.status} />} />
                <DetailRow label="Valor da taxa" value={fmtBRL(data.amount)} />
                <DetailRow label="Dispositivo" value={data.device} />
                <DetailRow label="Data da inscrição" value={fmtDate(data.created_at)} />
                <DetailRow label="IP" value={data.ip} mono />
                <DetailRow label="Cidade/UF (Geo IP)" value={`${data.city || "—"}${data.region ? "/" + data.region : ""}`} />
              </DetailSection>

              <DetailSection title="IDENTIFICAÇÃO" icon={User2} color="#5b21b6">
                <DetailRow label="Nome completo" value={data.name} />
                <DetailRow label="CPF" value={data.cpf_fmt || data.cpf} mono />
                <DetailRow label="Data de nascimento" value={data.birth_date} />
                <DetailRow label="Sexo" value={data.sex} />
                <DetailRow label="Estado civil" value={data.marital_status} />
                <DetailRow label="Cor/Raça" value={data.race} />
                <DetailRow label="E-mail" value={data.email} />
                <DetailRow label="Telefone" value={data.phone} />
                <DetailRow label="Língua estrangeira" value={data.foreign_language} />
                <DetailRow label="UF de prova" value={data.exam_state} />
                <DetailRow label="Município de prova" value={data.exam_city} />
              </DetailSection>

              <DetailSection title="ATENDIMENTO ESPECIALIZADO" icon={Accessibility} color="#0ea5e9">
                <DetailRow label="Precisa de atendimento?" value={data.needs_assistance} />
                {data.assistance_details && (
                  <DetailRow label="Detalhes" value={data.assistance_details} />
                )}
              </DetailSection>

              <DetailSection title="ENSINO MÉDIO" icon={GraduationCap} color="#16a34a">
                <DetailRow label="Situação" value={data.hs_situation} />
                <DetailRow label="Tipo de escola" value={data.school_type} />
              </DetailSection>

              <DetailSection title="PAGAMENTO PIX" icon={Wallet} color="#f59e0b">
                <DetailRow label="Status atual" value={<span className="ds-pix-state">{data.status}</span>} />
                <DetailRow label="PIX gerado" value={<span className={data.pix_generated ? "ds-yes" : "ds-no"}>{data.pix_generated ? "Sim" : "Não"}</span>} />
                <DetailRow label="PIX copiado" value={<span className={data.pix_copied ? "ds-yes" : "ds-no"}>{data.pix_copied ? "Sim" : "Não"}</span>} />
                <DetailRow label="Comprovante baixado" value={<span className={data.pix_downloaded ? "ds-yes" : "ds-no"}>{data.pix_downloaded ? "Sim" : "Não"}</span>} />
                <DetailRow label="Recebedor (snapshot)" value={data.pix_recipient} />
                <DetailRow label="QR Code gerado na chave" value={<code className="ds-pix-key">{data.pix_key || "—"}</code>} />
              </DetailSection>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function AdminInscriptions() {
  const [kpis, setKpis] = useState(null);
  const [list, setList] = useState({ items: [], total: 0 });
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("all");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [detailsId, setDetailsId] = useState(null);

  const loadKpis = useCallback(async () => {
    try {
      const k = await dashboardApi.kpis();
      setKpis(k);
    } catch {}
  }, []);

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const d = await inscriptionsApi.list({ q, status, limit: 200 });
      setList(d);
    } finally {
      setLoading(false);
    }
  }, [q, status]);

  useEffect(() => { loadKpis(); }, [loadKpis]);
  useEffect(() => {
    const t = setTimeout(loadList, 250);
    return () => clearTimeout(t);
  }, [loadList]);

  // Auto-refresh a cada 60 segundos (KPIs + lista)
  useEffect(() => {
    const iv = setInterval(() => {
      loadKpis();
      loadList();
    }, 60000);
    return () => clearInterval(iv);
  }, [loadKpis, loadList]);

  const onRefresh = async () => {
    setRefreshing(true);
    try { await Promise.all([loadKpis(), loadList()]); }
    finally { setRefreshing(false); }
  };

  const onClearAll = async () => {
    if (!window.confirm(`Tem certeza que deseja LIMPAR todas as ${list.total} inscrições? Esta ação não pode ser desfeita.`)) return;
    await inscriptionsApi.clear();
    await onRefresh();
  };

  const onDeleteOne = async (id, name) => {
    if (!window.confirm(`Excluir a inscrição de "${name}"?`)) return;
    await inscriptionsApi.remove(id);
    await onRefresh();
  };

  const onDownloadTxt = () => {
    const url = inscriptionsApi.exportTxtUrl({ q, status });
    window.open(url, "_blank");
  };

  const onSeedDemo = async () => {
    if (!window.confirm("Gerar 8 inscrições de demonstração? (Use só para testar o painel.)")) return;
    await inscriptionsApi.seedDemo(8);
    await onRefresh();
  };

  const empty = !loading && list.items.length === 0;

  return (
    <div className="da-page" data-testid="admin-inscriptions">
      <header className="da-page-head">
        <div>
          <h1 className="da-page-title">Inscrições</h1>
          <p className="da-page-sub">Candidatos que efetivaram uma inscrição em algum concurso.</p>
        </div>
        <div className="da-page-actions">
          {list.total === 0 && (
            <button type="button" onClick={onSeedDemo} className="da-btn da-btn-ghost" data-testid="btn-seed-demo" title="Gera dados fictícios para você visualizar o painel">
              <FileText size={14} /> Demo
            </button>
          )}
          <button type="button" onClick={onDownloadTxt} className="da-btn da-btn-ghost" data-testid="btn-export-csv">
            <Download size={14} /> Baixar dados
          </button>
          <button type="button" onClick={onClearAll} className="da-btn da-btn-danger" data-testid="btn-clear-all">
            <Trash2 size={14} /> Limpar inscrições
          </button>
          <button type="button" onClick={onRefresh} className="da-btn da-btn-ghost" data-testid="btn-refresh">
            <RotateCcw size={14} className={refreshing ? "da-spin" : ""} /> Atualizar
          </button>
        </div>
      </header>

      {/* KPIs */}
      {kpis && (
        <section className="da-kpi-grid">
          <KpiCard label="ACESSOS" icon={Eye} accent="#7c3aed"
            value={fmtNum(kpis.acessos)} sub="Usuários únicos" testid="kpi-acessos" />
          <KpiCard label="TOTAL DE INSCRIÇÕES" icon={FileText} accent="#3b82f6"
            value={fmtNum(kpis.total_inscricoes)} sub="Candidatos cadastrados" testid="kpi-inscricoes" />
          <KpiCard label="VALOR TOTAL GERADO" icon={DollarSign} accent="#10b981"
            value={fmtBRL(kpis.valor_total_gerado)} sub={`${kpis.pix_gerados_count} PIX gerado(s)`} testid="kpi-valor-gerado" />
          <KpiCard label="PIX COPIADOS" icon={Copy} accent="#f59e0b"
            value={fmtBRL(kpis.valor_pix_copiados)} sub={`${kpis.pix_copiados_count} pix copiados`} testid="kpi-pix-copiados" />
          <KpiCard label="PIX BAIXADOS" icon={Download} accent="#ec4899"
            value={fmtBRL(kpis.valor_pix_baixados)} sub={`${kpis.pix_baixados_count} comprovantes baixados`} testid="kpi-pix-baixados" />
        </section>
      )}

      {/* Filtros */}
      <div className="ds-filters">
        <div className="ds-search">
          <Search size={16} />
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar por nome, CPF, e-mail, cidade ou nº de referência…"
            data-testid="inscriptions-search-input"
          />
        </div>
        <div className="ds-status-filter">
          <span className="ds-status-label">STATUS:</span>
          <div className="ds-select-wrap">
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              data-testid="inscriptions-status-filter"
            >
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <ChevronDown size={14} />
          </div>
        </div>
      </div>

      {/* Tabela */}
      <div className="da-card ds-table-card">
        <div className="ds-thead">
          <div>CANDIDATO</div>
          <div>CPF</div>
          <div>DISPOSITIVO</div>
          <div>VALOR</div>
          <div>STATUS</div>
          <div>INSCRIÇÃO EM</div>
          <div className="ds-tr-right">AÇÕES</div>
        </div>
        <div className="ds-tbody">
          {loading && <div className="da-empty">Carregando inscrições…</div>}
          {empty && (
            <div className="da-empty">
              Nenhuma inscrição encontrada. Quando um candidato finalizar a inscrição no site, ela aparecerá aqui.
            </div>
          )}
          {!loading && list.items.map((r) => (
            <div className="ds-row" key={r.id} data-testid={`inscription-row-${r.id}`}>
              <div className="ds-candidate">
                <div className="ds-name">{r.name || "Sem nome"}</div>
                <div className="ds-email">{r.email || "—"}</div>
              </div>
              <div className="ds-cpf">{r.cpf || "—"}</div>
              <div>
                <span className={`da-pill ${r.device === "Mobile" ? "is-mobile" : "is-desktop"}`}>
                  {r.device === "Mobile" ? <Smartphone size={12} /> : <Monitor size={12} />}
                  {r.device}
                </span>
              </div>
              <div className="ds-amount">{fmtBRL(r.amount)}</div>
              <div><StatusBadge status={r.status} /></div>
              <div className="ds-when">{fmtDate(r.created_at)}</div>
              <div className="ds-actions ds-tr-right">
                <button
                  type="button"
                  className="ds-btn-exibir"
                  onClick={() => setDetailsId(r.id)}
                  data-testid={`btn-exibir-${r.id}`}
                >
                  Exibir
                </button>
                <button
                  type="button"
                  className="ds-btn-trash"
                  onClick={() => onDeleteOne(r.id, r.name)}
                  data-testid={`btn-delete-${r.id}`}
                  aria-label="Excluir"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
        {!loading && list.items.length > 0 && (
          <div className="ds-tfoot">
            Mostrando <b>{list.items.length}</b> de <b>{fmtNum(list.total)}</b> inscrições
          </div>
        )}
      </div>

      {detailsId && <DetailsModal id={detailsId} onClose={() => setDetailsId(null)} />}
    </div>
  );
}
