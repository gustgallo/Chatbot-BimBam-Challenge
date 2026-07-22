import os
import sys
import glob
import tempfile

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename


# Configurar stdout y stderr en UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


from pdf_processor import PDFProcessor
from cohere_service import CohereRAGService


# Cargar variables de entorno desde .env en desarrollo local
load_dotenv()


# Crear aplicación Flask
app = Flask(
    __name__,
    static_folder="static",
    static_url_path=""
)

CORS(app)


# Directorio donde se encuentra app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# Carpeta temporal para archivos subidos
# En Vercel solamente se puede escribir temporalmente en /tmp
UPLOAD_DIR = os.path.join(
    tempfile.gettempdir(),
    "bimbam_uploads"
)

os.makedirs(UPLOAD_DIR, exist_ok=True)


# Servicios para procesamiento de PDF y Cohere
pdf_processor = PDFProcessor(
    chunk_size=700,
    chunk_overlap=150
)

cohere_service = CohereRAGService()


# Documentos indexados en memoria
indexed_documents = {}


def load_workspace_pdfs():
    """
    Escanea e indexa automáticamente los archivos PDF de BimBam Buy
    que se encuentran en la carpeta principal del proyecto.
    """

    pdf_files = glob.glob(
        os.path.join(BASE_DIR, "*.pdf")
    )

    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)

        if filename in indexed_documents:
            continue

        try:
            doc_data = pdf_processor.process_document(pdf_path)

            indexed_documents[filename] = {
                "info": {
                    "source": doc_data["source"],
                    "file_path": doc_data["file_path"],
                    "total_pages": doc_data["total_pages"],
                    "total_chunks": doc_data["total_chunks"],
                    "total_words": doc_data["total_words"],
                    "is_preset": True
                },
                "chunks": doc_data["chunks"]
            }

            print(
                f"[OK] Documento indexado automáticamente: {filename}"
            )

        except Exception as error:
            print(
                f"[ERROR] Error indexando {filename}: {error}"
            )


# Indexar los PDF incluidos en el proyecto
load_workspace_pdfs()


@app.route("/")
def serve_index():
    """
    Muestra la página principal ubicada en static/index.html.
    """

    return send_from_directory(
        app.static_folder,
        "index.html"
    )


@app.route("/api/health", methods=["GET"])
def health():
    """
    Ruta sencilla para comprobar que Flask funciona en Vercel.
    """

    return jsonify({
        "success": True,
        "status": "online",
        "message": "Aplicación Flask funcionando correctamente"
    })


@app.route("/api/status", methods=["GET"])
def get_status():
    """
    Devuelve el estado general del chatbot y los documentos indexados.
    """

    return jsonify({
        "status": "online",
        "cohere_configured": cohere_service.is_configured(),
        "total_documents": len(indexed_documents),
        "total_chunks": sum(
            len(document["chunks"])
            for document in indexed_documents.values()
        ),
        "documents": [
            document["info"]
            for document in indexed_documents.values()
        ]
    })


@app.route("/api/config-key", methods=["POST"])
def config_api_key():
    """
    Permite configurar la API Key de Cohere temporalmente.
    Para producción se recomienda usar COHERE_API_KEY en Vercel.
    """

    data = request.get_json() or {}

    api_key = data.get(
        "api_key",
        ""
    ).strip()

    if not api_key:
        return jsonify({
            "success": False,
            "error": "La API Key no puede estar vacía"
        }), 400

    try:
        cohere_service.set_api_key(api_key)

        return jsonify({
            "success": True,
            "cohere_configured": cohere_service.is_configured(),
            "message": "API Key de Cohere configurada correctamente"
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "error": f"Error configurando la API Key: {str(error)}"
        }), 500


@app.route("/api/documents", methods=["GET"])
def list_documents():
    """
    Devuelve todos los documentos indexados.
    """

    try:
        # Revisar si existen nuevos PDF en el proyecto
        load_workspace_pdfs()

        documents = [
            document["info"]
            for document in indexed_documents.values()
        ]

        return jsonify({
            "success": True,
            "documents": documents
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "error": f"Error consultando documentos: {str(error)}"
        }), 500


