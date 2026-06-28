"""
ConvoKit — capa de persistencia SQLite.

Toda la lógica de base de datos vive aquí. Los endpoints de FastAPI importan
las funciones de este módulo; nunca escriben SQL directamente.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_DB_PATH = os.getenv("DB_PATH") or str(Path(__file__).parent / "convokit.db")


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Crea todas las tablas si no existen. Se llama al arrancar la aplicación."""
    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS convocatorias (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre           TEXT    NOT NULL,
                fecha_creacion   TEXT    NOT NULL,
                documentos_json  TEXT    NOT NULL DEFAULT '[]',
                entregables_json TEXT    NOT NULL DEFAULT '{}'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_calls (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                convocatoria_id  INTEGER NOT NULL,
                salida           TEXT    NOT NULL,
                modelo           TEXT    NOT NULL,
                input_tokens     INTEGER NOT NULL,
                output_tokens    INTEGER NOT NULL,
                coste_eur        REAL    NOT NULL,
                timestamp        TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS generation_jobs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                convocatoria_id  INTEGER NOT NULL,
                salidas_json     TEXT    NOT NULL,
                status           TEXT    NOT NULL DEFAULT 'queued',
                progress_json    TEXT    NOT NULL DEFAULT '{}',
                created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
                updated_at       TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Convocatorias
# ---------------------------------------------------------------------------

def create_convocatoria(nombre: str) -> int:
    fecha = datetime.now(timezone.utc).isoformat()
    with _get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO convocatorias (nombre, fecha_creacion) VALUES (?, ?)",
            (nombre, fecha),
        )
        conn.commit()
        return cursor.lastrowid


def get_convocatoria(convocatoria_id: int) -> dict | None:
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM convocatorias WHERE id = ?", (convocatoria_id,)
        ).fetchone()
        cost_row = conn.execute(
            "SELECT COALESCE(SUM(coste_eur), 0) as total FROM api_calls WHERE convocatoria_id = ?",
            (convocatoria_id,),
        ).fetchone()

    if row is None:
        return None

    data = _row_to_dict(row)
    data["total_cost_eur"] = round(cost_row["total"], 6) if cost_row else 0.0
    return data


