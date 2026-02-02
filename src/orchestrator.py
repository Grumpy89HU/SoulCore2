import logging
import yaml
import time
import asyncio
import os
import contextlib
from datetime import datetime, timedelta
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

        # Adatbázis inicializálása
        self.db = SoulCoreDatabase(config_path=self.config_path)

    def _load_config(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

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
                            with contextlib.redirect_stdout(fnull):
                                instance.load()
                    print(f"✅ {name.capitalize()} aktív.")
                except Exception as e:
                    print(f"❌ Hiba a {name} betöltésekor: {e}")

    async def _run_in_thread(self, slot_name, prompt, params):
        if slot_name not in self.slots or not self.slots[slot_name].is_loaded:
            return ""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.slots[slot_name].generate, prompt, params)

    async def _translate(self, text, to_lang="en"):
        """Univerzális fordító zsilip a TranslateGamma számára."""
        if "translator" not in self.slots or not text:
            return text
        
        # Szigorúbb prompt a fordítónak, hogy ne magyarázzon, csak fordítson
        prompt = (
            f"<|start_header_id|>system<|end_header_id|>\n\n"
            f"You are the SoulCore Translation Gate. Translate the input to {to_lang}. "
            f"Preserve the tone and intent. Respond ONLY with the translated text.<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n{text}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        translated = await self._run_in_thread("translator", prompt, {"max_tokens": 512, "temperature": 0.1})
        return translated.strip()

    async def process_pipeline(self, user_query):
        start_time = time.time()
        identity = self.config['project'].get('identity', 'Kópé')
        
        # --- IDŐADATOK ---
        now = datetime.now()
        live_env = {
            "timestamp": now.strftime('%Y-%m-%d, %A'),
            "day_number": now.day
        }

        # 1. BELÉPŐ FORDÍTÁS (Magyar -> Angol)
        # Ezzel tisztítjuk le a Scribe és a King számára a bemenetet
        english_query = await self._translate(user_query, to_lang="English")
        
        # 2. Vault keresés (Az angol lekérdezés pontosabb találatokat adhat)
        raw_vault_data = self.db.query_vault(user_query, user_id=self.current_user)

        # 3. Scribe: Logikai Szintézis (Angolul elemzi az angol szöveget)
        situation_report = ""
        if "scribe" in self.slots:
            synthesis_prompt = (
                f"<|start_header_id|>system<|end_header_id|>\n\n"
                f"ENV_DATA: {live_env}\n"
                f"VAULT_DATA: {raw_vault_data}\n\n"
                f"TASK: Analyze the query. Output ONLY [VALID] or [CONFLICT: reason].<|eot_id|>"
                f"<|start_header_id|>user<|end_header_id|>\n\n{english_query}<|eot_id|>"
                f"<|start_header_id|>assistant<|end_header_id|>\n\n"
            )
            situation_report = await self._run_in_thread("scribe", synthesis_prompt, {"max_tokens": 128, "temperature": 0.1})

        # 4. King (Kópé): Angol válaszgenerálás (Max tudás kihasználása)
        english_response = ""
        if "king" in self.slots:
            response_prompt = (
                f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
                f"Identity: {identity}. You are a sovereign entity. "
                f"Analyze the situation and respond to the user in English. "
                f"CONTEXT: {{'env': {live_env}, 'vault': {raw_vault_data}, 'scribe_report': '{situation_report.strip()}'}}<|eot_id|>"
                f"<|start_header_id|>user<|end_header_id|>\n\n{english_query}<|eot_id|>"
                f"<|start_header_id|>assistant<|end_header_id|>\n\n"
            )
            english_response = await self._run_in_thread("king", response_prompt, {
                "max_tokens": 512, 
                "temperature": 0.5,
                "stop": ["<|eot_id|>"]
            })

        # 5. KILÉPŐ FORDÍTÁS (Angol válasz -> Természetes Magyar)
        if english_response:
            final_response = await self._translate(
                f"Translate this AI response to natural, sovereign Hungarian for Grumpy: {english_response}", 
                to_lang="Hungarian"
            )
        else:
            final_response = "Hiba történt a generálás során."

        # Belső naplózás
        self.db.save_internal_note(f"Q: {user_query} | EN_Q: {english_query} | Report: {situation_report.strip()}")
        if final_response:
            self.db.save_to_vault(f"User: {user_query} | AI: {final_response}", user_id=self.current_user)

        return {
            "identity": identity,
            "report": situation_report.strip(),
            "response": final_response.strip(),
            "metadata": {"time": round(time.time() - start_time, 3)}
        }

    def shutdown(self):
        for slot in self.slots.values():
            if hasattr(slot, 'unload'): slot.unload()
        if hasattr(self, 'db'): self.db.close()
        self.executor.shutdown(wait=False)