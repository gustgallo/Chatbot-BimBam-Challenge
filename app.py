import glob
import os
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

from cohere_service import CohereRAGService
from pdf_processor import PDFProcessor


# Evita errores de caracteres especiales en la consola de Windows.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# En desarrollo local carga .env. En Vercel utiliza las variables configuradas
# en Project Settings > Environment Variables.
load_dotenv()


BASE_DIR = Path(__file__).resolve().parent


def find_frontend_directory() -> Path | None:
    """
    Localiza automáticamente la carpeta que contiene index.html.

    Admite estas estructuras:
    - static/index.html
    - public/index.html
    - index.html en la raíz del proyecto
    """
    candidates = (
        BASE_DIR / "static",
        BASE_DIR / "public",
        BASE_DIR,
    )

    for directory in candidates:
        if (directory / "index.html").is_file():
            return directory

    return None


FRONTEND_DIR = find_frontend_directory()

# Flask no administrará automáticamente una ruta estática en la raíz. Las rutas
# para index.html, app.js y styles.css se definen de forma explícita más abajo.
app = Flask(__name__, static_folder=None)

# El frontend y la API normalmente viven en el mismo dominio. Se conserva CORS
# para permitir pruebas locales desde otro puerto.
CORS(app)

# Mantiene la carga por debajo del límite práctico de las funciones de Vercel.
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024

# Vercel solamente permite escritura temporal dentro de /tmp.
UPLOAD_DIR = Path(tempfile.gettempdir()) / "bimbam_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# Inicialización diferida. La página principal puede cargar aunque Cohere o el
# procesamiento de PDF presenten un problema posterior.
_pdf_processor: PDFProcessor | None = None
_cohere_service: CohereRAGService | None = None
_service_lock = threading.RLock()
_document_lock = threading.RLock()
_workspace_scan_completed = False

# Estado temporal de la instancia serverless actual.
indexed_documents: dict[str, dict[str, Any]] = {}


def get_pdf_processor() -> PDFProcessor:
    global _pdf_processor

    with _service_lock:
        if _pdf_processor is None:
            _pdf_processor = PDFProcessor(
                chunk_size=700,
                chunk_overlap=150,
            )

        return _pdf_processor


def get_cohere_service() -> CohereRAGService:
    global _cohere_service

    with _service_lock:
        if _cohere_service is None:
            _cohere_service = CohereRAGService()

        return _cohere_service


def build_document_record(doc_data: dict[str, Any], is_preset: bool) -> dict[str, Any]:
    """Convierte la respuesta de PDFProcessor al formato usado por la API."""
    return {
        "info": {
            "source": doc_data["source"],
            "file_path": doc_data["file_path"],
            "total_pages": doc_data["total_pages"],
            "total_chunks": doc_data["total_chunks"],
            "total_words": doc_data["total_words"],
            "is_preset": is_preset,
        },
        "chunks": doc_data["chunks"],
    }


def load_workspace_pdfs(force: bool = False) -> None:
    """
    Indexa una sola vez los PDF incluidos en la raíz del proyecto.

    No se ejecuta durante la importación de app.py para reducir fallos y tiempos
    de arranque en Vercel.
    """
    global _workspace_scan_completed

    with _document_lock:
        if _workspace_scan_completed and not force:
            return

        processor = get_pdf_processor()
        pdf_files = sorted(glob.glob(str(BASE_DIR / "*.pdf")))

        for pdf_path_text in pdf_files:
            pdf_path = Path(pdf_path_text)
            filename = pdf_path.name

            if filename in indexed_documents:
                continue

            try:
                doc_data = processor.process_document(str(pdf_path))
                indexed_documents[filename] = build_document_record(
                    doc_data,
                    is_preset=True,
                )
                app.logger.info("Documento indexado: %s", filename)
            except Exception:
                # Un PDF defectuoso no debe impedir que carguen los demás.
                app.logger.exception("No se pudo indexar el PDF: %s", filename)

        _workspace_scan_completed = True


def get_document_summaries() -> list[dict[str, Any]]:
    with _document_lock:
        return [document["info"] for document in indexed_documents.values()]


def frontend_error_response():
    checked_locations = [
        str(BASE_DIR / "static" / "index.html"),
        str(BASE_DIR / "public" / "index.html"),
        str(BASE_DIR / "index.html"),
    ]

    return jsonify({
        "success": False,
        "error": "No se encontró index.html en static, public ni en la raíz.",
        "checked_locations": checked_locations,
    }), 500


