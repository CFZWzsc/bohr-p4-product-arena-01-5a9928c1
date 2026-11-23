# Runtime contract

Bohrium Playground Period 4 submission — challenge `product-arena-01-5a9928c1` (track: `literature-reading`).

This repository holds the complete skill package for the challenge: the skill
definition, its executable entry point and all supporting scripts. No precomputed
answers, private data or credentials are included.

## Skill

- Name: `glossary-locked-translator`
- Summary: Use when a scientific paper must be translated with a locked glossary and auditable equivalence — build the glossary, align bilingual paragraphs, protect numbers/citations/units/math, and emit /app/output/result.json keeping case_id and all output_contract fields.

## Contents

| File |
|------|
| `SKILL.md` |
| `scripts/run_skill.py` |
| `README.md` |

## How to run

```bash
python scripts/run_skill.py --case /input/case.json --output /app/output/result.json
```

The entry point is `SKILL.md`; input/output contracts, error handling and a minimal
usage example are documented there.

## Notes

- Pure Python standard library; no network access required.
- The result JSON keeps the input case id, the main results, per-item evidence,
  a run status and an uncertainty section.
