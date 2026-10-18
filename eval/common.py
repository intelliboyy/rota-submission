import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def load_data(data_dir=None):
    d = data_dir or os.path.join(ROOT, "data")
    items = json.load(open(os.path.join(d, "items.json")))
    key = json.load(open(os.path.join(d, "visible_key.json")))
    spec = importlib.util.spec_from_file_location("official_score", os.path.join(d, "score.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return items, key, mod
