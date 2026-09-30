#!/usr/bin/env python3
"""Fail CI when a selected test suite silently skipped required coverage."""
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
cases = list(root.iter("testcase"))
bad = [case for case in cases if any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))]
if not cases or bad:
    raise SystemExit(f"Selected suite incomplete: {len(cases)} tests, {len(bad)} failed/errored/skipped")
print(f"Selected suite complete: {len(cases)} passed, no skips")
