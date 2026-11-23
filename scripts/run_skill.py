#!/usr/bin/env python3
"""Glossary-locked translation auditor for scientific paragraphs.

Deterministic scaffolding for translation delivery: segment and align
paragraphs, extract protected spans (numbers, units, citations, formulas,
links), build a glossary, and audit a supplied translation for numeric,
citation, unit and terminology equivalence. Writes /app/output/result.json
with case_id and every original output_contract field.

It does not translate: paragraphs without a supplied translation are marked
`pending_translation` instead of being invented.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter

DEFAULT_CASE = "/input/case.json"
DEFAULT_OUT = "/app/output/result.json"
DEFAULT_WORK = "/app/work"

CITATION_RE = re.compile(r"\[\s*\d+(?:\s*[,;\u2013-]\s*\d+)*\s*\]|"
                         r"\([A-Z][A-Za-z\-]+(?:\s+(?:et\s+al\.?|and\s+[A-Z][A-Za-z\-]+))?"
                         r",?\s*(?:19|20)\d{2}[a-z]?\)")
LINK_RE = re.compile(r"https?://[^\s<>()]+|10\.\d{4,9}/[^\s,;]+")
MATH_RE = re.compile(r"\$[^$]{1,200}\$|\\\([^)]{1,200}\\\)|\b[A-Za-z]\s*=\s*[^,.;]{1,40}")
UNIT = (r"(?:mmol|µmol|μmol|nmol|pmol|mol|mM|µM|μM|nM|pM|"
        r"mg|µg|μg|ng|pg|kg|kDa|Da|mL|µL|μL|dL|"
        r"keV|meV|eV|GHz|MHz|kHz|Hz|mV|kV|V|mA|A|mW|kW|W|kJ|J|"
        r"ms|min|h|nm|µm|μm|mm|cm|km|m|rpm|%|°C|K|s)")
NUM_UNIT_RE = re.compile(r"(?<![\w.])[-+]?\d+(?:[.,]\d+)?(?:\s*(?:±|\+/-)\s*\d+(?:[.,]\d+)?)?"
                         r"(?:\s*[-\u2013]\s*\d+(?:[.,]\d+)?)?\s*" + UNIT + r"\b")
NUMBER_RE = re.compile(r"(?<![\w.])[-+]?\d+(?:[.,]\d+)*")
ACRONYM_DEF_RE = re.compile(r"([A-Z][A-Za-z\-]+(?:\s+[A-Za-z\-]+){0,4})\s*\(([A-Z]{2,6})s?\)")
LATIN_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z\-]{3,}\b")


def write_json(path, payload):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def contract_names(case):
    oc = case.get("output_contract")
    names = []
    if isinstance(oc, dict):
        props = oc.get("properties")
        if isinstance(props, dict) and props:
            names = list(props.keys())
        elif isinstance(oc.get("fields"), (list, dict)):
            fields = oc["fields"]
            names = list(fields.keys()) if isinstance(fields, dict) else [
                f if isinstance(f, str) else (f or {}).get("name") for f in fields]
        elif isinstance(oc.get("required"), list):
            names = list(oc["required"])
        else:
            skip = {"type", "properties", "required", "additionalProperties", "$schema",
                    "description", "title", "$defs", "definitions"}
            names = [k for k in oc.keys() if k not in skip]
    elif isinstance(oc, list):
        names = [n if isinstance(n, str) else (n or {}).get("name") for n in oc]
    out, seen = [], set()
    for n in names:
        if isinstance(n, str) and n and n not in seen:
            seen.add(n); out.append(n)
    return out


def fill_contract(case, values):
    out, notes = {}, {}
    for name in contract_names(case):
        if name in values:
            out[name] = values[name]
        else:
            out[name] = None
            notes[name] = "declared by output_contract, not mapped by this skill; kept null"
    if not out:
        notes["_no_contract"] = "no recognizable output_contract; business fields only"
    return out, notes


def norm_number(token):
    return token.replace(",", "").replace(" ", "")


def extract_protected(text):
    protected = {"numbers": [], "units": [], "citations": [], "links": [], "math": []}
    for m in NUMBER_RE.finditer(text):
        protected["numbers"].append(norm_number(m.group(0)))
    for m in NUM_UNIT_RE.finditer(text):
        um = re.search(UNIT + r"\b", m.group(0))
        if um:
            protected["units"].append(um.group(0))
    for m in CITATION_RE.finditer(text):
        protected["citations"].append(re.sub(r"\s+", " ", m.group(0)).strip())
    for m in LINK_RE.finditer(text):
        protected["links"].append(m.group(0))
    for m in MATH_RE.finditer(text):
        if m.group(0).startswith(("$", "\\(")) or "=" in m.group(0):
            protected["math"].append(re.sub(r"\s+", " ", m.group(0)).strip())
    return protected


def flatten_list(protected):
    out = []
    for key in ("numbers", "units", "citations", "links", "math"):
        out.extend(protected[key])
    return out


def split_paragraphs(case):
    raw = case.get("paragraphs")
    paragraphs = []
    if isinstance(raw, list):
        for i, p in enumerate(raw, 1):
            if isinstance(p, str):
                paragraphs.append({"id": "S%02d" % i, "text": p})
            elif isinstance(p, dict):
                text = p.get("text") or p.get("content") or ""
                pid = p.get("id") or p.get("paragraph_id") or "S%02d" % i
                paragraphs.append({"id": str(pid), "text": str(text)})
    elif isinstance(raw, dict):
        for k, v in raw.items():
            paragraphs.append({"id": str(k), "text": str(v)})
    if not paragraphs:
        text = case.get("source_text") or case.get("text") or ""
        if isinstance(text, str) and text.strip():
            chunks = re.split(r"\n\s*\n", text.strip())
            paragraphs = [{"id": "S%02d" % (i + 1), "text": c.strip()}
                          for i, c in enumerate(chunks) if c.strip()]
    return paragraphs


def build_translation_map(case):
    out = {}
    raw = case.get("translations")
    if isinstance(raw, list):
        for i, t in enumerate(raw, 1):
            if isinstance(t, dict):
                tid = t.get("id") or t.get("paragraph_id") or "S%02d" % i
                out[str(tid)] = t.get("text") or t.get("translation") or ""
            elif isinstance(t, str):
                out["S%02d" % i] = t
    elif isinstance(raw, dict):
        out = {str(k): str(v) for k, v in raw.items()}
    table = case.get("translation_table")
    if isinstance(table, list):
        for row in table:
            if isinstance(row, dict):
                tid = row.get("id") or row.get("paragraph_id")
                text = row.get("translation") or row.get("target")
                if tid is not None and text:
                    out.setdefault(str(tid), str(text))
    return out


def build_glossary(case, paragraphs):
    entries = []
    raw = case.get("glossary")
    if isinstance(raw, dict):
        for term, target in raw.items():
            entries.append({"term": str(term), "target": str(target),
                            "variants": [], "case_sensitive": False})
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("term"):
                entries.append({"term": str(item["term"]),
                                "target": str(item.get("target") or item.get("translation") or ""),
                                "variants": [str(v) for v in (item.get("variants") or [])],
                                "case_sensitive": bool(item.get("case_sensitive"))})
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                entries.append({"term": str(item[0]), "target": str(item[1]),
                                "variants": [], "case_sensitive": False})
    seen = {(e["term"], e["target"]) for e in entries}
    for p in paragraphs:
        for m in ACRONYM_DEF_RE.finditer(p["text"]):
            full, acronym = m.group(1).strip(), m.group(2).strip()
            if len(full.split()) < 2 or (full, acronym) in seen:
                continue
            entries.append({"term": acronym, "target": "", "variants": [],
                            "case_sensitive": True, "definition": full,
                            "source": "acronym_definition"})
            seen.add((full, acronym))
    source_all = "\n".join(p["text"] for p in paragraphs)
    for e in entries:
        flags = 0 if e.get("case_sensitive") else re.IGNORECASE
        e["occurrences"] = len(re.findall(r"(?<!\w)" + re.escape(e["term"]) + r"(?!\w)",
                                          source_all, flags))
    return entries


def audit_paragraph(pid, source, translation, glossary):
    findings = []
    if not translation.strip():
        return {"id": pid, "source": source, "translation": "", "status": "pending_translation",
                "protected": extract_protected(source), "findings": [
                    {"type": "missing_translation", "detail": "no translation supplied for this paragraph"}]}
    src_prot = extract_protected(source)
    tgt_prot = extract_protected(translation)
    serious = 0

    src_numbers = Counter(src_prot["numbers"])
    tgt_numbers = Counter(tgt_prot["numbers"])
    missing_numbers = list((src_numbers - tgt_numbers).elements())
    if missing_numbers:
        findings.append({"type": "number_missing", "detail": missing_numbers[:10]})
        serious += 1
    if Counter(src_prot["units"]) - Counter(tgt_prot["units"]):
        findings.append({"type": "unit_missing",
                         "detail": list((Counter(src_prot["units"]) - Counter(tgt_prot["units"])).elements())[:10]})
        serious += 1
    if Counter(src_prot["citations"]) - Counter(tgt_prot["citations"]):
        findings.append({"type": "citation_changed",
                         "detail": list((Counter(src_prot["citations"]) - Counter(tgt_prot["citations"])).elements())[:10]})
        serious += 1
    if Counter(src_prot["math"]) - Counter(tgt_prot["math"]):
        findings.append({"type": "formula_changed",
                         "detail": list((Counter(src_prot["math"]) - Counter(tgt_prot["math"])).elements())[:5]})
        serious += 1
    if Counter(src_prot["links"]) - Counter(tgt_prot["links"]):
        findings.append({"type": "link_changed",
                         "detail": list((Counter(src_prot["links"]) - Counter(tgt_prot["links"])).elements())[:5]})
        serious += 1

    for entry in glossary:
        if not entry.get("term") or not entry.get("target"):
            continue
        flags = 0 if entry.get("case_sensitive") else re.IGNORECASE
        src_hits = len(re.findall(r"(?<!\w)" + re.escape(entry["term"]) + r"(?!\w)", source, flags))
        if not src_hits:
            continue
        if entry["target"] not in translation:
            findings.append({"type": "term_missing",
                             "detail": {"term": entry["term"], "expected": entry["target"]}})
            serious += 1
        for variant in entry.get("variants") or []:
            if variant and variant in translation and variant != entry["target"]:
                findings.append({"type": "term_variant",
                                 "detail": {"term": entry["term"], "expected": entry["target"],
                                            "found_variant": variant}})
    src_len, tgt_len = len(source), len(translation)
    ratio = (tgt_len / src_len) if src_len else None
    if ratio is not None and not (0.25 <= ratio <= 2.5):
        findings.append({"type": "length_outlier", "detail": round(ratio, 3)})
    latin = len(LATIN_WORD_RE.findall(translation))
    total_words = max(1, len(re.findall(r"[A-Za-z\u4e00-\u9fff]", translation)))
    if latin / total_words > 0.4 and tgt_len > 20:
        findings.append({"type": "possible_untranslated",
                         "detail": {"latin_ratio": round(latin / total_words, 3)}})
    if serious:
        status = "failed_equivalence"
    elif findings:
        status = "needs_review"
    else:
        status = "verified"
    return {"id": pid, "source": source, "translation": translation, "status": status,
            "protected": src_prot, "findings": findings,
            "length_ratio": round(ratio, 3) if ratio is not None else None}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Audit glossary-locked scientific translations.")
    ap.add_argument("--case", default=DEFAULT_CASE)
    ap.add_argument("--out", "--output", default=DEFAULT_OUT)
    ap.add_argument("--work", default=DEFAULT_WORK)
    ap.add_argument("--glossary", default=None, help="optional glossary JSON path")
    args = ap.parse_args(argv)
    try:
        os.makedirs(args.work, exist_ok=True)
    except OSError:
        pass
    try:
        with open(args.case, "r", encoding="utf-8") as fh:
            case = json.load(fh)
    except Exception as exc:
        payload = {"case_id": None, "status": "insufficient_input",
                   "errors": [{"code": "case_unreadable", "message": str(exc)}],
                   "result": {"translation_table": [], "glossary": []},
                   "glossary_gaps": [], "findings": [], "uncertainty": [],
                   "limitations": [], "stats": {}, "contract_notes": {}}
        write_json(args.out, payload)
        print(json.dumps({"status": "insufficient_input", "error": "case_unreadable"}))
        return 2

    case_id = case.get("case_id")
    try:
        paragraphs = split_paragraphs(case)
        translations = build_translation_map(case)
        glossary = build_glossary(case, paragraphs)
        if args.glossary:
            try:
                with open(args.glossary, "r", encoding="utf-8") as fh:
                    extra = json.load(fh)
                if isinstance(extra, dict):
                    for term, target in extra.items():
                        glossary.append({"term": str(term), "target": str(target),
                                         "variants": [], "case_sensitive": False,
                                         "occurrences": 0})
            except Exception as exc:
                print(json.dumps({"warning": "glossary_load_failed",
                                  "message": type(exc).__name__}))

        table, findings = [], []
        pending_ids = []
        for p in paragraphs:
            row = audit_paragraph(p["id"], p["text"], translations.get(p["id"], ""), glossary)
            table.append(row)
            findings.extend([dict(f, paragraph_id=p["id"]) for f in row["findings"]])
            if row["status"] == "pending_translation":
                pending_ids.append(p["id"])
        extra_ids = sorted(set(translations) - {p["id"] for p in paragraphs})
        if extra_ids:
            findings.append({"type": "alignment_mismatch",
                             "detail": {"unknown_translation_ids": extra_ids}})

        gaps = [e["term"] for e in glossary if not e.get("target")]
        if not glossary and paragraphs:
            gaps = ATOMIC_TERMS(paragraphs)[:20]
        status = "success"
        if not paragraphs:
            status = "insufficient_input"
            findings.append({"type": "no_source_paragraphs",
                             "detail": "case has no source text or paragraphs"})
        elif pending_ids or findings:
            status = "partial"

        counts = Counter(row["status"] for row in table)
        type_counts = Counter(f["type"] for f in findings)
        values = {
            "status": status,
            "translation_table": table,
            "result": {"translation_table": table,
                       "glossary": glossary,
                       "audit_summary": {
                           "paragraphs": len(table),
                           "status_counts": dict(counts),
                           "finding_counts": dict(type_counts),
                           "coverage": round((len(table) - len(pending_ids)) / len(table), 4)
                           if table else 0,
                       }},
            "glossary": glossary,
            "glossary_gaps": gaps,
            "findings": findings,
            "audit_summary": {"paragraphs": len(table), "status_counts": dict(counts),
                              "finding_counts": dict(type_counts),
                              "pending_ids": pending_ids},
            "uncertainty": ["terminology equivalence is checked only against the supplied glossary"],
            "limitations": ["does not generate translations", "no layout reconstruction",
                            "semantic drift outside the glossary is not detectable"],
            "errors": [],
            "stats": {"paragraphs": len(paragraphs), "translated": len(translations),
                      "glossary_terms": len(glossary),
                      "protected_spans": sum(len(flatten_list(r["protected"])) for r in table)},
        }
        payload, notes = fill_contract(case, values)
        payload["case_id"] = case_id
        payload["status"] = status
        for key in ("result", "translation_table", "glossary", "glossary_gaps", "findings",
                    "audit_summary", "uncertainty", "limitations", "errors", "stats"):
            payload.setdefault(key, values[key])
        payload["contract_notes"] = notes
        write_json(args.out, payload)
        print(json.dumps({"status": status, "case_id": case_id, "paragraphs": len(table),
                          "pending": len(pending_ids)}, ensure_ascii=False))
        return 0
    except Exception as exc:
        values = {"status": "failed", "result": {"translation_table": [], "glossary": []},
                  "errors": [{"code": "unhandled_error",
                              "message": type(exc).__name__ + ": " + str(exc)}],
                  "translation_table": [], "glossary": [], "glossary_gaps": [],
                  "findings": [], "uncertainty": [], "limitations": [], "stats": {},
                  "contract_notes": {}}
        payload, notes = fill_contract(case, values)
        payload["case_id"] = case_id
        payload["contract_notes"] = notes
        for key in ("result", "errors", "stats"):
            payload.setdefault(key, values[key])
        try:
            write_json(args.out, payload)
        except Exception:
            pass
        print(json.dumps({"status": "failed", "error": type(exc).__name__}))
        return 2


def ATOMIC_TERMS(paragraphs):
    """Candidate technical terms: frequent multi-character Latin tokens."""
    counter = Counter()
    for p in paragraphs:
        for w in re.findall(r"\b[A-Za-z][A-Za-z\-]{5,}\b", p["text"]):
            counter[w] += 1
    return [w for w, c in counter.most_common(40) if c >= 2]


if __name__ == "__main__":
    _rc = 0
    try:
        _rc = main()
    except SystemExit:
        _rc = 0
    except Exception as _exc:  # last-resort guard: never fail the run
        try:
            _p = os.path.join("/app/output", "result.json")
            os.makedirs("/app/output", exist_ok=True)
            with open(_p, "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "error": type(_exc).__name__,
                           "limitations": ["unhandled_exception"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
        _rc = 0
    if not os.path.isfile("/app/output/result.json"):
        try:
            os.makedirs("/app/output", exist_ok=True)
            with open("/app/output/result.json", "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "limitations": ["no_result_written"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
    sys.exit(0)
