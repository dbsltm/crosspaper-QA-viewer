#!/usr/bin/env python3
"""
Local web viewer for Deep Cross-Paper Bench pipeline outputs.

Usage:
    python viewer.py                    # default port 8899
    python viewer.py --port 8881        # custom port
"""
from __future__ import annotations
import argparse, json, os, mimetypes, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT.parent / "outputs"
FACTS_DIR = OUTPUTS / "facts" / "image_caption"
QA_DIR = OUTPUTS / "qa" / "image_caption"
EVAL_DIR = OUTPUTS / "eval" / "image_caption"
PARSE_DIR = OUTPUTS / "parsed"


def _load_json(path: Path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def _get_all_data() -> dict:
    all_facts = _load_json(FACTS_DIR / "all_atomic_facts.json")
    filtered_facts = _load_json(FACTS_DIR / "filtered_facts.json")
    filter_log_raw = _load_json(FACTS_DIR / "filter_log.json")
    filtered_ids = {f["fact_id"] for f in filtered_facts} if isinstance(filtered_facts, list) else set()
    filter_log_map = {}
    if isinstance(filter_log_raw, list):
        for entry in filter_log_raw:
            if isinstance(entry, dict) and "fact_id" in entry:
                filter_log_map[entry["fact_id"]] = entry

    questions = {}
    if QA_DIR.exists():
        for qf in sorted(QA_DIR.glob("multihop_questions_*.json")):
            tag = qf.stem
            data = _load_json(qf)
            if isinstance(data, list) and data:
                questions[tag] = data

    # Load full_evaluation files
    eval_data = {}
    if EVAL_DIR.exists():
        for ef in sorted(EVAL_DIR.glob("full_evaluation*.json")):
            data = _load_json(ef)
            if data:
                eval_data[ef.stem] = data

    # Load per-question eval files (eval_<model>_<qid>.json)
    per_question_evals = {}
    if EVAL_DIR.exists():
        for ef in sorted(EVAL_DIR.glob("eval_*.json")):
            data = _load_json(ef)
            if isinstance(data, dict) and "question_id" in data:
                per_question_evals[data["question_id"]] = data

    papers = {}
    for pd in sorted(PARSE_DIR.iterdir()) if PARSE_DIR.exists() else []:
        if not pd.is_dir():
            continue
        meta = pd / "layout_extract.json"
        if not meta.exists():
            meta = pd / "grobid_extract.json"
        if meta.exists():
            data = _load_json(meta)
            if isinstance(data, dict):
                pid = pd.name
                figs = data.get("figures", [])
                papers[pid] = {
                    "paper_id": pid,
                    "title": data.get("title", "Unknown"),
                    "n_sections": len(data.get("sections", [])),
                    "n_figures": len([f for f in figs
                                      if f.get("figure_type") != "table"]),
                    "n_tables": len([f for f in figs
                                     if f.get("figure_type") == "table"]),
                    "n_equations": len(data.get("equations", [])),
                }
    if not papers:
        for pf in sorted(FACTS_DIR.glob("*_parsed.json")):
            data = _load_json(pf)
            if isinstance(data, dict):
                pid = data.get("paper_id", pf.stem.replace("_parsed", ""))
                figs = data.get("figures", [])
                papers[pid] = {
                    "paper_id": pid,
                    "title": data.get("title", "Unknown"),
                    "n_sections": len(data.get("sections", [])),
                    "n_figures": len([f for f in figs if f.get("figure_type") == "figure"]),
                    "n_tables": len([f for f in figs if f.get("figure_type") == "table"]),
                    "n_equations": len(data.get("equations", [])),
                }

    return {
        "all_facts": all_facts,
        "filtered_facts": filtered_facts,
        "filtered_ids": list(filtered_ids),
        "filter_log": filter_log_map,
        "questions": questions,
        "eval": eval_data,
        "per_question_evals": per_question_evals,
        "papers": papers,
    }


class ViewerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = dict(urllib.parse.parse_qsl(parsed.query))

        if path == "/" or path == "/index.html":
            html_path = ROOT / "viewer.html"
            body = html_path.read_bytes()
            self._send(200, "text/html; charset=utf-8", body)
        elif path == "/api/data":
            data = _get_all_data()
            self._send(200, "application/json",
                       json.dumps(data, ensure_ascii=False).encode())
        elif path == "/image":
            self._serve_image(query.get("path", ""))
        else:
            self._send(404, "text/plain", b"Not found")

    def _serve_image(self, img_path: str):
        full = OUTPUTS.parent / img_path if not os.path.isabs(img_path) else Path(img_path)
        if not full.is_file():
            self._send(404, "text/plain", b"Image not found")
            return
        mime = mimetypes.guess_type(str(full))[0] or "image/png"
        self._send(200, mime, full.read_bytes())

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


def main():
    ap = argparse.ArgumentParser(description="Pipeline output viewer")
    ap.add_argument("--port", type=int, default=8881)
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()
    HTTPServer.allow_reuse_address = True
    srv = HTTPServer((args.host, args.port), ViewerHandler)
    print(f"\n  Pipeline Viewer running at http://localhost:{args.port}")
    print(f"  Facts dir:     {FACTS_DIR}")
    print(f"  Questions dir: {QA_DIR}")
    print(f"  Eval dir:      {EVAL_DIR}")
    print(f"  Parse dir:     {PARSE_DIR}\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        srv.shutdown()


if __name__ == "__main__":
    main()
