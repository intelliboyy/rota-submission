"""Model access with a hard per-item call budget.

Every attempt counts against the budget (a failed HTTP call may still be
counted by the grader's proxy), the OpenAI client's silent retries are turned
off, and X-Item-Id is sent on every call.
"""
import json
import os
import threading
import time

EXPECTED_MODEL = "ibm-granite/granite-4.2-8b"


class BudgetExceeded(Exception):
    pass


class ItemBudget:
    def __init__(self, item_id, cap):
        self.item_id, self.cap, self.used = item_id, cap, 0

    @property
    def left(self):
        return self.cap - self.used

    def take(self):
        if self.used >= self.cap:
            raise BudgetExceeded(f"{self.item_id}: budget {self.cap} exhausted")
        self.used += 1


class LLM:
    """backend: callable (item_id, messages) -> text.  Exceptions become ''."""

    def __init__(self, backend, log_path=None):
        self.backend = backend
        self.log_path = log_path
        self._lock = threading.Lock()

    def complete(self, budget, messages, tag=""):
        budget.take()
        t0 = time.time()
        err = None
        try:
            text = self.backend(budget.item_id, messages) or ""
        except Exception as e:          # network / API error: counted, not retried here
            text, err = "", repr(e)
        if self.log_path:
            rec = {"item": budget.item_id, "call": budget.used, "tag": tag,
                   "secs": round(time.time() - t0, 2), "chars": len(text), "error": err}
            with self._lock, open(self.log_path, "a") as f:
                f.write(json.dumps(rec) + "\n")
        return text


def load_settings():
    """Read .env (if present) and return base_url, api_key, model.

    Preferred names: OPENROUTER_BASE_URL, OPENROUTER_API_KEY, MODEL.  Aliases are
    accepted, and if the key is under an unexpected name, the single variable
    defined in .env whose name contains "KEY" is used.  Secrets are never printed.
    """
    env_file_keys = []
    try:
        from dotenv import dotenv_values, load_dotenv
        load_dotenv()
        env_file_keys = list(dotenv_values().keys())
    except ImportError:
        pass

    def first(*keys):
        for k in keys:
            if os.environ.get(k):
                return os.environ[k]
        return None

    base = first("OPENROUTER_BASE_URL", "OPENAI_BASE_URL", "BASE_URL", "API_BASE_URL", "API_BASE")
    key = first("OPENROUTER_API_KEY", "OPENAI_API_KEY", "API_KEY")
    if not key:
        cands = [k for k in env_file_keys if "KEY" in k.upper() and os.environ.get(k)]
        if len(cands) == 1:
            key = os.environ[cands[0]]
    model = first("MODEL", "MODEL_NAME", "MODEL_ID", "OPENROUTER_MODEL", "OPENAI_MODEL") or EXPECTED_MODEL
    missing = [n for n, v in (("base URL (OPENROUTER_BASE_URL)", base), ("API key (OPENROUTER_API_KEY)", key)) if not v]
    if missing:
        raise SystemExit(f"Missing {', '.join(missing)}. Variables found in .env: {env_file_keys or 'none'}.")
    if "granite" not in model.lower():
        raise SystemExit(f"Refusing to run: model '{model}' is not the Granite model the key is for.")
    return base, key, model


class OpenAIBackend:
    def __init__(self, base_url, api_key, model, timeout=120, max_tokens=1200):
        from openai import OpenAI
        # max_retries=0: the SDK must never retry behind our back (budget!)
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0)
        self.model, self.max_tokens = model, max_tokens

    def __call__(self, item_id, messages):
        r = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=1.0,
            top_p=0.95,
            max_tokens=self.max_tokens,
            extra_headers={"X-Item-Id": item_id},
            extra_body={"reasoning": {"enabled": False}},
        )
        return r.choices[0].message.content or ""


def make_llm(log_path=None):
    base, key, model = load_settings()
    return LLM(OpenAIBackend(base, key, model), log_path)
