"""Rotas de configuração."""
import json
from pathlib import Path
from fastapi import APIRouter

router = APIRouter(prefix="/api/config", tags=["config"])

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


@router.get("")
def get_config():
    settings = {}
    for f in ("empresa_perfil.json", "concorrentes.json"):
        fpath = CONFIG_DIR / f
        if fpath.exists():
            with open(fpath, "r", encoding="utf-8") as fp:
                settings[f.replace(".json", "")] = json.load(fp)
    return settings


@router.put("")
def update_config(body: dict):
    for key in ("empresa_perfil", "concorrentes"):
        if key in body:
            fpath = CONFIG_DIR / f"{key}.json"
            with open(fpath, "w", encoding="utf-8") as fp:
                json.dump(body[key], fp, ensure_ascii=False, indent=2)
    return {"ok": True}
