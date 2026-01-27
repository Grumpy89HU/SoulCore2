from abc import ABC, abstractmethod
import logging

class BaseSlot(ABC):
    def __init__(self, name, config):
        self.name = name
        self.config = config
        self.model = None
        self.tokenizer = None
        self.logger = logging.getLogger(f"Slot-{name}")
        self.is_loaded = False

    @abstractmethod
    def load(self):
        """A modell betöltése a VRAM-ba (EXL2 vagy más engine)."""
        pass

    @abstractmethod
    def unload(self):
        """VRAM felszabadítása."""
        pass

    @abstractmethod
    def generate(self, prompt, params=None):
        """Válasz generálása a kapott prompt alapján."""
        pass

    def get_status(self):
        return {
            "name": self.name,
            "loaded": self.is_loaded,
            "vram_limit": self.config.get("max_vram_mb", "N/A"),
            "device": self.config.get("gpu_id", 0)
        }
