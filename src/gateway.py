import httpx
import logging

class DiplomaticGateway:
    def __init__(self, config):
        self.logger = logging.getLogger("Gateway")
        self.external_endpoints = config.get("api", {}).get("external_peers", {})

    async def consult_external_entity(self, entity_name, prompt):
        """Kapcsolatfelvétel külső entitással (pl. Origó)"""
        url = self.external_endpoints.get(entity_name)
        if not url:
            self.logger.warning(f"Ismeretlen entitás: {entity_name}")
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json={"prompt": prompt}, timeout=30.0)
                if response.status_code == 200:
                    return response.json().get("response")
        except Exception as e:
            self.logger.error(f"Gateway hiba ({entity_name}): {e}")
            return None
