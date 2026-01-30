import logging
import yaml
import time
import asyncio
import os
import contextlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from src.database import SoulCoreDatabase

class Orchestrator:
    def __init__(self, config_path="conf/soulcore_config.yaml"):
        self.logger = logging.getLogger("Kernel")
        self.config_path = config_path
        self.config = self._load_config()
        self.slots = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        session = self.config.get('active_session', {})
        self.current_user = session.get('user_id', 'unknown_user')
        self.chat_id = session.get('chat_id', 'default_chat')
        
        self.user_lang = self.config['project'].get('user_lang', 'hu')
        self.internal_lang = self.config['project'].get('internal_lang', 'en')

        db_cfg = self.config.get('databases', {}).get('vector_vault', {})
        self.db = SoulCoreDatabase(vector_db_path=db_cfg.get('path', 'vault/db/soul_vectors'))

    def _load_config(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    # ... boot_slots és _run_in_thread maradt a régi ...
    def boot_slots(self):
        from src.loaders.gguf_loader import GGUFSlot
        slot_configs = self.config.get("slots", {})
        for name, cfg in slot_configs.items():
            if cfg.get("enabled"):
                print(f"🔄 Slot ébresztése: {name}...")
                instance = GGUFSlot(name, cfg)
                self.slots[name] = instance
                try:
                    with open(os.devnull, "w") as fnull:
                        with contextlib.redirect_stderr(fnull):
                            instance.load()
                    print(f"✅ {name.capitalize()} aktív.")
                except Exception as e:
                    print(f"❌ Hiba: {e}")

    async def _run_in_thread(self, slot_name, prompt, params):
        if slot_name not in self.slots or not self.slots[slot_name].is_loaded:
            return ""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.slots[slot_name].generate, prompt, params)

    async def _translate(self, text, from_lang, to_lang):
        if "translator" not in self.slots or not text:
            return text
        prompt = (
            f"<|start_header_id|>system<|end_header_id|>\n\n"
            f"Translate to {to_lang}. Preserve context. Respond ONLY with translation.<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n{text}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        translated = await self._run_in_thread("translator", prompt, {"max_tokens": 512, "temperature": 0.1})
        return translated.strip()

    async def process_pipeline(self, user_query):
        start_time = time.time()
        identity = self.config['project'].get('identity', 'Kópé')
        now = datetime.now()
        timestamp_ctx = f"Current Time: {now.strftime('%A, %Y-%m-%d %H:%M')}"

        # 1. Translator: Bemeneti nyelv -> Belső angol logika
        english_query = await self._translate(user_query, "auto", "English")
        
        # 2. Scribe: Logikai feldolgozás és RAG lekérdezés
        search_query = english_query
        if "scribe" in self.slots:
            # Először csak kulcsszavakat kérünk a Vault-hoz
            scribe_keywords_prompt = (
                f"<|start_header_id|>system<|end_header_id|>\n\n"
                f"{timestamp_ctx}\n"
                f"Extract search keywords for the database. If the query is about 'tomorrow', "
                f"calculate the day name and add it to keywords. Respond ONLY with keywords.<|eot_id|>"
                f"<|start_header_id|>user<|end_header_id|>\n\n{english_query}<|eot_id|>"
                f"<|start_header_id|>assistant<|end_header_id|>\n\n"
            )
            search_query = await self._run_in_thread("scribe", scribe_keywords_prompt, {"max_tokens": 32})

        # 3. Vault: Nyers adatok lehívása
        raw_vault_data = self.db.query_private_data(self.current_user, search_query)

        # 4. Scribe: Szintézis (Helyzetjelentés készítése a Királynak)
        # Itt oldjuk fel az időbeli és logikai ellentmondásokat
        situation_report = ""
        system_now = datetime.now().strftime('%Y-%m-%d, %A')
        if "scribe" in self.slots:
            # Ez a Scribe promptja - SOHA nem változik a kódodban (Nincs hard-kód!)
            synthesis_prompt = (
                f"<|im_start|>system\n"
                f"CURRENT_TIME: {system_now}\n"
                f"RULES: {raw_vault_data}\n\n"
                f"TASK: Verify if the USER_QUERY is executable under the RULES.\n"
                f"PROCEDURE:\n"
                f"1. Extract the temporal target (When does the user want to act?).\n"
                f"2. Cross-reference this target date/time with ALL numerical and temporal constraints in RULES.\n"
                f"3. Identify any logical collision (e.g. Parity, Day of week, prohibited hours).\n"
                f"4. Result: [VALID] or [CONFLICT: (reason)].<|im_end|>\n"
                f"<|im_start|>user\n{english_query}<|im_end|>\n"
                f"<|im_start|>assistant\n"
            )
            situation_report = await self._run_in_thread("scribe", synthesis_prompt, {"max_tokens": 128})

        # 5. A KIRÁLY: Szuverén válaszadás a tiszta jelentés alapján
        # Ő már nem számol, nem kutat, csak interpretál és beszél
        response = ""
        if "king" in self.slots:
            response_prompt = (
                f"<|start_header_id|>system<|end_header_id|>\n\n"
                f"Identity: {identity}. \n"
                f"SITUATIONAL REPORT: {situation_report}\n"
                f"User asked: {user_query}\n"
                f"Rule: Always follow the Situational Report strictly. Be creative but accurate. "
                f"Respond in Hungarian.<|eot_id|>"
                f"<|start_header_id|>assistant<|end_header_id|>\n\n"
            )
            response = await self._run_in_thread("king", response_prompt, {
                "max_tokens": 512,
                "temperature": 0.7, # Visszaadjuk a Király szabadságát!
                "stop": ["<|eot_id|>", "<|start_header_id|>"]
            })

        return {
            "identity": identity,
            "report": situation_report.strip(), # Hogy lássuk, mit kapott a Király
            "response": response.strip(),
            "metadata": {"time": round(time.time() - start_time, 3)}
        }

    def shutdown(self):
        for slot in self.slots.values():
            if hasattr(slot, 'unload'): slot.unload()
        if hasattr(self, 'db'): self.db.close()
        self.executor.shutdown(wait=False)