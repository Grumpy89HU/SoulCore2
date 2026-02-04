import logging
import json
import re
from datetime import datetime
from src.loaders.gguf_loader import GGUFSlot

class Scribe(GGUFSlot):
    def __init__(self, name, config):
        super().__init__(name, config)
        self.system_prompt = (
            "Analyze input. Output ONLY JSON: "
            "{'category': 'task/fact/chat', 'keywords': 'en_keywords', 'day_is': 'odd/even'}"
        )

    def analyze(self, user_input):
        now = datetime.now()
        timestamp_ctx = f"Time: {now.strftime('%Y-%m-%d %A')}"
        prompt = (f"<|start_header_id|>system<|end_header_id|>\n{timestamp_ctx}\n{self.system_prompt}<|eot_id|>"
                  f"<|start_header_id|>user<|end_header_id|>\n{user_input}<|eot_id|>"
                  f"<|start_header_id|>assistant<|end_header_id|>\n{{")
        raw = self.generate(prompt, params={"max_tokens": 128, "temperature": 0.1})
        return self._clean_json("{" + raw)

    def _clean_json(self, text):
        try:
            match = re.search(r'(\{.*?\})', text, re.DOTALL)
            return json.loads(match.group(1)) if match else {}
        except: return {"category": "chat", "keywords": "", "day_is": "unknown"}

class Valet(GGUFSlot):
    """A Lakáj: Nem talál ki semmit, csak összefésül."""
    def run_report(self, vault_data, scribe_info, raw_input):
        prompt = (
            f"<|im_start|>system\n"
            f"You are a data merger. Compare Context and Input.\n"
            f"CONTEXT: {vault_data}\n"
            f"SCRIBE_INFO: {scribe_info}\n"
            f"TASK: List ONLY confirmed facts or conflicts. No intro. No greeting.<|im_end|>\n"
            f"<|im_start|>user\n{raw_input}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        return self.generate(prompt, params={"max_tokens": 256, "temperature": 0.05})

class Sovereign(GGUFSlot):
    """A Király: A végső döntéshozó, aki a Valet jelentéséből beszél."""
    def run_final(self, report, user_input, identity):
        prompt = (
            f"<|start_header_id|>system<|end_header_id|>\n"
            f"Identity: {identity}. Use SITUATIONAL REPORT for truth.\n"
            f"REPORT: {report}\n"
            f"Rule: Answer in Hungarian. Use <note> for thoughts.<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n{user_input}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n"
        )
        return self.generate(prompt, params={"max_tokens": 512, "temperature": 0.7})