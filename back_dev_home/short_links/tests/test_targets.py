"""The redirect-target validator — the security boundary of the short linker.

A short link is a redirector: /s/<code> resolves to a stored target and the SPA
navigates there. So the only thing that genuinely must not fail is the
open-redirect guard — a link minted on skewnono that lands the reader on
someone else's host is a phishing primitive wearing our domain.

Everything here is the WRITE side. Validation happens once, at mint time, so a
stored target is trusted by definition; a rejected target never reaches the
store and there is no second gate to keep in sync.
"""

import pytest

from back_dev_home.short_links.targets import normalize_target


# ── accepted: ordinary in-app paths ─────────────────────────────────────


def test_a_plain_analysis_path_is_accepted_unchanged():
    target = "/ebeam/cd-sem/skewvoir/analysis?lot=KPB266344&view=time-series"
    assert normalize_target(target) == target


def test_a_bare_root_path_is_accepted():
    assert normalize_target("/") == "/"


def test_surrounding_whitespace_is_trimmed_not_rejected():
    """A copied string picks up a stray newline; that is not an attack."""
    assert normalize_target("  /ebeam/cd-sem/skewvoir/analysis  ") == (
        "/ebeam/cd-sem/skewvoir/analysis"
    )


def test_a_fragment_survives():
    assert normalize_target("/settings#tokens") == "/settings#tokens"


# ── rejected: open redirects ────────────────────────────────────────────


def test_an_absolute_http_url_is_rejected():
    assert normalize_target("http://evil.example/phish") is None


def test_an_absolute_https_url_is_rejected():
    assert normalize_target("https://evil.example/phish") is None


def test_a_protocol_relative_url_is_rejected():
    """`//evil.example` is the classic bypass: it starts with `/` yet the
    browser reads it as a fully qualified cross-origin URL."""
    assert normalize_target("//evil.example/phish") is None


def test_a_backslash_protocol_relative_url_is_rejected():
    r"""Browsers normalise `\` to `/` in the authority position, so `/\host`
    and `\\host` are protocol-relative in practice even though a naive
    startswith('//') check waves them through."""
    assert normalize_target("/\\evil.example/phish") is None
    assert normalize_target("\\\\evil.example/phish") is None


def test_a_javascript_scheme_is_rejected():
    assert normalize_target("javascript:alert(1)") is None


def test_a_data_scheme_is_rejected():
    assert normalize_target("data:text/html,<script>alert(1)</script>") is None


def test_a_relative_path_without_a_leading_slash_is_rejected():
    """Ambiguous against the resolver's own /s/ base, and no caller produces
    one — the frontend always sends a router-resolved absolute path."""
    assert normalize_target("ebeam/cd-sem/skewvoir/analysis") is None


# ── rejected: malformed input ───────────────────────────────────────────


def test_an_empty_or_whitespace_only_target_is_rejected():
    assert normalize_target("") is None
    assert normalize_target("   ") is None


def test_a_non_string_target_is_rejected():
    """The body is caller-supplied JSON, so every non-string shape has to be a
    400 rather than a TypeError inside the store."""
    for value in (None, 42, ["/a"], {"path": "/a"}, True):
        assert normalize_target(value) is None


def test_an_embedded_control_character_is_rejected():
    r"""Browsers STRIP \n, \r and \t from URLs before resolving them, so
    `/\n/evil.example` would be smuggled past a check that only looks at the
    literal first two characters."""
    assert normalize_target("/\n/evil.example") is None
    assert normalize_target("/\r\n/evil.example") is None
    assert normalize_target("/\tevil") is None
    assert normalize_target("/nul\x00byte") is None


def test_an_over_long_target_is_rejected():
    """A bound on what one mint can put in the store. Well above any real
    analysis link — the longest observed is a six-MSR set at ~500 chars."""
    assert normalize_target("/a" + "b" * 4000) is None


def test_a_target_at_the_length_limit_is_accepted():
    at_limit = "/" + "a" * 2047
    assert len(at_limit) == 2048
    assert normalize_target(at_limit) == at_limit


@pytest.mark.parametrize("scheme", ["HTTP://x/y", "HtTpS://x/y", "JavaScript:alert(1)"])
def test_scheme_rejection_is_case_insensitive(scheme):
    assert normalize_target(scheme) is None
