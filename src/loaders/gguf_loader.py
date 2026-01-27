import os
from huggingface_hub import hf_hub_download
from llama_cpp import Llama
from src.base_slot import BaseSlot

class GGUFSlot(BaseSlot):
    def __init__(self, slot_name, config):
        super().__init__(slot_name, config)
        # A configban lévő 'model_path' legyen a mappa, a 'filename' pedig a fájl
        self.model_dir = config.get("model_path")
        self.repo_id = config.get("repo_id")
        self.filename = config.get("filename") 
        # A teljes útvonal a konkrét .gguf fájlhoz:
        self.full_model_path = os.path.join(self.model_dir, self.filename)

    def _ensure_model_exists(self):
        # Most már a konkrét fájlt ellenőrizzük, nem csak a mappát!
        if not os.path.exists(self.full_model_path):
            self.logger.info(f"GGUF fájl hiányzik. Letöltés: {self.repo_id} -> {self.filename}")
            
            os.makedirs(self.model_dir, exist_ok=True)
            
            hf_hub_download(
                repo_id=self.repo_id,
                filename=self.filename,
                local_dir=self.model_dir,
                local_dir_use_symlinks=False
            )
        else:
            self.logger.info(f"GGUF fájl megtalálva: {self.filename}")

    def load(self):
        self._ensure_model_exists()
        self.logger.info(f"GGUF modell betöltése (Llama-cpp): {self.filename}")
        
        try:
            self.model = Llama(
                model_path=self.full_model_path, # A konkrét fájl útvonala!
                n_gpu_layers=-1, 
                n_ctx=self.config.get("ctx_size", 4096),
                verbose=False
            )
            self.is_loaded = True
        except Exception as e:
            self.logger.error(f"Hiba a Llama-cpp betöltésekor: {e}")
            raise e

    def unload(self):
        if hasattr(self, 'model') and self.model:
            # A llama-cpp-nél néha kell egy explicit bezárás
            self.model.close() 
            del self.model
            self.is_loaded = False
            self.logger.info(f"Slot {self.name} felszabadítva.")

    def generate(self, prompt, params=None):
        if not self.is_loaded:
            return "Error: Model not loaded."
        
        max_tokens = params.get('max_tokens', 256) if params else 256
        output = self.model(
            prompt, 
            max_tokens=max_tokens, 
            stop=["<|eot_id|>", "<|im_end|>", "User:"] # Gemma 3 specifikus stoppok
        )
        return output["choices"][0]["text"].strip()