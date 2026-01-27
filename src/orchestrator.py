import yaml
import logging
import os
from pathlib import Path

# Loaderek importálása
#from src.loaders.exl2_loader import EXL2Slot
from src.loaders.gguf_loader import GGUFSlot
from src.loaders.transformers_loader import TransformersSlot

# Speciális logikai slotok importálása
from src.slots.scribe import Scribe
from src.slots.scribe import Valet # Feltételezve, hogy egy fájlban vannak vagy külön importálod
from src.slots.specialized_slots import Sovereign

class Orchestrator:
    # 1. Meghatározzuk, melyik engine-hez melyik Loader osztály tartozik
    ENGINE_MAPPING = {
        "gguf": "src.loaders.gguf_loader.GGUFSlot",
        "transformers": "src.loaders.transformers_loader.TransformersSlot"
    }

    # 2. Meghatározzuk, melyik névhez melyik Logikai osztály tartozik
    ROLE_MAPPING = {
        "scribe": Scribe,
        "valet": Valet,
        "queen": Sovereign,
        "king": Sovereign
    }

    def __init__(self, config_path="conf/soulcore_config.yaml"):
        self.config = self._load_config(config_path)
        self.logger = self._setup_logging()
        self.slots = {}
        
        self.logger.info(f"--- {self.config['project']['name']} v{self.config['project']['version']} Boot Sequence ---")
        self._validate_folders()

    def _load_config(self, path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Konfiguráció nem található: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _setup_logging(self):
        log_dir = Path(self.config['storage']['vault_root']) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            handlers=[
                logging.FileHandler(log_dir / "system.log", encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger("Kernel")

    def _validate_folders(self):
        paths = [
            self.config['storage']['model_root'],
            self.config['storage']['vault_root'],
            os.path.join(self.config['storage']['vault_root'], "db")
        ]
        for p in paths:
            Path(p).mkdir(parents=True, exist_ok=True)

    def _initialize_slot(self, name, params):
        """Dinamikus slot betöltő motor, ami kezeli az engine-t és a szerepkört is."""
        if not params.get('enabled'):
            return None

        engine_type = params.get('engine', 'transformers') # Alapértelmezett a legbiztosabb
        
        # Kiválasztjuk a megfelelő Loader-t (Pl. GGUFSlot)
        loader_class = self.ENGINE_MAPPING.get(engine_type, TransformersSlot)
        
        # Kiválasztjuk a logikai kiegészítést (Pl. Scribe)
        # Itt egy Python trükköt használunk: dinamikusan létrehozunk egy osztályt, 
        # ami a Logikai szerepből ÉS a Loaderből is örököl.
        role_class = self.ROLE_MAPPING.get(name)

        self.logger.info(f"Slot inicializálása: {name} | Engine: {engine_type} | Role: {role_class.__name__ if role_class else 'Base'}")

        try:
            # Létrehozzuk a példányt. Mivel a Scribe az EXL2Slot-ból (vagy most már GGUF-ból) származik,
            # a role_class-t példányosítjuk, de figyelni kell az öröklődésre!
            # Ha a Scribe fixen EXL2Slot-ból származik a fájlban, akkor itt hívjuk meg:
            instance = role_class(name, params)
            instance.load()
            return instance
        except Exception as e:
            self.logger.error(f"Hiba a(z) {name} betöltésekor ({engine_type}): {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    def boot_slots(self):
        for name, params in self.config['slots'].items():
            slot_instance = self._initialize_slot(name, params)
            if slot_instance:
                self.slots[name] = slot_instance
        
        active = [n for n in self.slots]
        self.logger.info(f"Rendszer üzemkész. Aktív slotok: {active}")

    def process_pipeline(self, user_input):
        """A teljes kognitív folyamat: Inger -> Elemzés -> Kontextus -> Válasz."""
        self.logger.info(f"Új bemenet: '{user_input}'")
        
        try:
            # 1. SZINT: Írnok (Intent Analysis)
            scribe_res = "N/A"
            if 'scribe' in self.slots:
                scribe_res = self.slots['scribe'].run(user_input)
                self.logger.info(f"[Scribe] Elemzés kész.")

            # 2. SZINT: Lakáj (Memory & RAG)
            context = "Nincs extra kontextus."
            if 'valet' in self.slots:
                context = self.slots['valet'].run(scribe_res, user_input)
                self.logger.info(f"[Valet] Kontextus felépítve.")

            # 3. SZINT: A Szuverén (King/Queen) - Ha be van kapcsolva
            final_response = ""
            if 'king' in self.slots:
                final_response = self.slots['king'].run(context, user_input)
            elif 'queen' in self.slots:
                final_response = self.slots['queen'].run(context, user_input)
            else:
                # Ha csak a kicsik futnak (teszt üzemmód 1 GPU-val)
                final_response = f"DEBUG: Scribe: {scribe_res} | Valet: {context[:100]}..."

            return {
                "scribe": scribe_res,
                "valet": context,
                "response": final_response
            }

        except Exception as e:
            self.logger.error(f"Pipeline hiba: {e}")
            return {"error": str(e)}

    def shutdown(self):
        """VRAM tiszta felszabadítása."""
        self.logger.info("Rendszer leállítása, VRAM ürítése...")
        for name, slot in self.slots.items():
            slot.unload()