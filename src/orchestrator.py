import logging
import time
import asyncio
import os
import re
import json
import contextlib
from concurrent.futures import ThreadPoolExecutor
from src.database import SoulCoreDatabase

class Orchestrator:
    def __init__(self, db_path="vault/db/soulcore.db"):
        self.logger = logging.getLogger("Kernel")
        
        # 1. ADATBÁZIS INICIALIZÁLÁSA (YAML helyett)
        self.db = SoulCoreDatabase(db_path=db_path)
        
        # 2. DINAMIKUS KONFIGURÁCIÓ BETÖLTÉSE
        project_cfg = self.db.get_config("project") or {}
        session_cfg = self.db.get_config("active_session") or {}
        
        self.identity = project_cfg.get('identity', 'Kópé')
        self.user_lang = project_cfg.get('user_lang', 'hu')
        self.internal_lang = project_cfg.get('internal_lang', 'en')
        
        self.current_user = session_cfg.get('user_id', 'Grumpy')
        self.chat_id = session_cfg.get('chat_id', 'dev_room_001')
        
        self.slots = {}
        self.executor = ThreadPoolExecutor(max_workers=4)

    def boot_slots(self):
        """Minden engedélyezett slotot betölt az adatbázisból."""
        from src.loaders.gguf_loader import GGUFSlot
        
        # Csak azokat a slotokat kérjük le, amik 'enabled = 1'
        active_slots = self.db.get_enabled_slots()
        
        for name, cfg in active_slots.items():
            print(f"🔄 Slot ébresztése: {name}...")
            time.sleep(1)
            instance = GGUFSlot(name, cfg)
            self.slots[name] = instance
            try:
                with open(os.devnull, "w") as fnull:
                    with contextlib.redirect_stderr(fnull), contextlib.redirect_stdout(fnull):
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
        if "translator" not in self.slots or not text:
            return text
        
        prompt = (
            f"<|start_header_id|>system<|end_header_id|>\n\n"
            f"You are the SoulCore Translation Gate. Translate the user's text to {to_lang}. "
            f"Respond ONLY with the translated text, no explanation.<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n{text}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        translated = await self._run_in_thread("translator", prompt, {"max_tokens": 1024, "temperature": 0.1})
        return translated.strip()

    def _parse_tags(self, text):
        """Kinyeri a speciális tageket és a tiszta választ."""
        extracted = {"note": None, "notepad": None, "memory": None, "translate": True}
        
        # 1. Tagek kinyerése
        for tag in ["note", "notepad", "memory", "translate"]:
            pattern = f"<{tag}>(.*?)</{tag}>"
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                content = match.group(1).strip()
                if tag == "translate" and "false" in content.lower():
                    extracted["translate"] = False
                else:
                    extracted[tag] = content

        # 2. A válasz megtisztítása: CSAK a tageket vesszük ki, a köztük lévő szöveget NEM, 
        # kivéve a note-ot és a többit, amit belsőnek szánunk.
        clean = text
        for tag in ["note", "notepad", "memory", "translate"]:
            clean = re.sub(f"<{tag}>.*?</{tag}>", "", clean, flags=re.DOTALL | re.IGNORECASE)
        
        # Ha a modell elfelejtette bezárni a taget, akkor is takarítsunk:
        clean = re.sub(r'<[^>]+>', '', clean).strip()
        
        extracted["clean_text"] = clean
        return extracted

    async def process_pipeline(self, user_query):
        start_time = time.time()
        
        # 1. FORDÍTÁS (BE) + RAG LEKÉRDEZÉS
        english_query = await self._translate(user_query, to_lang=self.internal_lang)
        raw_vault_data = self.db.query_vault(user_query, user_id=self.current_user)

        # 2. SCRIBE (Helyzetjelentés)
        situation_report = "[VALID]"
        if "scribe" in self.slots:
            synthesis_prompt = (
                f"<|start_header_id|>system<|end_header_id|>\n\n"
                f"VAULT: {raw_vault_data}\n"
                f"Analyze user query. Output ONLY [VALID] or [CONFLICT].<|eot_id|>"
                f"<|start_header_id|>user<|end_header_id|>\n\n{english_query}<|eot_id|>"
                f"<|start_header_id|>assistant<|end_header_id|>\n\n"
            )
            situation_report = await self._run_in_thread("scribe", synthesis_prompt, {"max_tokens": 10, "temperature": 0.1})

        # 3. KING (A központi tudat)
        final_response = "..."
        if "king" in self.slots:
            # Itt levettem a kényszerített <note>-ot a végéről, hogy a modell maga döntse el, használja-e
            response_prompt = (
                f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
                f"Identity: {self.identity}. User Language: {self.user_lang}.\n"
                f"You are a sovereign AI. You can use <note> for thinking, <notepad> for facts, <memory> for vault storage.\n"
                f"CONTEXT: {{'vault': {raw_vault_data}, 'report': '{situation_report.strip()}'}}<|eot_id|>"
                f"<|start_header_id|>user<|end_header_id|>\n\n{english_query}<|eot_id|>"
                f"<|start_header_id|>assistant<|end_header_id|>\n\n"
            )
            raw_king_output = await self._run_in_thread("king", response_prompt, {"max_tokens": 2048, "temperature": 0.7})
            
            # Tagek feldolgozása
            parsed = self._parse_tags(raw_king_output)
            
            # Mentések...
            if parsed["note"]: self.db.save_message(self.chat_id, "internal_note", parsed["note"])
            if parsed["notepad"]: self.db.set_config("scratchpad", parsed["notepad"])
            if parsed["memory"]: self.db.save_to_vault(parsed["memory"], user_id=self.current_user)

            # 4. FORDÍTÁS (KI) - Biztonsági fék: ha üres a clean_text, használjuk a nyerset
            response_to_send = parsed["clean_text"] if parsed["clean_text"] else raw_king_output
            
            if parsed["translate"] and self.user_lang != "en" and response_to_send:
                final_response = await self._translate(response_to_send, to_lang=self.user_lang)
            else:
                final_response = response_to_send
            
            debug_data = {"note": parsed["note"], "notepad": parsed["notepad"], "memory": parsed["memory"]}

        # 5. SQL MENTÉS
        self.db.save_message(self.chat_id, "user", user_query)
        self.db.save_message(self.chat_id, "assistant", final_response, debug=json.dumps(debug_data))

        return {
            "identity": self.identity,
            "report": situation_report.strip(),
            "response": final_response,
            "debug": debug_data,
            "metadata": {"time": round(time.time() - start_time, 3)}
        }

    def shutdown(self):
        for slot in self.slots.values():
            if hasattr(slot, 'unload'): slot.unload()
        self.db.close()
        self.executor.shutdown(wait=False)