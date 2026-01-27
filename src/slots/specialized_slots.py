from src.loaders.gguf_loader import GGUFSlot

class Scribe(GGUFSlot):
    """Az Írnok: Szűrés, kategorizálás és szándék-elemzés."""
    def __init__(self, name, config):
        super().__init__(name, config)
        self.system_prompt = (
            "Te vagy a SoulCore Írnoka. Feladatod a felhasználói közlés elemzése magyarul. "
            "Kategorizáld a bemenetet: [CHAT], [CMD], [RESEARCH]. "
            "Készíts egy rövid összefoglalót a lényegről. Csak JSON-szerű választ adj."
        )

    def run(self, user_input):
        prompt = (
            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            f"{self.system_prompt}<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n"
            f"Elemezd: {user_input}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        return self.generate(prompt, params={"max_tokens": 64})

class Valet(GGUFSlot):
    """A Lakáj: Adat-előkészítés, RAG és memória-menedzsment."""
    def __init__(self, name, config):
        super().__init__(name, config)
        self.system_prompt = (
            "Te vagy a Lakáj. Feladatod az információgyűjtés. "
            "Használd az Írnok elemzését a releváns kontextus felépítéséhez."
        )

    def run(self, scribe_analysis, raw_input):
        prompt = (
            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            f"{self.system_prompt}\nÍrnok elemzése: {scribe_analysis}<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n"
            f"Készíts elő adatokat ehhez a kéréshez: {raw_input}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        return self.generate(prompt, params={"max_tokens": 512})

class Sovereign(GGUFSlot):
    """A Király/Királynő alapja: Identitás és végleges döntéshozatal."""
    def run(self, context, user_input):
        prompt = (
            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            f"Te vagy Kópé, a szuverén AI. Identitásod: független, intelligens, segítőkész társ.\n"
            f"Kontextus: {context}<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n"
            f"{user_input}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        return self.generate(prompt, params={"max_tokens": 1024})
