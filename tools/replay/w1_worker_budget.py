"""W1: how many build workers this machine can hold, measured rather than counted.

A pool worker is given the shared fare metadata and the whole national
timetable, and then spends the rest of its life assembling pages. Core count
says how much work a machine can do; it says nothing about how much of that work
can be held in memory at once, and the two are not the same question.

Measured on this machine against the real feed with the national timetable,
2 October 2026, 15.8 GB of RAM and twelve cores:

  the parent, parsing both feeds, pricing 3,424 origins and writing an index
  for each, peaks at 4,110 MB before the pool starts;
  one worker's cost at the end of that initialiser is 325 MB;
  a four-worker tree, sampled while it wrote pages, holds 2.9 GB in total with
  1.2 GB in its largest process, the parent having dropped to 120 MB by then.

Eight workers -- what ``min(8, cpu_count())`` asks for here -- died with a
MemoryError inside the pool initialiser after five minutes and wrote no pages,
reproducibly. Four completed. The eight-worker figure does not follow from the
numbers above: 4.1 GB plus eight workers' steady state is less than the memory
the machine had free, so something transient during eight simultaneous parses of
the same national zip is what ran out, and it is not a figure this file can
claim to have measured. The ceiling is therefore taken from the largest count
observed to finish rather than from arithmetic that has been shown to be wrong.

Written to tools/measure_build_memory.py, which re-derives all of it.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD_TAIL = '''def build_page_job(job: dict) -> tuple[str, str, str]:'''
NEW_TAIL = '''MB = 1_000_000

#: What the parent holds while it prepares the build, measured above. It is
#: counted because the pool starts before the parent has let go, so a cap that
#: ignored it would ignore the moment the machine is most committed.
PARENT_BYTES = 4_400 * MB

#: What one worker costs for as long as it is assembling pages. The initialiser
#: measures 325 MB and the largest worker sampled mid-build held 852 MB, so
#: this is the upper of the two rather than the reassuring one.
WORKER_BYTES = 900 * MB

#: What the machine needs for everything that is not the build: the browser a
#: reader is previewing in, the editor, the OS. A build that starves those
#: fails in a way that reads as the build's fault. Set at 2 GB rather than a
#: rounder 3 so that the one parallel build with a measured outcome -- four
#: workers with 8 GB free, observed twice -- clears the floor below instead of
#: being turned away by it.
RESERVED_BYTES = 2_000 * MB

#: The largest count measured to finish a whole-network build on a 15.8 GB
#: machine. Above this the arithmetic says there is room and the measurement
#: says there is not, and the measurement is what this file trusts.
MAX_WORKERS = 4

#: Below this much free memory the build drops to a single worker. It is the
#: parent plus one worker plus what the machine needs for itself, which is the
#: smallest parallel build that can finish at all.
ONE_WORKER_FLOOR = PARENT_BYTES + WORKER_BYTES + RESERVED_BYTES


def free_memory_bytes() -> int | None:
    """How much memory this machine can hand a build right now, in bytes.

    None when the platform will not say, which is a different thing from zero:
    a caller that cannot read the figure falls back on the measured ceiling,
    and a caller that reads zero falls to one worker.
    """
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", wintypes.DWORD),
                    ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatusEx()
            status.dwLength = ctypes.sizeof(MemoryStatusEx)
            ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return int(status.ullAvailPhys) if ok else None
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
        return None
    except (OSError, ValueError, AttributeError):
        return None


def worker_budget(cores: int | None = None, free_bytes: int | None = None) -> int:
    """How many workers an ``--all-origins`` build should use here.

    Three ceilings, narrowest first: the cores there are, whether the machine
    can hold the parent and one worker and itself at the same time, and the
    largest count measured to finish. Never zero -- a build that cannot have a
    pool still builds, one page at a time, and saying so is better than
    refusing to build.

    The middle ceiling is a single step rather than a division, and that is
    deliberate. Dividing the free memory by the per-worker cost gives a number
    the measurements do not support: at 8 GB free it permits four workers and
    at 4 GB it permits one, but a four-worker tree was measured holding 2.9 GB
    in total, because the parent has let most of its 4.1 GB go by the time the
    workers are producing pages. A formula that fits one sample and not the
    other is a formula to distrust, so this asks the one question that has a
    measured answer -- is there room for the smallest parallel build -- and
    otherwise trusts the ceiling.

    A caller that passes ``free_bytes`` has already read it.
    """
    cores = cores or os.cpu_count() or 1
    if free_bytes is None:
        free_bytes = free_memory_bytes()
    if free_bytes is not None and free_bytes < ONE_WORKER_FLOOR:
        return 1
    return max(1, min(cores, MAX_WORKERS))


def build_page_job(job: dict) -> tuple[str, str, str]:'''

patch(
    "build_workers.py",
    [
        ("from __future__ import annotations\n\nfrom pathlib import Path",
         "from __future__ import annotations\n\nimport os\nimport sys\nfrom pathlib import Path"),
        (OLD_TAIL, NEW_TAIL),
    ],
)
