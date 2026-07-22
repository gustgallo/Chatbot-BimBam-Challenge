import os
from typing import List, Dict, Any
from pypdf import PdfReader

class PDFProcessor:
    def __init__(self, chunk_size: int = 700, chunk_overlap: int = 150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def extract_text_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extrae el texto de un archivo PDF ubicado en el sistema de archivos.
        Devuelve una lista de páginas con su contenido y número de página.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"El archivo {file_path} no existe.")

        reader = PdfReader(file_path)
        pages_data = []
        filename = os.path.basename(file_path)

        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                pages_data.append({
                    "page": page_num,
                    "text": text,
                    "source": filename
                })

        return pages_data

    def extract_text_from_bytes(self, file_bytes, filename: str) -> List[Dict[str, Any]]:
        """
        Extrae texto de un objeto bytes de PDF.
        """
        reader = PdfReader(file_bytes)
        pages_data = []

        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                pages_data.append({
                    "page": page_num,
                    "text": text,
                    "source": filename
                })

        return pages_data

    def create_chunks(self, pages_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Divide las páginas extraídas en fragmentos (chunks) con solapamiento
        para preservar contexto en las consultas RAG.
        """
        chunks = []
        chunk_id = 0

        for p_data in pages_data:
            text = p_data["text"]
            source = p_data["source"]
            page = p_data["page"]

            if len(text) <= self.chunk_size:
                chunks.append({
                    "chunk_id": f"{source}_p{page}_{chunk_id}",
                    "text": text,
                    "source": source,
                    "page": page
                })
                chunk_id += 1
            else:
                # Sliding window chunking
                start = 0
                while start < len(text):
                    end = start + self.chunk_size
                    chunk_text = text[start:end]
                    
                    # Tratar de cortar en fin de palabra o oración para no romper frases
                    if end < len(text):
                        last_space = chunk_text.rfind(' ')
                        if last_space > self.chunk_size // 2:
                            end = start + last_space
                            chunk_text = text[start:end]

                    chunks.append({
                        "chunk_id": f"{source}_p{page}_{chunk_id}",
                        "text": chunk_text.strip(),
                        "source": source,
                        "page": page
                    })
                    chunk_id += 1

                    start += max(1, len(chunk_text) - self.chunk_overlap)

        return chunks

    def process_document(self, file_path: str) -> Dict[str, Any]:
        """
        Procesamiento completo de un documento local: lectura, extracción y chunking.
        """
        pages = self.extract_text_from_file(file_path)
        chunks = self.create_chunks(pages)
        filename = os.path.basename(file_path)
        total_words = sum(len(p["text"].split()) for p in pages)

        return {
            "source": filename,
            "file_path": file_path,
            "total_pages": len(pages),
            "total_chunks": len(chunks),
            "total_words": total_words,
            "pages": pages,
            "chunks": chunks
        }
