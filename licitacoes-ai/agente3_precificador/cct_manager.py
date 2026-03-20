"""CRUD de CCTs (Convenções Coletivas de Trabalho)."""
import json
import logging
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import CCTS_DIR
from shared.database import upsert_cct, get_cct_ativa, listar_ccts_ativas, get_db

log = logging.getLogger("cct_manager")


def carregar_cct_arquivo(filepath: Path | str) -> dict:
    """Carrega CCT de um arquivo JSON."""
    filepath = Path(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def importar_ccts_diretorio():
    """Importa todas as CCTs do diretório data/ccts/ para o banco."""
    CCTS_DIR.mkdir(parents=True, exist_ok=True)
    count = 0

    for f in CCTS_DIR.glob("*.json"):
        try:
            dados = carregar_cct_arquivo(f)
            sindicato = dados.get("sindicato", f.stem)
            uf = dados.get("uf", "RJ")
            vigencia = dados.get("vigencia", {})

            upsert_cct(
                sindicato=sindicato,
                uf=uf,
                dados_json=dados,
                vigencia_inicio=vigencia.get("inicio"),
                vigencia_fim=vigencia.get("fim"),
                numero_registro=dados.get("registro_mte"),
            )
            count += 1
            log.info(f"CCT importada: {sindicato} ({uf})")
        except Exception as e:
            log.error(f"Erro ao importar {f.name}: {e}")

    return count


def get_piso_salarial(sindicato: str, uf: str, funcao: str) -> float | None:
    """Busca o piso salarial de uma função na CCT ativa."""
    cct = get_cct_ativa(sindicato, uf)
    if not cct:
        return None

    dados = cct.get("dados", {})
    pisos = dados.get("pisos_salariais", {})

    # Busca exata
    if funcao in pisos:
        return pisos[funcao]

    # Busca parcial (normalizada)
    funcao_norm = funcao.lower().replace(" ", "_").replace("-", "_")
    for k, v in pisos.items():
        if funcao_norm in k.lower() or k.lower() in funcao_norm:
            return v

    return None


def get_beneficios(sindicato: str, uf: str) -> dict:
    """Retorna benefícios da CCT ativa."""
    cct = get_cct_ativa(sindicato, uf)
    if not cct:
        return {}
    return cct.get("dados", {}).get("beneficios", {})


def get_adicionais(sindicato: str, uf: str) -> dict:
    """Retorna adicionais da CCT ativa."""
    cct = get_cct_ativa(sindicato, uf)
    if not cct:
        return {}
    return cct.get("dados", {}).get("adicionais", {})
