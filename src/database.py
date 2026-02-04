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
        
<<<<<<< HEAD
        # Kezdeti adatok betöltése, ha üres az adatbázis
=======
        # Ha nincs meg a projekt konfig, akkor ez az első indítás
>>>>>>> d3e372da30590eab253bed78f91e2eca3a01a21e
        if not self.get_config("project"):
            self._seed_initial_data()
        
        self.rag_cfg = self.get_config("rag_system")
        self.storage_cfg = self.get_config("storage")

        # 1. VEKTOROS MOTOR (Qdrant)
<<<<<<< HEAD
        try:
            print(f"🧬 Szuverén Embedding betöltése: {self.rag_cfg['embedding']['local_path']}")
            self.embedding_model = SentenceTransformer(self.rag_cfg['embedding']['local_path'])
            self.client = QdrantClient(path=self.vector_path)
            self._init_vector_collections()
        except Exception as e:
            self.logger.error(f"Vektoros motor hiba: {e}")

        # 2. RERANKER
        self.reranker = None
        if self.rag_cfg.get('reranker', {}).get('enabled'):
            print(f"🔍 Szuverén Reranker aktív.")
            try:
                self.reranker = CrossEncoder(self.rag_cfg['reranker']['local_path'])
            except Exception as e:
                self.logger.error(f"Reranker hiba: {e}")

=======
        print(f"🧬 Szuverén Embedding betöltése: {self.rag_cfg['embedding']['local_path']}")
        self.embedding_model = SentenceTransformer(self.rag_cfg['embedding']['local_path'])
        self.client = QdrantClient(path=self.vector_path)
        self._init_vector_collections()

        # 2. RERANKER
        self.reranker = None
        if self.rag_cfg['reranker'].get('enabled'):
            print(f"🔍 Szuverén Reranker aktív.")
            self.reranker = CrossEncoder(self.rag_cfg['reranker']['local_path'])

