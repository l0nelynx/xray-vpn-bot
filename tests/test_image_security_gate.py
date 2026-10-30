"""A newer installed distribution cannot hide a vulnerable vendored copy."""
from copy import deepcopy

from scripts.ci.check_image import blocking_findings


def report():
    return {"Results": [{
        "Type": "python-pkg",
        "Packages": [
            {"Name": "urllib3", "Version": "2.7.0", "AnalyzedBy": "sbom", "Identifier": {"UID": "vendor"}},
            {"Name": "urllib3", "Version": "2.8.0", "AnalyzedBy": "python-pkg",
             "FilePath": "site-packages/urllib3.dist-info/METADATA", "Identifier": {"UID": "installed"}},
        ],
        "Vulnerabilities": [{"PkgName": "urllib3", "InstalledVersion": "2.7.0",
                             "Severity": "HIGH", "PkgIdentifier": {"UID": "vendor"}}],
    }]}


def test_gate_blocks_vendored_copy_even_with_clean_installed_replacement():
    assert len(blocking_findings(report())) == 1


def test_gate_blocks_both_vendored_and_installed_findings():
    data = report()
    finding = deepcopy(data["Results"][0]["Vulnerabilities"][0])
    finding.update(InstalledVersion="2.8.0", PkgIdentifier={"UID": "installed"})
    data["Results"][0]["Vulnerabilities"].append(finding)
    assert len(blocking_findings(data)) == 2


def test_gate_accepts_a_clean_scan():
    data = report()
    data["Results"][0]["Vulnerabilities"] = []
    assert not blocking_findings(data)


def test_gate_leaves_lower_severity_findings_outside_the_blocking_policy():
    data = report()
    data["Results"][0]["Vulnerabilities"][0]["Severity"] = "LOW"
    assert not blocking_findings(data)
