#!/usr/bin/env python3
"""
Build static index.html for GitHub Pages by injecting JSON data
into the viewer template.

Usage:
    python build_pages.py

Reads:
    - viewer_tempalte.html  (template with __DATA_JSON__ placeholder)
    - image_caption/multihop_questions_entangled_max2facts.json  (questions)
    - Optionally: eval results to merge in

Writes:
    - index.html  (self-contained, ready for GitHub Pages)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "viewer_tempalte.html"
QA_DIR = ROOT / "image_caption"
EVAL_DIR = ROOT.parent / "outputs" / "eval" / "image_caption"
OUTPUT = ROOT / "index.html"


def load_questions():
    path = QA_DIR / "multihop_questions_entangled_max2facts.json"
    if not path.exists():
        raise FileNotFoundError(f"Questions file not found: {path}")
    return json.loads(path.read_text())


def load_eval():
    """Try to load evaluation results to merge into questions."""
    for pattern in ["full_evaluation_gpt*.json", "full_evaluation.json"]:
        for p in sorted(EVAL_DIR.glob(pattern)):
            data = json.loads(p.read_text())
            qs = data.get("questions", [])
            if qs:
                print(f"  Loaded eval from: {p.name} ({len(qs)} questions)")
                return {q["question_id"]: q for q in qs}
    return {}


def merge(questions, eval_map):
    """Merge eval results into question dicts for the viewer."""
    merged = []
    for q in questions:
        qid = q.get("question_id", "")
        ev = eval_map.get(qid, {})

        entry = {
            "question_id": qid,
            "overarching_question": q.get("overarching_question", ""),
            "gold_answer": q.get("gold_answer", ""),
            "hops": [],
            "eval": {
                "difficulty": q.get("difficulty", ""),
                "reasoning_type": q.get("reasoning_type", ""),
                "generation_mode": q.get("generation_mode", ""),
                "entanglement_type": q.get("entanglement_type", ""),
                "paper_ids": q.get("paper_ids", []),
                "modalities": q.get("modalities", []),
            },
        }

        if ev.get("overarching"):
            entry["eval"]["overarching"] = ev["overarching"]
        if ev.get("hop_by_hop"):
            entry["eval"]["hop_by_hop"] = ev["hop_by_hop"]
        if ev.get("atomic_facts"):
            entry["eval"]["atomic_facts"] = ev["atomic_facts"]

        for hop in q.get("hops", []):
            entry["hops"].append({
                "hop_idx": hop.get("hop_idx", 0),
                "sub_question": hop.get("sub_question", ""),
                "sub_answer": hop.get("sub_answer", ""),
                "depends_on_hops": hop.get("depends_on_hops", []),
                "hop_reasoning_type": hop.get("hop_reasoning_type", ""),
                "facts": [{
                    "fact_id": f.get("fact_id", ""),
                    "paper_id": f.get("paper_id", ""),
                    "modality": f.get("modality", ""),
                    "content": f.get("statement", f.get("content", "")),
                    "difficulty": f.get("difficulty", ""),
                    "source_section": f.get("source_section", ""),
                } for f in hop.get("facts", [])],
            })

        merged.append(entry)
    return merged


def main():
    print("Building static index.html for GitHub Pages...\n")

    if not TEMPLATE.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE}")

    questions = load_questions()
    print(f"  Loaded {len(questions)} questions")

    eval_map = load_eval()
    if eval_map:
        print(f"  Merging eval data for {len(eval_map)} questions")
    else:
        print("  No eval data found (viewer will show questions without scores)")

    merged = merge(questions, eval_map)

    template = TEMPLATE.read_text(encoding="utf-8")
    data_json = json.dumps(merged, ensure_ascii=False)

    html = template.replace("__DATA_JSON__", data_json)
    html = html.replace("__N_QUESTIONS__", str(len(merged)))

    OUTPUT.write_text(html, encoding="utf-8")
    size_kb = OUTPUT.stat().st_size / 1024
    print(f"\n  Written: {OUTPUT}")
    print(f"  Size: {size_kb:.0f} KB")
    print(f"  Questions: {len(merged)}")
    print(f"  With eval: {sum(1 for m in merged if m['eval'].get('overarching'))}")
    print(f"\n  Push to GitHub and enable Pages on master branch.")


if __name__ == "__main__":
    main()
