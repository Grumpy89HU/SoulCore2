import logging
from datetime import datetime
from src.loaders.gguf_loader import GGUFSlot

class Scribe(GGUFSlot):
    """Az Írnok: Logikai szűrő és kulcsszó-generátor."""
    def run_keywords(self, user_input_english):
        now = datetime.now()
        timestamp_ctx = f"Current Time: {now.strftime('%A, %Y-%m-%d %H:%M')}"
        
        prompt = (
            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            f"{timestamp_ctx}\n"
            f"Extract search keywords for the database. If the query is about 'tomorrow', "
            f"calculate the day name and add it to keywords. Respond ONLY with keywords.<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n{user_input_english}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        return self.generate(prompt, params={"max_tokens": 32, "temperature": 0.1})

    def run_synthesis(self, user_input_english, vault_data):
        """Összefésüli a Vault adatait a kérdéssel."""
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

class Valet(GGUFSlot):
    """A Lakáj: A RAG folyamat kezelője."""
    def get_vault_context(self, db_instance, keywords, user_id):
        # Ez a kulcs: a Lakáj meghívja az adatbázist
        context = db_instance.query_vault(keywords, user_id=user_id)
        if not context:
            return "No specific rules found in vault."
        return context

class King(GGUFSlot):
    """A Király: A végső döntéshozó."""
    def run(self, user_input, situation_report, identity="Kópé"):
        prompt = (
            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            f"Identity: {identity}. \n"
            f"SITUATIONAL REPORT: {situation_report}\n"
            f"Rule: Follow the Situational Report strictly. Respond in Hungarian.<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n{user_input}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        return self.generate(prompt, params={
            "max_tokens": 512, 
            "temperature": 0.7,
            "stop": ["<|eot_id|>"]
        })