@app.get("/")
def serve_index():
    """Entrega la interfaz principal."""
    if FRONTEND_DIR is None:
        return frontend_error_response()

    return send_from_directory(str(FRONTEND_DIR), "index.html")


@app.get("/api/health")
def health():
    """Comprueba Flask, la carpeta del frontend y la variable de Cohere."""
    return jsonify({
        "success": True,
        "status": "online",
        "message": "Aplicación Flask funcionando correctamente",
        "frontend_directory": str(FRONTEND_DIR) if FRONTEND_DIR else None,
        "index_found": bool(FRONTEND_DIR),
        "cohere_key_present": bool(os.getenv("COHERE_API_KEY")),
    })


@app.get("/api/status")
def get_status():
    try:
        load_workspace_pdfs()
        service = get_cohere_service()

        with _document_lock:
            total_chunks = sum(
                len(document["chunks"])
                for document in indexed_documents.values()
            )

            documents = get_document_summaries()

        return jsonify({
            "status": "online",
            "cohere_configured": service.is_configured(),
            "total_documents": len(documents),
            "total_chunks": total_chunks,
            "documents": documents,
        })
    except Exception as error:
        app.logger.exception("Error consultando el estado")
        return jsonify({
            "success": False,
            "status": "error",
            "error": str(error),
        }), 500


@app.post("/api/config-key")
def config_api_key():
    """
    Configura una clave solo cuando el servidor no tiene COHERE_API_KEY.

    En producción es preferible definirla directamente en Vercel.
    """
    if os.getenv("COHERE_API_KEY"):
        return jsonify({
            "success": False,
            "error": "La API Key ya está configurada mediante una variable de entorno.",
        }), 403

    data = request.get_json(silent=True) or {}
    api_key = str(data.get("api_key", "")).strip()

    if not api_key:
        return jsonify({
            "success": False,
            "error": "La API Key no puede estar vacía",
        }), 400

    try:
        service = get_cohere_service()
        service.set_api_key(api_key)

        return jsonify({
            "success": True,
            "cohere_configured": service.is_configured(),
            "message": "API Key de Cohere configurada temporalmente",
        })
    except Exception as error:
        app.logger.exception("Error configurando la API Key")
        return jsonify({
            "success": False,
            "error": f"Error configurando la API Key: {error}",
        }), 500


@app.get("/api/documents")
def list_documents():
    try:
        load_workspace_pdfs()
        return jsonify({
            "success": True,
            "documents": get_document_summaries(),
        })
    except Exception as error:
        app.logger.exception("Error consultando documentos")
        return jsonify({
            "success": False,
            "error": f"Error consultando documentos: {error}",
        }), 500


@app.post("/api/upload")
def upload_pdf():
    """Sube e indexa temporalmente un PDF de hasta 4 MB."""
    uploaded_file = request.files.get("file")

    if uploaded_file is None:
        return jsonify({
            "success": False,
            "error": "No se envió ningún archivo",
        }), 400

    original_filename = uploaded_file.filename or ""

    if not original_filename.strip():
        return jsonify({
            "success": False,
            "error": "Nombre de archivo inválido",
        }), 400

    if not original_filename.lower().endswith(".pdf"):
        return jsonify({
            "success": False,
            "error": "Solo se permiten archivos en formato PDF",
        }), 400

    filename = secure_filename(original_filename)

    if not filename or not filename.lower().endswith(".pdf"):
        return jsonify({
            "success": False,
            "error": "Nombre de archivo inválido",
        }), 400

    file_path = UPLOAD_DIR / filename

    try:
        uploaded_file.save(str(file_path))
        processor = get_pdf_processor()
        doc_data = processor.process_document(str(file_path))

        with _document_lock:
            indexed_documents[filename] = build_document_record(
                doc_data,
                is_preset=False,
            )
            document_info = indexed_documents[filename]["info"]

        return jsonify({
            "success": True,
            "message": f"Documento '{filename}' subido e indexado exitosamente",
            "document": document_info,
        })
    except Exception as error:
        app.logger.exception("Error procesando el PDF subido")

        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            pass

        return jsonify({
            "success": False,
            "error": f"Error al procesar el PDF: {error}",
        }), 500


