"""Redirect-target validation for the short linker.

Pure and dependency-free (mirrors ``announcements/providers/mock.py``'s
``is_active``) so the rules are unit-testable without a Flask app.

WHY THIS EXISTS AT ALL: /s/<code> is a redirector. Whatever string we agree to
store is a string we will later navigate a reader's browser to, on our own
domain, from a link that looks like ours. That makes the validator the security
boundary of the whole feature, not a tidiness check — a missed case turns
skewnono into an open redirect, i.e. a phishing primitive wearing an internal
hostname that staff have been trained to trust.

The gate is on the WRITE side only. Validation runs once at mint time, so a
stored target is trusted by definition and there is no second gate on read that
could drift out of step with this one.
"""

from __future__ import annotations

__all__ = ["MAX_TARGET_LEN", "normalize_target"]


MAX_TARGET_LEN = 2048
"""Upper bound on one stored target. Roughly 4x the longest real analysis link
(a six-MSR comparison set lands near 500 chars), so it bounds what a single
mint can put in the store without being a limit anyone meets by accident."""


def normalize_target(raw: object) -> str | None:
    """Return the target to store, or ``None`` if it must be refused.

    Accepts a same-origin, root-relative path. Everything else — absolute URLs,
    protocol-relative URLs, non-http schemes, and anything carrying characters
    a browser would strip before resolving — is refused.
    """
    if not isinstance(raw, str):
        # bool is an int, not a str, so it lands here with every other
        # non-string JSON shape. The body is caller-supplied, so this is a 400
        # rather than a TypeError raised inside the store.
        return None

    target = raw.strip()
    if not target or len(target) > MAX_TARGET_LEN:
        return None

    # Browsers STRIP tab/newline/CR from a URL before resolving it, and treat a
    # NUL as a terminator, so a literal check of the first two characters can be
    # walked straight past by "/\n/evil.example". Refusing every control
    # character (and every interior space) means the string we validate is the
    # string the browser will resolve.
    if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in target):
        return None

    # A backslash is normalised to a forward slash in the authority position, so
    # "/\host" and "\\host" are protocol-relative in practice. Fold them before
    # the prefix checks rather than enumerating each spelling.
    folded = target.replace("\\", "/")

    if not folded.startswith("/"):
        # Catches every scheme (http:, https:, javascript:, data:, …) in one
        # rule, case-insensitively and without a scheme allowlist to maintain,
        # plus bare relative paths, which no caller produces and which would be
        # ambiguous against the resolver's own /s/ base.
        return None

    if folded.startswith("//"):
        # Protocol-relative: starts with "/" yet the browser reads it as a fully
        # qualified cross-origin URL. This is the case the guard exists for.
        return None

    return target