def list_convocatorias() -> list[dict]:
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.nombre, c.fecha_creacion, c.entregables_json,
                   COALESCE(SUM(a.coste_eur), 0) AS total_cost_eur
            FROM convocatorias c
            LEFT JOIN api_calls a ON a.convocatoria_id = c.id
            GROUP BY c.id
            ORDER BY c.fecha_creacion DESC
            """
        ).fetchall()

    result = []
    for row in rows:
        entregables = json.loads(row["entregables_json"])
        result.append(
            {
                "id": row["id"],
                "nombre": row["nombre"],
                "fecha_creacion": row["fecha_creacion"],
                "entregables_disponibles": list(entregables.keys()),
                "total_cost_eur": round(row["total_cost_eur"], 6),
            }
        )
    return result


def update_documentos(convocatoria_id: int, documentos: list[dict]) -> None:
    with _get_connection() as conn:
        conn.execute(
            "UPDATE convocatorias SET documentos_json = ? WHERE id = ?",
            (json.dumps(documentos, ensure_ascii=False), convocatoria_id),
        )
        conn.commit()


def append_documentos(convocatoria_id: int, new_docs: list[dict]) -> None:
    """Añade documentos adicionales a la convocatoria sin reemplazar los existentes."""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT documentos_json FROM convocatorias WHERE id = ?", (convocatoria_id,)
        ).fetchone()
        if row is None:
            return
        existing = json.loads(row["documentos_json"])
        existing.extend(new_docs)
        conn.execute(
            "UPDATE convocatorias SET documentos_json = ? WHERE id = ?",
            (json.dumps(existing, ensure_ascii=False), convocatoria_id),
        )
        conn.commit()


def update_entregables(convocatoria_id: int, entregables: dict) -> None:
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT entregables_json FROM convocatorias WHERE id = ?",
            (convocatoria_id,),
        ).fetchone()
        if row is None:
            return
        existing = json.loads(row["entregables_json"])
        existing.update(entregables)
        conn.execute(
            "UPDATE convocatorias SET entregables_json = ? WHERE id = ?",
            (json.dumps(existing, ensure_ascii=False), convocatoria_id),
        )
        conn.commit()


def delete_convocatoria(convocatoria_id: int) -> bool:
    with _get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM convocatorias WHERE id = ?", (convocatoria_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# API calls — registro de uso y costes
# ---------------------------------------------------------------------------

def record_api_call(
    convocatoria_id: int,
    salida: str,
    modelo: str,
    input_tokens: int,
    output_tokens: int,
    coste_eur: float,
) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO api_calls
                (convocatoria_id, salida, modelo, input_tokens, output_tokens, coste_eur, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (convocatoria_id, salida, modelo, input_tokens, output_tokens, coste_eur, ts),
        )
        conn.commit()


def get_api_stats() -> dict:
    """Devuelve estadísticas globales de uso de la API."""
    with _get_connection() as conn:
        total = conn.execute(
            "SELECT COALESCE(SUM(coste_eur), 0) as total, COUNT(*) as calls FROM api_calls"
        ).fetchone()
        by_output = conn.execute(
            """
            SELECT salida, COALESCE(SUM(coste_eur), 0) as total_cost,
                   COUNT(*) as calls, AVG(coste_eur) as avg_cost
            FROM api_calls
            GROUP BY salida ORDER BY salida
            """
        ).fetchall()
        by_model = conn.execute(
            """
            SELECT modelo, COALESCE(SUM(coste_eur), 0) as total_cost, COUNT(*) as calls,
                   SUM(input_tokens) as total_input, SUM(output_tokens) as total_output
            FROM api_calls
            GROUP BY modelo
            """
        ).fetchall()
        n_convs = conn.execute("SELECT COUNT(*) as n FROM convocatorias").fetchone()

    return {
        "total_cost_eur": round(total["total"], 4),
        "total_calls": total["calls"],
        "total_convocatorias": n_convs["n"],
        "by_output": [
            {
                "salida": r["salida"],
                "total_cost_eur": round(r["total_cost"], 4),
                "calls": r["calls"],
                "avg_cost_eur": round(r["avg_cost"], 6),
            }
            for r in by_output
        ],
        "by_model": [
            {
                "modelo": r["modelo"],
                "total_cost_eur": round(r["total_cost"], 4),
                "calls": r["calls"],
                "total_input_tokens": r["total_input"],
                "total_output_tokens": r["total_output"],
            }
            for r in by_model
        ],
    }


# ---------------------------------------------------------------------------
# Jobs — cola de generación
# ---------------------------------------------------------------------------

def create_job(convocatoria_id: int, salidas: list[dict]) -> int:
    progress = {"outputs": {str(s["output_type"]): {"status": "queued"} for s in salidas}}
    with _get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO generation_jobs (convocatoria_id, salidas_json, status, progress_json)
            VALUES (?, ?, 'queued', ?)
            """,
            (
                convocatoria_id,
                json.dumps(salidas, ensure_ascii=False),
                json.dumps(progress, ensure_ascii=False),
            ),
        )
        conn.commit()
        return cursor.lastrowid


def get_job(job_id: int) -> dict | None:
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM generation_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "convocatoria_id": row["convocatoria_id"],
        "status": row["status"],
        "progress": json.loads(row["progress_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def update_job(job_id: int, status: str, progress: dict) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    with _get_connection() as conn:
        conn.execute(
            "UPDATE generation_jobs SET status = ?, progress_json = ?, updated_at = ? WHERE id = ?",
            (status, json.dumps(progress, ensure_ascii=False), ts, job_id),
        )
        conn.commit()


def reset_stuck_jobs() -> None:
    """Marca como 'error' los jobs que quedaron en running/queued tras un reinicio."""
    msg = "Generación interrumpida por reinicio del servidor. Vuelve a generar."
    ts = datetime.now(timezone.utc).isoformat()
    with _get_connection() as conn:
        stuck = conn.execute(
            "SELECT id, progress_json FROM generation_jobs WHERE status IN ('running', 'queued')"
        ).fetchall()
        for job_id, prog_raw in stuck:
            prog = json.loads(prog_raw) if prog_raw else {}
            prog["error"] = msg
            for out in prog.get("outputs", {}).values():
                if out.get("status") in ("running", "queued", None):
                    out["status"] = "error"
                    out["error"] = msg
            conn.execute(
                "UPDATE generation_jobs SET status = 'error', progress_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(prog, ensure_ascii=False), ts, job_id),
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["documentos_json"] = json.loads(data["documentos_json"])
    data["entregables_json"] = json.loads(data["entregables_json"])
    return data
