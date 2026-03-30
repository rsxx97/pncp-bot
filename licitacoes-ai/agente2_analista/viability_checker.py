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


def verificar_prazo(data_abertura: str, data_encerramento: str = None) -> CheckViabilidade:
    """Verifica se há tempo suficiente para preparar proposta.

    Usa data_encerramento (prazo final) como referência principal.
    Se não tiver, usa data_abertura como fallback.
    """
    data_ref = data_encerramento or data_abertura
    if not data_ref:
        return CheckViabilidade(
            check="prazo_proposta",
            status="alerta",
            detalhe="Data de encerramento não informada",
        )

    try:
        dt = datetime.fromisoformat(data_ref.replace("Z", "+00:00"))
        dias = (dt.date() - date.today()).days

        if dias < 0:
            return CheckViabilidade(
                check="prazo_proposta",
                status="falha",
                detalhe=f"Prazo já encerrado ({abs(dias)} dia(s) atrás)",
            )
        elif dias < 3:
            return CheckViabilidade(
                check="prazo_proposta",
                status="alerta",
                detalhe=f"Prazo curto: apenas {dias} dia(s) restantes",
            )
        else:
            return CheckViabilidade(
                check="prazo_proposta",
                status="ok",
                detalhe=f"{dias} dias até encerramento",
            )
    except (ValueError, TypeError):
        return CheckViabilidade(
            check="prazo_proposta",
            status="alerta",
            detalhe=f"Data não parseável: {data_ref}",
        )


def rankear_empresas(
    objeto: str,
    uf_edital: str,
    esfera: str,
    data_abertura: str = None,
    data_encerramento: str = None,
    atestados_exigidos: list[str] = None,
) -> list[dict]:
    """Avalia TODAS as empresas do grupo contra o edital e retorna ranking.

    Para cada empresa calcula:
    - Match de serviço (objeto do edital vs serviços da empresa)
    - Match de atestados (exigidos vs disponíveis)
    - Viabilidade (sanções, UF, prazo)
    - Vantagem fiscal (desonerada, regime, RAT)

    Returns:
        Lista rankeada (melhor primeiro):
        [{"nome", "score", "viavel", "motivo", "checks", "vantagens"}]
    """
    perfil = _load_perfil()
    resultado = []
    objeto_lower = (objeto or "").lower()

    for emp in perfil["empresas"]:
        nome = emp["nome"]
        score = 0
        motivos = []
        vantagens = []

        # 1. Match de serviço (0-40)
        servicos = [s.lower() for s in emp.get("servicos", [])]
        match_servico = any(s in objeto_lower for s in servicos)
        # Também checa keywords mais amplas
        keywords_map = {
            "limpeza": ["limpeza", "conservação", "asseio", "facilities", "predial", "zeladoria"],
            "segurança": ["vigilância", "segurança", "vigia", "brigada", "bombeiro", "controlador de acesso"],
            "administrativo": ["apoio administrativo", "recepção", "portaria", "copeira", "copeiragem"],
            "manutenção": ["manutenção", "elétrica", "hidráulica"],
            "engenharia": ["engenharia", "construção", "reforma", "obra", "infraestrutura"],
        }
        for categoria, keywords in keywords_map.items():
            if any(k in objeto_lower for k in keywords):
                if any(k in " ".join(servicos) for k in keywords):
                    match_servico = True
                    break

        if match_servico:
            score += 40
            motivos.append("Servico compativel")
        else:
            score += 5
            motivos.append("Servico nao e core")

        # 2. Match de atestados (0-25)
        atestados_disp = [a.lower() for a in emp.get("atestados_disponiveis", [])]
        if not atestados_exigidos:
            score += 20
            motivos.append("Sem exigencia de atestado")
        else:
            matches = 0
            faltantes = []
            for exigido in atestados_exigidos:
                ex_lower = exigido.lower()
                found = any(
                    any(p in disp for p in ex_lower.split()[:3])
                    for disp in atestados_disp
                )
                if found:
                    matches += 1
                else:
                    faltantes.append(exigido[:50])

            if matches == len(atestados_exigidos):
                score += 25
                vantagens.append("Todos atestados disponiveis")
            elif matches > 0:
                score += int(15 * matches / len(atestados_exigidos))
                motivos.append(f"Atestado faltante: {'; '.join(faltantes[:2])}")
            else:
                score += 0
                motivos.append(f"Sem atestados compativeis")

        # 3. Vantagem fiscal (0-20)
        if emp.get("desonerada"):
            score += 10
            vantagens.append("Desonerada (INSS 10%)")
        if emp.get("regime_tributario") == "lucro_real":
            pis = emp.get("pis_efetivo_pct", 1.65)
            cofins = emp.get("cofins_efetivo_pct", 7.6)
            if pis < 1.0 and cofins < 4.0:
                score += 10
                vantagens.append(f"PIS {pis}% + COFINS {cofins}% (creditos)")
            else:
                score += 5
        rat = emp.get("rat_ajustado_pct", emp.get("rat_pct", 3.0))
        if rat <= 1.5:
            score += 5
            vantagens.append(f"RAT baixo ({rat}%)")

        # 4. Viabilidade (pode zerar score)
        viavel = True
        checks_resultado = []

        # Sanção
        check_sancao = verificar_sancao(nome, esfera)
        checks_resultado.append(check_sancao)
        if check_sancao.status == "falha":
            viavel = False
            score = 0
            motivos = [check_sancao.detalhe]

        # UF
        check_uf = verificar_uf(nome, uf_edital)
        checks_resultado.append(check_uf)
        if check_uf.status == "falha":
            viavel = False
            score = 0

        # Prazo
        check_prazo = verificar_prazo(data_abertura, data_encerramento)
        checks_resultado.append(check_prazo)
        if check_prazo.status == "falha":
            viavel = False
            score = 0

        resultado.append({
            "nome": nome,
            "score": min(score, 100),
            "viavel": viavel,
            "motivo": "; ".join(motivos),
            "vantagens": vantagens,
            "regime": emp.get("regime_tributario", ""),
            "desonerada": emp.get("desonerada", False),
            "checks": [c.model_dump() for c in checks_resultado],
        })

    # Ordena: viáveis primeiro, depois por score desc
    resultado.sort(key=lambda x: (x["viavel"], x["score"]), reverse=True)

    log.info(f"Ranking empresas: {[(r['nome'], r['score'], r['viavel']) for r in resultado]}")
    return resultado


def verificar_viabilidade(
    empresa_nome: str,
    uf_edital: str,
    esfera: str,
    data_abertura: str = None,
    data_encerramento: str = None,
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
        verificar_prazo(data_abertura, data_encerramento),
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
