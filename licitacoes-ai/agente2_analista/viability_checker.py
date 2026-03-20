"""Verificador de viabilidade — regras de negócio sem LLM."""
import json
import logging
from datetime import datetime, date
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import CNAES_GRUPO
from shared.models import CheckViabilidade

log = logging.getLogger("viability_checker")


def _load_perfil() -> dict:
    perfil_path = Path(__file__).parent.parent / "config" / "empresa_perfil.json"
    with open(perfil_path, "r", encoding="utf-8") as f:
        return json.load(f)


def verificar_cnae(empresa_nome: str, dados_edital: dict) -> CheckViabilidade:
    """Verifica se os CNAEs da empresa atendem."""
    # Por enquanto, verifica se o objeto é compatível com os serviços
    perfil = _load_perfil()
    empresa = None
    for e in perfil["empresas"]:
        if empresa_nome.lower() in e["nome"].lower():
            empresa = e
            break

    if not empresa:
        return CheckViabilidade(
            check="cnae_compativel",
            status="alerta",
            detalhe=f"Empresa '{empresa_nome}' não encontrada no perfil",
        )

    return CheckViabilidade(
        check="cnae_compativel",
        status="ok",
        detalhe=f"{empresa['nome']} possui CNAEs: {', '.join(empresa['cnaes'])}",
    )


def verificar_sancao(empresa_nome: str, esfera: str) -> CheckViabilidade:
    """Verifica se há sanção ativa que impeça participação."""
    perfil = _load_perfil()
    for e in perfil["empresas"]:
        if empresa_nome.lower() in e["nome"].lower():
            restricoes = e.get("restricoes", {})
            sancao = restricoes.get("sancao_agu")
            if sancao and sancao.get("ativa"):
                vigencia = sancao.get("vigencia_ate", "")
                try:
                    dt_vigencia = datetime.strptime(vigencia, "%Y-%m-%d").date()
                    if dt_vigencia > date.today():
                        if esfera == "federal":
                            return CheckViabilidade(
                                check="sancao_ativa",
                                status="falha",
                                detalhe=f"Sanção AGU ativa até {vigencia}. Órgão FEDERAL — IMPEDIDA de participar.",
                            )
                        else:
                            return CheckViabilidade(
                                check="sancao_ativa",
                                status="alerta",
                                detalhe=f"Sanção AGU ativa até {vigencia}, mas órgão {esfera} — pode participar.",
                            )
                except ValueError:
                    pass

    return CheckViabilidade(
        check="sancao_ativa",
        status="ok",
        detalhe="Sem sanções ativas",
    )


def verificar_uf(empresa_nome: str, uf_edital: str) -> CheckViabilidade:
    """Verifica se a empresa atua na UF do edital."""
    perfil = _load_perfil()
    for e in perfil["empresas"]:
        if empresa_nome.lower() in e["nome"].lower():
            ufs = e.get("uf_atuacao", [])
            if uf_edital in ufs:
                return CheckViabilidade(
                    check="uf_atuacao",
                    status="ok",
                    detalhe=f"{e['nome']} atua em {uf_edital}",
                )
            else:
                return CheckViabilidade(
                    check="uf_atuacao",
                    status="alerta",
                    detalhe=f"{e['nome']} não atua em {uf_edital} (atua em: {', '.join(ufs)})",
                )

    return CheckViabilidade(
        check="uf_atuacao",
        status="alerta",
        detalhe=f"Empresa não encontrada no perfil",
    )


def verificar_atestados(empresa_nome: str, atestados_exigidos: list[str]) -> CheckViabilidade:
    """Verifica se a empresa possui atestados compatíveis."""
    if not atestados_exigidos:
        return CheckViabilidade(
            check="atestados",
            status="ok",
            detalhe="Sem exigências específicas de atestado",
        )

    perfil = _load_perfil()
    for e in perfil["empresas"]:
        if empresa_nome.lower() in e["nome"].lower():
            disponiveis = [a.lower() for a in e.get("atestados_disponiveis", [])]
            faltantes = []
            for exigido in atestados_exigidos:
                match = any(
                    any(palavra in disp for palavra in exigido.lower().split()[:3])
                    for disp in disponiveis
                )
                if not match:
                    faltantes.append(exigido)

            if not faltantes:
                return CheckViabilidade(
                    check="atestados",
                    status="ok",
                    detalhe="Atestados disponíveis compatíveis",
                )
            else:
                return CheckViabilidade(
                    check="atestados",
                    status="alerta",
                    detalhe=f"Possível falta de atestado: {'; '.join(faltantes[:3])}",
                )

    return CheckViabilidade(
        check="atestados",
        status="alerta",
        detalhe="Empresa não encontrada no perfil",
    )


def verificar_prazo(data_abertura: str) -> CheckViabilidade:
    """Verifica se há tempo suficiente para preparar proposta."""
    if not data_abertura:
        return CheckViabilidade(
            check="prazo_proposta",
            status="alerta",
            detalhe="Data de abertura não informada",
        )

    try:
        dt = datetime.fromisoformat(data_abertura.replace("Z", "+00:00"))
        dias = (dt.date() - date.today()).days

        if dias < 0:
            return CheckViabilidade(
                check="prazo_proposta",
                status="falha",
                detalhe=f"Prazo já encerrado ({dias} dias atrás)",
            )
        elif dias < 3:
            return CheckViabilidade(
                check="prazo_proposta",
                status="alerta",
                detalhe=f"Prazo curto: apenas {dias} dia(s) úteis",
            )
        else:
            return CheckViabilidade(
                check="prazo_proposta",
                status="ok",
                detalhe=f"{dias} dias até abertura",
            )
    except (ValueError, TypeError):
        return CheckViabilidade(
            check="prazo_proposta",
            status="alerta",
            detalhe=f"Data não parseável: {data_abertura}",
        )


def verificar_viabilidade(
    empresa_nome: str,
    uf_edital: str,
    esfera: str,
    data_abertura: str = None,
    atestados_exigidos: list[str] = None,
) -> dict:
    """Executa todos os checks e retorna parecer consolidado.

    Returns:
        {
            "parecer": "go" | "nogo" | "go_com_ressalvas",
            "checks": [CheckViabilidade],
            "motivo_nogo": str | None
        }
    """
    checks = [
        verificar_cnae(empresa_nome, {}),
        verificar_sancao(empresa_nome, esfera),
        verificar_uf(empresa_nome, uf_edital),
        verificar_atestados(empresa_nome, atestados_exigidos or []),
        verificar_prazo(data_abertura),
    ]

    falhas = [c for c in checks if c.status == "falha"]
    alertas = [c for c in checks if c.status == "alerta"]

    if falhas:
        motivo = "; ".join(c.detalhe for c in falhas)
        return {
            "parecer": "nogo",
            "checks": [c.model_dump() for c in checks],
            "motivo_nogo": motivo,
        }
    elif alertas:
        return {
            "parecer": "go_com_ressalvas",
            "checks": [c.model_dump() for c in checks],
            "motivo_nogo": None,
        }
    else:
        return {
            "parecer": "go",
            "checks": [c.model_dump() for c in checks],
            "motivo_nogo": None,
        }
