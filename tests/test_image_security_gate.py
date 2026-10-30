"""A stale embedded SBOM must never hide an installed-package vulnerability."""
from copy import deepcopy

from scripts.ci.check_image import blocking_findings


def report():
    return {"Results": [{
        "Type": "python-pkg",
        "Packages": [
            {"Name": "certifi", "Version": "2026.7.22", "AnalyzedBy": "sbom", "Identifier": {"UID": "old"}},
            {"Name": "certifi", "Version": "2026.10.23", "AnalyzedBy": "python-pkg",
             "FilePath": "site-packages/certifi.dist-info/METADATA", "Identifier": {"UID": "new"}},
        ],
        "Vulnerabilities": [{"PkgName": "certifi", "InstalledVersion": "2026.7.22",
                             "Severity": "CRITICAL", "PkgIdentifier": {"UID": "old"}}],
    }]}


def test_gate_recognizes_only_clean_locked_installed_replacement():
    blocking, superseded = blocking_findings(report(), "certifi==2026.10.23\n")
    assert not blocking and len(superseded) == 1


def test_gate_blocks_vulnerable_installed_package_even_with_newer_version():
    data = report()
    finding = deepcopy(data["Results"][0]["Vulnerabilities"][0])
    finding.update(InstalledVersion="2026.10.23", PkgIdentifier={"UID": "new"})
    data["Results"][0]["Vulnerabilities"].append(finding)
    blocking, superseded = blocking_findings(data, "certifi==2026.10.23\n")
    assert len(blocking) == 2 and not superseded


def test_gate_blocks_uninstalled_or_unlocked_replacement():
    assert blocking_findings(report(), "certifi==2026.7.22\n")[0]
    data = report()
    data["Results"][0]["Packages"].pop()
    assert blocking_findings(data, "certifi==2026.10.23\n")[0]
