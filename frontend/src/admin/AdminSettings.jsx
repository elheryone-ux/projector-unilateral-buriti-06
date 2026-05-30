import React, { useEffect, useState, useCallback } from "react";
import { Zap, Send, Pin, ExternalLink, CheckCircle, AlertCircle } from "lucide-react";
import { settingsApi } from "./api";

function Toast({ kind, text, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 4000);
    return () => clearTimeout(t);
  }, [onClose]);
  const Icon = kind === "ok" ? CheckCircle : AlertCircle;
  return (
    <div className={`cfg-toast cfg-toast-${kind}`} data-testid={`toast-${kind}`}>
      <Icon size={16} /> {text}
    </div>
  );
}

function Switch({ checked, onChange, ariaLabel, testid }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      onClick={() => onChange(!checked)}
      className={`cfg-switch ${checked ? "on" : ""}`}
      data-testid={testid}
    >
      <span className="cfg-switch-knob" />
    </button>
  );
}

export default function AdminSettings() {
  const [loading, setLoading] = useState(true);
  const [savingPix, setSavingPix] = useState(false);
  const [savingTg, setSavingTg] = useState(false);
  const [testingTg, setTestingTg] = useState(false);
  const [toast, setToast] = useState(null);

  // PIX
  const [pixKey, setPixKey] = useState("");
  const [pixName, setPixName] = useState("");
  const [pixCity, setPixCity] = useState("");

  // Telegram
  const [botToken, setBotToken] = useState("");
  const [chatId, setChatId] = useState("");
  const [tgEnabled, setTgEnabled] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const s = await settingsApi.get();
      setPixKey(s.pix_key || "");
      setPixName(s.pix_recipient_name || "");
      setPixCity(s.pix_recipient_city || "");
      setBotToken(s.telegram_bot_token || "");
      setChatId(s.telegram_chat_id || "");
      setTgEnabled(!!s.telegram_enabled);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const savePix = async () => {
    setSavingPix(true);
    try {
      await settingsApi.savePix({
        pix_key: pixKey,
        pix_recipient_name: pixName,
        pix_recipient_city: pixCity,
      });
      setToast({ kind: "ok", text: "Chave PIX salva com sucesso." });
    } catch (e) {
      setToast({ kind: "err", text: e?.response?.data?.detail || "Erro ao salvar PIX." });
    } finally { setSavingPix(false); }
  };

  const saveTg = async () => {
    setSavingTg(true);
    try {
      await settingsApi.saveTelegram({
        telegram_bot_token: botToken,
        telegram_chat_id: chatId,
        telegram_enabled: tgEnabled,
      });
      setToast({ kind: "ok", text: "Notificações do Telegram salvas." });
    } catch (e) {
      setToast({ kind: "err", text: e?.response?.data?.detail || "Erro ao salvar Telegram." });
    } finally { setSavingTg(false); }
  };

  const testTg = async () => {
    if (!botToken || !chatId) {
      setToast({ kind: "err", text: "Preencha e salve Bot Token e Chat ID antes de testar." });
      return;
    }
    setTestingTg(true);
    try {
      await settingsApi.testTelegram();
      setToast({ kind: "ok", text: "Mensagem de teste enviada! Confira o Telegram." });
    } catch (e) {
      setToast({ kind: "err", text: e?.response?.data?.detail || "Falha ao enviar teste." });
    } finally { setTestingTg(false); }
  };

  return (
    <div className="da-page" data-testid="admin-settings">
      <header className="da-page-head">
        <div>
          <h1 className="da-page-title">Configurações</h1>
          <p className="da-page-sub">Configure a chave PIX e as notificações do Telegram.</p>
        </div>
      </header>

      {/* CARD: CHAVE PIX */}
      <div className="da-card cfg-card" data-testid="cfg-pix-card">
        <div className="cfg-card-head">
          <div className="cfg-ic cfg-ic-pix"><Zap size={20} /></div>
          <div>
            <h2 className="cfg-title">Chave PIX</h2>
            <p className="cfg-sub">
              Cadastre a chave PIX que vai receber os pagamentos das inscrições.
              <br />Aceita CPF, CNPJ, e-mail, telefone ou chave aleatória.
            </p>
          </div>
        </div>

        <div className="cfg-form">
          <label className="cfg-field cfg-field-full">
            <span>CHAVE PIX <i className="cfg-req">*</i></span>
            <input
              type="text"
              value={pixKey}
              onChange={(e) => setPixKey(e.target.value)}
              placeholder="ex: 6dd231fe-d8cf-495e-9e80-0aa80dedf99f"
              disabled={loading}
              data-testid="input-pix-key"
            />
          </label>

          <div className="cfg-row-2">
            <label className="cfg-field">
              <input
                type="text"
                value={pixName}
                onChange={(e) => setPixName(e.target.value)}
                placeholder="Nome do recebedor (ex: Inscrição Enem 2026)"
                disabled={loading}
                data-testid="input-pix-name"
              />
            </label>
            <label className="cfg-field">
              <input
                type="text"
                value={pixCity}
                onChange={(e) => setPixCity(e.target.value)}
                placeholder="Cidade (ex: BRASÍLIA DF)"
                disabled={loading}
                data-testid="input-pix-city"
              />
            </label>
          </div>

          <div className="cfg-actions">
            <button
              type="button"
              onClick={savePix}
              disabled={savingPix || loading}
              className="da-btn da-btn-primary"
              data-testid="btn-save-pix"
            >
              {savingPix ? "Salvando…" : "Salvar chave PIX"}
            </button>
          </div>
        </div>
      </div>

      {/* CARD: TELEGRAM */}
      <div className="da-card cfg-card" data-testid="cfg-telegram-card">
        <div className="cfg-card-head">
          <div className="cfg-ic cfg-ic-tg"><Send size={20} /></div>
          <div>
            <h2 className="cfg-title">Notificações Telegram</h2>
            <p className="cfg-sub">
              Receba uma mensagem no seu bot/grupo do Telegram sempre que uma nova inscrição for criada.
            </p>
          </div>
        </div>

        <div className="cfg-form">
          <label className="cfg-field cfg-field-full">
            <span>BOT TOKEN <i className="cfg-req">*</i></span>
            <input
              type="text"
              value={botToken}
              onChange={(e) => setBotToken(e.target.value)}
              placeholder="ex: 8766120852:AAF9NYCW8oFGNhKdFaO9Nob-MdiRKfOw7zk"
              disabled={loading}
              data-testid="input-bot-token"
            />
          </label>

          <label className="cfg-field cfg-field-full">
            <span>CHAT ID (GRUPO OU USUÁRIO) <i className="cfg-req">*</i></span>
            <input
              type="text"
              value={chatId}
              onChange={(e) => setChatId(e.target.value)}
              placeholder="ex: -1003742872851"
              disabled={loading}
              data-testid="input-chat-id"
            />
          </label>

          <div className="cfg-toggle-block">
            <span className="cfg-toggle-label">STATUS DAS NOTIFICAÇÕES</span>
            <div className="cfg-toggle-row">
              <Switch
                checked={tgEnabled}
                onChange={setTgEnabled}
                ariaLabel="Ativar notificações"
                testid="toggle-telegram"
              />
              <span className={`cfg-toggle-text ${tgEnabled ? "on" : "off"}`}>
                {tgEnabled
                  ? "ATIVO — VOCÊ RECEBERÁ NOTIFICAÇÃO A CADA NOVA INSCRIÇÃO"
                  : "DESATIVADO — NENHUMA NOTIFICAÇÃO SERÁ ENVIADA"}
              </span>
            </div>
          </div>

          <div className="cfg-info">
            <div className="cfg-info-title">
              <Pin size={14} /> Como obter Bot Token e Chat ID?
            </div>
            <ul>
              <li>Crie um bot conversando com <code>@BotFather</code> no Telegram (comando <code>/newbot</code>) — ele te dará o <b>Bot Token</b>.</li>
              <li>Adicione o bot ao seu <b>grupo</b> e envie qualquer mensagem.</li>
              <li>Acesse <code>https://api.telegram.org/bot&lt;SEU_TOKEN&gt;/getUpdates</code> no navegador.</li>
              <li>Copie o valor de <code>chat.id</code> (grupos começam com sinal de menos, ex.: <code>-100…</code>).</li>
              <li>Cole os valores acima e clique em <b>Salvar</b>.</li>
            </ul>
          </div>

          <div className="cfg-actions">
            <button
              type="button"
              onClick={testTg}
              disabled={testingTg || loading}
              className="da-btn da-btn-ghost cfg-btn-test"
              data-testid="btn-test-telegram"
            >
              <ExternalLink size={14} /> {testingTg ? "Enviando…" : "Testar envio"}
            </button>
            <button
              type="button"
              onClick={saveTg}
              disabled={savingTg || loading}
              className="da-btn da-btn-primary"
              data-testid="btn-save-telegram"
            >
              {savingTg ? "Salvando…" : "Salvar Telegram"}
            </button>
          </div>
        </div>
      </div>

      {toast && <Toast kind={toast.kind} text={toast.text} onClose={() => setToast(null)} />}
    </div>
  );
}
