"""Check every commit a push added against CONTRIBUTING.md.

    python -m tools.release.commits --before <sha>

The convention was documented and checked by a tool that rejected all 87
commits in the repository, so it was enforced by nobody. The tool now agrees
with the history, and this is what keeps them agreeing over a push. A scheduled
or manual run adds no commits, so `--before` is empty or all zeros and this
says there is nothing to check rather than passing silently.

A base commit that is not in the clone means the push replaced the history it
was based on, so every commit HEAD carries is new to the remote and the range
cannot be walked. Failing then would leave a rewrite no way through but a second
push, and walking the whole history under the grammar would fail on the 41
commits that predate it, which the convention deliberately does not apply
backwards. The credit rule has no such history -- it was applied backwards on
21 October 2026 -- so that is the rule a rewritten history is held to.

Exit codes: 0 every commit passes (or there was none to check), 1 one does not,
or the range held no commit at all.
"""

from __future__ import annotations

import argparse
import subprocess

from tools.check_commit_message import check
from tools.release import error

NO_BASE = ("", "0" * 40)


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--before", default="", help="github.event.before: the remote's head before the push")
    args = parser.parse_args(argv)
    if args.before in NO_BASE:
        print("This run added no commits, so there is no message to check.")
        return 0
    credits_only = git("rev-parse", "--verify", "--quiet", f"{args.before}^{{commit}}").returncode != 0
    if credits_only:
        print(
            "This push replaced its base, so every commit HEAD carries is new to the remote: "
            "checking all of them against the credit rule, and not against a grammar they predate."
        )
    shas = git("rev-list", "HEAD" if credits_only else f"{args.before}..HEAD").stdout.split()
    if not shas:
        error("commit message", f"{args.before}..HEAD contains no commit, so no message was checked.")
        return 1
    failed = 0
    for sha in shas:
        message = git("log", "-1", "--format=%B", sha).stdout
        authors = [git("log", "-1", f"--format={who}", sha).stdout.strip() for who in ("%an <%ae>", "%cn <%ce>")]
        problems = check(message, authors, credits_only=credits_only)
        if problems:
            failed += 1
            for problem in problems:
                print(f"{sha[:12]}: {problem}")
            error("commit message", git("log", "-1", "--format=%s", sha).stdout.strip())
    if failed:
        print(f"{failed} of the {len(shas)} commit messages this push added do not follow CONTRIBUTING.md.")
        return 1
    print(f"All {len(shas)} commit messages this push added follow CONTRIBUTING.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
