import json
import logging

class SoulCoreScribe:
    def __init__(self, model_slot):
        """
        model_slot: Ez az a GGUF betöltő, ami a 3B-s Llamát kezeli.
        """
        self.slot = model_slot
        self.system_prompt = """
        You are the 'Scribe', the gatekeeper of SoulCore 2.0.
        Your task is to analyze the user input and classify it for the memory systems.
        Return ONLY a JSON object.
        
        Categories:
        - 'scratchpad': Immediate info needed for the current task (token-saver).
        - 'memory': Long-term personal fact about Grumpy.
        - 'public_knowledge': Objective fact to be added to AI-Wikipedia.
        - 'internal_note': Complex request where the AI needs a draft before responding.
        - 'chat': Simple greeting or casual talk.

        Output format:
        {
            "category": "string",
            "summary_en": "one sentence English essence",
            "action_required": boolean,
            "urgency": 1-5
        }
        """

    async def classify(self, user_text):
        logging.info(f"Scribe: Analyzing input -> {user_text[:50]}...")
        
        # A 3B-s modelltől kérünk egy JSON-t
        response = await self.slot.generate(
            system=self.system_prompt,
            prompt=user_text,
            max_tokens=150,
            temperature=0.1 # A precizitás miatt alacsony!
        )
        
        try:
            # Megkeressük a JSON részt, ha a modell esetleg dumlálna (de a Scribe-tól nem várjuk el)
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            json_str = response[start_idx:end_idx]
            return json.loads(json_str)
        except Exception as e:
            logging.error(f"Scribe JSON parse error: {e}")
            return {"category": "chat", "summary_en": "Failed to parse", "action_required": False, "urgency": 1}

    async def analyze(self, user_input):
        # A Scribe elemzi a bemenetet
        raw_output = await self.driver.generate(self.system_prompt, user_input)
        try:
            return json.loads(raw_output)
        except:
            # Ha az AI hibázna a formátumban, itt javítjuk ki
            return {"category": "chat", "summary": "Error parsing", "urgency": 1}
