from src.loaders.gguf_loader import GGUFSlot

class Scribe(GGUFSlot):
    def generate(self, prompt, params=None):
        # Explicit meghívjuk a betöltő generálófüggvényét
        return super().generate(prompt, params)

    def unload(self):
        # Explicit meghívjuk a betöltő unload függvényét
        return super().unload()

    def run(self, user_input):
        prompt = (
            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            f"Te vagy a SoulCore Írnoka. Elemezd a bemenetet. Kategóriák: [CHAT], [CMD], [RESEARCH]. "
            f"Csak a kategóriát és a lényeget írd le.<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n"
            f"{user_input}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        return self.generate(prompt, params={"max_tokens": 50})

class Valet(GGUFSlot):
    def generate(self, prompt, params=None):
        return super().generate(prompt, params)

    def unload(self):
        return super().unload()

    def run(self, scribe_analysis, raw_input):
        prompt = (
            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            f"Te vagy a Lakáj. Feladatod az információgyűjtés és a kontextus előkészítése. "
            f"Az Írnok elemzése: {scribe_analysis}<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n"
            f"Készíts elő adatokat ehhez: {raw_input}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        return self.generate(prompt, params={"max_tokens": 256})