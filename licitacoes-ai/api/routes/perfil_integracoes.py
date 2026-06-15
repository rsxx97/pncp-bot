"""Integrações Trello + Drive por tenant_empresa.

Cada empresa do tenant tem seu próprio board Trello (api_key/token/board_id).
Drive usa Service Account global do SaaS — cada empresa só registra folder_id.
"""
import os
import sys
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from api.deps import get_connection
from api.routes.auth import require_tenant

router = APIRouter(prefix="/api/perfil/empresas", tags=["integracoes"])


def _get_empresa_do_tenant(empresa_id: int, tenant_id: int) -> dict:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM tenant_empresas WHERE id = ? AND tenant_id = ? AND ativo = 1",
        (empresa_id, tenant_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Empresa não encontrada no seu cadastro")
    return dict(row)


def _mascarar(valor: str | None) -> str | None:
    if not valor:
        return None
    if len(valor) <= 6:
        return "***"
    return valor[:4] + "…" + valor[-3:]


class IntegracoesUpdate(BaseModel):
    trello_api_key: str | None = None
    trello_token: str | None = None
    trello_board_id: str | None = None
    drive_folder_id: str | None = None


@router.get("/{empresa_id}/integracoes")
def get_integracoes(empresa_id: int, tenant: dict = Depends(require_tenant)):
    emp = _get_empresa_do_tenant(empresa_id, tenant["id"])
    return {
        "empresa_id": empresa_id,
        "trello_api_key": _mascarar(emp.get("trello_api_key")),
        "trello_api_key_set": bool(emp.get("trello_api_key")),
        "trello_token": _mascarar(emp.get("trello_token")),
        "trello_token_set": bool(emp.get("trello_token")),
        "trello_board_id": emp.get("trello_board_id"),
        "drive_folder_id": emp.get("drive_folder_id"),
        "drive_sa_disponivel": bool(os.environ.get("GOOGLE_SA_JSON")),
    }


@router.put("/{empresa_id}/integracoes")
def put_integracoes(empresa_id: int, body: IntegracoesUpdate, tenant: dict = Depends(require_tenant)):
    _get_empresa_do_tenant(empresa_id, tenant["id"])
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return {"ok": True, "atualizados": 0}
    conn = get_connection()
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [empresa_id]
    conn.execute(f"UPDATE tenant_empresas SET {sets} WHERE id = ?", vals)
    conn.commit()
    return {"ok": True, "atualizados": len(updates)}


@router.post("/{empresa_id}/integracoes/testar-trello")
def testar_trello(empresa_id: int, tenant: dict = Depends(require_tenant)):
    emp = _get_empresa_do_tenant(empresa_id, tenant["id"])
    k = emp.get("trello_api_key")
    t = emp.get("trello_token")
    board = emp.get("trello_board_id")
    if not (k and t and board):
        raise HTTPException(400, "Faltam credenciais Trello (api_key, token, board_id)")
    try:
        r = httpx.get(
            f"https://api.trello.com/1/boards/{board}",
            params={"key": k, "token": t, "fields": "id,name,url"},
            timeout=15,
        )
        if r.status_code != 200:
            raise HTTPException(400, f"Trello retornou {r.status_code}: {r.text[:200]}")
        info = r.json()
        listas = httpx.get(
            f"https://api.trello.com/1/boards/{board}/lists",
            params={"key": k, "token": t, "fields": "id,name", "filter": "open"},
            timeout=15,
        ).json()
        return {
            "ok": True,
            "board_nome": info.get("name"),
            "board_url": info.get("url"),
            "listas": [{"id": l["id"], "name": l["name"]} for l in listas],
        }
    except httpx.HTTPError as e:
        raise HTTPException(400, f"Erro ao conectar no Trello: {e}")


@router.post("/{empresa_id}/integracoes/testar-drive")
def testar_drive(empresa_id: int, tenant: dict = Depends(require_tenant)):
    emp = _get_empresa_do_tenant(empresa_id, tenant["id"])
    folder = emp.get("drive_folder_id")
    if not folder:
        raise HTTPException(400, "Empresa sem drive_folder_id configurado")
    sa_path = os.environ.get("GOOGLE_SA_JSON")
    if not sa_path or not Path(sa_path).exists():
        raise HTTPException(503, "Service Account Drive não configurado no servidor (GOOGLE_SA_JSON)")
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        raise HTTPException(503, "Dependências google ausentes (google-auth, google-api-python-client)")
    creds = service_account.Credentials.from_service_account_file(
        sa_path, scopes=["https://www.googleapis.com/auth/drive"]
    )
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    try:
        info = svc.files().get(fileId=folder, fields="id,name,webViewLink").execute()
        return {"ok": True, "pasta_nome": info.get("name"), "url": info.get("webViewLink")}
    except Exception as e:
        raise HTTPException(400, f"Erro ao acessar pasta no Drive: {e}")


class SincronizarEditalRequest(BaseModel):
    pncp_id: str
    lista_id: str | None = None
    label_color: str | None = None


@router.post("/{empresa_id}/sincronizar-edital")
def sincronizar_edital(
    empresa_id: int,
    body: SincronizarEditalRequest,
    tenant: dict = Depends(require_tenant),
):
    """Cria card no Trello + pasta no Drive para o edital. Atualiza editais.trello_card_id / drive_folder_id."""
    emp = _get_empresa_do_tenant(empresa_id, tenant["id"])

    conn = get_connection()
    edital_row = conn.execute(
        "SELECT * FROM editais WHERE pncp_id = ?", (body.pncp_id,)
    ).fetchone()
    if not edital_row:
        raise HTTPException(404, "Edital não encontrado")
    edital = dict(edital_row)

    resultado = {"trello_card_id": None, "drive_folder_id": None, "warnings": []}

    k = emp.get("trello_api_key")
    t = emp.get("trello_token")
    board = emp.get("trello_board_id")
    if k and t and board:
        lista_id = body.lista_id
        if not lista_id:
            listas = httpx.get(
                f"https://api.trello.com/1/boards/{board}/lists",
                params={"key": k, "token": t, "filter": "open"},
                timeout=15,
            ).json()
            lista_id = listas[0]["id"] if listas else None
        if not lista_id:
            resultado["warnings"].append("Board sem listas, card não criado")
        else:
            valor = edital.get("valor_estimado") or 0
            objeto = (edital.get("objeto") or "")[:120]
            nome = f"[{edital.get('uf', '?')}] {edital.get('orgao_nome', '?')[:50]} — R$ {valor:,.0f}"
            desc = (
                f"**Objeto:** {objeto}\n\n"
                f"**Órgão:** {edital.get('orgao_nome', '')}\n"
                f"**UF:** {edital.get('uf', '')} · **Município:** {edital.get('municipio', '')}\n"
                f"**Modalidade:** {edital.get('modalidade', '')}\n"
                f"**Valor estimado:** R$ {valor:,.2f}\n"
                f"**Abertura:** {edital.get('data_abertura', '-')}\n"
                f"**Encerramento:** {edital.get('data_encerramento', '-')}\n\n"
                f"**Link:** {edital.get('link_edital', '')}\n"
                f"**PNCP ID:** {edital.get('pncp_id')}"
            )
            card_params = {"key": k, "token": t, "idList": lista_id, "name": nome, "desc": desc, "pos": "bottom"}
            if edital.get("data_encerramento"):
                card_params["due"] = edital["data_encerramento"]
            r = httpx.post("https://api.trello.com/1/cards", params=card_params, timeout=15)
            if r.status_code in (200, 201):
                card = r.json()
                resultado["trello_card_id"] = card["id"]
                if body.label_color:
                    labels = httpx.get(
                        f"https://api.trello.com/1/boards/{board}/labels",
                        params={"key": k, "token": t},
                        timeout=15,
                    ).json()
                    alvo = next((l for l in labels if l["color"] == body.label_color), None)
                    if alvo:
                        httpx.post(
                            f"https://api.trello.com/1/cards/{card['id']}/idLabels",
                            params={"key": k, "token": t, "value": alvo["id"]},
                            timeout=15,
                        )
            else:
                resultado["warnings"].append(f"Trello erro {r.status_code}: {r.text[:120]}")
    else:
        resultado["warnings"].append("Trello não configurado pra essa empresa")

    drive_root = emp.get("drive_folder_id")
    sa_path = os.environ.get("GOOGLE_SA_JSON")
    if drive_root and sa_path and Path(sa_path).exists():
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            creds = service_account.Credentials.from_service_account_file(
                sa_path, scopes=["https://www.googleapis.com/auth/drive"]
            )
            svc = build("drive", "v3", credentials=creds, cache_discovery=False)
            nome_pasta = f"{edital.get('orgao_nome', 'Orgao')[:60]}_{edital['pncp_id']}".replace("/", "-")
            file_metadata = {
                "name": nome_pasta,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [drive_root],
            }
            folder = svc.files().create(body=file_metadata, fields="id,webViewLink").execute()
            resultado["drive_folder_id"] = folder["id"]
        except Exception as e:
            resultado["warnings"].append(f"Drive erro: {e}")
    else:
        if not drive_root:
            resultado["warnings"].append("Drive não configurado pra essa empresa")
        elif not sa_path:
            resultado["warnings"].append("Service Account não configurado no servidor")

    conn.execute(
        "UPDATE editais SET trello_card_id = COALESCE(?, trello_card_id), drive_folder_id = COALESCE(?, drive_folder_id), tenant_empresa_id = ? WHERE pncp_id = ?",
        (resultado["trello_card_id"], resultado["drive_folder_id"], empresa_id, body.pncp_id),
    )
    conn.commit()

    return resultado
