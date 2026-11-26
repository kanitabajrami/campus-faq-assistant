"""Week 3 tests: normal, invalid, exceptional and error-handling cases.
Expected results are fixed BEFORE running (what a correct assistant should do).
Writes logs/Week3_Test_Log.csv and logs/Week3_Comparison.csv."""
import csv
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from assistant import FAQAssistant, KnowledgeBaseError  # noqa: E402
from baseline import OUT_OF_SCOPE  # noqa: E402

TMP = Path(tempfile.mkdtemp())
bot = FAQAssistant(log_path=TMP / "test_query_log.csv")
LOG = []


def record(tid, cat, desc, inp, expected, actual, notes=""):
    LOG.append({"test_id": tid, "category": cat, "description": desc, "input": inp, "expected": expected,
                "actual": actual, "status": "PASS" if expected == actual else "FAIL", "notes": notes,
                "date": date.today().isoformat()})


def outcome(r):
    """One comparable label for a response."""
    if r["status"] == "ok":
        return r["tfidf"]["predicted_faq_id"]
    if r["status"] == "no_match":
        return "NO_MATCH (fallback)"
    return f"{r['status'].upper()}:{r.get('error_code', '')}".rstrip(":")


def show(s):
    """Printable form of a test input (control characters are shown as escapes)."""
    if not isinstance(s, str):
        return repr(s)
    if len(s) >= 70:
        return s[:30] + " ... [%d chars]" % len(s)
    return s.encode("unicode_escape").decode("ascii") if any(ord(c) < 32 for c in s) else s


# ---------- A. Normal cases ----------
NORMAL = [
    ("N01", "Where can I see the exam timetable?", "FAQ002"),
    ("N02", "How do I sign up for courses?", "FAQ003"),
    ("N03", "Where do I find scholarship details?", "FAQ004"),
    ("N04", "How can I get my transcript?", "FAQ005"),
    ("N05", "How many credits do I need to graduate?", "FAQ007"),
    ("N06", "How can I pay an invoice online?", "FAQ009"),
    ("N07", "My MySEEU account is locked.", "FAQ010"),
    ("N08", "What payment options exist for tuition?", "FAQ008"),
    ("N09", "How can I contact Student Services?", "FAQ006"),
    ("N10", "Where can I find the academic calendar?", "FAQ001"),
    ("N11", "What is the best pizza in town?", "NO_MATCH (fallback)"),
]
for tid, q, exp in NORMAL:
    record(tid, "Normal case", "In-scope question answered correctly" if exp.startswith("FAQ") else "Out-of-scope question gets the fallback",
           q, exp, outcome(bot.ask(q)))

# complete workflow: input -> validation -> retrieval -> answer with source -> log row
logfile = TMP / "workflow_log.csv"
wb = FAQAssistant(log_path=logfile)
r = wb.ask("How do I sign up for courses?")
rows = list(csv.DictReader(open(logfile, encoding="utf-8")))
complete = (r["status"] == "ok" and bool(r["tfidf"]["entry"]["source_url"]) and bool(r["message"]) and len(rows) == 1
            and rows[0]["tfidf_id"] == "FAQ003")
record("N12", "Normal case", "Full workflow: answer + source URL + one log row written", "How do I sign up for courses?",
       "answer, source and log row present", "answer, source and log row present" if complete else "something missing")

# ---------- B. Invalid input ----------
INVALID = [
    ("I01", "Empty text", "", "INVALID:EMPTY"),
    ("I02", "Only spaces and a tab", "   \t  ", "INVALID:EMPTY"),
    ("I03", "None instead of text", None, "INVALID:NOT_TEXT"),
    ("I04", "A number instead of text", 12345, "INVALID:NOT_TEXT"),
    ("I05", "Only punctuation", "?!?! ... ,,,", "INVALID:NO_LETTERS"),
    ("I06", "Only digits", "12345 67890", "INVALID:NO_LETTERS"),
    ("I07", "301 characters (over the limit)", "a" * 301, "INVALID:TOO_LONG"),
    ("I08", "Control characters are removed", "How do I register\x00\x07 for\ncourses?\x1b", "FAQ003"),
    ("I09", "HTML/script text treated as plain text", "<script>alert(1)</script> exam schedule", "FAQ002"),
]
for tid, desc, q, exp in INVALID:
    record(tid, "Invalid input", desc, show(q), exp, outcome(bot.ask(q)))
record("I10", "Invalid input", "Exactly 300 characters is accepted (boundary)", "x * 300", "NO_MATCH (fallback)", outcome(bot.ask("x" * 300)))

# ---------- C. Exceptional cases ----------
EXC = [
    ("E01", "Albanian question (assistant is English only)", "Ku mund ta gjej orarin e provimeve?", "NO_MATCH (fallback)"),
    ("E02", "Only stop-words", "How do I do this?", "NO_MATCH (fallback)"),
    ("E03", "Typo in one word", "Where can I see the exm schedule?", "FAQ002"),
    ("E04", "Upper case and punctuation", "WHERE IS THE EXAM SCHEDULE???", "FAQ002"),
    ("E05", "Near miss: shares one word (pay) with FAQ009", "How do I pay for parking?", "NO_MATCH (fallback)"),
    ("E06", "Near miss: shares 'scholarship' with FAQ004", "How can I get a scholarship for studying abroad?", "NO_MATCH (fallback)"),
    ("E07", "Paraphrase with no shared words", "I need an official document showing my grades.", "FAQ005"),
]
for tid, desc, q, exp in EXC:
    record(tid, "Exceptional case", desc, q, exp, outcome(bot.ask(q)))
