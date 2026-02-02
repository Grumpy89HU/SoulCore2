import sqlite3
import json
import uuid
import os
import logging
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.http import models
import networkx as nx
from sentence_transformers import SentenceTransformer, CrossEncoder

class SoulCoreDatabase:
    def __init__(self, db_path="vault/db/soulcore.db"):
        self.logger = logging.getLogger("Database")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        
        self.vector_path = "vault/db/soul_vectors"
        self.graph_path = "vault/db/social_graph.json"
        
        self._init_sqlite()
        
        # Ha nincs meg a projekt konfig, akkor ez az első indítás
        if not self.get_config("project"):
            self._seed_initial_data()
        
        self.rag_cfg = self.get_config("rag_system")
        self.storage_cfg = self.get_config("storage")

        # 1. VEKTOROS MOTOR (Qdrant)
        print(f"🧬 Szuverén Embedding betöltése: {self.rag_cfg['embedding']['local_path']}")
        self.embedding_model = SentenceTransformer(self.rag_cfg['embedding']['local_path'])
        self.client = QdrantClient(path=self.vector_path)
        self._init_vector_collections()

        # 2. RERANKER
        self.reranker = None
        if self.rag_cfg['reranker'].get('enabled'):
            print(f"🔍 Szuverén Reranker aktív.")
            self.reranker = CrossEncoder(self.rag_cfg['reranker']['local_path'])

        # 3. GRÁF MEMÓRIA
        self.graph_db = self._load_graph()
        print(f"🏛️ SoulCore 2.0: SQL + RAG + Graph élesítve.")

    def _init_sqlite(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('CREATE TABLE IF NOT EXISTS system_config (key TEXT PRIMARY KEY, value TEXT)')
            # JAVÍTVA: n_ctx hozzáadva a táblához
            c.execute('''CREATE TABLE IF NOT EXISTS slots (
                name TEXT PRIMARY KEY, enabled INTEGER, role TEXT, engine TEXT, 
                model_name TEXT, filename TEXT, gpu_id INTEGER, max_vram_mb INTEGER, 
                n_ctx INTEGER, temperature REAL, model_path TEXT)''')
            c.execute('CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, username TEXT, role TEXT)')
            c.execute('''CREATE TABLE IF NOT EXISTS chats (
                chat_id TEXT PRIMARY KEY, user_id TEXT, title TEXT, 
                created_at TIMESTAMP, last_active TIMESTAMP)''')
            c.execute('''CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, role TEXT, 
                content TEXT, debug_data TEXT, timestamp TIMESTAMP)''')
            conn.commit()

    def get_config(self, key):
        with sqlite3.connect(self.db_path) as conn:
            res = conn.execute("SELECT value FROM system_config WHERE key = ?", (key,)).fetchone()
            return json.loads(res[0]) if res else None

    def set_config(self, key, value):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO system_config VALUES (?, ?)", (key, json.dumps(value)))
            conn.commit()

    # --- SLOTOK ---
    def save_slot(self, name, data):
        with sqlite3.connect(self.db_path) as conn:
            # JAVÍTVA: Pontosan 11 darab '?' kell a 11 oszlophoz
            conn.execute('''INSERT OR REPLACE INTO slots VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (
                    name, 
                    data.get('enabled', 0), 
                    data.get('role'), 
                    data.get('engine'), 
                    data.get('model_name'), 
                    data.get('filename'), 
                    data.get('gpu_id', 0), 
                    data.get('max_vram_mb', 0), 
                    data.get('n_ctx', 2048), 
                    data.get('temperature', 0.7), 
                    data.get('model_path')
                ))
            conn.commit()

    def get_enabled_slots(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return {row['name']: dict(row) for row in conn.execute("SELECT * FROM slots WHERE enabled = 1").fetchall()}

    # --- RAG MŰVELETEK ---
    def _init_vector_collections(self):
        try:
            collections = self.client.get_collections().collections
            if not any(c.name == "soul_vectors" for c in collections):
                dim = self.rag_cfg['embedding']['vector_dimension']
                self.client.create_collection(
                    collection_name="soul_vectors",
                    vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE)
                )
        except Exception as e: self.logger.error(f"Vektor hiba: {e}")

    def query_vault(self, query_text, user_id=None, limit=None):
        try:
            limit = limit or self.rag_cfg['context']['max_chunks_per_query']
            prefix = self.rag_cfg['embedding']['instruction_type']['query']
            vector = self.embedding_model.encode(f"{prefix}{query_text}").tolist()
            filt = models.Filter(must=[models.FieldCondition(key="user_id", match=models.MatchValue(value=user_id))]) if user_id else None
            results = self.client.search(collection_name="soul_vectors", query_vector=vector, limit=limit, query_filter=filt)
            if not results: return ""
            passages = [res.payload.get("text", "") for res in results]
            if self.reranker and len(passages) > 1:
                scores = self.reranker.predict([[query_text, p] for p in passages])
                ranked = sorted(zip(scores, passages), key=lambda x: x[0], reverse=True)
                return " | ".join([p for s, p in ranked if s >= self.rag_cfg['reranker']['relevance_threshold']][:self.rag_cfg['reranker']['top_n']])
            return " | ".join(passages[:5])
        except Exception as e: return ""

    def save_to_vault(self, text, user_id="Grumpy", chat_id="default"):
        prefix = self.rag_cfg['embedding']['instruction_type']['document']
        vector = self.embedding_model.encode(f"{prefix}{text}").tolist()
        self.client.upsert(
            collection_name="soul_vectors",
            points=[models.PointStruct(id=int(datetime.now().timestamp()*1000), vector=vector, payload={
                "user_id": user_id, "chat_id": chat_id, "text": text, "timestamp": datetime.now().isoformat()
            })]
        )

    def save_message(self, chat_id, role, content, debug=None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT INTO messages (chat_id, role, content, debug_data, timestamp) VALUES (?, ?, ?, ?, ?)",
                         (chat_id, role, content, json.dumps(debug) if debug else None, datetime.now()))
            # JAVÍTVA: chat létrehozása, ha még nincs
            conn.execute("INSERT OR IGNORE INTO chats (chat_id, user_id, created_at) VALUES (?, ?, ?)", (chat_id, "Grumpy", datetime.now()))
            conn.execute("UPDATE chats SET last_active = ? WHERE chat_id = ?", (datetime.now(), chat_id))
            conn.commit()

    def _load_graph(self):
        if os.path.exists(self.graph_path):
            with open(self.graph_path, 'r', encoding='utf-8') as f:
                return nx.node_link_graph(json.load(f))
        return nx.MultiDiGraph()

    def _seed_initial_data(self):
        print("🌱 Teljes SoulCore rendszer-migráció az adatbázisba...")
        
        self.set_config("project", {"name": "SoulCore", "version": "2.0", "identity": "Kópé", "user_lang": "hu", "internal_lang": "en"})
        self.set_config("api", {"host": "0.0.0.0", "port": 8000, "cors": ["*"], "timeout": 60})
        self.set_config("hardware", {"gpu_count": 1, "total_vram_limit_mb": 16384, "cuda_device": "cuda:0"})
        self.set_config("storage", {"model_root": "./models", "vault_root": "./vault", "db_limit_gb": 1500})
        
        self.set_config("rag_system", {
            "enabled": True,
            "embedding": {
                "local_path": "/mnt/raid/soulcore/SoulCore2.0/models/ragsystem/embeddinggemma",
                "vector_dimension": 768, "instruction_type": {"query": "query: ", "document": "passage: "}
            },
            "context": {"window_size": 131072, "chunk_size": 4096, "max_chunks_per_query": 15},
            "reranker": {"enabled": False, "local_path": "/mnt/raid/soulcore/SoulCore2.0/models/reranker/qwen3vlreranker2B", "top_n": 5, "relevance_threshold": 0.65}
        })

        # JAVÍTVA: n_ctx és max_vram_mb patikamérlegen porciózva a 16GB-hoz
        slots = {
            "translator": {
                "enabled": 1, "role": "Translator", "engine": "gguf", 
                "model_name": "Translategemma-4b", "filename": "translategemma-4b-it-Q4_K_M.gguf", 
                "gpu_id": 0, "max_vram_mb": 2500, "n_ctx": 1024, "temperature": 0.1, "model_path": "./models"
            },
            "scribe": {
                "enabled": 1, "role": "Gatekeeper", "engine": "gguf", 
                "model_name": "Llama-3.2-3B", "filename": "Llama-3.2-3B-Instruct-Q3_K_XL.gguf", 
                "gpu_id": 0, "max_vram_mb": 3000, "n_ctx": 2048, "temperature": 0.1, "model_path": "./models"
            },
            "valet": {
                "enabled": 1, "role": "Logistics", "engine": "gguf", 
                "model_name": "Llama-3.2-3B", "filename": "Llama-3.2-3B-Instruct-Q3_K_XL.gguf", 
                "gpu_id": 0, "max_vram_mb": 3000, "n_ctx": 2048, "temperature": 0.4, "model_path": "./models"
            },
            "king": {
                "enabled": 1, "role": "Sovereign", "engine": "gguf", 
                "model_name": "Gemma3 4B", "filename": "google_gemma-3-4b-it-Q4_K_M.gguf", 
                "gpu_id": 0, "max_vram_mb": 7000, "n_ctx": 8192, "temperature": 0.7, "model_path": "./models"
            }
        }
        for name, data in slots.items():
            self.save_slot(name, data)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?)", ("Grumpy", "Grumpy", "admin"))
            conn.commit()

    
    def get_full_config(self):
        """Összegyűjti az összes rendszerkonfigurációt egy struktúrába a frontend számára."""
        # Biztonsági háló: ha valamiért üres a lekérdezés, ne dőljön össze a front-end
        return {
            "project": self.get_config("project") or {},
            "api": self.get_config("api") or {},
            "hardware": self.get_config("hardware") or {},
            "storage": self.get_config("storage") or {},
            "rag_system": self.get_config("rag_system") or {}
        }
    
    def close(self):
        if hasattr(self, 'client'): self.client._client.close()