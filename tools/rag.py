from tools.base import BaseTool
import chromadb
import os
import uuid

class KnowledgeBaseTool(BaseTool):
    """Local Knowledge Base Tool using ChromaDB for RAG."""
    
    def __init__(self, emit_cb=None):
        self.emit_cb = emit_cb
        self.db_dir = os.path.join(os.getcwd(), "chroma_db")
        os.makedirs(self.db_dir, exist_ok=True)
        self._is_initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of ChromaDB to allow notification if download is needed."""
        if self._is_initialized:
            return

        # Check if the Chroma ONNX cache exists
        cache_dir = os.path.expanduser("~/.cache/chroma/onnx_models/all-MiniLM-L6-v2")
        if not os.path.exists(cache_dir):
            if self.emit_cb:
                self.emit_cb("system_msg", {"message": "📥 First-time RAG setup: Downloading embedding models (all-MiniLM-L6-v2). Please wait..."})

        self.client = chromadb.PersistentClient(path=self.db_dir)
        self.collection = self.client.get_or_create_collection(name="knowledge_base")
        self._is_initialized = True
        
    @property
    def name(self) -> str:
        return "knowledge_base"

    @property
    def description(self) -> str:
        return "Allows storing and retrieving text snippets from a local vector database. Useful for long-term memory or reading large documents."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["store", "search"],
                    "description": "Whether to 'store' text or 'search' for relevant information."
                },
                "text": {
                    "type": "string",
                    "description": "The text to store or the query to search for."
                },
                "metadata": {
                    "type": "string",
                    "description": "Optional metadata for storing (e.g., source file name)."
                }
            },
            "required": ["action", "text"]
        }

    def run(self, action: str, text: str, metadata: str = "user_input", **kwargs) -> str:
        try:
            self._ensure_initialized()
            if action == "store":
                doc_id = str(uuid.uuid4())
                self.collection.add(
                    documents=[text],
                    metadatas=[{"source": metadata}],
                    ids=[doc_id]
                )
                return f"Successfully stored text snippet with ID: {doc_id} and source: {metadata}"
                
            elif action == "search":
                results = self.collection.query(
                    query_texts=[text],
                    n_results=3
                )
                
                if not results['documents'][0]:
                    return "No relevant information found in the knowledge base."
                    
                output = "Found relevant snippets:\n"
                for i, doc in enumerate(results['documents'][0]):
                    meta = results['metadatas'][0][i].get("source", "unknown")
                    output += f"- [Source: {meta}]: {doc}\n"
                    
                return output
                
        except Exception as e:
            return f"Knowledge Base Error: {str(e)}"
