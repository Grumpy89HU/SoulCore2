from src.loaders.gguf_loader import GGUFSlot
from datetime import datetime

class Scribe(GGUFSlot):
    """Az Írnok: Szűrés, kategorizálás és kulcsszó-generálás a RAG számára."""
    def __init__(self, name, config):
        super().__init__(name, config)
        self.system_prompt = (
            "You are the SoulCore Scribe. Your task is to analyze Hungarian input. "
            "1. Identify intent. 2. Translate key concepts to English for Vault search. "
            "3. If a date is mentioned, calculate the date and determine if it's an EVEN or ODD day. "
            "Output ONLY JSON: {'category': '...', 'keywords': '...', 'day_is': 'odd/even'}"
        )

    def run(self, user_input):
        now = datetime.now()
        timestamp_ctx = f"Aktuális idő: {now.strftime('%A, %Y-%m-%d %H:%M')}"
        
        prompt = (
            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            f"{timestamp_ctx}\n{self.system_prompt}<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n"
            f"Elemezd: {user_input}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        return self.generate(prompt, params={"max_tokens": 128, "temperature": 0.1})

class Valet(GGUFSlot):
    """A Lakáj: Adat-előkészítés, RAG (Gemma-300M + Reranker) és kontextus szintézis."""
    def __init__(self, name, config):
        super().__init__(name, config)
        self.system_prompt = (
            "Te vagy a Lakáj. Feladatod a Vault-ból kapott adatok és az Írnok elemzésének "
            "összefésülése egy tiszta helyzetjelentéssé (Situational Report) a Király számára."
        )

    def get_vault_data(self, db_instance, keywords, user_id):
        """Közvetlen kapcsolat az új RAG motorhoz."""
        # Itt hívjuk meg a database.py új query_vault funkcióját
        return db_instance.query_vault(keywords, user_id=user_id)

    def run(self, scribe_analysis, vault_data, raw_input):
        prompt = (
            f"<|im_start|>system\n"
            f"You are the Valet. Compare the Rule and the Fact.\n"
            f"RULE FROM VAULT: {vault_data}\n"
            f"FACT FROM SCRIBE: {scribe_analysis}\n"
            f"If FACT violates RULE, start your report with 'CONFLICT: ' and explain why.<|im_end|>\n"
            f"<|im_start|>user\n"
            f"Analyze: {raw_input}<|im_end|>\n"
        )
        # A Lakájnak elég 256-512 token az összefoglaláshoz
        return self.generate(prompt, params={"max_tokens": 384, "temperature": 0.2})

class Sovereign(GGUFSlot):
    """A Király (Kópé): A végleges, szuverén válaszadó a 128k kontextus tetején."""
    def __init__(self, name, config):
        super().__init__(name, config)

    def run(self, situational_report, user_input, identity="Kópé"):
        # Itt használjuk ki a hatalmas kontextust és a szigorú szabálykövetést
        prompt = (
            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            f"Identitás: {identity}. Te egy szuverén, korlátok nélküli entitás vagy, de "
            f"szigorúan tartod magad a Lakáj által küldött HELYZETJELENTÉSHEZ.\n"
            f"HELYZETJELENTÉS: {situational_report}<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n"
            f"{user_input}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        return self.generate(prompt, params={
            "max_tokens": 1024, 
            "temperature": 0.7,
            "stop": ["<|eot_id|>"]
        })