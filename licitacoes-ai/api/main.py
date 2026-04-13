"""FastAPI app principal — serve API + React SPA."""
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.database import init_db
from api.routes import dashboard, editais, concorrentes, config, auth, perfil, pregoes, lances_robot, alertas

log = logging.getLogger("api")

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Licitacoes AI", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas API
app.include_router(dashboard.router)
app.include_router(editais.router)
app.include_router(concorrentes.router)
app.include_router(config.router)
app.include_router(auth.router)
app.include_router(perfil.router)
app.include_router(pregoes.router)
app.include_router(lances_robot.router)
app.include_router(alertas.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "licitacoes-ai"}


@app.on_event("startup")
def startup():
    init_db()
    log.info("API iniciada")


# Rota raiz — serve index.html
@app.get("/")
async def serve_index():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return HTMLResponse("<h1>Licitacoes AI</h1><p>Execute: cd frontend && npm run build</p>")


# Servir assets do build React
ASSETS_DIR = STATIC_DIR / "assets"
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


# Catch 404 — serve index.html para React Router (SPA fallback)
@app.exception_handler(StarletteHTTPException)
async def spa_fallback(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404 and not request.url.path.startswith("/api/"):
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
    return HTMLResponse(content=f'{{"detail":"{exc.detail}"}}', status_code=exc.status_code,
                        media_type="application/json")
