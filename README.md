# ConvoKit

Aplicación web interna de Innóvate 4.0 que genera siete entregables (guía del consultor, ficha comercial, post de LinkedIn, artículo SEO, landing page, set de prompts para la memoria y lista de documentación + correo al cliente) a partir de los documentos oficiales de una convocatoria de ayudas públicas, mediante la API de Claude.

## Estructura de carpetas

```
convokit/
├── CLAUDE.md          # Fuente de verdad del proyecto (arquitectura, reglas, orden)
├── README.md
├── .gitignore
├── docs/              # PRD del proyecto
├── backend/           # Python 3.11 + FastAPI
│   ├── main.py        # App FastAPI (de momento, solo /health)
│   ├── database.py    # Lógica SQLite (pendiente)
│   ├── prompts.py     # System prompts de Claude (pendiente)
│   ├── exporters.py   # Exportación JSON de salidas 6 y 7 (pendiente)
│   ├── requirements.txt
│   └── .env.example
└── frontend/          # React + Vite + Tailwind CSS
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
cp .env.example .env           # rellenar ANTHROPIC_API_KEY y DB_PATH
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