a, b = bot.ask("How do I sign up for courses?"), bot.ask("How do I sign up for courses?")
record("E08", "Exceptional case", "Same question twice gives the same result", "How do I sign up for courses? (x2)",
       "same FAQ and score", "same FAQ and score" if outcome(a) == outcome(b) and a["tfidf"]["score"] == b["tfidf"]["score"] else "different")
record("E09", "Exceptional case", "Very long noisy question (290 chars) does not crash", "exam schedule please " * 14,
       "FAQ002", outcome(bot.ask("exam schedule please " * 14)))

# ---------- D. Error handling ----------
def raises(fn):
    try:
        fn()
        return "no error"
    except KnowledgeBaseError as e:
        return "KnowledgeBaseError: " + str(e).split(":")[0].rstrip(".")[:60]
    except ValueError as e:
        return "ValueError: " + str(e)[:60]

bad = TMP / "no_answer_col.csv"; bad.write_text("faq_id,question\nFAQ1,How are you?\n", encoding="utf-8")
empty = TMP / "header_only.csv"; empty.write_text("faq_id,question,answer\n", encoding="utf-8")
record("H01", "Error handling", "FAQ file does not exist", "faq_missing.csv", "KnowledgeBaseError: FAQ file not found",
       raises(lambda: FAQAssistant(faq_path=TMP / "faq_missing.csv", log_path=None)))
record("H02", "Error handling", "FAQ file without the answer column", "no_answer_col.csv", "KnowledgeBaseError: FAQ file is missing required columns",
       raises(lambda: FAQAssistant(faq_path=bad, log_path=None)))
record("H03", "Error handling", "FAQ file with a header but no rows", "header_only.csv", "KnowledgeBaseError: FAQ file has no valid FAQ entries",
       raises(lambda: FAQAssistant(faq_path=empty, log_path=None)))
record("H04", "Error handling", "Threshold outside 0 to 1", "threshold=1.5", "ValueError: threshold must be a number between 0 and 1",
       raises(lambda: FAQAssistant(threshold=1.5, log_path=None)))
nolog = FAQAssistant(log_path="/proc/no_such_dir/query_log.csv").ask("How do I sign up for courses?")
record("H05", "Error handling", "Log file cannot be written: answer still returned, warning shown", "unwritable log path",
       "FAQ003 + log warning", "FAQ003 + log warning" if outcome(nolog) == "FAQ003" and nolog["log_warning"] else "answer lost or no warning")
dirty = FAQAssistant(faq_path=ROOT / "data" / "synthetic_faq_dirty.csv", log_path=None)
record("H06", "Error handling", "Dirty FAQ (duplicates, missing values): 2 clean rows kept and usable",
       "synthetic_faq_dirty.csv", "2 entries; FAQ S002", f"{len(dirty.faq)} entries; FAQ {outcome(dirty.ask('Where is the sample cafeteria?'))}")

NOTES = {
    "E05": "Known limitation: a single shared word (pay) is enough to pass the 0.20 threshold. Threshold tuning planned for Week 4.",
    "E06": "Known limitation: matches on 'scholarship' although the FAQ does not cover studying abroad.",
    "E07": "Known limitation: no shared words, so TF-IDF scores 0. Needs stemming, synonyms or embeddings (Week 5 experiments).",
    "E01": "System is English only (out of scope).",
    "H05": "Logging failure must never block the answer.",
}
for c in LOG:
    c["notes"] = NOTES.get(c["test_id"], c["notes"])

# ---------- write test log ----------
cols = ["test_id", "category", "description", "input", "expected", "actual", "status", "notes", "date"]
with open(ROOT / "logs" / "Week3_Test_Log.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(LOG)

# ---------- TF-IDF vs baseline on the 33 synthetic queries (Week 2 set) ----------
cmp_rows, t_ok, b_ok = [], 0, 0
cmp_bot = FAQAssistant(log_path=None)
for q in csv.DictReader(open(ROOT / "data" / "synthetic_queries.csv", encoding="utf-8")):
    r = cmp_bot.ask(q["query_text"])
    exp = q["expected_faq_id"]
    tp = r["tfidf"]["predicted_faq_id"]; bp = r["baseline"]["predicted_faq_id"]
    t_ok += tp == exp; b_ok += bp == exp
    cmp_rows.append({"query_id": q["query_id"], "query_type": q["query_type"], "query": q["query_text"], "expected": exp,
                     "tfidf_pred": tp, "tfidf_score": r["tfidf"]["score"], "tfidf_correct": int(tp == exp),
                     "baseline_pred": bp, "baseline_overlap": r["baseline"]["overlap"], "baseline_correct": int(bp == exp)})
with open(ROOT / "logs" / "Week3_Comparison.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(cmp_rows[0])); w.writeheader(); w.writerows(cmp_rows)

by = {}
for c in LOG: by.setdefault(c["category"], []).append(c["status"] == "PASS")
print("Test log:", sum(c["status"] == "PASS" for c in LOG), "/", len(LOG), "passed")
for k, v in by.items(): print(f"  {k:17s} {sum(v)}/{len(v)}")
for c in LOG:
    if c["status"] == "FAIL": print("  FAIL", c["test_id"], c["description"], "| expected:", c["expected"], "| actual:", c["actual"])
print(f"Comparison on {len(cmp_rows)} synthetic queries: TF-IDF {t_ok}/{len(cmp_rows)} ({100*t_ok/len(cmp_rows):.1f}%), baseline {b_ok}/{len(cmp_rows)} ({100*b_ok/len(cmp_rows):.1f}%)")
for ty in sorted({c['query_type'] for c in cmp_rows}):
    sub = [c for c in cmp_rows if c['query_type'] == ty]
    print(f"  {ty:24s} TF-IDF {sum(c['tfidf_correct'] for c in sub)}/{len(sub)}  baseline {sum(c['baseline_correct'] for c in sub)}/{len(sub)}")
