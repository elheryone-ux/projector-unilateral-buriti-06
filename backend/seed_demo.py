#!/usr/bin/env python3
"""
Seed de demonstração — 200 candidatos brasileiros simulando o fluxo real:
  - 100 apenas acessaram o site
  - 100 fizeram inscrição completa, distribuídos em:
      • 40 — só finalizaram a inscrição (status "Aguardando pagamento")
      • 30 — geraram PIX e copiaram (status "PIX copiado")
      • 30 — geraram PIX, copiaram e baixaram (status "PIX baixado")
Tudo com IPs brasileiros, nomes/CPF/cidades reais, mix de Mobile/Desktop,
distribuído cronologicamente nas últimas 168 horas (7 dias).
"""
import asyncio
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# ---------------------------------------------------------------------------
# Dados realistas
# ---------------------------------------------------------------------------
PRIMEIROS = [
    "Maria","João","José","Ana","Antonio","Francisco","Carlos","Paulo","Pedro","Lucas",
    "Luiz","Marcos","Luis","Gabriel","Rafael","Daniel","Marcelo","Bruno","Eduardo","Felipe",
    "Raimundo","Rodrigo","Manoel","Júlia","Mariana","Larissa","Beatriz","Isabela","Letícia",
    "Camila","Fernanda","Juliana","Patrícia","Aline","Adriana","Cláudia","Sandra","Vanessa",
    "Tatiana","Renata","Carla","Débora","Bianca","Sofia","Helena","Valentina","Lara","Manuela",
    "Heitor","Davi","Arthur","Bernardo","Miguel","Theo","Enzo","Lorenzo","Matheus","Vinícius",
    "Gustavo","Leonardo","Ricardo","Roberto","André","Diego","Thiago","Vítor","Henrique","Murilo",
    "Yasmin","Sophia","Alice","Cecília","Eloá","Lavínia","Isadora","Maitê","Maya","Antonella",
]
SOBRENOMES = [
    "Silva","Santos","Oliveira","Souza","Lima","Pereira","Carvalho","Ferreira","Rodrigues","Gomes",
    "Costa","Almeida","Ribeiro","Martins","Araújo","Barbosa","Cardoso","Cavalcanti","Castro","Cunha",
    "Dias","Duarte","Fernandes","Freitas","Garcia","Gonçalves","Mendes","Monteiro","Moraes","Moreira",
    "Nascimento","Nogueira","Nunes","Pinto","Pinheiro","Queiroz","Ramos","Reis","Rocha","Sales",
    "Sampaio","Teixeira","Vieira","Xavier","Mota","Macedo","Maia","Pacheco","Tavares","Marques",
]

# (cidade, UF) — cobertura nacional realista
CIDADES_BR = [
    ("São Paulo","SP"),("Guarulhos","SP"),("Campinas","SP"),("São Bernardo do Campo","SP"),("Santos","SP"),
    ("Rio de Janeiro","RJ"),("São Gonçalo","RJ"),("Niterói","RJ"),("Duque de Caxias","RJ"),
    ("Belo Horizonte","MG"),("Uberlândia","MG"),("Contagem","MG"),("Juiz de Fora","MG"),
    ("Salvador","BA"),("Feira de Santana","BA"),("Vitória da Conquista","BA"),("Camaçari","BA"),
    ("Brasília","DF"),("Taguatinga","DF"),
    ("Fortaleza","CE"),("Caucaia","CE"),("Juazeiro do Norte","CE"),("Maracanaú","CE"),
    ("Manaus","AM"),("Parintins","AM"),
    ("Curitiba","PR"),("Londrina","PR"),("Maringá","PR"),("Ponta Grossa","PR"),
    ("Porto Alegre","RS"),("Caxias do Sul","RS"),("Pelotas","RS"),("Canoas","RS"),
    ("Recife","PE"),("Olinda","PE"),("Jaboatão dos Guararapes","PE"),("Caruaru","PE"),
    ("Goiânia","GO"),("Aparecida de Goiânia","GO"),("Anápolis","GO"),
    ("Belém","PA"),("Ananindeua","PA"),("Santarém","PA"),
    ("Buriticupu","MA"),("São Luís","MA"),("Imperatriz","MA"),("Caxias","MA"),
    ("Teresina","PI"),("Parnaíba","PI"),
    ("Natal","RN"),("Mossoró","RN"),
    ("João Pessoa","PB"),("Campina Grande","PB"),
    ("Maceió","AL"),("Aracaju","SE"),("Vitória","ES"),("Vila Velha","ES"),
    ("Florianópolis","SC"),("Joinville","SC"),("Blumenau","SC"),
    ("Cuiabá","MT"),("Campo Grande","MS"),("Porto Velho","RO"),("Boa Vista","RR"),
    ("Macapá","AP"),("Rio Branco","AC"),("Palmas","TO"),
]