@app.post("/api/delete-document")
def delete_document():
    data = request.get_json(silent=True) or {}
    filename = str(data.get("filename", "")).strip()

    if not filename:
        return jsonify({
            "success": False,
            "error": "Debe proporcionar el nombre del documento",
        }), 400

    with _document_lock:
        document = indexed_documents.pop(filename, None)

    if document is None:
        return jsonify({
            "success": False,
            "error": "Documento no encontrado",
        }), 404

    # Solo intenta eliminar archivos temporales subidos por el usuario.
    if not document["info"].get("is_preset", False):
        try:
            Path(document["info"]["file_path"]).unlink(missing_ok=True)
        except OSError:
            app.logger.warning("No se pudo eliminar el archivo temporal: %s", filename)

    return jsonify({
        "success": True,
        "message": f"Documento '{filename}' eliminado del índice",
    })


@app.post("/api/chat")
def chat():
    try:
        data = request.get_json(silent=True) or {}
        query = str(data.get("message", "")).strip()
        active_sources = data.get("active_sources", [])
        history = data.get("history", [])

        if not query:
            return jsonify({
                "success": False,
                "error": "La pregunta no puede estar vacía",
            }), 400

        if not isinstance(active_sources, list):
            active_sources = []

        if not isinstance(history, list):
            history = []

        load_workspace_pdfs()
        service = get_cohere_service()

        if not service.is_configured():
            return jsonify({
                "success": False,
                "error": (
                    "La API Key de Cohere no está configurada. "
                    "Agrega COHERE_API_KEY en las variables de entorno de Vercel."
                ),
            }), 503

        all_chunks: list[dict[str, Any]] = []

        with _document_lock:
            if active_sources:
                for source in active_sources:
                    document = indexed_documents.get(str(source))
                    if document:
                        all_chunks.extend(document["chunks"])
            else:
                for document in indexed_documents.values():
                    all_chunks.extend(document["chunks"])

        if not all_chunks:
            return jsonify({
                "success": True,
                "answer": (
                    "No hay fuentes de información seleccionadas o indexadas. "
                    "Activa o sube al menos un documento PDF."
                ),
                "sources": [],
            })

        top_chunks = service.search_relevant_chunks(
            query,
            all_chunks,
            top_k=5,
        )

        response_data = service.generate_answer(
            query,
            top_chunks,
            chat_history=history,
        )

        return jsonify({
            "success": True,
            "answer": response_data.get(
                "answer",
                "No se pudo generar una respuesta",
            ),
            "sources": response_data.get("sources", []),
            "error": response_data.get("error"),
        })
    except Exception as error:
        app.logger.exception("Error procesando la solicitud del chatbot")
        return jsonify({
            "success": False,
            "error": f"Error procesando la pregunta: {error}",
        }), 500


@app.get("/favicon.ico")
@app.get("/favicon.png")
def serve_favicon():
    """Devuelve 204 sin contenido cuando no hay favicon en el proyecto."""
    if FRONTEND_DIR is not None:
        for name in ("favicon.ico", "favicon.png"):
            candidate = FRONTEND_DIR / name
            if candidate.is_file():
                return send_from_directory(str(FRONTEND_DIR), name)
    # Si no existe el favicon, responde vacío para no generar errores 500 en los logs.
    return "", 204


@app.get("/<path:filename>")
def serve_frontend_file(filename: str):
    """
    Sirve app.js, styles.css, imágenes y otros recursos del frontend.

    Esta ruta permite que el proyecto funcione aunque el HTML use rutas como
    /app.js o /styles.css.
    """
    if FRONTEND_DIR is None:
        return frontend_error_response()

    requested_file = FRONTEND_DIR / filename

    if requested_file.is_file():
        return send_from_directory(str(FRONTEND_DIR), filename)

    return jsonify({
        "success": False,
        "error": "Ruta no encontrada",
    }), 404


@app.errorhandler(413)
def file_too_large(_error):
    return jsonify({
        "success": False,
        "error": "El archivo supera el límite permitido de 4 MB",
    }), 413


@app.errorhandler(404)
def not_found(_error):
    return jsonify({
        "success": False,
        "error": "Ruta no encontrada",
    }), 404


@app.errorhandler(500)
def internal_error(error):
    app.logger.exception("Error interno no controlado: %s", error)
    return jsonify({
        "success": False,
        "error": "Error interno del servidor",
    }), 500


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Servidor BimBam Buy AI PDF Chatbot iniciado en http://localhost:5000")
    print("=" * 60 + "\n")

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
