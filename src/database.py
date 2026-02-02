import os
import datetime
import json
import logging
import yaml
from qdrant_client import QdrantClient
from qdrant_client.http import models
import networkx as nx
from sentence_transformers import SentenceTransformer, CrossEncoder

class SoulCoreDatabase:
    def __init__(self, config_path="conf/soulcore_config.yaml"):
        self.logger = logging.getLogger("Database")
        
        # 1. Konfiguráció betöltése
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Kritikus hiba: A konfiguráció nem található: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            full_config = yaml.safe_load(f)
            self.rag_cfg = full_config['rag_system']
            self.storage_cfg = full_config['storage']
            self.db_cfg = full_config['databases']

        # 2. Útvonalak és könyvtárak
        self.db_root = self.storage_cfg['vault_root']
        self.vector_path = self.db_cfg['vector_vault']['path']
        self.graph_path = self.db_cfg['graph_vault']['file_path']
        
        self.scratchpad_path = os.path.join(self.db_root, "scratchpad.txt")
        self.notes_path = os.path.join(self.db_root, "internal_notes.log")

        os.makedirs(os.path.dirname(self.graph_path), exist_ok=True)
        os.makedirs(self.vector_path, exist_ok=True)
        os.makedirs(self.db_root, exist_ok=True)

        # 3. VEKTOROS MOTOR
        embed_local_path = self.rag_cfg['embedding']['local_path']
        print(f"🧬 Szuverén Embedding betöltése: {embed_local_path}")
        self.embedding_model = SentenceTransformer(embed_local_path)
        
        # Lokális kliens inicializálása
        self.client = QdrantClient(path=self.vector_path)
        
        # 4. RERANKER
        self.reranker = None
        if self.rag_cfg['reranker']['enabled']:
            rerank_local_path = self.rag_cfg['reranker']['local_path']
            print(f"🔍 Szuverén Reranker betöltése: {rerank_local_path}")
            self.reranker = CrossEncoder(rerank_local_path)
        
        # 5. PRIVÁT GRÁF MEMÓRIA
        self.graph_db = self._load_graph()
        
        self._init_collections()
        print(f"🏛️ SoulCore 2.0 Database: Vault aktív ({self.vector_path})")

    def _init_collections(self):
        try:
            collections = self.client.get_collections().collections
            if not any(c.name == "soul_vectors" for c in collections):
                dim = self.rag_cfg['embedding']['vector_dimension']
                self.client.create_collection(
                    collection_name="soul_vectors",
                    vectors_config=models.VectorParams(
                        size=dim,
                        distance=models.Distance.COSINE
                    ),
                )
                print(f"✅ Új vektoros kollekció létrehozva: {dim} dimenzió.")
        except Exception as e:
            self.logger.error(f"Hiba a vektoros tár indításakor: {e}")

    def query_vault(self, query_text, user_id=None, limit=None):
        try:
            limit = limit or self.rag_cfg['context']['max_chunks_per_query']
            prefix = self.rag_cfg['embedding']['instruction_type']['query']
            prefixed_query = f"{prefix}{query_text}"
            
            query_vector = self.embedding_model.encode(prefixed_query).tolist()

            query_filter = None
            if user_id:
                query_filter = models.Filter(
                    must=[models.FieldCondition(key="user_id", match=models.MatchValue(value=user_id))]
                )

            # --- VERZIÓÁTHIDALÓ KERESÉS ---
            # Ha a közvetlen .search nem elérhető, megpróbáljuk a belső motoron keresztül
            if hasattr(self.client, 'search'):
                results = self.client.search(
                    collection_name="soul_vectors",
                    query_vector=query_vector,
                    limit=limit,
                    query_filter=query_filter
                )
            else:
                # Kényszerített lokális hívás friss verziókhoz
                results = self.client._client.search(
                    collection_name="soul_vectors",
                    query_vector=query_vector,
                    limit=limit,
                    query_filter=query_filter
                )

            if not results:
                return ""

            passages = [res.payload.get("text", "") for res in results]

            if self.reranker and len(passages) > 1:
                scores = self.reranker.predict([[query_text, p] for p in passages])
                ranked = sorted(zip(scores, passages), key=lambda x: x[0], reverse=True)
                threshold = self.rag_cfg['reranker']['relevance_threshold']
                final_passages = [p for s, p in ranked if s >= threshold]
                top_n = self.rag_cfg['reranker']['top_n']
                return " | ".join(final_passages[:top_n])
            
            return " | ".join(passages[:5])
        except Exception as e:
            self.logger.error(f"❌ RAG hiba a keresésnél: {e}")
            return ""

    def save_to_vault(self, text, user_id="common", chat_id="system", metadata=None):
        try:
            prefix = self.rag_cfg['embedding']['instruction_type']['document']
            prefixed_text = f"{prefix}{text}"
            vector = self.embedding_model.encode(prefixed_text).tolist()
            
            point_id = int(datetime.datetime.now().timestamp() * 1000)
            payload = {
                "user_id": user_id, "chat_id": chat_id, "text": text,
                "timestamp": datetime.datetime.now().isoformat()
            }
            if metadata: payload.update(metadata)

            self.client.upsert(
                collection_name="soul_vectors",
                points=[models.PointStruct(id=point_id, vector=vector, payload=payload)]
            )
            
            if user_id != "common":
                self.graph_db.add_node(text[:50], user_id=user_id, full_text=text)
                self._save_graph()
        except Exception as e:
            self.logger.error(f"❌ Hiba a Vault mentéskor: {e}")

    def _save_graph(self):
        data = nx.node_link_data(self.graph_db)
        with open(self.graph_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_graph(self):
        if os.path.exists(self.graph_path):
            try:
                with open(self.graph_path, 'r', encoding='utf-8') as f:
                    return nx.node_link_graph(json.load(f))
            except: return nx.MultiDiGraph()
        return nx.MultiDiGraph()

    def save_internal_note(self, note_content):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.notes_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {note_content}\n")

    def update_scratchpad(self, summary):
        with open(self.scratchpad_path, "w", encoding="utf-8") as f:
            f.write(f"SUMMARY: {summary}")

    def close(self):
        if hasattr(self, 'client') and self.client:
            self.client.close()