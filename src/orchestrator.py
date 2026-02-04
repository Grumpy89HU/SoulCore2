import logging
import time
import asyncio
import os
import re
import json
import contextlib
<<<<<<< HEAD
import psutil
from datetime import datetime
=======
>>>>>>> d3e372da30590eab253bed78f91e2eca3a01a21e
from concurrent.futures import ThreadPoolExecutor
from src.database import SoulCoreDatabase

class Orchestrator:
    def __init__(self, db_path="vault/db/soulcore.db"):
<<<<<<< HEAD
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger("Kernel")
        self.db = SoulCoreDatabase(db_path=db_path)
        
        project_cfg = self.db.get_config("project") or {}
=======
        self.logger = logging.getLogger("Kernel")
        
        # 1. ADATBÁZIS INICIALIZÁLÁSA (YAML helyett)
        self.db = SoulCoreDatabase(db_path=db_path)
        
        # 2. DINAMIKUS KONFIGURÁCIÓ BETÖLTÉSE
        project_cfg = self.db.get_config("project") or {}
        session_cfg = self.db.get_config("active_session") or {}
        
>>>>>>> d3e372da30590eab253bed78f91e2eca3a01a21e
        self.identity = project_cfg.get('identity', 'Kópé')
        self.user_lang = project_cfg.get('user_lang', 'hu')
        self.internal_lang = project_cfg.get('internal_lang', 'en')
        
<<<<<<< HEAD
        self.slots = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.start_time = time.time()

    def boot_slots(self):
        from src.slots.scribe import Scribe
        from src.slots.specialized_slots import Valet, Sovereign
        from src.loaders.gguf_loader import GGUFSlot
        
        active_slots = self.db.get_enabled_slots()
        # Dinamikus osztály-hozzárendelés a slot neve alapján
        slot_class_map = {
            "scribe": Scribe,
            "valet": Valet,
            "king": Sovereign
        }

        for name, cfg in active_slots.items():
            cls = slot_class_map.get(name, GGUFSlot)
            instance = cls(name, cfg)
            self.slots[name] = instance
            try:
                with open(os.devnull, "w") as fnull:
                    with contextlib.redirect_stderr(fnull):
                        instance.load()
                print(f"✅ Slot aktív: {name} (Class: {cls.__name__})")
            except Exception as e:
                print(f"❌ Hiba a {name} betöltésekor: {e}")

    def get_hardware_stats(self):
        return {
            "cpu_usage": psutil.cpu_percent(),
            "ram_usage": psutil.virtual_memory().percent,
            "uptime": round(time.time() - self.start_time, 2),
            "slots": {name: slot.is_loaded for name, slot in self.slots.items()}
        }
=======
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
>>>>>>> d3e372da30590eab253bed78f91e2eca3a01a21e

    async def _run_in_thread(self, slot_name, prompt, params):
        if slot_name not in self.slots or not self.slots[slot_name].is_loaded:
            return ""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.slots[slot_name].generate, prompt, params)

    async def _translate(self, text, to_lang="en"):
