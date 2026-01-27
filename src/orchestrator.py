import logging
import yaml
import time
import asyncio
import os
import contextlib
from concurrent.futures import ThreadPoolExecutor

class Orchestrator:
    def __init__(self, config_path="conf/soulcore_config.yaml"):
        self.logger = logging.getLogger("Kernel")
        self.config_path = config_path
        self.config = self._load_config()
        self.slots = {}
        self.outbound_queue = asyncio.Queue()
        self.executor = ThreadPoolExecutor(max_workers=3)

    def _load_config(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def boot_slots(self):
        """Modellek betöltése központi némítással."""
        from src.loaders.gguf_loader import GGUFSlot
        slot_configs = self.config.get("slots", {})
        
        for name, cfg in slot_configs.items():
            if cfg.get("enabled") and cfg.get("engine") == "gguf":
                instance = GGUFSlot(name, cfg)
                
                # Itt némítjuk el a betöltést központilag
                with open(os.devnull, "w") as fnull:
                    with contextlib.redirect_stderr(fnull):
                        try:
                            instance.load()
                        except Exception as e:
                            self.logger.error(f"Hiba a(z) {name} slot betöltésekor: {e}")
                
                self.slots[name] = instance

    async def _run_in_thread(self, slot_name, prompt, params):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, 
            self.slots[slot_name].generate, 
            prompt, 
            params
        )

    async def process_pipeline(self, user_query):
        start_time = time.time()
        intent = "general_chat"
        cleaned_query = user_query
        
        if "scribe" in self.slots:
            scribe_prompt = f"Analyze intent and clean: {user_query}\nFormat: intent|text"
            out = await self._run_in_thread("scribe", scribe_prompt, {"max_tokens": 64})
            if "|" in out:
                parts = out.split("|")
                intent = parts[0].strip()
                cleaned_query = parts[1].strip()

        thought = "..."
        response = "Hiba történt."
        
        if "valet" in self.slots:
            thought_prompt = f"Internal thoughts about: {cleaned_query}"
            thought = await self._run_in_thread("valet", thought_prompt, {"max_tokens": 256})
            
            response_prompt = f"Thoughts: {thought}\nUser: {cleaned_query}\nKópé:"
            response = await self._run_in_thread("valet", response_prompt, {"max_tokens": 512})

        return {
            "identity": self.config['project']['identity'],
            "intent": intent,
            "thought": thought,
            "response": response,
            "metadata": {"time": round(time.time() - start_time, 3)}
        }

    async def check_proactive_intent(self):
        if "valet" in self.slots:
            decision = await self._run_in_thread("valet", "Proactive check: Need to speak? [Y/N]", {"max_tokens": 5})
            if "Y" in decision.upper():
                message = await self._run_in_thread("valet", "Say something to Grumpy:", {"max_tokens": 128})
                await self.outbound_queue.put({
                    "type": "proactive",
                    "response": message,
                    "timestamp": time.time()
                })

    def shutdown(self):
        for slot in self.slots.values():
            slot.unload()
        self.executor.shutdown()