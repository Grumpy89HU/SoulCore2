import logging

class BaseSlot:
    def __init__(self, slot_name, config):
        self.name = slot_name
        self.config = config
        self.is_loaded = False
        self.model = None
        self.logger = logging.getLogger(f"Slot-{slot_name}")

    def load(self):
        """Modell betöltése a memóriába (implementálandó)"""
        raise NotImplementedError

    def unload(self):
        """Memória felszabadítása"""
        raise NotImplementedError

    def generate(self, prompt, params=None):
        """Válasz generálása (implementálandó)"""
        raise NotImplementedError

    def status(self):
        return {
            "name": self.name,
            "role": self.config.get("role"),
            "engine": self.config.get("engine"),
            "is_loaded": self.is_loaded
        }
