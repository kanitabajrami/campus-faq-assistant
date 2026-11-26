"""Campus FAQ Assistant: Week 3 prototype core.

Workflow: validate input -> TF-IDF retrieval (AI) + keyword baseline (no AI)
          -> accept / fallback -> response -> log.
Run:  python src/assistant.py "How do I sign up for courses?"
"""
import csv
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, str(Path(__file__).resolve().parent))
from baseline import OUT_OF_SCOPE, load_faq, match as baseline_match  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FAQ = ROOT / "data" / "faq.csv"
DEFAULT_LOG = ROOT / "logs" / "query_log.csv"
DEFAULT_THRESHOLD = 0.20
MAX_LEN = 300
MIN_LETTERS = 3
REQUIRED_COLUMNS = {"faq_id", "question", "answer"}
FALLBACK = ("Sorry, I could not find a reliable answer. Please check the official "
            "SEEU website or contact the relevant university office.")


class KnowledgeBaseError(Exception):
    """The FAQ file is missing, malformed or empty."""


def validate_question(raw):
    """Return (clean_text, error). error is None for valid input, else (code, message)."""
    if not isinstance(raw, str):
        return "", ("NOT_TEXT", "Please type your question as text.")
    text = " ".join(re.sub(r"[\x00-\x1f\x7f]+", " ", raw).split())
    if not text:
        return "", ("EMPTY", "Please type a question.")
    if len(text) > MAX_LEN:
        return text, ("TOO_LONG", f"Your question is too long (maximum {MAX_LEN} characters). Please shorten it.")
    if sum(ch.isalpha() for ch in text) < MIN_LETTERS:
        return text, ("NO_LETTERS", "Your question needs words. Please use letters, not only numbers or symbols.")
    return text, None


def load_knowledge_base(path):
    """Load and clean the FAQ file; raise KnowledgeBaseError with a clear message."""
    path = Path(path)
    if not path.exists():
        raise KnowledgeBaseError(f"FAQ file not found: {path}")
    try:
        with open(path, newline="", encoding="utf-8") as f:
            header = set(csv.DictReader(f).fieldnames or [])
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        raise KnowledgeBaseError(f"FAQ file cannot be read: {e}")
    missing = REQUIRED_COLUMNS - header
    if missing:
        raise KnowledgeBaseError(f"FAQ file is missing required columns: {sorted(missing)}")
    rows, issues = load_faq(path)
    if not rows:
        raise KnowledgeBaseError("FAQ file has no valid FAQ entries.")
    return rows, issues


class FAQAssistant:
    def __init__(self, faq_path=DEFAULT_FAQ, threshold=DEFAULT_THRESHOLD, log_path=DEFAULT_LOG):
        if not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
            raise ValueError("threshold must be a number between 0 and 1")
        self.threshold = float(threshold)
        self.log_path = Path(log_path) if log_path else None
        self.faq, self.kb_issues = load_knowledge_base(faq_path)
        try:
            self.vectorizer = TfidfVectorizer(lowercase=True, stop_words="english")
            self.faq_vectors = self.vectorizer.fit_transform([r["question"] for r in self.faq])
        except ValueError as e:                       # e.g. empty vocabulary
            raise KnowledgeBaseError(f"FAQ questions cannot be indexed: {e}")

    # ---- AI step: TF-IDF + cosine similarity ----
    def _tfidf(self, question):
        scores = cosine_similarity(self.vectorizer.transform([question]), self.faq_vectors)[0]
        order = scores.argsort()[::-1]
        top3 = [(self.faq[i], round(float(scores[i]), 3)) for i in order[:3] if scores[i] > 0]
        best = float(scores[order[0]])
        accepted = best >= self.threshold and best > 0
        return {"accepted": accepted, "score": round(best, 3),
                "predicted_faq_id": self.faq[order[0]]["faq_id"] if accepted else OUT_OF_SCOPE,
                "entry": self.faq[order[0]] if accepted else None, "top3": top3}

    def ask(self, raw_question):
        """Full workflow for one question. Never raises for bad user input."""
        t0 = time.perf_counter()
        text, error = validate_question(raw_question)
        result = {"question": text, "status": None, "message": None, "tfidf": None,
                  "baseline": None, "log_warning": None}
        if error:
            result.update(status="invalid", message=error[1], error_code=error[0])
        else:
            try:
                result["tfidf"] = self._tfidf(text)
                b = baseline_match(text, self.faq)
                result["baseline"] = {"accepted": b["accepted"], "overlap": b["overlap_score"],
                                      "predicted_faq_id": b["predicted_faq_id"],
                                      "entry": next((r for r in self.faq if r["faq_id"] == b["predicted_faq_id"]), None)}
                if result["tfidf"]["accepted"]:
                    result["status"], result["message"] = "ok", result["tfidf"]["entry"]["answer"]
                else:
                    result["status"], result["message"] = "no_match", FALLBACK
            except Exception as e:                      # unexpected internal error
                result.update(status="error", message="Something went wrong. Please try again.",
                              error_detail=str(e))
        result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        result["log_warning"] = self._log(result)
        return result

    def _log(self, r):
        """Append one row to the query log. A logging failure never breaks the answer."""
        if not self.log_path:
            return None
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            new = not self.log_path.exists()
            with open(self.log_path, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(["timestamp", "query_text", "status", "tfidf_id", "tfidf_score",
                                "baseline_id", "baseline_overlap", "latency_ms"])
                t, b = r["tfidf"], r["baseline"]
                w.writerow([datetime.now().isoformat(timespec="seconds"), r["question"][:MAX_LEN], r["status"],
                            t["predicted_faq_id"] if t else "", t["score"] if t else "",
                            b["predicted_faq_id"] if b else "", b["overlap"] if b else "", r["latency_ms"]])
            return None
        except OSError as e:
            return f"Query log could not be written: {e}"


def show(result):
    print(f"Question : {result['question']!r}")
    print(f"Status   : {result['status']}  ({result['latency_ms']} ms)")
    if result["status"] in ("ok", "no_match"):
        t, b = result["tfidf"], result["baseline"]
        print(f"TF-IDF   : {t['predicted_faq_id']} (score {t['score']})   Baseline: {b['predicted_faq_id']} (overlap {b['overlap']})")
        if t["entry"]:
            print(f"Matched  : {t['entry']['question']}")
            print(f"Source   : {t['entry'].get('source_url', '')}")
    print(f"Response : {result['message']}")
    if result["log_warning"]:
        print("Warning  :", result["log_warning"])


if __name__ == "__main__":
    try:
        bot = FAQAssistant()
    except KnowledgeBaseError as e:
        sys.exit(f"Cannot start: {e}")
    qs = sys.argv[1:]
    if qs:
        for i, q in enumerate(qs):
            if i:
                print()
            show(bot.ask(q))
    else:
        print("Campus FAQ Assistant (empty line to quit)")
        while True:
            q = input("\nYour question: ")
            if not q.strip():
                break
            show(bot.ask(q))