<<<<<<< HEAD
        if "translator" not in self.slots or not text: return text
        prompt = (f"<|start_header_id|>system<|end_header_id|>\n\nTranslate to {to_lang}. "
                  f"Provide ONLY the translated text, no chatter.<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{text}<|eot_id|>"
                  f"<|start_header_id|>assistant<|end_header_id|>\n\n")
        return (await self._run_in_thread("translator", prompt, {"max_tokens": 512, "temperature": 0.1})).strip()

    def _parse_tags(self, text):
        """Kinyeri a tag-eket. Ha nincs lezárva a tag, akkor is kinyeri a tartalmat a végéig."""
        tags = ["note", "message", "translate"]
        extracted_map = {tag: None for tag in tags}
        
        for tag in tags:
            # Mohó regex: keresi a nyitót, és a lezáróig VAGY a szöveg végéig tart
            pattern = rf"<{tag}>(.*?)(?:</{tag}>|$)"
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                extracted_map[tag] = match.group(1).strip()
        
        # Tisztított szöveg logika
        if extracted_map["message"]:
            extracted_map["clean_text"] = extracted_map["message"]
        elif extracted_map["translate"]:
            extracted_map["clean_text"] = extracted_map["translate"]
        else:
            # Ha nincsenek tag-ek, levágjuk a maradék technikai részeket
            temp = re.sub(r'<[^>]+>.*?</[^>]+>', '', text, flags=re.DOTALL)
            extracted_map["clean_text"] = re.sub(r'<[^>]+>', '', temp).strip()
            
        return extracted_map

    async def process_pipeline(self, user_query, chat_id="default_chat", user_id="anonymous"):
        start_process = time.time()
        self.logger.info(f"--- Pipeline Start: {user_query[:50]}... ---")
        self.db.save_message(chat_id, "user", user_query)
        
        # 1. SCRIBE - Elemzés és meta-adatok (ÚJ DÁTUM KEZELÉS)
        scribe_info = {}
        if "scribe" in self.slots:
            scribe_info = await self.slots["scribe"].analyze(user_query)
        self.logger.info(f"Scribe Info: {scribe_info}")

        # 2. VALET - RAG és Helyzetjelentés
        # A Scribe által kinyert kulcsszavakat használjuk a Vault-hoz
        keywords = scribe_info.get("keywords", user_query)
        vault_data = self.db.query_vault(keywords, user_id=user_id)
        
        valet_prompt = (
            f"<|im_start|>system\nYou are the Valet. Compare Rules and Facts.\n"
            f"VAULT RULES: {vault_data}\n"
            f"DAY TYPE: {scribe_info.get('day_is', 'unknown')}\n<|im_end|>\n"
            f"<|im_start|>user\n{user_query}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        situational_report = await self._run_in_thread("valet", valet_prompt, {"max_tokens": 384, "temperature": 0.1})
        self.logger.info(f"Valet Report: {situational_report}")

        # 3. ELŐKÉSZÍTÉS A KIRÁLYNAK
        english_query = await self._translate(user_query, to_lang=self.internal_lang)
        long_term_memory = self.db.get_all_long_memory()

        # 4. KING - Szuverén döntéshozatal
        king_prompt = (
            f"<|start_header_id|>system<|end_header_id|>\n\n"
            f"Identity: {self.identity}.\n"
            f"SITUATIONAL REPORT: {situational_report}\n"
            f"MEMORY: {long_term_memory}\n"
            f"INSTRUCTION: Use <note> for internal thoughts (include TRIGGER_SCRIBE if new info). "
            f"Provide Hungarian response in <message> or English in <translate>.<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n{english_query}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n<note>"
        )
        # Itt a <note> már meg van nyitva a prompt végén a stabilitás miatt
        raw_king_suffix = await self._run_in_thread("king", king_prompt, {"max_tokens": 1024, "temperature": 0.5})
        parsed_king = self._parse_tags("<note>" + raw_king_suffix)
        self.logger.info(f"King Note: {parsed_king['note']}")

        # 5. SCRIBE - Mentés (Csak ha van trigger)
        scribe_data = {"memory": None, "tasks": []}
        if parsed_king["note"] and "trigger_scribe" in parsed_king["note"].lower():
            # Itt használjuk a Scribe-ot a tényleges strukturált mentéshez
            scribe_save_prompt = (
                f"<|start_header_id|>system<|end_header_id|>\n"
                f"Extract ONLY new facts and tasks into JSON.\n"
                f"Format: {{\"memory\": \"fact\", \"tasks\": [\"task\"]}}<|eot_id|>"
                f"<|start_header_id|>user<|end_header_id|>\n{english_query}<|eot_id|>"
                f"<|start_header_id|>assistant<|end_header_id|>\n{{"
            )
            raw_scribe_save = await self._run_in_thread("scribe", scribe_save_prompt, {"max_tokens": 256, "temperature": 0.05})
            try:
                scribe_data = json.loads("{" + raw_scribe_save.split('}')[0] + "}")
                if scribe_data.get("tasks"):
                    for task in scribe_data["tasks"]:
                        self.db.set_long_memory(f"task_{int(time.time()*1000)}", f"TASK: {task}")
                if scribe_data.get("memory"):
                    self.db.set_long_memory(f"fact_{int(time.time()*1000)}", scribe_data["memory"])
            except:
                self.logger.warning("Scribe Save Parse Error")

        # 6. VÉGSŐ VÁLASZ GENERÁLÁSA
        if parsed_king["translate"]:
            final_response = await self._translate(parsed_king["translate"], to_lang=self.user_lang)
        else:
            final_response = parsed_king["clean_text"] or "..."

        self.db.save_message(chat_id, "assistant", final_response, 
                             debug={"note": parsed_king["note"], "report": situational_report})
        
        self.logger.info(f"--- Pipeline End ({round(time.time() - start_process, 2)}s) ---")

        return {
            "identity": self.identity,
            "response": final_response,
            "chat_id": chat_id,
            "metadata": {"time": round(time.time() - start_process, 3)}
=======
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
>>>>>>> d3e372da30590eab253bed78f91e2eca3a01a21e
        }

    def shutdown(self):
        for slot in self.slots.values():
            if hasattr(slot, 'unload'): slot.unload()
        self.db.close()
        self.executor.shutdown(wait=False)