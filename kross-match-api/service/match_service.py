import os
from typing import Optional
from model.match_model import MatchRequest, MatchResponse

# Cuando se configura SUPABASE_STORAGE_URL, las imágenes se sirven desde Supabase Storage.
# Ej: https://xyz.supabase.co/storage/v1/object/public/archetypes
_STORAGE_BASE = os.getenv("SUPABASE_STORAGE_URL", "").rstrip("/")


def _img(slug: str) -> Optional[str]:
    """Construye URL de imagen desde Supabase Storage. None si el env no está configurado."""
    return f"{_STORAGE_BASE}/{slug}-male.png" if _STORAGE_BASE else None


# 18 perfiles mapeados a (tipo)_(sabor)_(cerveza)
# Slugs de imagen siguen la estructura del JSON de diseño:
# /archetypes/{slug}-male.png | /archetypes/{slug}-female.png
PERFILES: dict[str, dict] = {
    "lager_suave_pils": {
        "nombrePerfil": "KROSS PILS",
        "tagline": "Sin rodeos, sin excesos. La pureza no necesita explicación.",
        "ratings": "🎯 PRECISIÓN  96%\n🍺 PUREZA  98%\n⚡ CLARIDAD  94%",
        "rareza": None,
        "collectionNumber": "01",
        "imageUrl": _img("purista"),
        "viralQuestion": "¿Quién es el Purista de tu grupo?",
        "shareHook": "Mi match perfecto es KROSS PILS. Sin rodeos, sin excesos. ¿Y el tuyo? #KrossMatch #Krossbar",
    },
    "lager_suave_golden": {
        "nombrePerfil": "KROSS GOLDEN",
        "tagline": "Ni extremos ni compromisos. Tu equilibrio une al grupo.",
        "ratings": "⚖️ BALANCE  99%\n🤝 ARMONÍA  95%\n🌟 PRESENCIA  90%",
        "rareza": None,
        "collectionNumber": "02",
        "imageUrl": _img("equilibrado"),
        "viralQuestion": "¿Quién es el Equilibrado de tu grupo?",
        "shareHook": "Mi match perfecto es KROSS GOLDEN. Ni extremos ni compromisos. #KrossMatch #Krossbar",
    },
    "lager_intenso_pils": {
        "nombrePerfil": "KROSS PILS",
        "tagline": "Ideas simples en experiencias memorables.",
        "ratings": "🌿 CREATIVIDAD  97%\n🧪 INNOVACIÓN  94%\n🌱 EXPLORACIÓN  99%",
        "rareza": "LEGENDARIO · TOP 5%",
        "collectionNumber": "03",
        "imageUrl": _img("alquimista-verde"),
        "viralQuestion": "¿Quién convierte lo simple en memorable?",
        "shareHook": "Soy El Alquimista Verde de Kross. Ideas simples en experiencias memorables. #KrossMatch #Krossbar",
    },
    "lager_intenso_golden": {
        "nombrePerfil": "KROSS GOLDEN",
        "tagline": "La calma es tu superpoder. La perfección está en lo ordinario.",
        "ratings": "🧘 CALMA  98%\n💧 CLARIDAD  95%\n🌊 PROFUNDIDAD  97%",
        "rareza": "ÉPICO · TOP 8%",
        "collectionNumber": "04",
        "imageUrl": _img("zen"),
        "viralQuestion": "¿Quién es el más calmado de tu grupo?",
        "shareHook": "Soy El Zen de Kross Golden. La calma es mi superpoder. #KrossMatch #Krossbar",
    },
    "lupulada_suave_ipa": {
        "nombrePerfil": "KROSS IPA",
        "tagline": "El amargor tropical y la actitud son tu firma personal.",
        "ratings": "🍊 ACTITUD  96%\n🔥 INTENSIDAD  92%\n💥 ORIGINALIDAD  95%",
        "rareza": None,
        "collectionNumber": "05",
        "imageUrl": _img("rebelde-citrico"),
        "viralQuestion": "¿Quién es el Rebelde Cítrico de tu grupo?",
        "shareHook": "Soy El Rebelde Cítrico de Kross IPA. El amargor tropical es mi firma. #KrossMatch #Krossbar",
    },
    "lupulada_intenso_ipa": {
        "nombrePerfil": "KROSS IPA",
        "tagline": "Directo, sin filtros. Tu presencia se siente antes de que llegues.",
        "ratings": "🎸 CARÁCTER  99%\n⚡ INTENSIDAD  98%\n🔊 IMPACTO  97%",
        "rareza": "ÉPICO · TOP 9%",
        "collectionNumber": "06",
        "imageUrl": _img("rockero"),
        "viralQuestion": "¿Quién es el Rockero de tu grupo?",
        "shareHook": "Soy El Rockero de Kross IPA. Directo, sin filtros, sin excusas. #KrossMatch #Krossbar",
    },
    "lupulada_suave_ipa_pomelo": {
        "nombrePerfil": "KROSS IPA POMELO",
        "tagline": "Elegiste la IPA más premiada del mundo. Clase antes de que existiera.",
        "ratings": "🏆 SOFISTICACIÓN  96%\n🍋 ACIDEZ  98%\n💎 RAREZA  94%",
        "rareza": "ÉPICO · TOP 10%",
        "collectionNumber": "07",
        "imageUrl": _img("citrus-supremo"),
        "viralQuestion": "¿Quién ya sabía lo mejor antes de que existiera?",
        "shareHook": "Soy El Citrus Supremo de Kross IPA Pomelo. La IPA más premiada del mundo. #KrossMatch #Krossbar",
    },
    "lupulada_intenso_ipa_pomelo": {
        "nombrePerfil": "KROSS IPA POMELO",
        "tagline": "El amargor perfecto que muy pocos saben apreciar.",
        "ratings": "⭐ BRILLANTEZ  99%\n🌺 TROPICAL  97%\n💫 RAREZA  98%",
        "rareza": "LEGENDARIO · TOP 7%",
        "collectionNumber": "08",
        "imageUrl": _img("astro-tropical"),
        "viralQuestion": "¿Quién brilla distinto en tu grupo?",
        "shareHook": "Soy El Astro Tropical de Kross IPA Pomelo. Brillante e inesperado. #KrossMatch #Krossbar",
    },
    "lupulada_suave_hazy": {
        "nombrePerfil": "KROSS HAZY LAGER",
        "tagline": "La complejidad inesperada te atrae. Siempre al próximo horizonte.",
        "ratings": "🌴 AVENTURA  97%\n🔍 CURIOSIDAD  95%\n🌊 FRESCURA  99%",
        "rareza": None,
        "collectionNumber": "09",
        "imageUrl": _img("explorador-tropical"),
        "viralQuestion": "¿Quién siempre va al próximo horizonte?",
        "shareHook": "Soy El Explorador Tropical de Kross Hazy. La frescura compleja que te atrapa. #KrossMatch #Krossbar",
    },
    "lupulada_intenso_hazy": {
        "nombrePerfil": "KROSS HAZY LAGER",
        "tagline": "Intensa, atrevida y difícil de olvidar.",
        "ratings": "🌶️ INTENSIDAD  10/10\n🍊 EXPLOSIÓN  10/10\n🔥 RAREZA  9/10",
        "rareza": "LEGENDARIO · TOP 8%",
        "collectionNumber": "10",
        "imageUrl": _img("salvaje"),
        "viralQuestion": "¿Quién explota el paladar de tu grupo?",
        "shareHook": "Soy El Salvaje de Kross Hazy. Intenso, atrevido y difícil de olvidar. #KrossMatch #Krossbar",
    },
    "maltosa_suave_stout": {
        "nombrePerfil": "KROSS STOUT",
        "tagline": "La complejidad es tu lenguaje natural. Aprecias los detalles oscuros.",
        "ratings": "📚 PROFUNDIDAD  98%\n🌙 ELEGANCIA  95%\n🧠 PERSPECTIVA  97%",
        "rareza": None,
        "collectionNumber": "11",
        "imageUrl": _img("erudito-nocturno"),
        "viralQuestion": "¿Quién es el más profundo de tu grupo?",
        "shareHook": "Soy El Erudito Nocturno de Kross Stout. La complejidad es mi idioma. #KrossMatch #Krossbar",
    },
    "maltosa_intenso_stout": {
        "nombrePerfil": "KROSS STOUT",
        "tagline": "Prendes la parrilla y cuentas las mejores historias.",
        "ratings": "🔥 CARÁCTER  99%\n🥩 INTENSIDAD  97%\n🌿 TRADICIÓN  96%",
        "rareza": "ÉPICO · TOP 7%",
        "collectionNumber": "12",
        "imageUrl": _img("guardian-fuego"),
        "viralQuestion": "¿Quién prende la parrilla en tu grupo?",
        "shareHook": "Soy El Guardián del Fuego de Kross Stout. Humo y carácter en cada sorbo. #KrossMatch #Krossbar",
    },
    "maltosa_suave_maibock": {
        "nombrePerfil": "KROSS MAIBOCK",
        "tagline": "La tradición bien ejecutada nunca falla.",
        "ratings": "🏛️ TRADICIÓN  98%\n✨ ESTILO  94%\n🎯 CONSISTENCIA  96%",
        "rareza": None,
        "collectionNumber": "13",
        "imageUrl": _img("tradicionalista"),
        "viralQuestion": "¿Quién es el más clásico de tu grupo?",
        "shareHook": "Soy El Tradicionalista de Kross Maibock. La tradición bien ejecutada nunca falla. #KrossMatch #Krossbar",
    },
    "maltosa_intenso_maibock": {
        "nombrePerfil": "KROSS MAIBOCK",
        "tagline": "Robusto, tostado. Tradición y fuego en cada sorbo.",
        "ratings": "⚔️ FORTALEZA  99%\n🔥 FUEGO  97%\n🏆 CARÁCTER  98%",
        "rareza": "LEGENDARIO · TOP 6%",
        "collectionNumber": "14",
        "imageUrl": _img("vikingo"),
        "viralQuestion": "¿Quién es el Vikingo de tu grupo?",
        "shareHook": "Soy El Vikingo de Kross Maibock. Robusto, tostado, indetenible. #KrossMatch #Krossbar",
    },
    "maltosa_suave_k5": {
        "nombrePerfil": "KROSS K5",
        "tagline": "24 medallas mundiales no mienten. La más premiada de Chile.",
        "ratings": "🥇 MAESTRÍA  99%\n🧪 COMPLEJIDAD  97%\n🏆 LEGADO  98%",
        "rareza": "LEGENDARIO · TOP 6%",
        "collectionNumber": "15",
        "imageUrl": _img("maestro"),
        "viralQuestion": "¿Quién tiene el paladar más refinado?",
        "shareHook": "Soy El Maestro de Kross K5. 24 medallas mundiales no mienten. #KrossMatch #Krossbar",
    },
    "maltosa_intenso_k5": {
        "nombrePerfil": "KROSS K5",
        "tagline": "La tradición con un giro de fuego. La combinación más osada.",
        "ratings": "💪 POTENCIA  100%\n🔥 COMPLEJIDAD  99%\n💎 RAREZA  98%",
        "rareza": "LEGENDARIO · TOP 5%",
        "collectionNumber": "16",
        "imageUrl": _img("indomable"),
        "viralQuestion": "¿Quién nunca acepta lo ordinario?",
        "shareHook": "Soy El Indomable de Kross K5. La combinación más osada. #KrossMatch #Krossbar",
    },
    "frutal_suave_berries": {
        "nombrePerfil": "KROSS BERRIES",
        "tagline": "La vida es demasiado corta para lo ordinario. Eres especial y lo sabes.",
        "ratings": "🍓 SENSIBILIDAD  98%\n🌸 DULZURA  97%\n✨ SINGULARIDAD  95%",
        "rareza": None,
        "collectionNumber": "17",
        "imageUrl": _img("romantico"),
        "viralQuestion": "¿Quién es el más especial de tu grupo?",
        "shareHook": "Mi match perfecto es KROSS BERRIES. La vida es demasiado corta para lo ordinario. #KrossMatch #Krossbar",
    },
    "frutal_intenso_berries": {
        "nombrePerfil": "KROSS BERRIES",
        "tagline": "Mezclas lo dulce con lo intenso y siempre te sale bien.",
        "ratings": "🌶️ ATREVIMIENTO  98%\n🍓 CREATIVIDAD  96%\n💥 EXPLOSIÓN  99%",
        "rareza": None,
        "collectionNumber": "18",
        "imageUrl": _img("atrevido"),
        "viralQuestion": "¿Quién mezcla lo dulce y lo intenso perfectamente?",
        "shareHook": "Mi match perfecto es KROSS BERRIES. Dulce por fuera, explosivo por dentro. #KrossMatch #Krossbar",
    },
}

_FALLBACK = MatchResponse(
    nombrePerfil="KROSS PILS",
    tagline="La pureza no necesita explicación.",
    ratings="🍺 PUREZA  98%",
    rareza=None,
    collectionNumber="01",
)


class MatchService:
    def calcular(self, req: MatchRequest) -> MatchResponse:
        key = f"{req.tipo}_{req.sabor}_{req.cerveza}"
        data = PERFILES.get(key)
        if not data:
            return _FALLBACK
        return MatchResponse(**data)


match_service = MatchService()
