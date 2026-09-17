"""Compare results/ against a run of the old all_main.py. Temporary: used to sign off the rewrite.

Usage: python -m experiments.parity <dir holding the old run's CSVs and run.log>
See docs/parity.md for how the reference was produced and what differences are expected.
"""

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from experiments.common import ROOT

RESULTS = ROOT / "results"


def compare(name, new: pd.DataFrame, old: pd.DataFrame, rtol=1e-9, atol=1e-9) -> int:
    bad = 0
    for col in old.columns:
        if col not in new.columns:
            print(f"  {name}: missing column {col}")
            bad += 1
            continue
        a, b = new[col].to_numpy(), old[col].to_numpy()
        if a.dtype.kind in "fiub" and b.dtype.kind in "fiub":
            same = np.isclose(a.astype(float), b.astype(float), rtol=rtol, atol=atol, equal_nan=True)
        else:
            same = a.astype(str) == b.astype(str)
        for row in np.flatnonzero(~same):
            print(f"  {name} row {row} {col}: new {a[row]} old {b[row]}")
            bad += 1
    print(f"{name}: {len(old)} rows x {len(old.columns)} columns, {bad} mismatches")
    return bad


def log_table(log: str, heading: str) -> pd.DataFrame:
    """Parse a whitespace table printed under a '=== heading' line in the old run.log."""
    lines = log[log.index(heading):].splitlines()[1:]
    lines = [l for l in lines if l.strip() and not l.startswith(("Does", "Saved"))]
    header = lines[0].split()
    rows = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) != len(header) or not re.match(r"^-?[\d.]+$", parts[0]):
            break
        rows.append([float(p) for p in parts])
    return pd.DataFrame(rows, columns=header)


def main(ref: Path):
    log = (ref / "run.log").read_text()
    bad = compare("ablation", pd.read_csv(RESULTS / "ablation/ablation.csv"),
                  pd.read_csv(ref / "ablation_results.csv"))
    bad += compare("cross_section", pd.read_csv(RESULTS / "cross_section/cross_section.csv"),
                   pd.read_csv(ref / "cross_sectional_results.csv"))
    # The log prints sweeps to 6 decimals, so compare at that precision.
    for table, heading in [("gamma", "=== Gamma sweep"), ("kappa", "=== Kappa sweep"),
                           ("touch_join", "=== Touch-join threshold sweep")]:
        bad += compare(f"sweep {table}", pd.read_csv(RESULTS / f"sweeps/{table}.csv"),
                       log_table(log, heading), rtol=0, atol=5.1e-7)
    print("PARITY OK" if bad == 0 else f"{bad} MISMATCHES")
    return bad


if __name__ == "__main__":
    sys.exit(1 if main(Path(sys.argv[1])) else 0)
