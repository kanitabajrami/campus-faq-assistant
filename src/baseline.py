"""Non-AI baseline for the Campus FAQ Assistant: keyword-overlap matching.

Rules (all checkable by hand):
 1. Lowercase the text and split it into tokens: letters and digits only.
 2. Remove stop-words (list below) and keep each remaining word once (a set).
 3. Score of an FAQ = number of tokens its QUESTION shares with the user question.
 4. Best FAQ = highest score; ties go to the smallest faq_id.
 5. Accept only if best score >= MIN_OVERLAP (1). Otherwise reject (OUT_OF_SCOPE).
No stemming, no weighting, no similarity score: that is what the AI step adds later.
"""
import csv
import re
import sys
from pathlib import Path

MIN_OVERLAP = 1
OUT_OF_SCOPE = "OUT_OF_SCOPE"

# General English stop-words + words that occur in most FAQ question templates
# (student, students, find, information, about).
STOPWORDS = frozenset("""
a about an and any are as at be by can do does find for from get has have how i if in
information is it me my need of on or should student students the their there this to
was we what when where which who will with you your
""".split())


def normalize(text):
    """Lowercase and collapse whitespace; non-strings become ''."""
    if not isinstance(text, str):
        return ""
    return " ".join(text.lower().split())


def tokenize(text):
    """Set of content words of a text (rules 1 and 2)."""
    return {t for t in re.findall(r"[a-z0-9]+", normalize(text)) if t not in STOPWORDS}


def load_faq(path):
    """Load an FAQ CSV. Returns (clean_rows, issues).
    Dropped rows: missing id/question/answer, duplicate faq_id, duplicate question."""
    rows, issues = [], []
    seen_ids, seen_questions = set(), set()
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            fid = (r.get("faq_id") or "").strip()
            q = (r.get("question") or "").strip()
            a = (r.get("answer") or "").strip()
            if not fid or not q or not a:
                issues.append((fid or "(no id)", "missing question/answer/id"))
            elif fid in seen_ids:
                issues.append((fid, "duplicate faq_id"))
            elif normalize(q) in seen_questions:
                issues.append((fid, "duplicate question"))
            else:
                seen_ids.add(fid)
                seen_questions.add(normalize(q))
                r = dict(r, faq_id=fid, question=q, answer=a)
                r["tokens"] = tokenize(q)
                rows.append(r)
    return rows, issues


def dedupe_queries(queries):
    """Drop repeated queries (ignoring case and spacing); keep the first."""
    seen, out = set(), []
    for q in queries:
        key = normalize(q)
        if key not in seen:
            seen.add(key)
            out.append(q)
    return out


def match(query, faq_rows, min_overlap=MIN_OVERLAP):
    """Return the baseline decision for one user question."""
    q_tokens = tokenize(query)
    scores = {r["faq_id"]: len(q_tokens & r["tokens"]) for r in faq_rows}
    best_id, best = None, 0
    for fid in sorted(scores):                      # sorted -> ties go to smallest id
        if scores[fid] > best:
            best_id, best = fid, scores[fid]
    accepted = best >= min_overlap and best > 0
    tied = sorted(f for f, s in scores.items() if s == best) if accepted else []
    return {
        "query_tokens": sorted(q_tokens),
        "scores": scores,
        "overlap_score": best,
        "accepted": accepted,
        "predicted_faq_id": best_id if accepted else OUT_OF_SCOPE,
        "tied_ids": tied,
    }


def ask(question, faq_rows):
    """Print a readable baseline answer (used for the demo and screenshot)."""
    res = match(question, faq_rows)
    print(f"Question       : {question!r}")
    print(f"Query tokens   : {res['query_tokens']}")
    nonzero = {k: v for k, v in res["scores"].items() if v}
    print(f"Non-zero scores: {nonzero if nonzero else 'none'}")
    if res["accepted"]:
        row = next(r for r in faq_rows if r["faq_id"] == res["predicted_faq_id"])
        tie = f"  (tie between {res['tied_ids']}, smallest id wins)" if len(res["tied_ids"]) > 1 else ""
        print(f"Decision       : ACCEPT {row['faq_id']} with overlap {res['overlap_score']}{tie}")
        print(f"Matched FAQ    : {row['question']}")
        print(f"Answer         : {row['answer']}")
    else:
        print("Decision       : REJECT (OUT_OF_SCOPE) - no FAQ shares a content word")
        print("Please check the official SEEU website or contact the relevant office.")
    return res


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    faq, problems = load_faq(root / "data" / "faq.csv")
    if problems:
        print("Data issues:", problems)
    questions = sys.argv[1:] or ["How do I sign up for courses?"]
    for i, qn in enumerate(questions):
        if i:
            print()
        ask(qn, faq)
