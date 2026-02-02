import pynvml  # NVIDIA Management Library
import logging
import time

class SoulCoreMonitor:
    def __init__(self):
        try:
            pynvml.nvmlInit()
            self.has_gpu = True
        except:
            self.has_gpu = False
            print("⚠️ No NVIDIA GPU detected or NVML missing.")

        # Központi log beállítása
        logging.basicConfig(
            filename='vault/logs/system.log',
            level=logging.INFO,
            format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
        )
        self.logger = logging.getLogger("SoulCore")

    def get_gpu_stats(self):
        """Lekéri a kártyák hőmérsékletét és VRAM használatát."""
        stats = []
        if not self.has_gpu: return "N/A"
        
        device_count = pynvml.nvmlDeviceGetCount()
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            stats.append({
                "gpu": i,
                "temp": f"{temp}°C",
                "vram_used": f"{mem.used // 1024**2} MB",
                "vram_total": f"{mem.total // 1024**2} MB"
            })
        return stats

    def log_event(self, module, message, level="info"):
        """Egységes logolás a rendszer minden részéből."""
        full_msg = f"[{module.upper()}] {message}"
        if level == "info": self.logger.info(full_msg)
        elif level == "error": self.logger.error(full_msg)
        
        # Opcionálisan kiírjuk a konzolra is szépen
        print(f"📡 {full_msg}")
