"""Run all Week 2 tests and write logs/Week2_Test_Log.csv (expected vs actual).
Part 1: hand-written test cases (expected values worked out by hand BEFORE running).
Part 2: evaluation of the baseline on the synthetic query set."""
import csv
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from baseline import OUT_OF_SCOPE, dedupe_queries, load_faq, match  # noqa: E402

faq, _ = load_faq(ROOT / "data" / "faq.csv")
LOG = []


def fmt(res):
    return f"{res['predicted_faq_id']} (overlap {res['overlap_score']})"


def record(test_id, category, description, test_input, expected, actual, notes=""):
    LOG.append({"test_id": test_id, "category": category, "description": description,
                "input": test_input, "expected": expected, "actual": actual,
                "status": "PASS" if expected == actual else "FAIL", "notes": notes,
                "date": date.today().isoformat()})


# ---------------- Part 1: matching test cases ----------------
CASES = [
 # id, category, description, input, expected
 ("N01", "Normal", "Paraphrase with one shared word", "Where can I check the exam timetable?", "FAQ002 (overlap 1)"),
 ("N02", "Normal", "Paraphrase 'sign up' for 'register'", "How do I sign up for courses?", "FAQ003 (overlap 1)"),
 ("N03", "Normal", "Exact copy of FAQ008 question (5 shared words)", "What payment options are available for tuition fees?", "FAQ008 (overlap 5)"),
 ("N04", "Normal", "Several shared words (many, credits, graduate)", "How many credits do I need to graduate?", "FAQ007 (overlap 3)"),
 ("N05", "Normal", "Tie FAQ008 vs FAQ009: smallest id wins", "How much does tuition cost per semester and how can I pay?", "FAQ008 (overlap 1)"),
 ("M01", "Missing/zero data", "Empty question", "", "OUT_OF_SCOPE (overlap 0)"),
 ("M02", "Missing/zero data", "Only spaces", "     ", "OUT_OF_SCOPE (overlap 0)"),
 ("M03", "Missing/zero data", "None instead of text", None, "OUT_OF_SCOPE (overlap 0)"),
 ("M04", "Missing/zero data", "Zero overlap (unrelated question)", "What is the best pizza in town?", "OUT_OF_SCOPE (overlap 0)"),
 ("M05", "Missing/zero data", "Only stop-words, no content word", "How do I do this?", "OUT_OF_SCOPE (overlap 0)"),
 ("M08", "Missing/zero data", "Only template words (find, information, students)", "Where can students find information?", "OUT_OF_SCOPE (overlap 0)"),
 ("D03", "Duplicate data", "Repeated words are counted once", "exam exam exam schedule schedule", "FAQ002 (overlap 2)"),
 ("E01", "Edge case", "Upper case and punctuation", "WHERE CAN I SEE THE EXAM SCHEDULE???", "FAQ002 (overlap 2)"),
 ("E02", "Edge case", "Punctuation only", "?!?! ... ,,,", "OUT_OF_SCOPE (overlap 0)"),
 ("E03", "Edge case", "Typo in one word, other word still matches", "Where is the exm schedule?", "FAQ002 (overlap 1)"),
 ("E04", "Edge case", "Typo in the only content word", "How do I get my transcrpit?", "OUT_OF_SCOPE (overlap 0)"),
 ("E05", "Edge case", "Albanian question (system is English only)", "Ku mund ta gjej orarin e provimeve?", "OUT_OF_SCOPE (overlap 0)"),
 ("E06", "Edge case", "Plural 'exams' does not match 'exam' (no stemming)", "When are the exams held?", "OUT_OF_SCOPE (overlap 0)"),
 ("E07", "Edge case", "Very long input (400 words)", "exam schedule " * 200, "FAQ002 (overlap 2)"),
]
for tid, cat, desc, q, expected in CASES:
    shown = "(None)" if q is None else (q if len(q) < 80 else q[:40].strip() + " ... [400 words]")
    record(tid, cat, desc, shown, expected, fmt(match(q, faq)))

