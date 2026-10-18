Place the company files here locally. They are not part of the public repository.

- `items.json`
- `visible_key.json`
- `score.py`

Copy them from the take-home package, then:

```
python run data/items.json --budget 1x --out answers.json
python data/score.py data/visible_key.json answers.json
```
