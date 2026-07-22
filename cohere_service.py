import os
import math
import cohere
from typing import List, Dict, Any, Optional

class CohereRAGService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("COHERE_API_KEY", "")
        self.client = None
        if self.api_key:
            self._init_client(self.api_key)

    def set_api_key(self, api_key: str):
        self.api_key = api_key.strip()
        self._init_client(self.api_key)

    def _init_client(self, api_key: str):
        try:
            # Cohere SDK v5+ supports ClientV2 or Client
            if hasattr(cohere, "ClientV2"):
                self.client = cohere.ClientV2(api_key=api_key)
            else:
                self.client = cohere.Client(api_key=api_key)
        except Exception as e:
            print(f"Error inicializando cliente Cohere: {e}")
            self.client = None

    def is_configured(self) -> bool:
        return bool(self.api_key and self.client)

    def compute_cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """
        Cálculo de similitud cosenoidal en Python puro sin dependencias de DLL externas (NumPy).
        """
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot_product / (norm_a * norm_b))

    def _fallback_keyword_similarity(self, query: str, text: str) -> float:
        """
        Búsqueda por coincidencia de palabras clave para fallback en caso de error de red o API key.
        """
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())
        if not query_words or not text_words:
            return 0.0
        intersection = query_words.intersection(text_words)
        return len(intersection) / math.sqrt(len(query_words) * len(text_words))

    def search_relevant_chunks(self, query: str, chunks: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Busca los fragmentos más relevantes para la consulta utilizando embeddings de Cohere.
        """
        if not chunks:
            return []

        scored_chunks = []
        chunk_texts = [c["text"] for c in chunks]

        if self.is_configured():
            try:
                # Generar embedding para la pregunta y para los chunks usando embed-multilingual-v3.0
                response_embeds = self.client.embed(
                    texts=[query] + chunk_texts,
                    model="embed-multilingual-v3.0",
                    input_type="search_query"
                )

                embeddings = response_embeds.embeddings
                query_vec = embeddings[0]
                chunk_vecs = embeddings[1:]

                for idx, chunk in enumerate(chunks):
                    sim = self.compute_cosine_similarity(query_vec, chunk_vecs[idx])
                    chunk_copy = dict(chunk)
                    chunk_copy["score"] = sim
                    scored_chunks.append(chunk_copy)

                scored_chunks.sort(key=lambda x: x["score"], reverse=True)
                return scored_chunks[:top_k]

            except Exception as e:
                print(f"Error al generar embeddings con Cohere, usando fallback: {e}")

        # Fallback si no hay API Key o falla embedding
        for chunk in chunks:
            score = self._fallback_keyword_similarity(query, chunk["text"])
            chunk_copy = dict(chunk)
            chunk_copy["score"] = score
            scored_chunks.append(chunk_copy)

        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        return scored_chunks[:top_k]

    def generate_answer(self, query: str, relevant_chunks: List[Dict[str, Any]], chat_history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Genera una respuesta utilizando la API de Chat de Cohere con RAG (Retrieval Augmented Generation).
        """
        if not self.is_configured():
            return {
                "answer": "⚠️ Por favor, ingresa una **API Key válida de Cohere** en la esquina superior derecha o en la configuración para poder procesar la consulta con Inteligencia Artificial.",
                "sources": [],
                "error": "API Key no configurada"
            }

        if not relevant_chunks:
            return {
                "answer": "No se encontraron fragmentos de información relevantes en los documentos cargados actualmente.",
                "sources": []
            }

        # Construir contexto para la API de Cohere
        context_str = ""
        unique_sources = {}
        for idx, chunk in enumerate(relevant_chunks, start=1):
            src = chunk['source']
            page = chunk['page']
            context_str += f"\n--- DOCUMENTO FUENTE [{idx}]: {src} (Página {page}) ---\n{chunk['text']}\n"
            
            key = f"{src}_p{page}"
            if key not in unique_sources:
                unique_sources[key] = {
                    "source": src,
                    "page": page,
                    "snippet": chunk['text'][:180] + "..." if len(chunk['text']) > 180 else chunk['text']
                }

        system_prompt = (
            "Eres el asistente virtual con Inteligencia Artificial de BimBam Buy (E-commerce de compras digitales ágiles y seguras).\n"
            "Tu misión es responder las preguntas de los usuarios utilizando EXCLUSIVAMENTE la información contenida en los fragmentos de documentos proporcionados a continuación.\n\n"
            "REGLAS E STRICTAS:\n"
            "1. Responde de manera clara, amable, profesional y concisa en español.\n"
            "2. Si la respuesta está contenida en los documentos, indícala citando los documentos fuente y páginas utilizadas (ejemplo: [Politicas de Reembolsos.pdf, Pág 1]).\n"
            "3. Si la pregunta no se puede responder con los documentos proporcionados, indica amablemente que la información no se encuentra en las fuentes actuales de BimBam Buy.\n"
            "4. Utiliza formato Markdown (viñetas, negritas) para facilitar la lectura al usuario.\n\n"
            f"DOCUMENTOS FUENTE DISPONIBLES:\n{context_str}"
        )

        try:
            # Invocar la API de Chat de Cohere
            messages = [{"role": "system", "content": system_prompt}]
            
            # Agregar historial si existe
            if chat_history:
                for msg in chat_history[-4:]: # últimos 4 mensajes
                    messages.append({
                        "role": "user" if msg.get("role") == "user" else "assistant",
                        "content": msg.get("content", "")
                    })

            messages.append({"role": "user", "content": query})

            # Llamada al modelo Cohere (ClientV2 o Client)
            if hasattr(self.client, "chat"):
                response = self.client.chat(
                    model="command-r-08-2024", # O command-r-plus / command-r
                    messages=messages,
                    temperature=0.3
                )
                
                # Extraer texto según estructura de respuesta Cohere v2 / v1
                if hasattr(response, "message") and hasattr(response.message, "content"):
                    if isinstance(response.message.content, list):
                        answer_text = "".join([c.text for c in response.message.content if hasattr(c, "text")])
                    else:
                        answer_text = str(response.message.content)
                elif hasattr(response, "text"):
                    answer_text = response.text
                else:
                    answer_text = str(response)

            return {
                "answer": answer_text,
                "sources": list(unique_sources.values())
            }

        except Exception as e:
            print(f"Error al llamar a Cohere Chat API: {e}")
            # Si falla el modelo especificado, intentar con 'command-r'
            try:
                response = self.client.chat(
                    model="command-r",
                    messages=messages,
                    temperature=0.3
                )
                if hasattr(response, "message") and hasattr(response.message, "content"):
                    answer_text = "".join([c.text for c in response.message.content if hasattr(c, "text")])
                elif hasattr(response, "text"):
                    answer_text = response.text
                else:
                    answer_text = str(response)

                return {
                    "answer": answer_text,
                    "sources": list(unique_sources.values())
                }
            except Exception as e2:
                return {
                    "answer": f"❌ Error al consultar la API de Cohere: {str(e2)}. Por favor verifica tu API Key.",
                    "sources": [],
                    "error": str(e2)
                }
