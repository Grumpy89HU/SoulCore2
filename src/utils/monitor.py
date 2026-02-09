import pynvml
import logging
import os
from datetime import datetime
from typing import List, Dict, Union, Any

class SoulCoreMonitor:
    def __init__(self, log_path: str = 'vault/logs/system.log'):
        # Log könyvtár létrehozása, ha nem létezne
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        
        # NVML inicializálása
        try:
            pynvml.nvmlInit()
            self.has_gpu = True
            self.device_count = pynvml.nvmlDeviceGetCount()
        except Exception as e:
            self.has_gpu = False
            self.device_count = 0
            print(f"⚠️ NVIDIA GPU nem észlelhető vagy NVML hiba: {e}")

        # Központi log beállítása
        logging.basicConfig(
            filename=log_path,
            level=logging.INFO,
            format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
        )
        self.logger = logging.getLogger("SoulCore")

    def get_gpu_stats(self) -> Union[List[Dict[str, Any]], str]:
        """Lekéri a GPU-k részletes állapotát (Hőmérséklet, VRAM, Terhelés)."""
        if not self.has_gpu:
            return "N/A"
        
        stats = []
        try:
            for i in range(self.device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                
                # Hőmérséklet
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                
                # Memória adatok
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                vram_used_mb = mem.used // 1024**2
                vram_total_mb = mem.total // 1024**2
                vram_pct = round((mem.used / mem.total) * 100, 1)
                
                # GPU mag kihasználtság (Utilization)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                
                stats.append({
                    "gpu_index": i,
                    "name": pynvml.nvmlDeviceGetName(handle),
                    "temp": f"{temp}°C",
                    "vram_used_mb": vram_used_mb,
                    "vram_total_mb": vram_total_mb,
                    "vram_usage_pct": vram_pct,
                    "gpu_load_pct": util.gpu,
                    "mem_load_pct": util.memory
                })
        except Exception as e:
            self.log_event("Monitor", f"Hiba a GPU statisztikák lekérésekor: {e}", level="error")
            return "ERROR"
            
        return stats

    def log_event(self, module: str, message: str, level: str = "info"):
        """
        Egységes logolás. 
        Szintek: info, warning, error, critical
        """
        full_msg = f"[{module.upper()}] {message}"
        
        # Log fájlba írás
        if level.lower() == "info":
            self.logger.info(full_msg)
            icon = "📡"
        elif level.lower() == "warning":
            self.logger.warning(full_msg)
            icon = "⚠️"
        elif level.lower() == "error":
            self.logger.error(full_msg)
            icon = "❌"
        elif level.lower() == "critical":
            self.logger.critical(full_msg)
            icon = "🔥"
        else:
            self.logger.info(full_msg)
            icon = "📝"

        # Konzolra írás (színes jelzéssel)
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {icon} {full_msg}")

    def check_vram_safety(self, threshold_pct: float = 90.0) -> bool:
        """Ellenőrzi, hogy van-e elég szabad VRAM a biztonságos futáshoz."""
        stats = self.get_gpu_stats()
        if isinstance(stats, list):
            for gpu in stats:
                if gpu["vram_usage_pct"] > threshold_pct:
                    self.log_event("Monitor", f"VRAM kritikus szinten: {gpu['vram_usage_pct']}%", level="warning")
                    return False
        return True

    def __del__(self):
        """Erőforrások felszabadítása."""
        if self.has_gpu:
            try:
                pynvml.nvmlShutdown()
            except:
                pass