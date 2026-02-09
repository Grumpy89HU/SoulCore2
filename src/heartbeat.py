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
        self.polling_interval = 15  # 15 másodperces polling a kisebb terhelésért
        self.reflection_counter = 0
        self.reflection_limit = 20  # ~5 perc (20 * 15s)
        self.error_threshold = 3    # Ennyi egymást követő hiba után jön a restart
        self.consecutive_errors = 0
        self.vram_threshold_pct = 92 # 92% feletti VRAM használatnál riasztás

    async def start(self):
        if not self.is_active:
            self.is_active = True
            self.logger.info("💓 Heartbeat (Kognitív Őrszem) élesítve.")
            asyncio.create_task(self._loop())

    async def stop(self):
        self.logger.info("🛑 Heartbeat leállítása...")
        self.is_active = False

    async def _loop(self):
        while self.is_active:
            try:
                # 1. RENDSZER-EGÉSZSÉG ELLENŐRZÉSE
                await self._check_system_health()
                
                # 2. HARDVER MONITORING (VRAM védelem)
                await self._monitor_resources()

                # 3. ÖNREFLEXIÓ (Döntéshozatali hurok)
                self.reflection_counter += 1
                if self.reflection_counter >= self.reflection_limit:
                    # Nem blokkoló hívás az önreflexióhoz
                    asyncio.create_task(self._run_reflection())
                    self.reflection_counter = 0
                
                # Ha idáig eljutott a hurok, az életjelek rendben vannak
                self.consecutive_errors = 0

            except Exception as e:
                self.consecutive_errors += 1
                self.logger.error(f"⚠️ Heartbeat anomália ({self.consecutive_errors}/{self.error_threshold}): {e}")
                if self.consecutive_errors >= self.error_threshold:
                    await self._trigger_self_restart(f"Kritikus hurok hiba: {str(e)}")

            await asyncio.sleep(self.polling_interval)

    async def _check_system_health(self):
        """Ellenőrzi, hogy a slotok élnek-e és válaszolnak-e."""
        for name, slot in self.core.slots.items():
            status = slot.status()
            if not status["loaded"]:
                self.logger.warning(f"🚨 Slot elakadás észlelve: {name}. Újratöltési kísérlet...")
                try:
                    # Megpróbáljuk újra betölteni a slotot
                    slot.load()
                    self.logger.info(f"✅ Slot {name} sikeresen újraélesztve.")
                except Exception as e:
                    await self._trigger_self_restart(f"Slot {name} kritikus hiba: {e}")

    async def _monitor_resources(self):
        """Figyeli a rendszermemóriát és VRAM-ot."""
        stats = self.core.get_hardware_stats()
        # Ha a RAM használat túl magas
        if stats["ram_usage"] > 95:
            self.logger.warning(f"❗ KRITIKUS RAM HASZNÁLAT: {stats['ram_usage']}%")
            # Itt később bevezethetünk egy slot-ürítési logikát

    async def _run_reflection(self):
        """Kópé eldönti, akar-e proaktívan cselekedni vagy üzenni."""
        # Csak akkor fut le, ha a King slot szabad
        if "king" in self.core.slots and self.core.slots["king"].is_loaded:
            self.logger.info("🧠 Kognitív önreflexió indítása...")
            
            try:
                # Egy gyors csekk a Valet-tel, hogy van-e teendő
                prompt = (
                    "<|im_start|>system\nYou are SoulCore Internal Sentry. "
                    "Analyze if there is any urgent matter or proactive insight needed for Grumpy. "
                    "Current time: {}. Reply with 'YES' or 'NO' only.<|im_end|>\n"
                    "<|im_start|>user\nShould we initiate proactive communication?<|im_end|>\n"
                    "<|im_start|>assistant\n"
                ).format(datetime.now().strftime("%H:%M"))

                # A safe_generate használata a blokkolás elkerülésére
                decision = await self.core._run_in_thread("valet", "generate", prompt, {"max_tokens": 5, "temperature": 0.0})
                
                if decision and "YES" in decision.upper():
                    self.logger.info("🎯 Proaktív igény észlelve, pipeline indítása...")
                    # Meghívjuk az Orchestrator proaktív metódusát (ha létezik)
                    if hasattr(self.core, 'process_proactive_thought'):
                        asyncio.create_task(self.core.process_proactive_thought())
            except Exception as e:
                self.logger.error(f"Reflexiós hiba: {e}")

    async def _trigger_self_restart(self, reason):
        """Az autonóm újraindítás logikája, ha a rendszer instabillá válik."""
        self.logger.critical(f"🔥 !!! AUTONÓM ÚJRAINDÍTÁS INDÍTVA: {reason} !!!")
        
        # Próbálunk szólni a külvilágnak, ha van rá mód
        if hasattr(self.core, 'db'):
            self.core.db.save_message("system", "system_event", f"Restart: {reason}")
        
        # Ha van WebSocket vagy Queue, ide küldhetünk egy "System Rebooting" eventet
        
        # Várunk a logok kiírására
        await asyncio.sleep(3)
        
        # Újraindítás
        os.execv(sys.executable, [sys.executable] + sys.argv)