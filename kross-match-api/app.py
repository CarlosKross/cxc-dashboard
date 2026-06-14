import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from model.match_model import MatchRequest, MatchResponse
from service.match_service import match_service

app = FastAPI(title="Kross Match API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.post("/api/kross-match/calcular", response_model=MatchResponse)
async def calcular_match(req: MatchRequest) -> MatchResponse:
    if req.tipo not in {"lager", "lupulada", "maltosa", "frutal"}:
        raise HTTPException(status_code=400, detail=f"tipo inválido: {req.tipo}")
    if req.sabor not in {"suave", "intenso"}:
        raise HTTPException(status_code=400, detail=f"sabor inválido: {req.sabor}")
    return match_service.calcular(req)


# Serve the HTML app at root — must be mounted last
_static_dir = os.path.join(os.path.dirname(__file__), "src/main/resources/static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