# ---------------- Part 1b: data-quality test cases ----------------
dirty, issues = load_faq(ROOT / "data" / "synthetic_faq_dirty.csv")
reasons = sorted(r for _, r in issues)
record("M06", "Missing/zero data", "FAQ row with empty answer is dropped", "synthetic_faq_dirty.csv, row S004",
       "S004 dropped", "S004 dropped" if ("S004", "missing question/answer/id") in issues else "S004 kept")
record("M07", "Missing/zero data", "FAQ row with empty question is dropped", "synthetic_faq_dirty.csv, row S005",
       "S005 dropped", "S005 dropped" if ("S005", "missing question/answer/id") in issues else "S005 kept")
record("D01", "Duplicate data", "Second row with same faq_id is dropped", "synthetic_faq_dirty.csv, 2nd S001",
       "duplicate faq_id removed", "duplicate faq_id removed" if ("S001", "duplicate faq_id") in issues else "not detected")
record("D02", "Duplicate data", "Same question with other case/spacing is dropped", "synthetic_faq_dirty.csv, S003",
       "duplicate question removed", "duplicate question removed" if ("S003", "duplicate question") in issues else "not detected")
record("D05", "Duplicate data", "Clean rows kept after cleaning the dirty file", "synthetic_faq_dirty.csv (6 rows)",
       "2 rows kept (S001, S002)", f"{len(dirty)} rows kept ({', '.join(r['faq_id'] for r in dirty)})")
dq = dedupe_queries(["Where can I see the exam schedule?", "  where can i see the EXAM schedule?  ", "How do I sign up for courses?"])
record("D04", "Duplicate data", "Repeated query (case/spacing) evaluated once", "3 queries, 1 repeated", "2 unique queries", f"{len(dq)} unique queries")

# ---------------- Part 2: evaluation on synthetic queries ----------------
with open(ROOT / "data" / "synthetic_queries.csv", newline="", encoding="utf-8") as f:
    queries = list(csv.DictReader(f))
assert len({q["query_text"].lower() for q in queries}) == len(queries), "duplicate query in dataset"
for q in queries:
    res = match(q["query_text"], faq)
    exp, act = q["expected_faq_id"], res["predicted_faq_id"]
    if exp == act:
        note = "correct"
    elif exp == OUT_OF_SCOPE:
        note = "false acceptance (out-of-scope question matched an FAQ)"
    elif act == OUT_OF_SCOPE:
        note = "false rejection (in-scope question rejected)"
    else:
        note = "wrong FAQ returned"
    record("V" + q["query_id"][1:], "Evaluation (" + q["query_type"] + ")", f"Synthetic query {q['query_id']}",
           q["query_text"], exp, f"{act} (overlap {res['overlap_score']})", note)
    LOG[-1]["status"] = "PASS" if exp == act else "FAIL"   # evaluation rows compare the FAQ id only

LOG.sort(key=lambda r: ("NMDEV".index(r["test_id"][0]), r["test_id"]))

cols = ["test_id", "category", "description", "input", "expected", "actual", "status", "notes", "date"]
out = ROOT / "logs" / "Week2_Test_Log.csv"
with open(out, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(LOG)

unit = [r for r in LOG if not r["test_id"].startswith("V")]
ev = [r for r in LOG if r["test_id"].startswith("V")]
print(f"Test cases      : {sum(r['status']=='PASS' for r in unit)}/{len(unit)} passed")
for r in unit:
    if r["status"] == "FAIL":
        print("  FAIL", r["test_id"], r["description"], "| expected:", r["expected"], "| actual:", r["actual"])
print(f"Synthetic eval  : {sum(r['status']=='PASS' for r in ev)}/{len(ev)} correct "
      f"({100*sum(r['status']=='PASS' for r in ev)/len(ev):.1f}%)")
for r in ev:
    if r["status"] == "FAIL":
        print("  FAIL", r["test_id"], r["input"], "->", r["actual"], "|", r["notes"])
print("Log written:", out.relative_to(ROOT))
