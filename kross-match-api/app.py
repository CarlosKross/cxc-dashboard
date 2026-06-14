import os
import sys
import json
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from model.match_model import MatchRequest, MatchResponse
from service.match_service import match_service

app = FastAPI(title="Kross Match API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

_VALID_TIPOS = {"lager", "lupulada", "maltosa", "frutal"}
_VALID_SABORES = {"suave", "intenso"}


@app.post("/api/kross-match/calcular", response_model=MatchResponse)
async def calcular_match(req: MatchRequest) -> MatchResponse:
    if req.tipo not in _VALID_TIPOS:
        raise HTTPException(status_code=400, detail=f"tipo inválido: {req.tipo}")
    if req.sabor not in _VALID_SABORES:
        raise HTTPException(status_code=400, detail=f"sabor inválido: {req.sabor}")
    return match_service.calcular(req)


@app.post("/api/kross-match/event")
async def track_event(payload: dict) -> Response:
    """Recibe eventos de analytics. En producción escribe a Supabase analytics_events."""
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr, flush=True)
    return Response(status_code=204)


# Serve el HTML de la app al final — debe ir después de las rutas API
_static_dir = os.path.join(os.path.dirname(__file__), "src/main/resources/static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
