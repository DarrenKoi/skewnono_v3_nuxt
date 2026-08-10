"""Office-only CLI scripts. Importing the package makes stdout UTF-8-safe.

Every script here is run at the office, on Windows, where Python's default
stream encoding is the ANSI code page (cp949 on a Korean install). Almost all
of them print an em dash somewhere, and cp949 cannot encode one:

    UnicodeEncodeError: 'cp949' codec can't encode character '\\u2014'

A real Windows console avoids this on its own -- since 3.6 Python writes to it
through a UTF-16 API -- so the failure only appears when output is REDIRECTED
or piped, which is exactly what an operator does to keep a record of a long
office run. It also does not reproduce in an IDE console, which defaults to
UTF-8. That asymmetry is what makes it confusing to hit: the same command works
in one window and dies in another.

Reconfiguring here rather than in each script means one place instead of
twenty, and it runs for the documented `python -m scripts.<name>` form because
`-m` imports the package first.

    errors="replace" is the belt: if UTF-8 is somehow unavailable, an
    unrepresentable character degrades to `?` instead of killing a measurement
    run that has already spent minutes against a real tool. Losing a dash beats
    losing the numbers.

Running a script BY PATH (`python scripts/deploy/pack.py`) does not import this
package and so does not get the fix. Prefer the `-m` form.
"""

import sys

for _stream in (sys.stdout, sys.stderr):
    # Not every stdout is a TextIOWrapper -- IDE consoles and capture harnesses
    # substitute their own objects, and some have no reconfigure() at all. They
    # are also the environments that are already UTF-8, so skipping them is
    # both safe and correct.
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is None:
        continue
    try:
        _reconfigure(encoding="utf-8", errors="replace")
    except (ValueError, OSError):
        # A detached or already-closed stream. Nothing to print to anyway.
        pass
