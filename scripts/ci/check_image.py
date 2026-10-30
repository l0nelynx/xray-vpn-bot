"""Gate a Trivy JSON report, retaining raw findings as the audit artifact.

CPython's embedded build SBOM can describe old build-environment Python packages
even after their installed distributions were updated. Only superseded SBOM
records with a physically installed, locked, scanner-clean replacement are
excluded. Real package findings and unsuperseded SBOM records always block.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def blocking_findings(report: dict, constraints: str) -> tuple[list[dict], list[dict]]:
    pins = {
        normalize(m[1]): m[2]
        for line in constraints.splitlines()
        if (m := re.match(r"^([\w.-]+)==([^\s;]+)", line))
    }
    blocking, superseded = [], []
    for result in report.get("Results", []):
        packages = result.get("Packages", [])
        analyzers = {p.get("Identifier", {}).get("UID"): p.get("AnalyzedBy") for p in packages}
        findings = result.get("Vulnerabilities", [])
        vulnerable = {(normalize(v["PkgName"]), v["InstalledVersion"]) for v in findings}
        installed = {
            (normalize(p["Name"]), p["Version"])
            for p in packages if p.get("FilePath") and p.get("AnalyzedBy") == "python-pkg"
        }
        for finding in findings:
            name = normalize(finding["PkgName"])
            pin = pins.get(name)
            if (
                result.get("Type") == "python-pkg"
                and analyzers.get(finding.get("PkgIdentifier", {}).get("UID")) == "sbom"
                and pin and pin != finding["InstalledVersion"]
                and (name, pin) in installed and (name, pin) not in vulnerable
            ):
                superseded.append(finding)
            elif finding.get("Severity") in {"HIGH", "CRITICAL"}:
                blocking.append(finding)
    return blocking, superseded


def main() -> int:
    report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    if report.get("SchemaVersion") != 2 or not report.get("Results"):
        raise ValueError("Missing package scan results; refusing to promote an unverified image")
    blocking, superseded = blocking_findings(
        report, Path("infra/docker/constraints.txt").read_text(encoding="utf-8"),
    )
    for finding in superseded:
        print(f"Superseded build SBOM: {finding['PkgName']} {finding['InstalledVersion']} "
              f"{finding['VulnerabilityID']} (locked installed replacement is clean)")
    for finding in blocking:
        print(f"BLOCK {finding['Severity']}: {finding['PkgName']} {finding['InstalledVersion']} "
              f"{finding['VulnerabilityID']} fixed={finding.get('FixedVersion', 'unavailable')}")
    print(f"Image gate: {len(blocking)} blocking, {len(superseded)} superseded build-SBOM findings")
    return int(bool(blocking))


if __name__ == "__main__":
    raise SystemExit(main())
