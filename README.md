# ConvoKit

Aplicación web interna de Innóvate 4.0 que genera seis entregables (guía del consultor,
ficha comercial, landing page embebible en WordPress con evaluador de encaje opcional,
set de prompts para la memoria, lista de documentación + correo al cliente, y evaluador
de encaje standalone) a partir de los documentos oficiales de una convocatoria de ayudas
públicas, mediante la API de Claude. Ver [CLAUDE.md](CLAUDE.md) para la arquitectura y
las reglas completas — es la fuente de verdad del proyecto.

## Estructura de carpetas

```
convokit/
├── CLAUDE.md               # Fuente de verdad del proyecto (arquitectura, reglas, orden)
├── README.md
├── .gitignore
├── docs/                   # PRD y contrato de exportación de la salida 4
├── backend/                # Python 3.11 + FastAPI
│   ├── main.py             # Endpoints FastAPI y orquestación de generación
│   ├── database.py         # CRUD SQLite
│   ├── prompts.py          # System prompts de Claude por salida
│   ├── extractors.py       # Extracción de texto de PDF/DOCX/XLSX/TXT
│   ├── exporters.py        # Exportación JSON de las salidas 4 y 5
│   ├── pricing.py          # Modelos y precios por token; registro en api_calls
│   ├── result_email.py     # HTML de los correos de resultado del evaluador (Resend)
│   ├── output3_template.py # Inyección del cuerpo de la landing (salida 3)
│   ├── output6_template.py # Construcción del evaluador (salida 6, standalone o embebido)
│   ├── landing_template.html   # Plantilla scoped de la landing
│   ├── evaluador_core.html     # Motor scoped del evaluador (HTML/CSS/JS)
│   ├── requirements.txt
│   └── .env.example
└── frontend/               # React + Vite + Tailwind CSS
    ├── src/
    ├── package.json
    └── .env.example
```

## Arrancar en local

### Backend (Python 3.11 + FastAPI)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows (PowerShell: .venv\Scripts\Activate.ps1)
# source .venv/bin/activate    # macOS / Linux
pip install -r requirements.txt
cp .env.example .env           # rellenar ANTHROPIC_API_KEY, DB_PATH y las variables de Resend
uvicorn main:app --reload --port 8000
```

El backend queda disponible en `http://localhost:8000`. Comprueba el health check en `http://localhost:8000/health`.

### Frontend (React + Vite + Tailwind)

```bash
cd frontend
npm install
cp .env.example .env           # poner VITE_API_URL=http://localhost:8000
npm run dev
```

El frontend queda disponible en `http://localhost:5173` y muestra el estado de conexión con el backend.
