import asyncio
import logging
import os
import sys
import time
from datetime import datetime

class Heartbeat:
    def __init__(self, orchestrator):
        self.core = orchestrator
        self.logger = logging.getLogger("Heartbeat")
        self.is_active = False
        self.polling_interval = 10  # 10 másodperces polling
        self.reflection_counter = 0
        self.reflection_limit = 30  # ~5 perc
        self.error_threshold = 3    # Ennyi egymást követő hiba után jön a restart
        self.consecutive_errors = 0

    async def start(self):
        if not self.is_active:
            self.is_active = True
            self.logger.info("[*] Heartbeat Kognitív Motor elindítva.")
            asyncio.create_task(self._loop())

    async def stop(self):
        self.is_active = False

    async def _loop(self):
        while self.is_active:
            try:
                # 1. RENDSZER-SENTRY (Öngyógyítás)
                await self._check_system_health()

                # 2. ÖNREFLEXIÓ (Proaktív kommunikáció)
                self.reflection_counter += 1
                if self.reflection_counter >= self.reflection_limit:
                    asyncio.create_task(self._run_reflection())
                    self.reflection_counter = 0
                
                # Ha idáig eljutott, nullázzuk a hiba számlálót
                self.consecutive_errors = 0

            except Exception as e:
                self.consecutive_errors += 1
                self.logger.error(f"Heartbeat hiba ({self.consecutive_errors}/{self.error_threshold}): {e}")
                if self.consecutive_errors >= self.error_threshold:
                    await self._trigger_self_restart("Kritikus hurok hiba")

            await asyncio.sleep(self.polling_interval)

    async def _check_system_health(self):
        """Ellenőrzi, hogy a slotok élnek-e."""
        for name, slot in self.core.slots.items():
            if not slot.is_loaded:
                self.logger.warning(f"Slot elakadás észlelve: {name}. Újratöltési kísérlet...")
                try:
                    slot.load()
                except:
                    await self._trigger_self_restart(f"Slot {name} összeomlott")

    async def _run_reflection(self):
        """Kópé eldönti, akar-e üzenni."""
        if "valet" in self.core.slots:
            prompt = "SYSTEM_STATUS: Operational. Current Time: {}. Do you have any proactive thoughts for Grumpy? [Y/N]".format(time.strftime("%H:%M"))
            decision = self.core.slots["valet"].generate(decision_prompt=prompt, params={"max_tokens": 10})
            
            if "Y" in decision.upper():
                await self.core.check_proactive_intent()

    async def _trigger_self_restart(self, reason):
        """Az autonóm újraindítás logikája."""
        self.logger.critical(f"!!! AUTONÓM ÚJRAINDÍTÁS: {reason} !!!")
        
        # Üzenet küldése a streamre, hogy a kliens tudja, mi történik
        await self.core.outbound_queue.put({
            "type": "system_event",
            "content": f"A rendszer újraindítja magát: {reason}",
            "timestamp": time.time()
        })
        
        # Várunk egy kicsit, hogy az üzenet kimenjen
        await asyncio.sleep(2)
        
        # A main.py-ban használt restart logika
        os.execv(sys.executable, [sys.executable] + sys.argv)
