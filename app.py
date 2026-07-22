import os
import sys
import glob
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Reconfigurar stdout/stderr a UTF-8 para evitar errores de encoding en Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from pdf_processor import PDFProcessor
from cohere_service import CohereRAGService

# Cargar variables de entorno si existe .env
load_dotenv()

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

# Directorio base y carpeta de descargas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Servicios de procesamiento y Cohere AI
pdf_processor = PDFProcessor(chunk_size=700, chunk_overlap=150)
cohere_service = CohereRAGService()

# Estado en memoria de los documentos indexados
indexed_documents = {}

def load_workspace_pdfs():
    """
    Escanea e indexa automáticamente los archivos PDF de BimBam Buy presentes en el workspace.
    """
    pdf_files = glob.glob(os.path.join(BASE_DIR, "*.pdf"))
    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        if filename not in indexed_documents:
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
                print(f"[OK] Documento indexado automaticamente: {filename}")
            except Exception as e:
                print(f"[ERROR] Error indexando {filename}: {e}")

# Indexar los PDFs del workspace al iniciar
load_workspace_pdfs()

@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify({
        "status": "online",
        "cohere_configured": cohere_service.is_configured(),
        "total_documents": len(indexed_documents),
        "total_chunks": sum(len(doc["chunks"]) for doc in indexed_documents.values()),
        "documents": [doc["info"] for doc in indexed_documents.values()]
    })

@app.route("/api/config-key", methods=["POST"])
def config_api_key():
    data = request.get_json() or {}
    api_key = data.get("api_key", "").strip()
    if not api_key:
        return jsonify({"success": False, "error": "La API Key no puede estar vacía"}), 400

    cohere_service.set_api_key(api_key)
    return jsonify({
        "success": True,
        "cohere_configured": cohere_service.is_configured(),
        "message": "API Key de Cohere configurada correctamente"
    })

@app.route("/api/documents", methods=["GET"])
def list_documents():
    """
    Retorna la lista de todos los documentos indexados con su estado y metadatos.
    """
    # Actualizar escaneo por si hay nuevos PDFs
    load_workspace_pdfs()
    docs = [doc["info"] for doc in indexed_documents.values()]
    return jsonify({"success": True, "documents": docs})

@app.route("/api/upload", methods=["POST"])
def upload_pdf():
    """
    Permite al usuario subir un archivo PDF a través de la interfaz web.
    """
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No se envió ningún archivo"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "Nombre de archivo inválido"}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({"success": False, "error": "Solo se permiten archivos en formato PDF (.pdf)"}), 400

    try:
        filename = file.filename
        file_path = os.path.join(UPLOAD_DIR, filename)
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
            "message": f"Documento '{filename}' subido e indexado exitosamente",
            "document": indexed_documents[filename]["info"]
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Error al procesar el PDF: {str(e)}"}), 500

@app.route("/api/delete-document", methods=["POST"])
def delete_document():
    data = request.get_json() or {}
    filename = data.get("filename")
    if filename in indexed_documents:
        del indexed_documents[filename]
        return jsonify({"success": True, "message": f"Documento '{filename}' eliminado del índice"})
    return jsonify({"success": False, "error": "Documento no encontrado"}), 404

@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Procesa la pregunta del usuario consultando las fuentes PDF seleccionadas usando RAG con Cohere.
    """
    data = request.get_json() or {}
    query = data.get("message", "").strip()
    active_sources = data.get("active_sources", []) # Lista de nombres de archivos seleccionados por el usuario
    history = data.get("history", [])

    if not query:
        return jsonify({"success": False, "error": "La pregunta no puede estar vacía"}), 400

    # Recopilar fragmentos solo de las fuentes activas
    all_chunks = []
    if active_sources:
        for src in active_sources:
            if src in indexed_documents:
                all_chunks.extend(indexed_documents[src]["chunks"])
    else:
        # Si no especifica fuentes activas, buscar en todas las fuentes disponibles
        for doc in indexed_documents.values():
            all_chunks.extend(doc["chunks"])

    if not all_chunks:
        return jsonify({
            "success": True,
            "answer": "⚠️ No hay fuentes de información seleccionadas o indexadas actualmente. Por favor activa o sube al menos un documento PDF en la columna derecha.",
            "sources": []
        })

    # 1. Búsqueda de fragmentos más relevantes con embeddings
    top_chunks = cohere_service.search_relevant_chunks(query, all_chunks, top_k=5)

    # 2. Generación de respuesta con Cohere Chat
    response_data = cohere_service.generate_answer(query, top_chunks, chat_history=history)

    return jsonify({
        "success": True,
        "answer": response_data["answer"],
        "sources": response_data.get("sources", []),
        "error": response_data.get("error")
    })

if __name__ == "__main__":
    print("\n" + "="*60)
    print("Servidor BimBam Buy AI PDF Chatbot iniciado en http://localhost:5000")
    print("="*60 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=True)
