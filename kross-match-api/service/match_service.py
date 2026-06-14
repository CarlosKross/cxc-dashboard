from model.match_model import MatchRequest, MatchResponse

# 18 perfiles mapeados a (tipo)_(sabor)_(cerveza)
# nombrePerfil: nombre de la cerveza mostrado como protagonista del match
# tagline: frase memorable del perfil
# ratings: atributos multi-línea mostrados en la story card (\n = salto de línea)
# rareza: badge dorado opcional, solo para arquetipos TOP < 10%

PERFILES: dict[str, dict] = {
    "lager_suave_pils": {
        "nombrePerfil": "KROSS PILS",
        "tagline": "Sin rodeos, sin excesos. La pureza no necesita explicación.",
        "ratings": "🎯 PRECISIÓN  96%\n🍺 PUREZA  98%\n⚡ CLARIDAD  94%",
        "rareza": None,
    },
    "lager_suave_golden": {
        "nombrePerfil": "KROSS GOLDEN",
        "tagline": "Ni extremos ni compromisos. Tu equilibrio une al grupo.",
        "ratings": "⚖️ BALANCE  99%\n🤝 ARMONÍA  95%\n🌟 PRESENCIA  90%",
        "rareza": None,
    },
    "lager_intenso_pils": {
        "nombrePerfil": "KROSS PILS",
        "tagline": "Ideas simples en experiencias memorables.",
        "ratings": "🌿 CREATIVIDAD  97%\n🧪 INNOVACIÓN  94%\n🌱 EXPLORACIÓN  99%",
        "rareza": "LEGENDARIO · TOP 5%",
    },
    "lager_intenso_golden": {
        "nombrePerfil": "KROSS GOLDEN",
        "tagline": "La calma es tu superpoder. La perfección está en lo ordinario.",
        "ratings": "🧘 CALMA  98%\n💧 CLARIDAD  95%\n🌊 PROFUNDIDAD  97%",
        "rareza": "ÉPICO · TOP 8%",
    },
    "lupulada_suave_ipa": {
        "nombrePerfil": "KROSS IPA",
        "tagline": "El amargor tropical y la actitud son tu firma personal.",
        "ratings": "🍊 ACTITUD  96%\n🔥 INTENSIDAD  92%\n💥 ORIGINALIDAD  95%",
        "rareza": None,
    },
    "lupulada_intenso_ipa": {
        "nombrePerfil": "KROSS IPA",
        "tagline": "Directo, sin filtros. Tu presencia se siente antes de que llegues.",
        "ratings": "🎸 CARÁCTER  99%\n⚡ INTENSIDAD  98%\n🔊 IMPACTO  97%",
        "rareza": "ÉPICO · TOP 9%",
    },
    "lupulada_suave_ipa_pomelo": {
        "nombrePerfil": "KROSS IPA POMELO",
        "tagline": "Elegiste la IPA más premiada del mundo. Clase antes de que existiera.",
        "ratings": "🏆 SOFISTICACIÓN  96%\n🍋 ACIDEZ  98%\n💎 RAREZA  94%",
        "rareza": "ÉPICO · TOP 10%",
    },
    "lupulada_intenso_ipa_pomelo": {
        "nombrePerfil": "KROSS IPA POMELO",
        "tagline": "El amargor perfecto que muy pocos saben apreciar.",
        "ratings": "⭐ BRILLANTEZ  99%\n🌺 TROPICAL  97%\n💫 RAREZA  98%",
        "rareza": "LEGENDARIO · TOP 7%",
    },
    "lupulada_suave_hazy": {
        "nombrePerfil": "KROSS HAZY LAGER",
        "tagline": "La complejidad inesperada te atrae. Siempre al próximo horizonte.",
        "ratings": "🌴 AVENTURA  97%\n🔍 CURIOSIDAD  95%\n🌊 FRESCURA  99%",
        "rareza": None,
    },
    "lupulada_intenso_hazy": {
        "nombrePerfil": "KROSS HAZY LAGER",
        "tagline": "Intensa, atrevida y difícil de olvidar.",
        "ratings": "🌶️ INTENSIDAD  10/10\n🍊 EXPLOSIÓN  10/10\n🔥 RAREZA  9/10",
        "rareza": "LEGENDARIO · TOP 8%",
    },
    "maltosa_suave_stout": {
        "nombrePerfil": "KROSS STOUT",
        "tagline": "La complejidad es tu lenguaje natural. Aprecias los detalles oscuros.",
        "ratings": "📚 PROFUNDIDAD  98%\n🌙 ELEGANCIA  95%\n🧠 PERSPECTIVA  97%",
        "rareza": None,
    },
    "maltosa_intenso_stout": {
        "nombrePerfil": "KROSS STOUT",
        "tagline": "Prendes la parrilla y cuentas las mejores historias.",
        "ratings": "🔥 CARÁCTER  99%\n🥩 INTENSIDAD  97%\n🌿 TRADICIÓN  96%",
        "rareza": "ÉPICO · TOP 7%",
    },
    "maltosa_suave_maibock": {
        "nombrePerfil": "KROSS MAIBOCK",
        "tagline": "La tradición bien ejecutada nunca falla.",
        "ratings": "🏛️ TRADICIÓN  98%\n✨ ESTILO  94%\n🎯 CONSISTENCIA  96%",
        "rareza": None,
    },
    "maltosa_intenso_maibock": {
        "nombrePerfil": "KROSS MAIBOCK",
        "tagline": "Robusto, tostado. Tradición y fuego en cada sorbo.",
        "ratings": "⚔️ FORTALEZA  99%\n🔥 FUEGO  97%\n🏆 CARÁCTER  98%",
        "rareza": "LEGENDARIO · TOP 6%",
    },
    "maltosa_suave_k5": {
        "nombrePerfil": "KROSS K5",
        "tagline": "24 medallas mundiales no mienten. La más premiada de Chile.",
        "ratings": "🥇 MAESTRÍA  99%\n🧪 COMPLEJIDAD  97%\n🏆 LEGADO  98%",
        "rareza": "LEGENDARIO · TOP 6%",
    },
    "maltosa_intenso_k5": {
        "nombrePerfil": "KROSS K5",
        "tagline": "La tradición con un giro de fuego. La combinación más osada.",
        "ratings": "💪 POTENCIA  100%\n🔥 COMPLEJIDAD  99%\n💎 RAREZA  98%",
        "rareza": "LEGENDARIO · TOP 5%",
    },
    "frutal_suave_berries": {
        "nombrePerfil": "KROSS BERRIES",
        "tagline": "La vida es demasiado corta para lo ordinario. Eres especial y lo sabes.",
        "ratings": "🍓 SENSIBILIDAD  98%\n🌸 DULZURA  97%\n✨ SINGULARIDAD  95%",
        "rareza": None,
    },
    "frutal_intenso_berries": {
        "nombrePerfil": "KROSS BERRIES",
        "tagline": "Mezclas lo dulce con lo intenso y siempre te sale bien.",
        "ratings": "🌶️ ATREVIMIENTO  98%\n🍓 CREATIVIDAD  96%\n💥 EXPLOSIÓN  99%",
        "rareza": None,
    },
}

_FALLBACK = MatchResponse(
    nombrePerfil="KROSS PILS",
    tagline="La pureza no necesita explicación.",
    ratings="🍺 PUREZA  98%",
    rareza=None,
)


class MatchService:
    def calcular(self, req: MatchRequest) -> MatchResponse:
        key = f"{req.tipo}_{req.sabor}_{req.cerveza}"
        data = PERFILES.get(key)
        if not data:
            return _FALLBACK
        return MatchResponse(**data)


match_service = MatchService()
