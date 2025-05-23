#!/usr/bin/env python3
"""
Run many potential.py jobs **serially** on the local machine.
Ideal if you have a GPU but few available CPUs. My GPU (RTX 3090 Ti) breaks even with ~10 CPU processors (Intel CoreTM i9-14900K) in speed.

Example
-------
python run_potentials_serial.py ../protein.pdb ../traj.dcd --top ../topol.top -t 5 --skip 50
"""

import argparse, os, sys, subprocess
from time import time
import numpy as np
import MDAnalysis as mda
from pathlib import Path

SCRIPT_DIR   = Path(__file__).resolve().parent
POTENTIAL_PATH = SCRIPT_DIR / "potential.py"      # => /full/path/to/potential.py
# throw error if potential.py is not found in the same directory as this script
if not POTENTIAL_PATH.exists():
    sys.exit(f"ERROR: cannot find potential.py in {SCRIPT_DIR}. "
             "Please put potential.py and run_potentials_serial.py are in the same directory.")


def run_cmd(cmd):
    """Run a shellless subprocess and return (returncode, cmd, stderr string)."""
    ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if ret.returncode != 0:
        return False, cmd, ret.stderr.decode()
    return True, cmd, ""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Launch one potential.py job per residue (or custom group) "
                    "serially on local CPU/GPU."
    )
    parser.add_argument("protein",  help="input PDB (unprocessed)")
    parser.add_argument("trajectory", help="trajectory file (e.g. traj.dcd)")
    parser.add_argument("--top", default="topol.top",
                        help="Gromacs topology file (default topol.top)")
    parser.add_argument("--multiChain", action="store_true",
                        help="Protein has multiple chains")
    parser.add_argument("--groupsFile",
                        help="File with MDAnalysis selection strings, one per line")
    parser.add_argument("-t","--time", type=int, default=5,
                        help="Last X ns to analyse in each job (default 5)")
    parser.add_argument("--nogpu", action="store_true", default=False,
                        help="Force CPU platform (pass --nogpu to potential.py)")
    parser.add_argument("--skip", type=int, default=100,
                        help="Frame stride (default 100; reduce for better estimate of mean)")
    parser.add_argument("--cutoff", type=float, default=4.25,
                        help="Cutoff distance in Angstrom (default 4.25)")
    parser.add_argument("--outdir", type=str, default="potentials",
                        help="Output directory (default: potentials)")
    
    args = parser.parse_args()
    if args.multiChain and args.groupsFile:
        sys.exit("ERROR: use EITHER --multiChain OR --groupsFile, not both")

    pdb_path  = args.protein if args.protein.endswith(".pdb") else args.protein + ".pdb"
    if not os.path.exists(pdb_path):
        sys.exit(f"ERROR: cannot find {pdb_path}")

    processed_pdb_path  = pdb_path[:-4] + "_processed.pdb"
    if not os.path.exists(processed_pdb_path):
        sys.exit(f"ERROR: cannot find processed PDB {processed_pdb_path}")

    if not os.path.exists(args.trajectory):
        sys.exit(f"ERROR: cannot find trajectory {args.trajectory}")

    protein_name = os.path.splitext(os.path.basename(pdb_path))[0]

    # parse the groups
    u = mda.Universe(pdb_path)

    if args.groupsFile:
        with open(args.groupsFile) as fh:
            groups = [line.strip() for line in fh if line.strip() and not line.startswith("#")]
        work_items = [
            dict(kind="group",
                 cmd=["python", str(POTENTIAL_PATH), processed_pdb_path, args.trajectory,
                      "--groupsFile", args.groupsFile, "--groupNum", str(i+1),
                      "-t", str(args.time),
                      "--skip", str(args.skip),
                      "--cutoff", str(args.cutoff)]
                 + (["--nogpu"] if args.nogpu else []))
            for i in range(len(groups))
        ]

    elif args.multiChain:
        resids = u.residues.resids
        segids = u.residues.segids
        work_items = [
            dict(kind="residue",
                 cmd=["python", str(POTENTIAL_PATH), processed_pdb_path, args.trajectory,
                      "--top", args.top,
                      "-res", str(rid), "-ch", str(sid),
                      "-t", str(args.time),
                      "--skip", str(args.skip),
                      "--cutoff", str(args.cutoff)]
                 + (["--nogpu"] if args.nogpu else []))
            for rid, sid in zip(resids, segids)
        ]

    else:  # single‑chain residue mode
        resids = u.residues.resids
        work_items = [
            dict(kind="residue",
                 cmd=["python", str(POTENTIAL_PATH), processed_pdb_path, args.trajectory,
                      "--top", args.top,
                      "-res", str(rid),
                      "-t", str(args.time),
                      "--skip", str(args.skip),
                      "--cutoff", str(args.cutoff)]
                 + (["--nogpu"] if args.nogpu else []))
            for rid in resids
        ]

    total_jobs = len(work_items)
    print(f"Preparing {total_jobs} jobs measuring potentials (running serially)...\n")

    #  serial execution with progress
    start = time()
    fails = []
    done_so_far = 0

    for w in work_items:
        ok, cmd, err = run_cmd(w["cmd"])
        done_so_far += 1
        if not ok:
            fails.append((cmd, err.strip()))
        print(f"\rCompleted {done_so_far}/{total_jobs}", end="", flush=True)

    elapsed = time() - start
    print("\n")

    #  summarize
    if fails:
        print(f"Finished with {len(fails)} failures out of {total_jobs} jobs.\n")
        for cmd, err in fails:
            print("Command:", " ".join(cmd))
            print("Error  :", err or "(no stderr)")
            print("-"*60)
    else:
        print(f"All {total_jobs} jobs finished successfully in "
              f"{elapsed/60:.1f} min.")
