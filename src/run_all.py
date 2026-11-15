"""Re-run the whole pipeline from the public snapshots in data/public:
simulate -> SQL -> notebook (executed) -> PDF report -> dashboard.

    python src/run_all.py

The real GA4 extract (data/raw/ga4) is not committed: without it, sql/01-02 are skipped and the
GA4 aggregates already in data/output are used. Rebuild it with python src/extract_ga4.py.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
py = sys.executable
steps = [
    [py, "src/simulate.py"],
    [py, "src/run_sql.py"],
    [py, "src/build_notebook.py"],
    [py, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute", "--inplace",
     "--ExecutePreprocessor.timeout=1800", "notebooks/analysis.ipynb"],
    [py, "src/build_report.py"],
    [py, "src/build_dashboard.py"],
]
for s in steps:
    print("\n===", " ".join(s[1:]))
    subprocess.run(s, check=True, cwd=ROOT)
print("\nDone: docs/Tameson_PaidAcquisition_CaseStudy.pdf and docs/dashboard.html")