# Blocos de IP majoritariamente alocados ao Brasil (Telefônica, Claro, Oi, NET, Vivo, etc.)
BR_IP_PREFIXES = ["177", "187", "189", "191", "200", "201", "179", "186"]

CARGOS = [
    ("F", "201 Auxiliar de Serviços Gerais", 80.00),
    ("F", "202 Motorista", 80.00),
    ("F", "203 Vigilante", 80.00),
    ("M", "204 Assistente Administrativo", 90.00),
    ("M", "205 Técnico em Enfermagem", 90.00),
    ("M", "206 Secretário Escolar", 90.00),
    ("M", "207 Orientador(a) Social", 90.00),
    ("S", "301 Professor de Português", 110.00),
    ("S", "302 Professor de Matemática", 110.00),
    ("S", "303 Médico Clínico Geral", 110.00),
    ("S", "304 Enfermeiro(a)", 110.00),
    ("S", "305 Engenheiro Civil", 110.00),
    ("S", "306 Analista Administrativo", 110.00),
    ("S", "313 Farmacêutico(a)", 110.00),
]
NIVEL_LABEL = {"F": "Fundamental", "M": "Médio", "S": "Superior"}
LINGUAS = ["Inglês", "Espanhol"]
SEXOS = ["Masculino", "Feminino"]
ESTADOS_CIVIS = ["Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)", "União Estável"]
RACAS = ["Branca", "Parda", "Preta", "Amarela", "Indígena"]
HS_SIT = [
    "Já concluí o ensino médio.",
    "Estou cursando o ensino médio, e estou na última série.",
    "Estou cursando o ensino médio, mas não estou na última série.",
]
SCHOOLS = ["Escola pública.", "Escola privada (sem bolsa).", "Escola privada (com bolsa integral)."]


def gen_cpf() -> str:
    """Gera um CPF com dígitos verificadores válidos."""
    n = [random.randint(0, 9) for _ in range(9)]
    d1 = (sum((10 - i) * n[i] for i in range(9))) % 11
    d1 = 0 if d1 < 2 else 11 - d1
    n.append(d1)
    d2 = (sum((11 - i) * n[i] for i in range(10))) % 11
    d2 = 0 if d2 < 2 else 11 - d2
    n.append(d2)
    return "".join(map(str, n))


def br_ip() -> str:
    return f"{random.choice(BR_IP_PREFIXES)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"


def gen_phone(uf: str) -> str:
    ddds = {"SP": ["11","13","19"],"RJ":["21","22","24"],"MG":["31","32","33"],"BA":["71","73","75","77"],
            "DF":["61"],"CE":["85","88"],"AM":["92","97"],"PR":["41","42","43","44","45"],
            "RS":["51","53","54","55"],"PE":["81","87"],"GO":["62","64"],"PA":["91","93","94"],
            "MA":["98","99"],"PI":["86","89"],"RN":["84"],"PB":["83"],"AL":["82"],"SE":["79"],
            "ES":["27","28"],"SC":["47","48","49"],"MT":["65","66"],"MS":["67"],"RO":["69"],
            "RR":["95"],"AP":["96"],"AC":["68"],"TO":["63"]}
    d = random.choice(ddds.get(uf, ["11"]))
    return f"({d}) 9{random.randint(1000,9999)}-{random.randint(1000,9999)}"


