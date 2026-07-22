"""
Capa de persistencia usando Vercel KV (Upstash Redis).

Si KV_REST_API_URL y KV_REST_API_TOKEN están configuradas (Vercel KV),
los documentos se guardan en Redis y persisten entre instancias serverless.

Si no están configuradas (entorno local), se usa solo memoria RAM.
"""

import json
import os
from typing import Any

# Nombre del hash en Redis que almacena todos los documentos indexados.
_KV_HASH_KEY = "bimbam:documents"


def _get_redis():
    """
    Retorna un cliente Redis de Upstash o None si no hay credenciales.
    Importación diferida para no romper el arranque si el paquete no está.
    """
    url = os.getenv("KV_REST_API_URL") or os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("KV_REST_API_TOKEN") or os.getenv("UPSTASH_REDIS_REST_TOKEN")

    if not url or not token:
        return None

    try:
        from upstash_redis import Redis  # type: ignore
        return Redis(url=url, token=token)
    except ImportError:
        return None
    except Exception as exc:
        print(f"[KV] Error al crear cliente Redis: {exc}")
        return None


def kv_save_document(filename: str, record: dict[str, Any]) -> bool:
    """
    Guarda el registro de un documento (metadatos + chunks) en KV.
    Retorna True si se guardó en Redis, False si solo quedó en memoria.
    """
    redis = _get_redis()
    if redis is None:
        return False

    try:
        # Los chunks se guardan como JSON.  Redis hash: clave=filename, valor=JSON.
        redis.hset(_KV_HASH_KEY, filename, json.dumps(record, ensure_ascii=False))
        return True
    except Exception as exc:
        print(f"[KV] Error al guardar documento '{filename}': {exc}")
        return False


def kv_load_all_documents() -> dict[str, dict[str, Any]]:
    """
    Carga todos los documentos persistidos en KV al arrancar la instancia.
    Retorna un dict vacío si KV no está disponible o no hay documentos.
    """
    redis = _get_redis()
    if redis is None:
        return {}

    try:
        raw = redis.hgetall(_KV_HASH_KEY)
        if not raw:
            return {}

        result = {}
        for filename, value in raw.items():
            try:
                result[filename] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                print(f"[KV] No se pudo deserializar el documento '{filename}'")

        return result
    except Exception as exc:
        print(f"[KV] Error al cargar documentos: {exc}")
        return {}


def kv_delete_document(filename: str) -> bool:
    """
    Elimina un documento de KV.
    Retorna True si se eliminó correctamente.
    """
    redis = _get_redis()
    if redis is None:
        return False

    try:
        redis.hdel(_KV_HASH_KEY, filename)
        return True
    except Exception as exc:
        print(f"[KV] Error al eliminar documento '{filename}': {exc}")
        return False


def kv_is_available() -> bool:
    """Comprueba si KV está configurado y accesible."""
    return _get_redis() is not None
