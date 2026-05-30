import React from "react";

export default function AdminPlaceholder({ title, hint }) {
  return (
    <div className="da-page" data-testid="admin-placeholder">
      <header className="da-page-head">
        <div>
          <h1 className="da-page-title">{title}</h1>
          <p className="da-page-sub">Em construção — será habilitado nas próximas etapas.</p>
        </div>
      </header>
      <div className="da-card">
        <div className="da-placeholder">
          <div>
            <h2>{title}</h2>
            <p>{hint || "Esta seção será integrada em uma próxima iteração."}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
