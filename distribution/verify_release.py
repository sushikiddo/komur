"""Verify Windows Tk cases in fresh processes, as the real application starts."""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    gui_files = []
    for path in sorted((root / "tests").glob("test_*.py")):
        source = path.read_text(encoding="utf-8-sig")
        if "tk.Tk(" in source or "app_factory" in source or "cat.DesktopCat(" in source:
            gui_files.append(path.relative_to(root).as_posix())
    collected = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", "--collect-only", "-q", *gui_files],
                               cwd=root, capture_output=True, text=True, encoding="utf-8")
    if collected.returncode:
        raise RuntimeError(collected.stdout + collected.stderr)
    cases = [line.strip() for line in collected.stdout.splitlines() if line.startswith("tests/") and "::" in line]
    if not cases:
        raise RuntimeError("No GUI cases collected")
    report = {"ok": False, "passed": 0, "skipped": 0, "gui_cases": len(cases), "runs": []}
    with tempfile.TemporaryDirectory(prefix=".release-proof-", dir=root) as folder:
        test_root = Path(folder).resolve()
        if not test_root.is_relative_to(root):
            raise RuntimeError("Test workspace escaped project")
        groups = [["tests", *("--ignore=" + item for item in gui_files)]] + [[case] for case in cases]
        for index, selection in enumerate(groups):
            command = [sys.executable, "-X", "utf8", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                       "--basetemp=" + str(test_root / str(index)), *selection]
            result = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8")
            output = result.stdout + result.stderr
            report["runs"].append({"selection": selection, "exit_code": result.returncode, "output": output})
            for label in ("passed", "skipped"):
                matches = re.findall(r"(?<!subtests )\b(\d+) " + label + r"\b", output)
                if matches:
                    report[label] += int(matches[-1])
            if result.returncode:
                Path(root / "release-verification-v4.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                print(output, flush=True)
                raise SystemExit(result.returncode)
            print(f"Verified group {index + 1}/{len(groups)}", flush=True)
    report["ok"] = True
    Path(root / "release-verification-v4.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "runs"}), flush=True)


if __name__ == "__main__":
    main()
