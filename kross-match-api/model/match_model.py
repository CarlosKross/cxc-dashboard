from pydantic import BaseModel
from typing import Optional


class MatchRequest(BaseModel):
    tipo: str    # lager | lupulada | maltosa | frutal
    sabor: str   # suave | intenso
    cerveza: str # pils | golden | ipa | ipa_pomelo | hazy | stout | maibock | k5 | berries


class MatchResponse(BaseModel):
    nombrePerfil: str
    tagline: str
    ratings: str
    rareza: Optional[str] = None
    collectionNumber: str = "01"
    imageUrl: Optional[str] = None        # Supabase Storage URL (se activa con env SUPABASE_STORAGE_URL)
    viralQuestion: Optional[str] = None   # Pregunta viral por arquetipo
    shareHook: Optional[str] = None       # Texto para Web Share API
