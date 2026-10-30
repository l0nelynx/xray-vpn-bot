"""Gate every HIGH/CRITICAL Trivy finding, including vendored/SBOM components.

Installing a newer distribution does not replace a tool's vendored copy, so
those findings must never be suppressed merely because a clean version exists
elsewhere in the image. Keep the unfiltered report as the CI artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def blocking_findings(report: dict) -> list[dict]:
    return [
        finding
        for result in report.get("Results", [])
        for finding in result.get("Vulnerabilities", [])
        if finding.get("Severity") in {"HIGH", "CRITICAL"}
    ]


def main() -> int:
    report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    if report.get("SchemaVersion") != 2 or not report.get("Results"):
        raise ValueError("Missing package scan results; refusing to promote an unverified image")
    blocking = blocking_findings(report)
    for finding in blocking:
        print(f"BLOCK {finding['Severity']}: {finding['PkgName']} {finding['InstalledVersion']} "
              f"{finding['VulnerabilityID']} fixed={finding.get('FixedVersion', 'unavailable')}")
    print(f"Image gate: {len(blocking)} blocking findings")
    return int(bool(blocking))


if __name__ == "__main__":
    raise SystemExit(main())
