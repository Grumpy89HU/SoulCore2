import logging
import json
import re
from datetime import datetime
from src.loaders.gguf_loader import GGUFSlot

class Scribe(GGUFSlot):
    """Az Írnok: Elemzés, meta-adat kinyerés, RAG kulcsszavak és szintézis."""
    
    def __init__(self, name, config):
        super().__init__(name, config)
        # Egységesített név: system_prompt
        self.system_prompt = (
            "You are the SoulCore Scribe. Analyze input and extract metadata.\n"
            "Categories: 'task', 'fact', 'chat'.\n"
            "Format: {\"category\": \"...\", \"keywords\": \"...\", \"day_is\": \"odd/even\", \"summary_en\": \"...\"}"
        )

    async def analyze(self, user_input_hu):
        """Általános elemzés az adatbázis számára (JSON kimenet)."""
        now = datetime.now()
        timestamp_ctx = f"Aktuális idő: {now.strftime('%A, %Y-%m-%d %H:%M')}"
        
        prompt = (
            f"<|start_header_id|>system<|end_header_id|>\n\n{timestamp_ctx}\n{self.system_prompt}<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\nElemezd: {user_input_hu}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n{{"
        )
        
        # A generate szinkron hívás a GGUFSlot-ban, nem kell await
        raw_output = self.generate(prompt, params={"max_tokens": 128, "temperature": 0.1})
        return self._clean_json("{" + raw_output)

    def run_keywords(self, user_input_english):
        """Kulcsszavak kinyerése a Vault kereséshez."""
        now = datetime.now()
        timestamp_ctx = f"Current Time: {now.strftime('%A, %Y-%m-%d %H:%M')}"
        
        prompt = (
            f"<|start_header_id|>system<|end_header_id|>\n\n"
            f"{timestamp_ctx}\n"
            f"Extract search keywords for the database. If the query is about 'tomorrow', "
            f"calculate the day name and add it to keywords. Respond ONLY with keywords.<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n{user_input_english}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        return self.generate(prompt, params={"max_tokens": 32, "temperature": 0.1})

    def run_synthesis(self, user_input_english, vault_data):
        """Összefésüli a Vault adatait a kéréssel logikai ütközésekért."""
        system_now = datetime.now().strftime('%Y-%m-%d, %A')
        prompt = (
            f"<|im_start|>system\n"
            f"CURRENT_TIME: {system_now}\n"
            f"RULES FROM VAULT: {vault_data}\n\n"
            f"TASK: Verify if the USER_QUERY is executable under the RULES.\n"
            f"Identify any logical collision (e.g. Parity, Day of week).\n"
            f"Result: [VALID] or [CONFLICT: (reason)].<|im_end|>\n"
            f"<|im_start|>user\n{user_input_english}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        return self.generate(prompt, params={"max_tokens": 128, "temperature": 0.1})

    def _clean_json(self, text):
        """Kinyeri és validálja a JSON választ."""
        try:
            # Megkeressük a legelső { és legutolsó } karaktereket
            start_idx = text.find('{')
            end_idx = text.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                return json.loads(text[start_idx:end_idx])
        except Exception as e:
            logging.error(f"Scribe JSON Parse Error: {e}")
        return {"category": "chat", "keywords": "", "day_is": "unknown", "summary_en": "Failed to parse"}