@app.route("/api/upload", methods=["POST"])
def upload_pdf():
    """
    Permite subir temporalmente un archivo PDF.
    Los archivos guardados en Vercel pueden desaparecer al reiniciar
    la función serverless.
    """

    if "file" not in request.files:
        return jsonify({
            "success": False,
            "error": "No se envió ningún archivo"
        }), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({
            "success": False,
            "error": "Nombre de archivo inválido"
        }), 400

    if not file.filename.lower().endswith(".pdf"):
        return jsonify({
            "success": False,
            "error": "Solo se permiten archivos en formato PDF"
        }), 400

    try:
        # Limpiar el nombre del archivo para evitar rutas peligrosas
        filename = secure_filename(file.filename)

        if not filename:
            return jsonify({
                "success": False,
                "error": "Nombre de archivo inválido"
            }), 400

        file_path = os.path.join(
            UPLOAD_DIR,
            filename
        )

        file.save(file_path)

        doc_data = pdf_processor.process_document(file_path)

        indexed_documents[filename] = {
            "info": {
                "source": doc_data["source"],
                "file_path": doc_data["file_path"],
                "total_pages": doc_data["total_pages"],
                "total_chunks": doc_data["total_chunks"],
                "total_words": doc_data["total_words"],
                "is_preset": False
            },
            "chunks": doc_data["chunks"]
        }

        return jsonify({
            "success": True,
            "message": (
                f"Documento '{filename}' subido "
                "e indexado exitosamente"
            ),
            "document": indexed_documents[filename]["info"]
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "error": f"Error al procesar el PDF: {str(error)}"
        }), 500


@app.route("/api/delete-document", methods=["POST"])
def delete_document():
    """
    Elimina un documento del índice almacenado en memoria.
    """

    data = request.get_json() or {}

    filename = data.get(
        "filename",
        ""
    ).strip()

    if not filename:
        return jsonify({
            "success": False,
            "error": "Debe proporcionar el nombre del documento"
        }), 400

    if filename in indexed_documents:
        del indexed_documents[filename]

        return jsonify({
            "success": True,
            "message": (
                f"Documento '{filename}' eliminado del índice"
            )
        })

    return jsonify({
        "success": False,
        "error": "Documento no encontrado"
    }), 404


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Procesa las preguntas del usuario utilizando los fragmentos
    de los PDF indexados y Cohere.
    """

    try:
        data = request.get_json() or {}

        query = data.get(
            "message",
            ""
        ).strip()

        active_sources = data.get(
            "active_sources",
            []
        )

        history = data.get(
            "history",
            []
        )

        if not query:
            return jsonify({
                "success": False,
                "error": "La pregunta no puede estar vacía"
            }), 400

        if not cohere_service.is_configured():
            return jsonify({
                "success": False,
                "error": (
                    "La API Key de Cohere no está configurada. "
                    "Agrega COHERE_API_KEY en las variables "
                    "de entorno de Vercel."
                )
            }), 500

        all_chunks = []

        # Usar únicamente las fuentes seleccionadas
        if active_sources:
            for source in active_sources:
                if source in indexed_documents:
                    all_chunks.extend(
                        indexed_documents[source]["chunks"]
                    )

        # Si no se seleccionaron fuentes, utilizar todas
        else:
            for document in indexed_documents.values():
                all_chunks.extend(
                    document["chunks"]
                )

        if not all_chunks:
            return jsonify({
                "success": True,
                "answer": (
                    "No hay fuentes de información seleccionadas "
                    "o indexadas actualmente. Activa o sube al "
                    "menos un documento PDF."
                ),
                "sources": []
            })

        # Buscar los fragmentos más relacionados con la pregunta
        top_chunks = cohere_service.search_relevant_chunks(
            query,
            all_chunks,
            top_k=5
        )

        # Generar respuesta con Cohere
        response_data = cohere_service.generate_answer(
            query,
            top_chunks,
            chat_history=history
        )

        return jsonify({
            "success": True,
            "answer": response_data.get(
                "answer",
                "No se pudo generar una respuesta"
            ),
            "sources": response_data.get(
                "sources",
                []
            ),
            "error": response_data.get("error")
        })

    except Exception as error:
        app.logger.exception(
            "Error procesando la solicitud del chatbot"
        )

        return jsonify({
            "success": False,
            "error": f"Error procesando la pregunta: {str(error)}"
        }), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error": "Ruta no encontrada"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "error": "Error interno del servidor"
    }), 500


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print(
        "Servidor BimBam Buy AI PDF Chatbot iniciado "
        "en http://localhost:5000"
    )
    print("=" * 60 + "\n")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )