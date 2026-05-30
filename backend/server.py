"""
Backend FastAPI — Site Donas + Painel Administrativo /donaspainel.

Responsável por:
  - Tracking de eventos do site (acessos, inscrições, PIX gerado/copiado/baixado)
  - Geolocalização por IP (ip-api.com) com cache em Mongo
  - Auth JWT do painel admin
  - Endpoints do dashboard (KPIs, funil, localizações, atividade, tempo real)
  - Endpoints de inscrições (lista, detalhes, exclusão, limpeza, exportação CSV)
"""

from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import csv
import io
import os
import re
import uuid
import random
import logging
import asyncio
import bcrypt
import jwt
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
JWT_ALGORITHM = "HS256"
TOKEN_EXP_HOURS = 24

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("donas")

app = FastAPI(title="Donas API")
api_router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Helpers — hashing / jwt
# ---------------------------------------------------------------------------
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "role": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXP_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_admin(request: Request) -> dict:
    token = request.cookies.get("admin_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("role") != "admin":
            raise HTTPException(status_code=401, detail="Permissão insuficiente")
        admin = await db.admins.find_one({"username": payload["sub"]})
        if not admin:
            raise HTTPException(status_code=401, detail="Admin não encontrado")
        return {"username": admin["username"], "role": "admin"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


# ---------------------------------------------------------------------------
# Helpers — request meta (IP + device)
# ---------------------------------------------------------------------------
def get_client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "0.0.0.0"


def detect_device(user_agent: str) -> str:
    if not user_agent:
        return "Desconhecido"
    ua = user_agent.lower()
    if any(k in ua for k in ["mobi", "android", "iphone", "ipod"]):
        return "Mobile"
    if "ipad" in ua or "tablet" in ua:
        return "Tablet"
    return "Desktop"


async def geolocate_ip(ip: str) -> dict:
    if not ip or ip.startswith(("127.", "10.", "192.168.", "172.")) or ip in ("0.0.0.0", "::1"):
        return {"ip": ip, "city": "Desconhecida", "region": "—", "country": "—"}
    cached = await db.ip_cache.find_one({"ip": ip})
    if cached:
        return cached
    try:
        async with httpx.AsyncClient(timeout=4.0) as cli:
            r = await cli.get(f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city")
            data = r.json()
            if data.get("status") == "success":
                geo = {
                    "ip": ip,
                    "city": data.get("city") or "Desconhecida",
                    "region": data.get("regionName") or "—",
                    "country": data.get("country") or "—",
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                }
                await db.ip_cache.insert_one(dict(geo))
                geo.pop("_id", None)
                return geo
    except Exception as e:
        log.warning(f"Geo lookup falhou para {ip}: {e}")
    return {"ip": ip, "city": "Desconhecida", "region": "—", "country": "—"}


def gen_inscription_number() -> str:
    """Gera um número de inscrição estilo Enem (12 dígitos, começando com 26)."""
    rand = random.randint(10**9, 10**10 - 1)  # 10 dígitos
    return f"26{rand}"[:12]


def compute_inscription_status(pix_generated: bool, pix_copied: bool, pix_downloaded: bool) -> str:
    """Status DERIVADO das flags (fallback quando não há ação recente).
    Prioridade: BAIXADO > COPIADO > GERADO > AGUARDANDO.
    """
    if pix_downloaded:
        return "PIX baixado"
    if pix_copied:
        return "PIX copiado"
    if pix_generated:
        return "PIX gerado"
    return "Aguardando pagamento"


def format_cpf(cpf: Optional[str]) -> str:
    if not cpf:
        return ""
    d = re.sub(r"\D", "", cpf)
    if len(d) == 11:
        return f"{d[0:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"
    return cpf


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class AccessIn(BaseModel):
    page: Optional[str] = "/"
    referrer: Optional[str] = ""


class RegistrationIn(BaseModel):
    # Identificação
    name: Optional[str] = ""
    email: Optional[str] = ""
    cpf: Optional[str] = ""
    phone: Optional[str] = ""
    birth_date: Optional[str] = ""           # ex: "03/02/2009" ou ISO
    sex: Optional[str] = ""                  # Masculino/Feminino
    marital_status: Optional[str] = ""       # Solteiro(a)/Casado(a)/...
    race: Optional[str] = ""                 # Branca/Preta/...
    # Prova
    foreign_language: Optional[str] = ""     # Inglês/Espanhol
    exam_state: Optional[str] = ""           # UF
    exam_city: Optional[str] = ""            # Município
    # Atendimento especializado
    needs_assistance: Optional[str] = "Não"
    assistance_details: Optional[str] = ""
    # Ensino médio
    hs_situation: Optional[str] = ""
    school_type: Optional[str] = ""
    # Misc
    page: Optional[str] = "cadastro"
    amount: Optional[float] = 85.0           # valor padrão da taxa


class PixGeneratedIn(BaseModel):
    registration_id: Optional[str] = None
    cpf: Optional[str] = None  # fallback: localiza a inscrição mais recente deste CPF
    candidate_name: Optional[str] = ""
    pix_code: Optional[str] = ""
    amount: float = 0.0
    recipient: Optional[str] = ""            # snapshot do recebedor
    pix_key: Optional[str] = ""              # chave PIX usada


class PixActionIn(BaseModel):
    registration_id: Optional[str] = None
    cpf: Optional[str] = None
    pix_code: Optional[str] = ""
    candidate_name: Optional[str] = ""
    amount: float = 0.0


class LoginIn(BaseModel):
    username: str
    password: str


# ---------------------------------------------------------------------------
# Startup — seed admin + índices
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    await db.accesses.create_index([("created_at", -1)])
    await db.registrations.create_index([("created_at", -1)])
    await db.registrations.create_index("status")
    await db.registrations.create_index("cpf")
    await db.events.create_index([("created_at", -1)])
    await db.events.create_index("type")
    await db.ip_cache.create_index("ip", unique=True)
    await db.admins.create_index("username", unique=True)

    existing = await db.admins.find_one({"username": ADMIN_USERNAME})
    if not existing:
        await db.admins.insert_one({
            "username": ADMIN_USERNAME,
            "password_hash": hash_password(ADMIN_PASSWORD),
            "role": "root",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        log.info(f"Admin '{ADMIN_USERNAME}' criado.")
    else:
        # Garante que o admin seed mantém senha correta e role=root
        updates = {}
        if not verify_password(ADMIN_PASSWORD, existing["password_hash"]):
            updates["password_hash"] = hash_password(ADMIN_PASSWORD)
        if existing.get("role") != "root":
            updates["role"] = "root"
        if updates:
            await db.admins.update_one({"username": ADMIN_USERNAME}, {"$set": updates})
            log.info(f"Admin '{ADMIN_USERNAME}' atualizado: {list(updates)}")


@app.on_event("shutdown")
async def shutdown():
    client.close()


# ---------------------------------------------------------------------------
# Tracking endpoints (público)
# ---------------------------------------------------------------------------
@api_router.get("/")
async def root():
    return {"message": "Donas API", "ok": True}


def classify_access_event(page: str, device: str, geo_city: str, geo_region: str) -> dict:
    """A partir do path da página, transforma um simples 'access' em um evento
    semântico para o feed de atividade em tempo real."""
    p = (page or "").lower()
    location = f"{geo_city or 'Desconhecida'}/{geo_region or '—'}"
    if "cadastro" in p:
        return {
            "type": "inscription_started",
            "title": "Inscrição iniciada",
            "subtitle": f"Tela de cadastro · {location} · {device}",
        }
    if "edital" in p:
        return {
            "type": "edital_access",
            "title": "Acesso ao edital",
            "subtitle": f"{location} · {device}",
        }
    if "inscricao" in p:
        return {
            "type": "inscription_form",
            "title": "Cargo escolhido",
            "subtitle": f"Tela de seleção de cargo · {location} · {device}",
        }
    if "pagar" in p:
        return {
            "type": "pay_screen",
            "title": "Tela de pagamento aberta",
            "subtitle": f"{location} · {device}",
        }
    if "central" in p:
        return {
            "type": "central_access",
            "title": "Acesso à central do candidato",
            "subtitle": f"{location} · {device}",
        }
    # Acesso padrão (home, demais páginas) — diferencia por dispositivo
    return {
        "type": "access",
        "title": f"Novo acesso {device.lower()}" if device else "Novo acesso",
        "subtitle": f"{location}",
    }


@api_router.post("/track/access")
async def track_access(payload: AccessIn, request: Request):
    """Registra um acesso ao site.

    Deduplicação: 1 acesso por IP a cada 30 minutos (sessão).
      • Se o mesmo IP já bateu nos últimos 30 min, NÃO cria nova linha em
        `db.accesses` (o modal "Acessos ao site" fica limpo).
      • Para o feed de atividade, dedup é por (IP, tipo de evento): se o usuário
        navega home → cadastro → edital, cada um vira UM evento; mas refresh na
        mesma página não duplica.
      • Após 30 min de inatividade, contagem reinicia (re-registra como nova sessão).
    """
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent", "")
    device = detect_device(ua)
    now = datetime.now(timezone.utc)
    session_window_min = 30
    cutoff = (now - timedelta(minutes=session_window_min)).isoformat()

    # 1) Acesso (modal): só insere se não houver outro do mesmo IP dentro da janela.
    recent_access = await db.accesses.find_one(
        {"ip": ip, "created_at": {"$gte": cutoff}},
        {"_id": 1},
    )
    geo = await geolocate_ip(ip)
    new_access_id: Optional[str] = None
    if not recent_access:
        new_access_id = str(uuid.uuid4())
        await db.accesses.insert_one({
            "id": new_access_id,
            "ip": ip,
            "city": geo["city"], "region": geo["region"], "country": geo["country"],
            "device": device, "user_agent": ua,
            "page": payload.page, "referrer": payload.referrer,
            "created_at": now.isoformat(),
        })

    # 2) Evento (feed): só insere se não houver mesmo IP+tipo dentro da janela.
    evt = classify_access_event(payload.page or "", device, geo["city"], geo["region"])
    recent_event = await db.events.find_one(
        {"ip": ip, "type": evt["type"], "created_at": {"$gte": cutoff}},
        {"_id": 1},
    )
    if not recent_event:
        await db.events.insert_one({
            "id": str(uuid.uuid4()),
            "type": evt["type"],
            "title": evt["title"],
            "subtitle": evt["subtitle"],
            "ip": ip, "device": device,
            "city": geo["city"], "region": geo["region"],
            "page": payload.page,
            "created_at": now.isoformat(),
        })

    return {
        "ok": True,
        "deduped_access": recent_access is not None,
        "deduped_event": recent_event is not None,
        "ip": ip, "city": geo["city"], "region": geo["region"],
        "device": device,
    }


@api_router.post("/track/registration")
async def track_registration(payload: RegistrationIn, request: Request):
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent", "")
    device = detect_device(ua)
    geo = await geolocate_ip(ip)
    rid = str(uuid.uuid4())
    inscription_number = gen_inscription_number()
    now_iso = datetime.now(timezone.utc).isoformat()

    doc = {
        "id": rid,
        "inscription_number": inscription_number,
        # Identificação
        "name": payload.name,
        "email": payload.email,
        "cpf": payload.cpf,
        "phone": payload.phone,
        "birth_date": payload.birth_date,
        "sex": payload.sex,
        "marital_status": payload.marital_status,
        "race": payload.race,
        # Prova
        "foreign_language": payload.foreign_language,
        "exam_state": payload.exam_state,
        "exam_city": payload.exam_city,
        # Atendimento
        "needs_assistance": payload.needs_assistance or "Não",
        "assistance_details": payload.assistance_details,
        # Ensino médio
        "hs_situation": payload.hs_situation,
        "school_type": payload.school_type,
        # Geo / device
        "ip": ip,
        "user_agent": ua,
        "device": device,
        "city": geo["city"],
        "region": geo["region"],
        "country": geo["country"],
        # PIX / status
        "status": "Aguardando pagamento",
        "amount": float(payload.amount or 85.0),
        "pix_generated": False,
        "pix_copied": False,
        "pix_downloaded": False,
        "pix_code": "",
        "pix_recipient": "",
        "pix_key": "",
        # Misc
        "page": payload.page,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.registrations.insert_one(dict(doc))
    await db.events.insert_one({
        "id": rid,
        "type": "registration",
        "title": "Inscrição enviada",
        "subtitle": f"{(payload.name or 'Candidato').upper()} · {format_cpf(payload.cpf)} · Nº {inscription_number}",
        "device": device,
        "city": geo["city"],
        "region": geo["region"],
        "created_at": now_iso,
    })
    # Notifica Telegram (se configurado e ativo) — mensagem com status dinâmico
    try:
        s = await get_settings()
        if s.get("telegram_enabled") and s.get("telegram_bot_token") and s.get("telegram_chat_id"):
            txt = format_telegram_message(doc)
            res = await send_telegram(txt)
            if res.get("ok") and res.get("message_id"):
                # guarda o message_id para futuras edições conforme o status muda
                await db.registrations.update_one(
                    {"id": rid},
                    {"$set": {"telegram_message_id": res["message_id"]}},
                )
    except Exception as e:
        log.warning(f"Falha no Telegram notify: {e}")
    doc.pop("_id", None)
    return doc


async def _resolve_registration_id(registration_id: Optional[str], cpf: Optional[str]) -> Optional[str]:
    """Devolve o id da inscrição. Se `registration_id` for falsy, tenta achar
    pela inscrição mais recente do CPF informado. Resolve casos onde o site
    perdeu o id no localStorage (inscrições antigas, browser limpo, etc)."""
    if registration_id:
        return registration_id
    if not cpf:
        return None
    cpf_digits = re.sub(r"\D", "", str(cpf))
    if not cpf_digits:
        return None
    # tenta com dígitos limpos e com a versão formatada original
    doc = await db.registrations.find_one(
        {"$or": [{"cpf": cpf_digits}, {"cpf": cpf}]},
        {"id": 1, "_id": 0},
        sort=[("created_at", -1)],
    )
    return doc.get("id") if doc else None


async def _update_inscription_status(registration_id: Optional[str], flag_updates: Dict[str, Any]) -> Optional[dict]:
    """Atualiza uma inscrição pelo registration_id:
      - aplica as flags PIX recebidas (sem nunca desligar uma flag já ligada);
      - define o `status` como a **última ação** ocorrida (dinâmico):
          gerado → status "PIX gerado"; copiado → "PIX copiado"; baixado → "PIX baixado".
          Se o usuário copiar DEPOIS de baixar, status volta para "PIX copiado".
          Se baixar DEPOIS de copiar, vira "PIX baixado". E assim por diante.
      - flags continuam "grudadas" (idempotentes) para não duplicar valores nos KPIs.
    """
    if not registration_id:
        return None
    cur = await db.registrations.find_one({"id": registration_id})
    if not cur:
        return None
    pg = bool(cur.get("pix_generated")) or bool(flag_updates.get("pix_generated"))
    pc = bool(cur.get("pix_copied")) or bool(flag_updates.get("pix_copied"))
    pd = bool(cur.get("pix_downloaded")) or bool(flag_updates.get("pix_downloaded"))

    # Status = LAST_ACTION (dinâmico). Se não houver flag nova nessa chamada,
    # mantém o status atual; se houver, sobrescreve com o label da ação.
    last_action_status = None
    if flag_updates.get("pix_downloaded"):
        last_action_status = "PIX baixado"
    elif flag_updates.get("pix_copied"):
        last_action_status = "PIX copiado"
    elif flag_updates.get("pix_generated"):
        last_action_status = "PIX gerado"

    new_status = last_action_status or cur.get("status") or compute_inscription_status(pg, pc, pd)

    update = {
        "pix_generated": pg,
        "pix_copied": pc,
        "pix_downloaded": pd,
        "status": new_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    for k in ("pix_code", "pix_recipient", "pix_key",
              "pix_generated_at", "pix_copied_at", "pix_downloaded_at"):
        if flag_updates.get(k):
            update[k] = flag_updates[k]
    if flag_updates.get("amount"):
        update["amount"] = float(flag_updates["amount"])
    updated_doc = await db.registrations.find_one_and_update(
        {"id": registration_id}, {"$set": update}, return_document=True,
    )
    # Edita a mensagem no Telegram para refletir o novo status (sem reenviar)
    if updated_doc and updated_doc.get("telegram_message_id"):
        try:
            s = await get_settings()
            if s.get("telegram_enabled"):
                asyncio.create_task(edit_telegram(
                    int(updated_doc["telegram_message_id"]),
                    format_telegram_message(updated_doc),
                ))
        except Exception as e:
            log.warning(f"Falha ao editar Telegram: {e}")
    return updated_doc


@api_router.post("/track/pix-generated")
async def track_pix_generated(payload: PixGeneratedIn):
    pid = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": pid,
        "registration_id": payload.registration_id,
        "candidate_name": payload.candidate_name,
        "pix_code": payload.pix_code,
        "amount": float(payload.amount or 0.0),
        "recipient": payload.recipient,
        "pix_key": payload.pix_key,
        "created_at": now_iso,
    }
    await db.pix_generated.insert_one(dict(doc))
    # atualiza inscrição (idempotente, soma uma vez só por inscrição)
    await _update_inscription_status(
        payload.registration_id,
        {
            "pix_generated": True,
            "pix_code": payload.pix_code or "",
            "pix_recipient": payload.recipient or "",
            "pix_key": payload.pix_key or "",
            "amount": float(payload.amount or 0.0) or None,
            "pix_generated_at": now_iso,
        },
    )
    await db.events.insert_one({
        "id": pid,
        "type": "pix_generated",
        "title": "PIX gerado",
        "subtitle": f"{(payload.candidate_name or 'Candidato').upper()} · R$ {float(payload.amount or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        "created_at": now_iso,
    })
    doc.pop("_id", None)
    return doc


@api_router.post("/track/pix-copied")
async def track_pix_copied(payload: PixActionIn):
    pid = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    rid = await _resolve_registration_id(payload.registration_id, payload.cpf)
    doc = {
        "id": pid,
        "registration_id": rid,
        "candidate_name": payload.candidate_name,
        "pix_code": payload.pix_code,
        "amount": float(payload.amount or 0.0),
        "created_at": now_iso,
    }
    await db.pix_copied.insert_one(dict(doc))
    await _update_inscription_status(
        rid,
        {"pix_copied": True, "pix_copied_at": now_iso},
    )
    await db.events.insert_one({
        "id": pid,
        "type": "pix_copied",
        "title": "PIX copiado",
        "subtitle": f"{(payload.candidate_name or 'Candidato').upper()} · R$ {float(payload.amount or 0):.2f}".replace(".", ","),
        "created_at": now_iso,
    })
    doc.pop("_id", None)
    return doc


@api_router.post("/track/pix-downloaded")
async def track_pix_downloaded(payload: PixActionIn):
    pid = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    rid = await _resolve_registration_id(payload.registration_id, payload.cpf)
    doc = {
        "id": pid,
        "registration_id": rid,
        "candidate_name": payload.candidate_name,
        "amount": float(payload.amount or 0.0),
        "created_at": now_iso,
    }
    await db.pix_downloaded.insert_one(dict(doc))
    await _update_inscription_status(
        rid,
        {"pix_downloaded": True, "pix_downloaded_at": now_iso},
    )
    await db.events.insert_one({
        "id": pid,
        "type": "pix_downloaded",
        "title": "PIX baixado",
        "subtitle": f"{(payload.candidate_name or 'Candidato').upper()} · Comprovante impresso",
        "created_at": now_iso,
    })
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# Admin Auth endpoints
# ---------------------------------------------------------------------------
@api_router.post("/admin/auth/login")
async def admin_login(payload: LoginIn, response: Response):
    admin = await db.admins.find_one({"username": payload.username.strip()})
    if not admin or not verify_password(payload.password, admin["password_hash"]):
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")
    token = create_token(admin["username"])
    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=TOKEN_EXP_HOURS * 3600,
        path="/",
    )
    return {
        "token": token,
        "user": {"username": admin["username"], "role": "admin", "display_name": "donas (root)"},
    }


@api_router.get("/admin/auth/me")
async def admin_me(admin=Depends(get_current_admin)):
    return {"username": admin["username"], "role": admin["role"], "display_name": "donas (root)"}


@api_router.post("/admin/auth/logout")
async def admin_logout(response: Response):
    response.delete_cookie("admin_token", path="/")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Admin Users CRUD (auth required)
# ---------------------------------------------------------------------------
class AdminCreateIn(BaseModel):
    username: str
    password: str
    role: Optional[str] = "admin"   # "root" ou "admin"


def admin_to_dict(a: dict) -> dict:
    return {
        "username": a.get("username"),
        "role": a.get("role") or "admin",
        "created_at": a.get("created_at"),
    }


@api_router.get("/admin/users")
async def list_admins(admin=Depends(get_current_admin)):
    items = []
    async for a in db.admins.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", 1):
        items.append(admin_to_dict(a))
    return {"items": items, "total": len(items), "current": admin["username"]}


@api_router.post("/admin/users")
async def create_admin(payload: AdminCreateIn, admin=Depends(get_current_admin)):
    username = payload.username.strip().lower()
    password = payload.password
    role = (payload.role or "admin").strip().lower()
    if role not in ("admin", "root"):
        raise HTTPException(status_code=400, detail="Papel deve ser 'admin' ou 'root'")
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Usuário deve ter ao menos 3 caracteres")
    if not re.match(r"^[a-z0-9._-]+$", username):
        raise HTTPException(status_code=400, detail="Usuário só pode conter letras, números, ponto, hífen ou underline")
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="Senha deve ter ao menos 4 caracteres")
    if await db.admins.find_one({"username": username}):
        raise HTTPException(status_code=409, detail="Já existe um administrador com esse usuário")
    doc = {
        "username": username,
        "password_hash": hash_password(password),
        "role": role,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": admin["username"],
    }
    await db.admins.insert_one(doc)
    return admin_to_dict(doc)


@api_router.delete("/admin/users/{username}")
async def delete_admin(username: str, admin=Depends(get_current_admin)):
    username = username.strip().lower()
    target = await db.admins.find_one({"username": username})
    if not target:
        raise HTTPException(status_code=404, detail="Administrador não encontrado")
    if username == admin["username"]:
        raise HTTPException(status_code=400, detail="Você não pode excluir a si mesmo")
    if (target.get("role") or "admin") == "root":
        # Só permite excluir um root se sobrar pelo menos 1 root
        n_roots = await db.admins.count_documents({"role": "root"})
        if n_roots <= 1:
            raise HTTPException(status_code=400, detail="Não é possível excluir o último administrador root")
    await db.admins.delete_one({"username": username})
    return {"ok": True, "deleted": username}


# ---------------------------------------------------------------------------
# Settings (PIX + Telegram) — auth required
# ---------------------------------------------------------------------------
SETTINGS_ID = "global"


class PixSettingsIn(BaseModel):
    pix_key: str = ""
    pix_recipient_name: str = ""
    pix_recipient_city: str = ""


class TelegramSettingsIn(BaseModel):
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_enabled: bool = False


async def get_settings() -> dict:
    s = await db.settings.find_one({"_id": SETTINGS_ID}) or {}
    return {
        "pix_key": s.get("pix_key", ""),
        "pix_recipient_name": s.get("pix_recipient_name", ""),
        "pix_recipient_city": s.get("pix_recipient_city", ""),
        "telegram_bot_token": s.get("telegram_bot_token", ""),
        "telegram_chat_id": s.get("telegram_chat_id", ""),
        "telegram_enabled": bool(s.get("telegram_enabled", False)),
        "updated_at": s.get("updated_at"),
    }


@api_router.get("/admin/settings")
async def settings_get(admin=Depends(get_current_admin)):
    return await get_settings()


@api_router.get("/settings/public")
async def settings_public():
    """Endpoint público com APENAS as informações PIX que o pagar.html precisa
    (chave PIX, recebedor, cidade). Bot token nunca é exposto aqui."""
    s = await get_settings()
    return {
        "pix_key": s["pix_key"],
        "pix_recipient_name": s["pix_recipient_name"],
        "pix_recipient_city": s["pix_recipient_city"],
    }


@api_router.put("/admin/settings/pix")
async def settings_save_pix(payload: PixSettingsIn, admin=Depends(get_current_admin)):
    await db.settings.update_one(
        {"_id": SETTINGS_ID},
        {"$set": {
            "pix_key": payload.pix_key.strip(),
            "pix_recipient_name": payload.pix_recipient_name.strip(),
            "pix_recipient_city": payload.pix_recipient_city.strip(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return await get_settings()


@api_router.put("/admin/settings/telegram")
async def settings_save_telegram(payload: TelegramSettingsIn, admin=Depends(get_current_admin)):
    await db.settings.update_one(
        {"_id": SETTINGS_ID},
        {"$set": {
            "telegram_bot_token": payload.telegram_bot_token.strip(),
            "telegram_chat_id": payload.telegram_chat_id.strip(),
            "telegram_enabled": bool(payload.telegram_enabled),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return await get_settings()


async def send_telegram(text: str) -> dict:
    """Envia mensagem ao Telegram e devolve {ok, message_id?}."""
    s = await get_settings()
    token = s["telegram_bot_token"]
    chat_id = s["telegram_chat_id"]
    if not token or not chat_id:
        return {"ok": False, "error": "Bot token ou chat_id não configurados."}
    try:
        async with httpx.AsyncClient(timeout=8.0) as cli:
            r = await cli.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
            )
            data = r.json()
            if not data.get("ok"):
                return {"ok": False, "error": data.get("description") or "Falha desconhecida"}
            return {"ok": True, "message_id": data.get("result", {}).get("message_id")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def edit_telegram(message_id: int, text: str) -> dict:
    """Edita uma mensagem existente no chat configurado."""
    s = await get_settings()
    token = s["telegram_bot_token"]
    chat_id = s["telegram_chat_id"]
    if not token or not chat_id or not message_id:
        return {"ok": False}
    try:
        async with httpx.AsyncClient(timeout=8.0) as cli:
            r = await cli.post(
                f"https://api.telegram.org/bot{token}/editMessageText",
                json={
                    "chat_id": chat_id, "message_id": int(message_id),
                    "text": text, "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            data = r.json()
            return {"ok": bool(data.get("ok")), "error": data.get("description")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


STATUS_EMOJI = {
    "Aguardando pagamento": "🟡",
    "PIX gerado": "🔵",
    "PIX copiado": "🟢",
    "PIX baixado": "✅",
}


def format_telegram_message(reg: dict) -> str:
    """Mensagem padrão com status dinâmico — usada tanto no send quanto no edit."""
    status = reg.get("status") or "Aguardando pagamento"
    emoji = STATUS_EMOJI.get(status, "🟡")
    nivel = reg.get("hs_situation") or "—"
    valor = float(reg.get("amount") or 0)
    cidade_uf = f"{reg.get('city') or '—'}/{reg.get('region') or '—'}"
    return (
        "<b>INSCRIÇÃO BURITICUPU-MA</b>\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Nome:</b> {(reg.get('name') or 'Candidato').upper()}\n"
        f"<b>CPF:</b> {format_cpf(reg.get('cpf', ''))}\n"
        f"<b>Nível:</b> {nivel}\n"
        f"<b>Valor:</b> R$ {valor:.2f}\n"
        f"<b>Cidade:</b> {cidade_uf}\n"
        f"<b>Dispositivo:</b> {reg.get('device') or '—'}\n"
        f"<b>Status:</b> {emoji} {status}"
    )


@api_router.post("/admin/settings/telegram/test")
async def settings_test_telegram(admin=Depends(get_current_admin)):
    txt = (
        "<b>✅ Painel Donas — teste de notificação</b>\n\n"
        "Tudo certo! A partir de agora você vai receber aqui um aviso "
        "sempre que uma nova inscrição for criada no site.\n\n"
        f"<i>Enviado por: {admin['username']}</i>"
    )
    res = await send_telegram(txt)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error") or "Erro ao enviar")
    return {"ok": True, "message": "Mensagem de teste enviada com sucesso."}


# ---------------------------------------------------------------------------
# Dashboard endpoints (auth required)
# ---------------------------------------------------------------------------
@api_router.get("/admin/dashboard/kpis")
async def kpis(admin=Depends(get_current_admin)):
    """KPIs por **inscrição** (não por evento), seguindo a regra do flow:
       - 1 inscrição com pix_copied=true conta 1 vez em PIX COPIADOS, somando o `amount` dela.
       - cliques repetidos no mesmo botão não inflam os valores.
       - ACESSOS = usuários únicos (IPs distintos).
    """
    # Acessos únicos por IP
    unique_ips_cursor = db.accesses.aggregate([
        {"$group": {"_id": "$ip"}},
        {"$count": "n"},
    ])
    acessos_unicos = 0
    async for r in unique_ips_cursor:
        acessos_unicos = r.get("n", 0)
    acessos_brutos = await db.accesses.count_documents({})

    # Inscrições (registrations efetivadas)
    registrations = await db.registrations.count_documents({})

    async def count_and_sum(flag: str):
        cnt = await db.registrations.count_documents({flag: True})
        total = 0.0
        async for d in db.registrations.find({flag: True}, {"amount": 1, "_id": 0}):
            total += float(d.get("amount") or 0)
        return cnt, total

    pix_gen_count, total_gerado = await count_and_sum("pix_generated")
    pix_cop_count, total_copiado = await count_and_sum("pix_copied")
    pix_dl_count, total_baixado = await count_and_sum("pix_downloaded")

    return {
        "acessos": acessos_unicos,                # usuários únicos
        "acessos_brutos": acessos_brutos,          # page-views totais (extra info)
        "total_inscricoes": registrations,
        "valor_total_gerado": total_gerado,
        "pix_gerados_count": pix_gen_count,
        "valor_pix_copiados": total_copiado,
        "pix_copiados_count": pix_cop_count,
        "valor_pix_baixados": total_baixado,
        "pix_baixados_count": pix_dl_count,
    }


@api_router.get("/admin/dashboard/funnel")
async def funnel(admin=Depends(get_current_admin)):
    # acessos únicos para topo do funil
    unique_ips_cursor = db.accesses.aggregate([
        {"$group": {"_id": "$ip"}},
        {"$count": "n"},
    ])
    acessos = 0
    async for r in unique_ips_cursor:
        acessos = r.get("n", 0)
    inscricoes = await db.registrations.count_documents({})
    pix_gerado = await db.registrations.count_documents({"pix_generated": True})
    pix_copiado = await db.registrations.count_documents({"pix_copied": True})
    pix_baixado = await db.registrations.count_documents({"pix_downloaded": True})

    def pct(a, b):
        return round((a / b * 100), 2) if b else 0.0

    return {
        "steps": [
            {"key": "acessos", "label": "Acessos ao site", "value": acessos, "left": 0, "delta_pct": None, "tag": "topo"},
            {"key": "inscricoes", "label": "Inscrições criadas", "value": inscricoes, "left": max(acessos - inscricoes, 0), "delta_pct": pct(inscricoes, acessos)},
            {"key": "pix_gerado", "label": "PIX gerado", "value": pix_gerado, "left": max(inscricoes - pix_gerado, 0), "delta_pct": pct(pix_gerado, inscricoes)},
            {"key": "pix_copiado", "label": "PIX copiado", "value": pix_copiado, "left": max(pix_gerado - pix_copiado, 0), "delta_pct": pct(pix_copiado, pix_gerado)},
            {"key": "pix_baixado", "label": "PIX baixado", "value": pix_baixado, "left": max(pix_copiado - pix_baixado, 0), "delta_pct": pct(pix_baixado, pix_copiado)},
        ],
        "rates": {
            "insc_to_pix": pct(pix_gerado, inscricoes),
            "pix_to_baixados": pct(pix_baixado, pix_gerado),
            "geral": pct(pix_baixado, acessos),
            "insc_to_copiado": pct(pix_copiado, inscricoes),
        },
    }


@api_router.get("/admin/dashboard/locations")
async def locations(admin=Depends(get_current_admin), limit: int = 12):
    pipeline = [
        {"$group": {"_id": {"city": "$city", "region": "$region"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    out = []
    async for r in db.accesses.aggregate(pipeline):
        city = r["_id"].get("city") or "Desconhecida"
        region = r["_id"].get("region") or "—"
        out.append({"city": city, "region": region, "count": r["count"]})
    return {"items": out}


@api_router.get("/admin/dashboard/activity-7days")
async def activity_7days(admin=Depends(get_current_admin)):
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=6)
    days = [(start + timedelta(days=i)) for i in range(7)]
    labels = [d.strftime("%d/%m") for d in days]

    def init_buckets():
        return {d.isoformat(): 0 for d in days}

    acc_buckets = init_buckets()
    insc_buckets = init_buckets()

    async for a in db.accesses.find({}, {"created_at": 1, "_id": 0}):
        try:
            d = datetime.fromisoformat(a["created_at"]).date().isoformat()
            if d in acc_buckets:
                acc_buckets[d] += 1
        except Exception:
            pass

    async for r in db.registrations.find({}, {"created_at": 1, "_id": 0}):
        try:
            d = datetime.fromisoformat(r["created_at"]).date().isoformat()
            if d in insc_buckets:
                insc_buckets[d] += 1
        except Exception:
            pass

    return {
        "labels": labels,
        "acessos": [acc_buckets[d.isoformat()] for d in days],
        "inscricoes": [insc_buckets[d.isoformat()] for d in days],
    }


@api_router.get("/admin/dashboard/realtime")
async def realtime(admin=Depends(get_current_admin), limit: int = 20):
    items = []
    async for e in db.events.find({}, {"_id": 0}).sort("created_at", -1).limit(limit):
        items.append(e)
    return {"items": items}


@api_router.get("/admin/dashboard/access-list")
async def access_list(admin=Depends(get_current_admin), q: Optional[str] = None, limit: int = 200):
    query = {}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        query = {"$or": [{"ip": rx}, {"city": rx}, {"region": rx}, {"device": rx}]}
    out = []
    async for a in db.accesses.find(query, {"_id": 0}).sort("created_at", -1).limit(limit):
        out.append(a)
    return {"items": out, "total": await db.accesses.count_documents({})}


@api_router.post("/admin/dashboard/reset-kpis")
async def reset_kpis(admin=Depends(get_current_admin)):
    await asyncio.gather(
        db.accesses.delete_many({}),
        db.registrations.delete_many({}),
        db.pix_generated.delete_many({}),
        db.pix_copied.delete_many({}),
        db.pix_downloaded.delete_many({}),
        db.events.delete_many({}),
    )
    return {"ok": True, "message": "KPIs zerados"}


# ---------------------------------------------------------------------------
# Inscriptions endpoints (auth required)
# ---------------------------------------------------------------------------
STATUS_VALUES = ["Aguardando pagamento", "PIX gerado", "PIX copiado", "PIX baixado"]


def _build_inscription_query(q: Optional[str], status: Optional[str]) -> dict:
    query: dict = {}
    if status and status != "all" and status in STATUS_VALUES:
        query["status"] = status
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        query["$or"] = [
            {"name": rx},
            {"email": rx},
            {"cpf": rx},
            {"city": rx},
            {"exam_city": rx},
            {"inscription_number": rx},
        ]
    return query


@api_router.get("/admin/inscriptions")
async def list_inscriptions(
    admin=Depends(get_current_admin),
    q: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    query = _build_inscription_query(q, status)
    cursor = (
        db.registrations.find(query, {"_id": 0})
        .sort("created_at", -1)
        .skip(max(0, int(offset)))
        .limit(max(1, min(int(limit), 500)))
    )
    items = []
    async for d in cursor:
        items.append({
            "id": d.get("id"),
            "inscription_number": d.get("inscription_number", ""),
            "name": d.get("name", ""),
            "email": d.get("email", ""),
            "cpf": format_cpf(d.get("cpf", "")),
            "device": d.get("device", "Desconhecido"),
            "amount": float(d.get("amount") or 0),
            "status": d.get("status") or "Aguardando pagamento",
            "city": d.get("city", ""),
            "region": d.get("region", ""),
            "created_at": d.get("created_at"),
        })
    total = await db.registrations.count_documents(query)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@api_router.get("/admin/inscriptions/export.csv")
async def export_inscriptions_csv(
    admin=Depends(get_current_admin),
    q: Optional[str] = None,
    status: Optional[str] = None,
):
    query = _build_inscription_query(q, status)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow([
        "Nº Inscrição", "Nome", "CPF", "E-mail", "Telefone",
        "Nascimento", "Sexo", "Estado Civil", "Cor/Raça",
        "Língua", "UF Prova", "Município Prova",
        "Atendimento Especializado", "Situação Ensino Médio", "Tipo Escola",
        "Status", "Valor (R$)", "PIX Gerado", "PIX Copiado", "Comprovante Baixado",
        "Dispositivo", "IP", "Cidade IP", "UF IP", "Data Inscrição",
    ])
    async for d in db.registrations.find(query, {"_id": 0}).sort("created_at", -1):
        writer.writerow([
            d.get("inscription_number", ""),
            d.get("name", ""),
            format_cpf(d.get("cpf", "")),
            d.get("email", ""),
            d.get("phone", ""),
            d.get("birth_date", ""),
            d.get("sex", ""),
            d.get("marital_status", ""),
            d.get("race", ""),
            d.get("foreign_language", ""),
            d.get("exam_state", ""),
            d.get("exam_city", ""),
            d.get("needs_assistance", ""),
            d.get("hs_situation", ""),
            d.get("school_type", ""),
            d.get("status", ""),
            f"{float(d.get('amount') or 0):.2f}".replace(".", ","),
            "Sim" if d.get("pix_generated") else "Não",
            "Sim" if d.get("pix_copied") else "Não",
            "Sim" if d.get("pix_downloaded") else "Não",
            d.get("device", ""),
            d.get("ip", ""),
            d.get("city", ""),
            d.get("region", ""),
            d.get("created_at", ""),
        ])
    buf.seek(0)
    data = "\ufeff" + buf.getvalue()
    filename = f"inscricoes_donas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([data]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api_router.get("/admin/inscriptions/export.txt")
async def export_inscriptions_txt(
    admin=Depends(get_current_admin),
    q: Optional[str] = None,
    status: Optional[str] = None,
):
    """Exporta as inscrições em TXT formatado, com TODOS os dados de cada
    candidato organizados nas mesmas 5 seções do modal "Exibir"."""
    query = _build_inscription_query(q, status)
    lines: List[str] = []
    total = await db.registrations.count_documents(query)

    header = [
        "═════════════════════════════════════════════════════════════════════════",
        "  DONAS — RELATÓRIO DETALHADO DE INSCRIÇÕES",
        f"  Exportado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        f"  Total de inscrições: {total}",
    ]
    if q:
        header.append(f"  Filtro de busca: \"{q}\"")
    if status and status != "all":
        header.append(f"  Filtro de status: {status}")
    header.append("═════════════════════════════════════════════════════════════════════════")
    header.append("")
    lines.extend(header)

    def row(label: str, value: Any) -> str:
        v = value if (value is not None and value != "") else "—"
        return f"  {label:<32} {v}"

    idx = 0
    async for d in db.registrations.find(query, {"_id": 0}).sort("created_at", -1):
        idx += 1
        amount_str = f"R$ {float(d.get('amount') or 0):.2f}".replace(".", ",")
        lines.append(f"┌─ INSCRIÇÃO #{idx} de {total} ─────────────────────────────────────────────")
        lines.append(f"│  Candidato: {(d.get('name') or '—').upper()}")
        lines.append(f"│  CPF: {format_cpf(d.get('cpf', ''))}  ·  Nº inscrição: {d.get('inscription_number', '—')}")
        lines.append("└─────────────────────────────────────────────────────────────────────────")
        lines.append("")

        lines.append("  [1] DADOS DA INSCRIÇÃO")
        lines.append("  " + "─" * 71)
        lines.append(row("Número de inscrição:", d.get("inscription_number")))
        lines.append(row("Status atual:", d.get("status")))
        lines.append(row("Valor da taxa:", amount_str))
        lines.append(row("Dispositivo:", d.get("device")))
        lines.append(row("Data da inscrição:", d.get("created_at")))
        lines.append(row("Última atualização:", d.get("updated_at")))
        lines.append(row("IP do candidato:", d.get("ip")))
        lines.append(row("Cidade/UF (Geo IP):", f"{d.get('city') or '—'}/{d.get('region') or '—'}"))
        lines.append(row("País (Geo IP):", d.get("country")))
        lines.append(row("Página de origem:", d.get("page")))
        lines.append(row("User-Agent:", (d.get("user_agent") or "")[:80]))
        lines.append("")

        lines.append("  [2] IDENTIFICAÇÃO")
        lines.append("  " + "─" * 71)
        lines.append(row("Nome completo:", (d.get("name") or "").upper()))
        lines.append(row("CPF:", format_cpf(d.get("cpf", ""))))
        lines.append(row("E-mail:", d.get("email")))
        lines.append(row("Telefone:", d.get("phone")))
        lines.append(row("Data de nascimento:", d.get("birth_date")))
        lines.append(row("Sexo:", d.get("sex")))
        lines.append(row("Estado civil:", d.get("marital_status")))
        lines.append(row("Cor/Raça:", d.get("race")))
        lines.append(row("Língua estrangeira:", d.get("foreign_language")))
        lines.append(row("UF de prova:", d.get("exam_state")))
        lines.append(row("Município de prova:", d.get("exam_city")))
        lines.append("")

        lines.append("  [3] ATENDIMENTO ESPECIALIZADO")
        lines.append("  " + "─" * 71)
        lines.append(row("Precisa de atendimento?", d.get("needs_assistance")))
        if d.get("assistance_details"):
            lines.append(row("Detalhes:", d.get("assistance_details")))
        lines.append("")

        lines.append("  [4] ENSINO MÉDIO / NÍVEL")
        lines.append("  " + "─" * 71)
        lines.append(row("Situação / Nível:", d.get("hs_situation")))
        lines.append(row("Tipo de escola / Cargo:", d.get("school_type")))
        lines.append("")

        lines.append("  [5] PAGAMENTO PIX")
        lines.append("  " + "─" * 71)
        lines.append(row("Status atual:", d.get("status")))
        lines.append(row("PIX gerado?", "Sim" if d.get("pix_generated") else "Não"))
        if d.get("pix_generated_at"):
            lines.append(row("  → em:", d.get("pix_generated_at")))
        lines.append(row("PIX copiado?", "Sim" if d.get("pix_copied") else "Não"))
        if d.get("pix_copied_at"):
            lines.append(row("  → em:", d.get("pix_copied_at")))
        lines.append(row("Comprovante baixado?", "Sim" if d.get("pix_downloaded") else "Não"))
        if d.get("pix_downloaded_at"):
            lines.append(row("  → em:", d.get("pix_downloaded_at")))
        lines.append(row("Recebedor (snapshot):", d.get("pix_recipient")))
        lines.append(row("Chave PIX:", d.get("pix_key")))
        if d.get("pix_code"):
            lines.append(row("Código PIX:", d.get("pix_code")))
        lines.append("")
        lines.append("=" * 73)
        lines.append("")

    if total == 0:
        lines.append("  (Nenhuma inscrição encontrada com os filtros atuais.)")
        lines.append("")

    lines.append(f"— Fim do relatório · {total} inscrição(ões) exportada(s) —")
    data = "\ufeff" + "\n".join(lines)
    filename = f"inscricoes_donas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    return StreamingResponse(
        iter([data]),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api_router.post("/admin/inscriptions/clear")
async def clear_inscriptions(admin=Depends(get_current_admin)):
    res = await db.registrations.delete_many({})
    await asyncio.gather(
        db.pix_generated.delete_many({}),
        db.pix_copied.delete_many({}),
        db.pix_downloaded.delete_many({}),
    )
    return {"ok": True, "deleted_count": res.deleted_count}


@api_router.post("/admin/inscriptions/seed-demo")
async def seed_demo_inscriptions(admin=Depends(get_current_admin), count: int = 8):
    """Cria inscrições fake para validar o painel. Não usa em produção."""
    demo = [
        ("Mario Colombelli Romera", "rafaela.colombelli@gmail.com", "47060032886", "Mobile", "PIX copiado", "Botucatu", "São Paulo", True, True, False),
        ("Jesus Suarez Peralta", "jesussuarezperalta8200@gmail.com", "71069538221", "Mobile", "PIX gerado", "Fortaleza", "Ceará", True, False, False),
        ("Matheus Mendes De Almeida", "dealmeidam802@gmail.com", "80284616974", "Mobile", "PIX gerado", "Fortaleza", "Ceará", True, False, False),
        ("Michele Si Yi Chen", "michelechen43@gmail.com", "09970180207", "Mobile", "PIX copiado", "São Paulo", "São Paulo", True, True, False),
        ("Emily Gabrieli Bueno Cordeiro De Paula", "cordeiro.paula.emily@escola.pr.gov.br", "16206777928", "Desktop", "PIX gerado", "Curitiba", "Paraná", True, False, False),
        ("Ana Beatriz Rodrigues Silva", "ustarb97@gmail.com", "59029163801", "Mobile", "Aguardando pagamento", "Fortaleza", "Ceará", False, False, False),
        ("Lavínia Marques Pimentel Lemos", "laviniampl@gmail.com", "15898890750", "Mobile", "PIX gerado", "Fortaleza", "Ceará", True, False, False),
        ("Carlos Eduardo Souza", "carlos.es@gmail.com", "32145698701", "Desktop", "PIX baixado", "Fortaleza", "Ceará", True, True, True),
    ][:count]
    now = datetime.now(timezone.utc)
    inserted = []
    for i, (name, email, cpf, device, status, city, region, pg, pc, pd) in enumerate(demo):
        ts = (now - timedelta(hours=i, minutes=random.randint(0, 59))).isoformat()
        rid = str(uuid.uuid4())
        doc = {
            "id": rid,
            "inscription_number": gen_inscription_number(),
            "name": name, "email": email, "cpf": cpf,
            "phone": f"(85) 9{random.randint(8000,9999)}-{random.randint(1000,9999)}",
            "birth_date": f"{random.randint(1,28):02d}/{random.randint(1,12):02d}/{random.randint(2003,2009)}",
            "sex": random.choice(["Masculino", "Feminino"]),
            "marital_status": "Solteiro(a)",
            "race": random.choice(["Branca", "Parda", "Preta", "Amarela"]),
            "foreign_language": random.choice(["Inglês", "Espanhol"]),
            "exam_state": region, "exam_city": city,
            "needs_assistance": "Não", "assistance_details": "",
            "hs_situation": "Estou cursando o ensino médio, mas não estou na última série/ano.",
            "school_type": random.choice(["Escola pública.", "Escola privada."]),
            "ip": f"201.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
            "user_agent": "demo", "device": device,
            "city": city, "region": region, "country": "Brasil",
            "status": status, "amount": 85.0,
            "pix_generated": pg, "pix_copied": pc, "pix_downloaded": pd,
            "pix_code": "00020126360014BR.GOV.BCB.PIX...DEMO" if pg else "",
            "pix_recipient": "Inscrição Enem 2026 · BRASÍLIA DF" if pg else "",
            "pix_key": str(uuid.uuid4()) if pg else "",
            "page": "cadastro",
            "created_at": ts, "updated_at": ts,
        }
        await db.registrations.insert_one(dict(doc))
        if pg:
            await db.pix_generated.insert_one({
                "id": str(uuid.uuid4()), "registration_id": rid,
                "candidate_name": name, "amount": 85.0,
                "pix_code": doc["pix_code"], "created_at": ts,
            })
        if pc:
            await db.pix_copied.insert_one({
                "id": str(uuid.uuid4()), "registration_id": rid,
                "candidate_name": name, "amount": 85.0, "created_at": ts,
            })
        if pd:
            await db.pix_downloaded.insert_one({
                "id": str(uuid.uuid4()), "registration_id": rid,
                "candidate_name": name, "amount": 85.0, "created_at": ts,
            })
        inserted.append(rid)
    return {"ok": True, "inserted": len(inserted)}


# ---- rotas com path param {rid} ficam por último para não capturar paths fixos ----
@api_router.get("/admin/inscriptions/{rid}")
async def get_inscription(rid: str, admin=Depends(get_current_admin)):
    doc = await db.registrations.find_one({"id": rid}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Inscrição não encontrada")
    doc["cpf_fmt"] = format_cpf(doc.get("cpf", ""))
    return doc


@api_router.delete("/admin/inscriptions/{rid}")
async def delete_inscription(rid: str, admin=Depends(get_current_admin)):
    res = await db.registrations.delete_one({"id": rid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Inscrição não encontrada")
    await asyncio.gather(
        db.pix_generated.delete_many({"registration_id": rid}),
        db.pix_copied.delete_many({"registration_id": rid}),
        db.pix_downloaded.delete_many({"registration_id": rid}),
    )
    return {"ok": True, "deleted_id": rid}


# ---------------------------------------------------------------------------
# Wire up
# ---------------------------------------------------------------------------
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