>>>>>>> d3e372da30590eab253bed78f91e2eca3a01a21e
        # 3. GRÁF MEMÓRIA
        self.graph_db = self._load_graph()
        print(f"🏛️ SoulCore 2.0: SQL + RAG + Graph élesítve.")

    def _init_sqlite(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('CREATE TABLE IF NOT EXISTS system_config (key TEXT PRIMARY KEY, value TEXT)')
<<<<<<< HEAD
=======
            # JAVÍTVA: n_ctx hozzáadva a táblához
>>>>>>> d3e372da30590eab253bed78f91e2eca3a01a21e
            c.execute('''CREATE TABLE IF NOT EXISTS slots (
                name TEXT PRIMARY KEY, enabled INTEGER, role TEXT, engine TEXT, 
                model_name TEXT, filename TEXT, gpu_id INTEGER, max_vram_mb INTEGER, 
                n_ctx INTEGER, temperature REAL, model_path TEXT)''')
            c.execute('CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, username TEXT, role TEXT)')
<<<<<<< HEAD
            
            c.execute('''CREATE TABLE IF NOT EXISTS chats (
                chat_id TEXT PRIMARY KEY, user_id TEXT, title TEXT, 
                created_at TEXT, last_active TEXT)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, role TEXT, 
                content TEXT, debug_data TEXT, timestamp TEXT)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS long_memory (
                key TEXT PRIMARY KEY, content TEXT, metadata TEXT, timestamp TEXT)''')
            conn.commit()

    # --- KONFIGURÁCIÓ KEZELÉS ---
=======
            c.execute('''CREATE TABLE IF NOT EXISTS chats (
                chat_id TEXT PRIMARY KEY, user_id TEXT, title TEXT, 
                created_at TIMESTAMP, last_active TIMESTAMP)''')
            c.execute('''CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, role TEXT, 
                content TEXT, debug_data TEXT, timestamp TIMESTAMP)''')
            conn.commit()

>>>>>>> d3e372da30590eab253bed78f91e2eca3a01a21e
    def get_config(self, key):
        with sqlite3.connect(self.db_path) as conn:
            res = conn.execute("SELECT value FROM system_config WHERE key = ?", (key,)).fetchone()
            return json.loads(res[0]) if res else None

    def set_config(self, key, value):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO system_config VALUES (?, ?)", (key, json.dumps(value)))
            conn.commit()

<<<<<<< HEAD
    def get_full_config(self):
        return {
            "project": self.get_config("project") or {},
            "api": self.get_config("api") or {},
            "hardware": self.get_config("hardware") or {},
            "storage": self.get_config("storage") or {},
            "rag_system": self.get_config("rag_system") or {}
        }

    # --- SLOT KEZELÉS ---
    def save_slot(self, name, data):
        with sqlite3.connect(self.db_path) as conn:
=======
    # --- SLOTOK ---
    def save_slot(self, name, data):
        with sqlite3.connect(self.db_path) as conn:
            # JAVÍTVA: Pontosan 11 darab '?' kell a 11 oszlophoz
>>>>>>> d3e372da30590eab253bed78f91e2eca3a01a21e
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

<<<<<<< HEAD
    # --- RAG / VEKTOR MŰVELETEK ---
=======
    # --- RAG MŰVELETEK ---
>>>>>>> d3e372da30590eab253bed78f91e2eca3a01a21e
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
<<<<<<< HEAD
            
=======
>>>>>>> d3e372da30590eab253bed78f91e2eca3a01a21e
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
<<<<<<< HEAD

    # --- CHAT ÉS ÜZENET KEZELÉS ---
    def save_message(self, chat_id, role, content, debug=None):
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            debug_val = json.dumps(debug) if debug and not isinstance(debug, str) else debug
            conn.execute("INSERT INTO messages (chat_id, role, content, debug_data, timestamp) VALUES (?, ?, ?, ?, ?)",
                         (chat_id, role, content, debug_val, now))
            
            res = conn.execute("SELECT chat_id FROM chats WHERE chat_id = ?", (chat_id,)).fetchone()
            if not res:
                title = (content[:30] + '...') if len(content) > 30 else content
                conn.execute("INSERT INTO chats (chat_id, user_id, title, created_at, last_active) VALUES (?, ?, ?, ?, ?)",
                             (chat_id, "Grumpy", title, now, now))
            else:
                conn.execute("UPDATE chats SET last_active = ? WHERE chat_id = ?", (now, chat_id))
            conn.commit()

    def get_chat_history(self, chat_id, limit=20):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            res = conn.execute("SELECT role, content, timestamp FROM messages WHERE chat_id = ? ORDER BY timestamp DESC LIMIT ?", 
                               (chat_id, limit)).fetchall()
            return list(reversed([dict(row) for row in res]))

    def get_all_chat_sessions(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            res = conn.execute("SELECT chat_id, title, last_active FROM chats ORDER BY last_active DESC").fetchall()
            return [dict(row) for row in res]

    def update_chat_title(self, chat_id, title):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE chats SET title = ? WHERE chat_id = ?", (title, chat_id))
            conn.commit()

    # --- HOSSZÚ TÁVÚ MEMÓRIA ---
    def set_long_memory(self, key, text, metadata=""):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO long_memory (key, content, metadata, timestamp) VALUES (?, ?, ?, ?)", 
                         (key, text, metadata, datetime.now().isoformat()))
            conn.commit()

    def get_all_long_memory(self):
        with sqlite3.connect(self.db_path) as conn:
            res = conn.execute("SELECT content FROM long_memory ORDER BY timestamp DESC").fetchall()
            if not res: return "No long-term memories stored yet."
            return "\n".join([row[0] for row in res])

    def save_to_long_memory(self, content, metadata=""):
        """Új tény mentése automatikus kulccsal."""
        with sqlite3.connect(self.db_path) as conn:
            key = str(uuid.uuid4())[:8]
            conn.execute(
                "INSERT INTO long_memory (key, content, metadata, timestamp) VALUES (?, ?, ?, ?)",
                (key, content, metadata, datetime.now().isoformat())
            )
            conn.commit()
            return key
=======

    def save_message(self, chat_id, role, content, debug=None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT INTO messages (chat_id, role, content, debug_data, timestamp) VALUES (?, ?, ?, ?, ?)",
                         (chat_id, role, content, json.dumps(debug) if debug else None, datetime.now()))
            # JAVÍTVA: chat létrehozása, ha még nincs
            conn.execute("INSERT OR IGNORE INTO chats (chat_id, user_id, created_at) VALUES (?, ?, ?)", (chat_id, "Grumpy", datetime.now()))
            conn.execute("UPDATE chats SET last_active = ? WHERE chat_id = ?", (datetime.now(), chat_id))
            conn.commit()
>>>>>>> d3e372da30590eab253bed78f91e2eca3a01a21e

    # --- GRÁF ÉS SEED ADATOK ---
    def _load_graph(self):
        if os.path.exists(self.graph_path):
<<<<<<< HEAD
            try:
                with open(self.graph_path, 'r', encoding='utf-8') as f:
                    return nx.node_link_graph(json.load(f))
            except Exception: return nx.MultiDiGraph()
=======
            with open(self.graph_path, 'r', encoding='utf-8') as f:
                return nx.node_link_graph(json.load(f))
>>>>>>> d3e372da30590eab253bed78f91e2eca3a01a21e
        return nx.MultiDiGraph()

    def _seed_initial_data(self):
        print("🌱 Teljes SoulCore rendszer-migráció az adatbázisba...")
<<<<<<< HEAD
=======
        
>>>>>>> d3e372da30590eab253bed78f91e2eca3a01a21e
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

<<<<<<< HEAD
=======
        # JAVÍTVA: n_ctx és max_vram_mb patikamérlegen porciózva a 16GB-hoz
>>>>>>> d3e372da30590eab253bed78f91e2eca3a01a21e
        slots = {
            "translator": {
                "enabled": 1, "role": "Translator", "engine": "gguf", 
                "model_name": "Translategemma-4b", "filename": "translategemma-4b-it-Q4_K_M.gguf", 
                "gpu_id": 0, "max_vram_mb": 2500, "n_ctx": 1024, "temperature": 0.1, "model_path": "./models"
            },
            "scribe": {
                "enabled": 1, "role": "Gatekeeper", "engine": "gguf", 
<<<<<<< HEAD
                "model_name": "NuExtract-v1.5", "filename": "NuExtract-v1.5-Q3_K_XL.gguf", 
                "gpu_id": 0, "max_vram_mb": 3000, "n_ctx": 2048, "temperature": 0.0, "model_path": "./models"
            },
            "valet": {
                "enabled": 1, "role": "Logistics", "engine": "gguf", 
                "model_name": "Qwen2.5 1.5B", "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf", 
                "gpu_id": 0, "max_vram_mb": 4000, "n_ctx": 2048, "temperature": 0.4, "model_path": "./models"
=======
                "model_name": "Llama-3.2-3B", "filename": "Llama-3.2-3B-Instruct-Q3_K_XL.gguf", 
                "gpu_id": 0, "max_vram_mb": 3000, "n_ctx": 2048, "temperature": 0.1, "model_path": "./models"
            },
            "valet": {
                "enabled": 1, "role": "Logistics", "engine": "gguf", 
                "model_name": "Llama-3.2-3B", "filename": "Llama-3.2-3B-Instruct-Q3_K_XL.gguf", 
                "gpu_id": 0, "max_vram_mb": 3000, "n_ctx": 2048, "temperature": 0.4, "model_path": "./models"
>>>>>>> d3e372da30590eab253bed78f91e2eca3a01a21e
            },
            "king": {
                "enabled": 1, "role": "Sovereign", "engine": "gguf", 
                "model_name": "Gemma3 4B", "filename": "google_gemma-3-4b-it-Q4_K_M.gguf", 
                "gpu_id": 0, "max_vram_mb": 7000, "n_ctx": 8192, "temperature": 0.7, "model_path": "./models"
            }
        }
        for name, data in slots.items():
            self.save_slot(name, data)
<<<<<<< HEAD

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?)", ("Grumpy", "Grumpy", "admin"))
            conn.commit()
=======
>>>>>>> d3e372da30590eab253bed78f91e2eca3a01a21e

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
<<<<<<< HEAD
        if hasattr(self, 'client'): 
            try:
                self.client._client.close()
            except: pass
=======
        if hasattr(self, 'client'): self.client._client.close()
>>>>>>> d3e372da30590eab253bed78f91e2eca3a01a21e