def gen_birth_date() -> str:
    year = random.randint(1980, 2008)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{day:02d}/{month:02d}/{year}"


def gen_name() -> str:
    n = random.choice(PRIMEIROS) + " "
    if random.random() < 0.4:
        n += random.choice(PRIMEIROS) + " "
    n += random.choice(SOBRENOMES) + " " + random.choice(SOBRENOMES)
    return n


def gen_inscription_number() -> str:
    return f"26{random.randint(10**9, 10**10 - 1)}"[:12]


def fmt_cpf(cpf: str) -> str:
    return f"{cpf[0:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:11]}"


def pick_device() -> str:
    # 55% mobile, 45% desktop (mix realista)
    return "Mobile" if random.random() < 0.55 else "Desktop"


def random_time(hours_ago_max: int = 168) -> datetime:
    """Distribuído ao longo dos últimos N horas."""
    return datetime.now(timezone.utc) - timedelta(
        hours=random.uniform(0, hours_ago_max),
    )


def event_doc(type_: str, title: str, subtitle: str, ts: datetime, **extra) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "type": type_,
        "title": title,
        "subtitle": subtitle,
        "created_at": ts.isoformat(),
        **extra,
    }


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------
async def seed():
    print("Limpando coleções existentes…")
    await asyncio.gather(
        db.accesses.delete_many({}),
        db.registrations.delete_many({}),
        db.pix_generated.delete_many({}),
        db.pix_copied.delete_many({}),
        db.pix_downloaded.delete_many({}),
        db.events.delete_many({}),
    )

    accesses = []
    registrations = []
    pix_gen = []
    pix_cop = []
    pix_down = []
    events = []

    print("Gerando 100 visitantes que só acessaram…")
    for i in range(100):
        ts = random_time()
        city, uf = random.choice(CIDADES_BR)
        ip = br_ip()
        device = pick_device()
        page = random.choice(["/home.html","/home.html","/home.html","/edital.html","/index.html"])
        acc = {
            "id": str(uuid.uuid4()),
            "ip": ip, "city": city, "region": uf, "country": "Brasil",
            "device": device, "user_agent": "demo",
            "page": page, "referrer": "",
            "created_at": ts.isoformat(),
        }
        accesses.append(acc)
        location = f"{city}/{uf}"
        if "edital" in page:
            events.append(event_doc(
                "edital_access", "Acesso ao edital", f"{location} · {device}", ts,
                ip=ip, device=device, city=city, region=uf, page=page,
            ))
        else:
            events.append(event_doc(
                "access", f"Novo acesso {device.lower()}", location, ts,
                ip=ip, device=device, city=city, region=uf, page=page,
            ))

    print("Gerando 100 inscritos com dados completos…")
    full_inscriptions = []
    for i in range(100):
        # Cada inscrito teve pelo menos 1 acesso (home), 1 acesso cadastro, 1 inscrição
        city, uf = random.choice(CIDADES_BR)
        ip = br_ip()
        device = pick_device()
        cpf = gen_cpf()
        name = gen_name()
        email = name.lower().split()[0] + str(random.randint(10,9999)) + random.choice(["@gmail.com","@hotmail.com","@outlook.com","@yahoo.com"])
        phone = gen_phone(uf)
        birth = gen_birth_date()
        sexo = random.choice(SEXOS)
        ecivil = random.choice(ESTADOS_CIVIS)
        raca = random.choice(RACAS)
        nivel, cargo, amount = random.choice(CARGOS)

        # Linha do tempo realista: acesso home → edital → cadastro → inscrição → (opt pagar/pix)
        t_home = random_time()
        t_edital = t_home + timedelta(minutes=random.randint(1, 6))
        t_cadastro = t_edital + timedelta(minutes=random.randint(2, 10))
        t_inscricao_pg = t_cadastro + timedelta(minutes=random.randint(2, 8))
        t_inscricao = t_inscricao_pg + timedelta(minutes=random.randint(1, 5))

        loc = f"{city}/{uf}"

        accesses.append({
            "id": str(uuid.uuid4()), "ip": ip, "city": city, "region": uf, "country": "Brasil",
            "device": device, "user_agent": "demo", "page": "/home.html", "referrer": "",
            "created_at": t_home.isoformat(),
        })
        events.append(event_doc("access", f"Novo acesso {device.lower()}", loc, t_home,
                                ip=ip, device=device, city=city, region=uf, page="/home.html"))

        # 70% também acessam o edital antes
        if random.random() < 0.7:
            accesses.append({
                "id": str(uuid.uuid4()), "ip": ip, "city": city, "region": uf, "country": "Brasil",
                "device": device, "user_agent": "demo", "page": "/edital.html", "referrer": "",
                "created_at": t_edital.isoformat(),
            })
            events.append(event_doc("edital_access", "Acesso ao edital", f"{loc} · {device}", t_edital,
                                    ip=ip, device=device, city=city, region=uf, page="/edital.html"))

        # Cadastro
        accesses.append({
            "id": str(uuid.uuid4()), "ip": ip, "city": city, "region": uf, "country": "Brasil",
            "device": device, "user_agent": "demo", "page": "/cadastro.html", "referrer": "",
            "created_at": t_cadastro.isoformat(),
        })
        events.append(event_doc("inscription_started", "Inscrição iniciada",
                                f"Tela de cadastro · {loc} · {device}", t_cadastro,
                                ip=ip, device=device, city=city, region=uf, page="/cadastro.html"))

        # Seleção de cargo (inscricao.html)
        accesses.append({
            "id": str(uuid.uuid4()), "ip": ip, "city": city, "region": uf, "country": "Brasil",
            "device": device, "user_agent": "demo", "page": "/inscricao.html", "referrer": "",
            "created_at": t_inscricao_pg.isoformat(),
        })
        events.append(event_doc("inscription_form", "Cargo escolhido",
                                f"Tela de seleção de cargo · {loc} · {device}", t_inscricao_pg,
                                ip=ip, device=device, city=city, region=uf, page="/inscricao.html"))

        # Inscrição
        rid = str(uuid.uuid4())
        ins_num = gen_inscription_number()
        full_inscriptions.append({
            "rid": rid, "name": name, "cpf": cpf, "amount": amount, "ts": t_inscricao,
            "device": device, "ip": ip, "city": city, "uf": uf,
        })
        registrations.append({
            "id": rid, "inscription_number": ins_num,
            "name": name, "email": email, "cpf": cpf, "phone": phone,
            "birth_date": birth, "sex": sexo, "marital_status": ecivil, "race": raca,
            "foreign_language": random.choice(LINGUAS),
            "exam_state": uf, "exam_city": city,
            "needs_assistance": "Não", "assistance_details": "",
            "hs_situation": NIVEL_LABEL[nivel], "school_type": cargo,
            "ip": ip, "user_agent": "demo", "device": device,
            "city": city, "region": uf, "country": "Brasil",
            "status": "Aguardando pagamento", "amount": amount,
            "pix_generated": False, "pix_copied": False, "pix_downloaded": False,
            "pix_code": "", "pix_recipient": "", "pix_key": "",
            "page": "inscricao",
            "created_at": t_inscricao.isoformat(), "updated_at": t_inscricao.isoformat(),
        })
        events.append(event_doc("registration", "Inscrição enviada",
                                f"{name.upper()} · {fmt_cpf(cpf)} · Nº {ins_num}", t_inscricao,
                                device=device, city=city, region=uf))

    print("Distribuindo flows PIX:  40 sem PIX  ·  30 gerou+copiou  ·  30 gerou+copiou+baixou")
    random.shuffle(full_inscriptions)
    # 40 sem PIX: ficam em "Aguardando pagamento" (nada a fazer)
    grupo_apenas_insc = full_inscriptions[0:40]
    grupo_gen_cop = full_inscriptions[40:70]
    grupo_gen_cop_baix = full_inscriptions[70:100]

    def fmt_brl(v): return f"R$ {v:.2f}".replace(".", ",")

    for ins in grupo_gen_cop:
        t_pay = ins["ts"] + timedelta(minutes=random.randint(2, 30))
        t_gen = t_pay + timedelta(seconds=random.randint(2, 15))
        t_cop = t_gen + timedelta(seconds=random.randint(3, 90))
        loc = f"{ins['city']}/{ins['uf']}"
        pix_key = f"fsadu-buriticupu-{random.randint(10**11, 10**12 - 1)}"
        pix_code = f"00020126580014br.gov.bcb.pix0136{pix_key}5204000053039865406{ins['amount']:.2f}5802BR5919FSADU FUNDACAO SOUS6010BURITICUPU62410503***6304A1B2".replace(".", "")

        # access pagar
        accesses.append({
            "id": str(uuid.uuid4()), "ip": ins["ip"], "city": ins["city"], "region": ins["uf"], "country": "Brasil",
            "device": ins["device"], "user_agent": "demo", "page": "/pagar.html", "referrer": "",
            "created_at": t_pay.isoformat(),
        })
        events.append(event_doc("pay_screen", "Tela de pagamento aberta", f"{loc} · {ins['device']}", t_pay,
                                ip=ins["ip"], device=ins["device"], city=ins["city"], region=ins["uf"], page="/pagar.html"))

        # pix gerado
        pix_gen.append({
            "id": str(uuid.uuid4()), "registration_id": ins["rid"],
            "candidate_name": ins["name"], "pix_code": pix_code,
            "amount": ins["amount"], "recipient": "FSADU FUNDACAO SOUS · BURITICUPU", "pix_key": pix_key,
            "created_at": t_gen.isoformat(),
        })
        events.append(event_doc("pix_generated", "PIX gerado",
                                f"{ins['name'].upper()} · {fmt_brl(ins['amount'])}", t_gen))

        # pix copiado
        pix_cop.append({
            "id": str(uuid.uuid4()), "registration_id": ins["rid"],
            "candidate_name": ins["name"], "pix_code": pix_code, "amount": ins["amount"],
            "created_at": t_cop.isoformat(),
        })
        events.append(event_doc("pix_copied", "PIX copiado",
                                f"{ins['name'].upper()} · {fmt_brl(ins['amount'])}", t_cop))

        # atualiza a inscrição: status = "PIX copiado" (última ação)
        for r in registrations:
            if r["id"] == ins["rid"]:
                r["pix_generated"] = True
                r["pix_copied"] = True
                r["pix_code"] = pix_code
                r["pix_recipient"] = "FSADU FUNDACAO SOUS · BURITICUPU"
                r["pix_key"] = pix_key
                r["pix_generated_at"] = t_gen.isoformat()
                r["pix_copied_at"] = t_cop.isoformat()
                r["status"] = "PIX copiado"
                r["updated_at"] = t_cop.isoformat()
                break

    for ins in grupo_gen_cop_baix:
        t_pay = ins["ts"] + timedelta(minutes=random.randint(2, 30))
        t_gen = t_pay + timedelta(seconds=random.randint(2, 15))
        t_cop = t_gen + timedelta(seconds=random.randint(3, 60))
        t_baix = t_cop + timedelta(seconds=random.randint(5, 120))
        loc = f"{ins['city']}/{ins['uf']}"
        pix_key = f"fsadu-buriticupu-{random.randint(10**11, 10**12 - 1)}"
        pix_code = f"00020126580014br.gov.bcb.pix0136{pix_key}5204000053039865406{ins['amount']:.2f}5802BR5919FSADU FUNDACAO SOUS6010BURITICUPU62410503***6304A1B2".replace(".", "")

        accesses.append({
            "id": str(uuid.uuid4()), "ip": ins["ip"], "city": ins["city"], "region": ins["uf"], "country": "Brasil",
            "device": ins["device"], "user_agent": "demo", "page": "/pagar.html", "referrer": "",
            "created_at": t_pay.isoformat(),
        })
        events.append(event_doc("pay_screen", "Tela de pagamento aberta", f"{loc} · {ins['device']}", t_pay,
                                ip=ins["ip"], device=ins["device"], city=ins["city"], region=ins["uf"], page="/pagar.html"))

        pix_gen.append({
            "id": str(uuid.uuid4()), "registration_id": ins["rid"],
            "candidate_name": ins["name"], "pix_code": pix_code,
            "amount": ins["amount"], "recipient": "FSADU FUNDACAO SOUS · BURITICUPU", "pix_key": pix_key,
            "created_at": t_gen.isoformat(),
        })
        events.append(event_doc("pix_generated", "PIX gerado",
                                f"{ins['name'].upper()} · {fmt_brl(ins['amount'])}", t_gen))

        pix_cop.append({
            "id": str(uuid.uuid4()), "registration_id": ins["rid"],
            "candidate_name": ins["name"], "pix_code": pix_code, "amount": ins["amount"],
            "created_at": t_cop.isoformat(),
        })
        events.append(event_doc("pix_copied", "PIX copiado",
                                f"{ins['name'].upper()} · {fmt_brl(ins['amount'])}", t_cop))

        pix_down.append({
            "id": str(uuid.uuid4()), "registration_id": ins["rid"],
            "candidate_name": ins["name"], "amount": ins["amount"],
            "created_at": t_baix.isoformat(),
        })
        events.append(event_doc("pix_downloaded", "PIX baixado",
                                f"{ins['name'].upper()} · Comprovante impresso", t_baix))

        # status = última ação = "PIX baixado"
        for r in registrations:
            if r["id"] == ins["rid"]:
                r["pix_generated"] = True
                r["pix_copied"] = True
                r["pix_downloaded"] = True
                r["pix_code"] = pix_code
                r["pix_recipient"] = "FSADU FUNDACAO SOUS · BURITICUPU"
                r["pix_key"] = pix_key
                r["pix_generated_at"] = t_gen.isoformat()
                r["pix_copied_at"] = t_cop.isoformat()
                r["pix_downloaded_at"] = t_baix.isoformat()
                r["status"] = "PIX baixado"
                r["updated_at"] = t_baix.isoformat()
                break

    # Inserção em massa
    print(f"Inserindo {len(accesses)} acessos, {len(registrations)} inscrições, "
          f"{len(pix_gen)} pix-gen, {len(pix_cop)} pix-cop, {len(pix_down)} pix-baix, "
          f"{len(events)} eventos…")
    await db.accesses.insert_many(accesses)
    await db.registrations.insert_many(registrations)
    if pix_gen: await db.pix_generated.insert_many(pix_gen)
    if pix_cop: await db.pix_copied.insert_many(pix_cop)
    if pix_down: await db.pix_downloaded.insert_many(pix_down)
    await db.events.insert_many(events)
    print("✅ Seed concluído!")

    print()
    print(f"  • Acessos únicos por IP:   {len({a['ip'] for a in accesses})}")
    print(f"  • Total inscrições:        {len(registrations)}")
    print(f"  • Apenas inscritos:        {len(grupo_apenas_insc)}")
    print(f"  • Gerou + copiou:          {len(grupo_gen_cop)}")
    print(f"  • Gerou + copiou + baixou: {len(grupo_gen_cop_baix)}")


if __name__ == "__main__":
    asyncio.run(seed())
