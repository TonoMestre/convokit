"""
ConvoKit — capa de persistencia SQLite.

Toda la lógica de base de datos vive aquí. Los endpoints de FastAPI importan
las funciones de este módulo; nunca escriben SQL directamente.

El esquema está diseñado para migrar a Supabase en el futuro sin cambios en la
lógica de negocio: mismos nombres de tabla y columna, mismo modelo relacional.
La única diferencia será sustituir sqlite3 por el cliente de Supabase/PostgreSQL.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Ruta del fichero SQLite. En Railway apunta al volumen montado para persistencia
# real entre reinicios. En desarrollo local se crea en /backend por defecto.
_DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent / "convokit.db"))


def _get_connection() -> sqlite3.Connection:
    """Abre y devuelve una conexión a SQLite con row_factory activada."""
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row  # permite acceder a columnas por nombre
    return conn


def init_db() -> None:
    """
    Crea la tabla 'convocatorias' si no existe.
    Se llama al arrancar la aplicación (desde main.py).
    """
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
        conn.commit()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def create_convocatoria(nombre: str) -> int:
    """
    Crea una nueva convocatoria con el nombre dado.
    Devuelve el id asignado por SQLite.
    """
    fecha = datetime.now(timezone.utc).isoformat()
    with _get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO convocatorias (nombre, fecha_creacion) VALUES (?, ?)",
            (nombre, fecha),
        )
        conn.commit()
        return cursor.lastrowid


def get_convocatoria(convocatoria_id: int) -> dict | None:
    """
    Devuelve la convocatoria completa como dict, o None si no existe.
    Los campos documentos_json y entregables_json se deserializan a Python.
    """
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM convocatorias WHERE id = ?",
            (convocatoria_id,),
        ).fetchone()

    if row is None:
        return None

    return _row_to_dict(row)


def list_convocatorias() -> list[dict]:
    """
    Lista todas las convocatorias ordenadas por fecha de creación descendente.
    Devuelve id, nombre, fecha_creacion y la lista de claves de entregables
    generados (para que el frontend sepa qué salidas tiene cada convocatoria
    sin cargar todo el texto).
    """
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT id, nombre, fecha_creacion, entregables_json FROM convocatorias ORDER BY fecha_creacion DESC"
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
            }
        )
    return result


def update_documentos(convocatoria_id: int, documentos: list[dict]) -> None:
    """
    Guarda el texto extraído de los documentos subidos.
    'documentos' es una lista de dicts con al menos 'etiqueta' y 'texto'.
    Reemplaza el valor previo por completo.
    """
    with _get_connection() as conn:
        conn.execute(
            "UPDATE convocatorias SET documentos_json = ? WHERE id = ?",
            (json.dumps(documentos, ensure_ascii=False), convocatoria_id),
        )
        conn.commit()


def update_entregables(convocatoria_id: int, entregables: dict) -> None:
    """
    Fusiona los entregables generados con los ya existentes.
    'entregables' es un dict {numero_salida: texto_generado}, p.ej. {"1": "..."}
    Se fusiona (no reemplaza) para no borrar salidas previas al regenerar una sola.
    """
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
    """
    Elimina una convocatoria y todos sus datos.
    Devuelve True si se borró algo, False si el id no existía.
    """
    with _get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM convocatorias WHERE id = ?",
            (convocatoria_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convierte una fila SQLite a dict deserializando los campos JSON."""
    data = dict(row)
    data["documentos_json"] = json.loads(data["documentos_json"])
    data["entregables_json"] = json.loads(data["entregables_json"])
    return data


# ---------------------------------------------------------------------------
# Script de prueba (solo en ejecución directa)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Test de database.py ===\n")

    init_db()
    print(f"Base de datos inicializada en: {_DB_PATH}\n")

    # Crear
    conv_id = create_convocatoria("INPYME 2026 — prueba")
    print(f"[create] Convocatoria creada con id={conv_id}")

    # Recuperar
    conv = get_convocatoria(conv_id)
    print(f"[get]    nombre={conv['nombre']}  fecha={conv['fecha_creacion']}")

    # Actualizar documentos
    docs = [
        {"etiqueta": "bases_reguladoras", "nombre_archivo": "bases.pdf", "texto": "Texto extraído de prueba."}
    ]
    update_documentos(conv_id, docs)
    conv = get_convocatoria(conv_id)
    print(f"[update_documentos] documentos guardados: {len(conv['documentos_json'])}")

    # Actualizar entregables (simula guardar la salida 1)
    update_entregables(conv_id, {"1": "Guía del consultor generada de prueba."})
    # Añadir otra salida sin borrar la primera
    update_entregables(conv_id, {"2": "Ficha comercial generada de prueba."})
    conv = get_convocatoria(conv_id)
    print(f"[update_entregables] entregables guardados: {list(conv['entregables_json'].keys())}")

    # Listar
    lista = list_convocatorias()
    print(f"[list]   total convocatorias: {len(lista)}")
    for c in lista:
        print(f"         id={c['id']}  nombre={c['nombre']}  entregables={c['entregables_disponibles']}")

    # Borrar
    borrado = delete_convocatoria(conv_id)
    print(f"[delete] borrado={borrado}")
    print(f"[list]   total tras borrar: {len(list_convocatorias())}")

    print("\n=== Todos los tests pasaron correctamente ===")
