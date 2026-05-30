# Donas — Painel Administrativo

## Problema (raw)
Importar projeto público do GitHub (`projector-unilateral-buriti-03`) e construir o painel administrativo `/donaspainel` (login `donas` / `Seinao10@@`) alimentado pelos eventos do site.

## Arquitetura
- **Backend**: FastAPI + Motor/MongoDB. JWT HS256 (cookie httpOnly + Bearer fallback). Geolocalização via ip-api.com (cache em Mongo). Seed automático do admin no startup.
- **Frontend**: React 19 + react-router + recharts + lucide-react. Rotas `/donaspainel/*` + redirect das demais rotas para `/home.html` (site estático).
- **Tracking**: `/tracking.js` injetado em todos os HTML, expõe `window.donasTrack.*` para os formulários.

## Coleções Mongo
- `admins`, `accesses`, `registrations` (inscrições com todos os campos + status + flags PIX), `pix_generated`, `pix_copied`, `pix_downloaded`, `events`, `ip_cache`.

## Endpoints
### Públicos (tracking)
- `POST /api/track/{access,registration,pix-generated,pix-copied,pix-downloaded}` — `registration` aceita 17+ campos (identidade, prova, atendimento, ensino médio) e PIX endpoints atualizam o status da inscrição vinculada.

### Auth (admin)
- `POST /api/admin/auth/{login,logout}`, `GET /api/admin/auth/me`

### Dashboard (auth)
- `GET /api/admin/dashboard/{kpis,funnel,locations,activity-7days,realtime,access-list}`
- `POST /api/admin/dashboard/reset-kpis`

### Inscrições (auth)
- `GET  /api/admin/inscriptions?q&status&limit&offset` — lista paginada
- `GET  /api/admin/inscriptions/export.csv?q&status` — exporta CSV UTF-8 (BOM)
- `POST /api/admin/inscriptions/clear` — limpa todas
- `POST /api/admin/inscriptions/seed-demo?count=8` — gera dados fake para teste
- `GET  /api/admin/inscriptions/{rid}` — detalhes completos do candidato
- `DELETE /api/admin/inscriptions/{rid}` — exclui uma inscrição

## Implementado
### 2026-01-28
- [x] Import GitHub → `/app` preservando `.env`
- [x] Backend completo de auth + tracking + dashboard
- [x] Painel React em `/donaspainel`: login, layout com sidebar, userbox + logout
- [x] Dashboard: 5 KPIs, Funil (donut + steps + taxas), Top Localizações, Atividade 7 dias, Atividade em Tempo Real (auto-refresh 15s), Modal de Acessos com busca
- [x] Site estático original servido em `/home.html` e demais páginas

### 2026-01-29 — Página Inscrições
- [x] Modelo `Registration` estendido (identidade, prova, ensino médio, atendimento, PIX snapshot, status, número de inscrição)
- [x] PIX endpoints atualizam o status da inscrição correspondente
- [x] Endpoints admin: list (com busca + filtro de status), get (detalhes), delete, clear, export CSV, seed-demo
- [x] Página `AdminInscriptions.jsx` com: KPIs no topo, busca por nome/CPF/e-mail/cidade/nº de referência, filtro de status (Todos/Aguardando/PIX gerado/PIX copiado/PIX baixado), tabela com 7 colunas + ações (Exibir/Excluir), modal de detalhes completo com 5 seções (Dados da inscrição, Identificação, Atendimento Especializado, Ensino Médio, Pagamento PIX), botões "Baixar dados", "Limpar inscrições" e "Atualizar"
- [x] CSV com BOM UTF-8 (Excel reconhece acentos)

## Backlog
- **P0**: Construir tela **Cadastro** (criar inscrição manualmente pelo painel)
- **P0**: Construir tela **Usuários** (criar/gerenciar mais admins)
- **P1**: Construir tela **Configurações** (mudar senha, nome do portal, chave PIX padrão)
- **P1**: Wire-up dos botões reais das páginas HTML (cadastro.html, pagar.html) chamando `window.donasTrack.*` com payload completo
- **P1**: Filtro de período no Dashboard (Hoje / 7d / 30d / Customizado)
- **P2**: Exportação PDF, WebSocket em vez de polling, 2FA/lockout para admin

### 2026-02 — Refinamento Mobile do Funil Público
- [x] `home.html`: header padronizado (logo "S" à esquerda, faixa azul fina, espaços reduzidos)
- [x] `cadastro.html` + `inscricao.html`: mesmo header mobile padrão; CPF/usuário oculto em mobile
- [x] `inscricao.html`: botão "Atualização de cadastro" oculto em mobile; correção do `:` quebrando linha em labels de rádio
- [x] `central.html`: header mobile padronizado, CPF oculto, tabela "Inscrições localizadas" convertida em cards empilhados (Inscrição / Cargo / Status com rótulos), botão "Iniciar nova inscrição" em largura total, footer compacto. Desktop preservado.

## Próximo passo sugerido
- Aplicar o mesmo padrão mobile de header em `pagar.html`, `edital.html` e `detalhes.html` (revisar página por página com o usuário).
- Wire-up dos formulários reais em `cadastro.html` / `inscricao.html` / `pagar.html` para que cada inscrição finalizada no site apareça automaticamente no painel com todos os dados certos.
