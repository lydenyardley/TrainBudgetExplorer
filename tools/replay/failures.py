"""Run the suite and print one trimmed line per failure.

The default unittest output quotes the whole rendered page inside the
AssertionError, which is a megabyte of noise when twenty tests fail on string
assertions. This prints the test name, the file and line of the assertion, and
the first 160 characters of the message.
"""

import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

result = subprocess.run(
    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
)
text = result.stderr
blocks = re.split(r"={70}\n", text)
for block in blocks:
    head = block.strip().splitlines()
    if not head or not head[0].startswith(("FAIL:", "ERROR:")):
        continue
    line = next((l for l in head if l.strip().startswith("File ")), "")
    message = next((l for l in head if l.startswith(("AssertionError", "Error"))), "")
    short = re.sub(r"'(?:<!doctype.*?)'", "'<page>'", message, flags=re.S)[:200]
    print(head[0])
    print("   ", line.strip().replace("C:\\Users\\Home\\GitHubProjects\\TrainBudgetExplorer\\", ""))
    print("   ", short)
print(text.strip().splitlines()[-1])
