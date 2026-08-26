# -*- coding: utf-8 -*-
"""
Entrypoint de referencia para REPRODUCIR los artefactos 01/02 de esta carpeta
directamente desde hosted Supabase, en modo estrictamente read-only.

Este script NO forma parte del backend de ConvoKit ni de i40 Analiza: es
documentación ejecutable, conservada aquí para que dentro de seis meses se
pueda responder "cómo se generó esto" sin depender de esta conversación ni
de shell history. No contiene ningún secreto -- las credenciales se leen del
propio `.env` de i40 Analiza (services/worker/.env), que no vive en este
repositorio.

Requisitos:
- Un checkout de i40 Analiza en I40_ANALIZA_PATH (por defecto "C:\\Dev\\i40 ANALIZA").
- El venv de i40 Analiza en services/worker/.venv (psycopg3 instalado ahí).
- services/worker/.env de i40 Analiza con DATABASE_URL apuntando al pooler
  de sesión de Supabase (solo lectura: la conexión se marca read_only antes
  de ejecutar ninguna consulta).

Uso (con el Python del propio venv de i40 Analiza, que es quien tiene psycopg
instalado -- ver services/worker/.venv/Scripts/python.exe en Windows):

    "<i40>\\services\\worker\\.venv\\Scripts\\python.exe" 03_export_real_pack_readonly.py \\
        --analysis-id c5bb1aa0-20c3-4f65-8a95-62607622140a \\
        --out-dir .

`--analysis-id` es el id real de la convocatoria "INPYME 2026" en
`public.analyses` (título "INPYME 2026", public_body "Conselleria
Industria", call_year 2026) -- localízalo de nuevo si cambia con:

    select id, title, public_body, call_year, status
      from public.analyses where title ilike '%INPYME%';

Garantías de solo-lectura:
- `conn.set_read_only(True)` se aplica ANTES de cualquier consulta: cualquier
  intento de escritura sería rechazado por el propio servidor Postgres, no
  solo evitado por disciplina del script.
- Nunca se hace commit; el rollback final es un no-op explícito (no hay
  ninguna escritura que revertir).
- Usa exclusivamente `export_application_knowledge_pack` y `to_convokit_pack`
  tal como existen en el código real de i40 Analiza (master) -- no reimplementa
  ni reinterpreta esa lógica.
"""
import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, timezone


def _load_env(path: str) -> dict:
    env = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def _sha256_of_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


async def _main(analysis_id: str, i40_path: str, out_dir: str) -> None:
    sys.path.insert(0, os.path.join(i40_path, "services", "worker", "src"))

    import psycopg  # noqa: E402  (proporcionado por el venv de i40 Analiza)
    from psycopg.rows import dict_row  # noqa: E402

    from i40_worker.application_knowledge import export as ex  # noqa: E402

    env_path = os.path.join(i40_path, "services", "worker", ".env")
    env = _load_env(env_path)
    database_url = env["DATABASE_URL"]

    conn = await psycopg.AsyncConnection.connect(database_url, autocommit=False)
    conn.row_factory = dict_row
    await conn.set_read_only(True)  # el servidor rechaza cualquier escritura a partir de aquí

    try:
        native_pack = await ex.export_application_knowledge_pack(conn, analysis_id)
    finally:
        await conn.rollback()  # no-op: no hubo ninguna escritura
        await conn.close()

    os.makedirs(out_dir, exist_ok=True)
    native_path = os.path.join(out_dir, "01_inpyme2026_application_knowledge_real.json")
    with open(native_path, "w", encoding="utf-8") as f:
        json.dump(native_pack, f, ensure_ascii=False, indent=2)

    convokit_pack = ex.to_convokit_pack(
        native_pack, pack_id="i40-real-inpyme2026-v1", convocatoria_ref="INPYME-2026-REAL"
    )
    convokit_path = os.path.join(out_dir, "02_inpyme2026_convokit_pack_real.json")
    with open(convokit_path, "w", encoding="utf-8") as f:
        json.dump(convokit_pack, f, ensure_ascii=False, indent=2)

    print("native SHA-256:  ", _sha256_of_file(native_path))
    print("convokit SHA-256:", _sha256_of_file(convokit_path))
    print("exported_at_utc: ", datetime.now(timezone.utc).isoformat())
    print(
        "NOTA: el SHA-256 depende del formato de serialización JSON (indent, orden de "
        "claves). Si difiere del registrado en 00_MANIFEST.md pero los CONTEOS/valores "
        "coinciden, es un cambio de formato, no de datos -- compara el contenido, no solo el hash."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-id", required=True, help="uuid de public.analyses (INPYME 2026)")
    parser.add_argument("--i40-path", default=r"C:\Dev\i40 ANALIZA", help="checkout local de i40 Analiza")
    parser.add_argument("--out-dir", default=".", help="directorio de salida para los dos JSON")
    args = parser.parse_args()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.analysis_id, args.i40_path, args.out_dir))
