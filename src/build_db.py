"""Build db/campus_faq.db from schema.sql and the CSV files, then store one baseline run."""
import csv
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from baseline import MIN_OVERLAP, OUT_OF_SCOPE, load_faq, match  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db" / "campus_faq.db"


def main():
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))

    faq, issues = load_faq(ROOT / "data" / "faq.csv")
    for name in sorted({r["category"] for r in faq}):
        con.execute("INSERT INTO category(name) VALUES (?)", (name,))
    cat_id = dict(con.execute("SELECT name, category_id FROM category"))
    for r in faq:
        con.execute("INSERT INTO faq VALUES (?,?,?,?,?,?)",
                    (r["faq_id"], cat_id[r["category"]], r["question"], r["answer"],
                     r["source_url"], r["last_verified"]))

    with open(ROOT / "data" / "synthetic_queries.csv", newline="", encoding="utf-8") as f:
        queries = list(csv.DictReader(f))
    for q in queries:
        exp = None if q["expected_faq_id"] == OUT_OF_SCOPE else q["expected_faq_id"]
        con.execute("INSERT INTO test_query VALUES (?,?,?,?,?)",
                    (q["query_id"], q["query_text"], exp, q["query_type"], q["source"]))

    run_id = con.execute("INSERT INTO test_run(method,min_overlap,run_at,n_queries,n_correct) "
                         "VALUES ('keyword_baseline',?,?,?,0)",
                         (MIN_OVERLAP, datetime.now().isoformat(timespec="seconds"), len(queries))).lastrowid
    n_correct = 0
    for q in queries:
        res = match(q["query_text"], faq)
        correct = int(res["predicted_faq_id"] == q["expected_faq_id"])
        n_correct += correct
        pred = res["predicted_faq_id"] if res["accepted"] else None
        con.execute("INSERT INTO test_result(run_id,query_id,predicted_faq_id,overlap_score,accepted,correct) "
                    "VALUES (?,?,?,?,?,?)",
                    (run_id, q["query_id"], pred, res["overlap_score"], int(res["accepted"]), correct))
    con.execute("UPDATE test_run SET n_correct=? WHERE run_id=?", (n_correct, run_id))
    con.commit()

    print(f"Database created: {DB.relative_to(ROOT)}")
    for t in ["category", "faq", "test_query", "test_run", "test_result"]:
        print(f"  {t:12s} rows: {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}")
    print(f"Baseline run stored: {n_correct}/{len(queries)} correct")
    con.close()


if __name__ == "__main__":
    main()
