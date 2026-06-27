"""
ConvoKit — precios de la API de Claude y cálculo de costes.

Para actualizar precios: modificar solo PRICING y EUR_USD_RATE.
Para cambiar el modelo por salida: modificar MODEL_PER_OUTPUT.
"""

# ---------------------------------------------------------------------------
# Modelos disponibles
# ---------------------------------------------------------------------------

MODELS: dict[str, str] = {
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}

# Salida 1: Sonnet (extracción técnica precisa del consultor).
# Salidas 2-5: Haiku (redacción a partir de datos ya presentes en los documentos).
MODEL_PER_OUTPUT: dict[int, str] = {
    1: MODELS["sonnet"],
    2: MODELS["haiku"],
    3: MODELS["haiku"],
    4: MODELS["haiku"],
    5: MODELS["haiku"],
}

# ---------------------------------------------------------------------------
# Precios y tipo de cambio
# ---------------------------------------------------------------------------

# USD por millón de tokens. Fuente: https://www.anthropic.com/pricing
PRICING: dict[str, dict[str, float]] = {
    MODELS["sonnet"]: {"input": 3.0,  "output": 15.0},
    MODELS["haiku"]:  {"input": 0.80, "output": 4.0},
}

# Tipo de cambio fijo EUR/USD. Actualizar si es necesario.
EUR_USD_RATE: float = 0.92


def calculate_cost_eur(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calcula el coste en EUR de una llamada a la API."""
    p = PRICING.get(model, PRICING[MODELS["sonnet"]])
    usd = (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000
    return round(usd * EUR_USD_RATE, 6)
