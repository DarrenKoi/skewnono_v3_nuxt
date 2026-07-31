# Anonymous Self-Identification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give an unidentified caller a screen to declare their employee number and name, verify it against the `members` directory, and tag the resulting identity so it is distinguishable from one the infrastructure supplied.

**Architecture:** Cookie reading moves out of the identity providers and into the middleware, which then owns a four-step chain — API token, `LASTUSER` cookie, declared session, per-phase fallback — and records both `g.user_id` and `g.identity_source`. The providers keep only the per-phase judgement of what an absent cookie means (`local-dev`/`local` at home, `anonymous`/`anonymous` on the cloud). Verification runs through a new `probe_member()` that distinguishes "no directory row" from "directory unreachable", and a pure decision function that maps the probe plus the entered name onto accept/reject. The gate that sends anonymous users to the form is Nuxt route middleware, never a Flask response.

**Tech Stack:** Flask (blueprints, signed session cookie), Redis (`members` hash), pytest, Nuxt 4 SPA (`ssr: false`), NuxtUI, `useState` composables, `node --test`.

**Spec:** `docs/superpowers/specs/2026-07-31-anonymous-self-identification-design.md`

## Global Constraints

- Python is the repo-root venv: run everything as `.venv/bin/python -m pytest -q` **from the repo root** — `-m` is what puts the root on `sys.path`.
- The full suite baseline before this plan starts is **1887 passed, 8 skipped**. Never finish a task with fewer passing.
- Never edit `back_dev_home/<feature>/data.py` and never edit `providers/office.py` (gitignored). Nothing in this plan touches a data provider.
- **The identity gate must never return a response for a non-`/api/*` path.** It is the app's first `before_request`; answering there blocks `index.html` and every bundle with it. This caused the Phase 3 blank-window deploy.
- No Pinia. Shared client state is a `useState`-backed composable; anything surviving reload goes through `composables/usePersistedState.ts`.
- `npm test` (`node --test`) covers **pure functions only** — there is no component mounting harness and no E2E suite. Screens are verified by hand via the `verify` skill.
- Run `npm run lint:md` from the repo root after any Markdown edit.
- Markdown tables use markdownlint `MD060` `compact` style. `docs/` written for teammates is Korean with `~입니다.` / `~합니다.` endings.
- Commit with **explicit pathspecs only** (`git commit -m "..." -- path/a path/b`). `git add -A`, `git add .`, `git commit -a` and bare `git stash` are banned — concurrent sessions share this working tree.
- Error taxonomy: bare `LookupError` → 502, bare `RuntimeError` → 503; subclasses stay 500. Boot-time refusal (Task 9) raises before any request exists, so the taxonomy does not apply there.

## Decisions this plan locks in beyond the spec text

Two points the spec leaves implicit. Both are called out again at the task that implements them.

1. **Which name gets stored when the directory cannot supply one.** §6.2 says the entered name is "확인용이며 저장 대상이 아닙니다", written when only `unavailable` was accepted. Now that `absent` is accepted too, storing nothing would leave an empno with no name at all — which defeats attribution, the entire goal. So: `verified: true` stores the **directory's** name; `verified: false` stores the **entered** name, flagged as unverified.
2. **`/api/me` must report admin via `is_admin_request()`, not `is_admin()`.** Otherwise the SPA renders admin surfaces for a declared identity that typed an admin empno. The server would still refuse the calls, but showing the UI at all invites the bug report.

## File Structure

**Backend — new**

| File | Responsibility |
| --- | --- |
| `back_dev_home/_auth/self_id.py` | The declared identity in the Flask session: read, write, clear. Nothing else knows the session key. |
| `back_dev_home/_auth/verify.py` | Pure decision: `(probe, entered name) → accept/verified/name`. No Flask, no Redis — this is what makes §6.2 testable at home. |

**Backend — modified**

| File | Change |
| --- | --- |
| `back_dev_home/_auth/provider.py` | Source-name constants; `read_identity_cookie()` made public; providers reduced to `fallback_identity()`. |
| `back_dev_home/_auth/middleware.py` | Owns the four-step chain; sets `g.identity_source`; `_deny_if_blocked` switches to `is_admin_request()`. |
| `back_dev_home/_auth/admin.py` | Adds `is_admin_request()` and the trusted-source allowlist. |
| `back_dev_home/_auth/directory.py` | Adds `Probe` and `probe_member()`; `lookup_member()` becomes the forgiving wrapper. |
| `back_dev_home/_auth/routes.py` | `GET /api/me` extended; `POST`/`DELETE /api/identify` added. |
| `back_dev_home/_logging/activity.py` | `identity_source` added to the activity document. |
| `back_dev_home/__init__.py` | Cloud secret-key requirement, 30-day session lifetime, conditional `ProxyFix`. |

**Frontend — new**

| File | Responsibility |
| --- | --- |
| `front-dev-home/app/utils/identityInput.ts` | Pure input normalization/validation — the only part `node --test` can reach. |
| `front-dev-home/app/utils/identityInput.test.ts` | Its test. |
| `front-dev-home/app/composables/useIdentity.ts` | `useState`-backed identity state + `identify()` / `signOut()` calls. |
| `front-dev-home/app/pages/identify.vue` | The empno + name form. |
| `front-dev-home/app/middleware/identify.global.ts` | Redirects anonymous callers to `/identify`. |

---

### Task 1: Identity source vocabulary and provider restructure

The providers currently read the cookie *and* supply the fallback, so the middleware receives one string and cannot tell which branch produced it. That is why home `local-dev` cannot be distinguished from a real cookie. Split the two jobs: this task moves cookie reading out and reduces each provider to its per-phase fallback.

**Files:**

- Modify: `back_dev_home/_auth/provider.py`
- Test: `back_dev_home/_auth/tests/test_provider.py`

**Interfaces:**

- Consumes: nothing (first task).
- Produces:
  - `SOURCE_TOKEN = "token"`, `SOURCE_COOKIE = "cookie"`, `SOURCE_DECLARED = "declared"`, `SOURCE_LOCAL = "local"`, `SOURCE_ANONYMOUS = "anonymous"` (module constants in `provider.py`)
  - `ANONYMOUS = "anonymous"` (unchanged, still exported)
  - `read_identity_cookie(request: Request) -> Optional[str]`
  - `IdentityProvider` Protocol with `fallback_identity(self) -> tuple[str, str]`
  - `LocalIdentityProvider().fallback_identity() == ("local-dev", "local")`
  - `CloudIdentityProvider().fallback_identity() == ("anonymous", "anonymous")`

- [ ] **Step 1: Write the failing tests**

Append to `back_dev_home/_auth/tests/test_provider.py`:

```python
from back_dev_home._auth.provider import (
    SOURCE_ANONYMOUS,
    SOURCE_COOKIE,
    SOURCE_DECLARED,
    SOURCE_LOCAL,
    SOURCE_TOKEN,
    read_identity_cookie,
)


def test_the_five_source_names_are_distinct():
    """`identity_source` only means something if no two steps share a name."""
    names = {SOURCE_TOKEN, SOURCE_COOKIE, SOURCE_DECLARED, SOURCE_LOCAL, SOURCE_ANONYMOUS}
    assert len(names) == 5


def test_read_identity_cookie_prefers_lastuser(app_request):
    with app_request(cookies={"LASTUSER": "2067928", "LAST_USER": "9999999"}) as request:
        assert read_identity_cookie(request) == "2067928"


def test_read_identity_cookie_accepts_the_second_spelling(app_request):
    with app_request(cookies={"LAST_USER": "2067928"}) as request:
        assert read_identity_cookie(request) == "2067928"


def test_read_identity_cookie_returns_none_when_absent(app_request):
    with app_request(cookies={}) as request:
        assert read_identity_cookie(request) is None


def test_read_identity_cookie_ignores_a_blank_value(app_request):
    """A host that sets the header with no value looks exactly like no host at
    all; treating "" as an identity would log every such visitor as one user."""
    with app_request(cookies={"LASTUSER": "   "}) as request:
        assert read_identity_cookie(request) is None


def test_home_fallback_is_local_dev_tagged_local():
    assert LocalIdentityProvider().fallback_identity() == ("local-dev", SOURCE_LOCAL)


def test_cloud_fallback_is_anonymous_tagged_anonymous():
    assert CloudIdentityProvider().fallback_identity() == (ANONYMOUS, SOURCE_ANONYMOUS)


def test_the_two_fallbacks_never_collide():
    """`local` is trusted for admin and `anonymous` is not, so a phase that
    returned the wrong one would silently hand admin to the internet-facing
    fallback. Different id AND different source, checked together."""
    home = LocalIdentityProvider().fallback_identity()
    cloud = CloudIdentityProvider().fallback_identity()
    assert home[0] != cloud[0]
    assert home[1] != cloud[1]
```

Add this fixture at the top of the same file (after the imports):

```python
import contextlib

import pytest
from flask import Flask


@pytest.fixture
def app_request():
    """Yield a real `flask.Request` carrying the given cookies.

    `read_identity_cookie` takes a Request rather than reading the global, so
    the tests need a request context but not a client, a route, or a provider.
    """
    app = Flask(__name__)

    @contextlib.contextmanager
    def _make(cookies: dict[str, str]):
        header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        with app.test_request_context("/", headers={"Cookie": header} if header else {}):
            from flask import request

            yield request

    return _make
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest back_dev_home/_auth/tests/test_provider.py -q`
Expected: FAIL — `ImportError: cannot import name 'SOURCE_ANONYMOUS'`

- [ ] **Step 3: Restructure `provider.py`**

Replace the body of `back_dev_home/_auth/provider.py` below the module docstring with:

```python
from typing import Optional, Protocol

from flask import Request

# Order IS the precedence, and it is user-confirmed (2026-07-31): LASTUSER wins.
# LAST_USER stays as a second spelling because afm/routes.py has always accepted
# either, and a host setting only that one would look exactly like "nobody is
# logged in" — a failure with no distinguishing symptom to debug from.
_IDENTITY_COOKIES = ("LASTUSER", "LAST_USER")

# The id a cloud caller gets when no cookie identifies them. Spelled the same
# as afm/routes.py:196 so one person browsing both apps unauthenticated is one
# id in the logs rather than two.
ANONYMOUS = "anonymous"

# The five ways a request can acquire an identity. These are the vocabulary of
# `g.identity_source`, which `admin.py` reads to decide whether an identity is
# trustworthy enough to be an admin — so they live in one place and are
# compared by constant, never by string literal at the call site.
SOURCE_TOKEN = "token"
SOURCE_COOKIE = "cookie"
SOURCE_DECLARED = "declared"
SOURCE_LOCAL = "local"
SOURCE_ANONYMOUS = ANONYMOUS


def read_identity_cookie(request: Request) -> Optional[str]:
    """The employee number the infrastructure put on this request, if any.

    Public because the MIDDLEWARE calls it, not the providers. The declared
    session sits between the cookie and the per-phase fallback in the identity
    chain, so no single object can own both ends of that chain — see the spec's
    §3. A blank value counts as absent: a host that sets the header with no
    value must not collapse every such visitor into one identity.
    """
    for name in _IDENTITY_COOKIES:
        value = (request.cookies.get(name) or "").strip()
        if value:
            return value
    return None


class IdentityProvider(Protocol):
    def fallback_identity(self) -> tuple[str, str]:
        """(user_id, identity_source) for a caller no cookie identified."""
        ...


class LocalIdentityProvider:
    """Home and office-localhost: a stand-in developer.

    `local-dev` is an admin id (`_auth/admin.py`), which is why its source name
    has to be distinct. Labelling it `cookie` would make `identity_source` lie
    about where it came from; leaving it out of `_TRUSTED_SOURCES` would remove
    the admin panel from every home session. It gets its own name, `local`, and
    that name is trusted — safely, because this provider is installed only when
    `is_cloud()` is false.
    """

    def fallback_identity(self) -> tuple[str, str]:
        return ("local-dev", SOURCE_LOCAL)


class CloudIdentityProvider:
    """Phase 3: `anonymous`.

    Same convention `afm/routes.py:196` has always used. An unidentified caller
    is a real caller on the private cloud — the network is already internal —
    so they get a usable app rather than a locked door, and the activity log
    gets a name for the traffic instead of a null.

    `anonymous` is a shared id, not an identity: it must never be admin. Three
    independent things keep that true — it is absent from both allowlists in
    `admin.py`, it is not X-prefixed so access control ignores it, and its
    source name is outside `_TRUSTED_SOURCES`. Do not add it to
    `SKEWNONO_ADMIN_USERS`.
    """

    def fallback_identity(self) -> tuple[str, str]:
        return (ANONYMOUS, SOURCE_ANONYMOUS)
```

- [ ] **Step 4: Repair the pre-existing tests in the same file**

The old tests call `.identify(request)`, which no longer exists. Rewrite each one that does: a test asserting the cookie was read becomes a `read_identity_cookie` test; a test asserting the fallback becomes a `fallback_identity` test. Keep `test_provider.py`'s existing hcputil-absence test (it asserts no `hcputil` module is imported) exactly as it is — it is a regression guard, not scaffolding.

- [ ] **Step 5: Run the whole auth suite**

Run: `.venv/bin/python -m pytest back_dev_home/_auth -q`
Expected: PASS. `test_middleware.py` will fail here if it constructs a provider and expects `identify()` — that is Task 4's subject; if it fails now, leave it failing and note it, or stub the middleware call minimally to keep the suite green. Prefer keeping it green.

- [ ] **Step 6: Commit**

```bash
git commit -m "refactor(auth): split cookie reading from the per-phase fallback

The providers read the cookie AND supplied the fallback, so the middleware
got one string and could not tell a real cookie from home's local-dev
substitute. Cookie reading becomes read_identity_cookie(), callable by the
middleware; each provider keeps only fallback_identity(), which now names
its own source. The declared session sits between those two steps, so no
single object can own both ends of the chain.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- back_dev_home/_auth/provider.py back_dev_home/_auth/tests/test_provider.py
```

---

### Task 2: The declared identity in the session

**Files:**

- Create: `back_dev_home/_auth/self_id.py`
- Test: `back_dev_home/_auth/tests/test_self_id.py`

**Interfaces:**

- Consumes: nothing.
- Produces:
  - `class Declared(TypedDict): empno: str; emp_nm: Optional[str]; verified: bool; declared_from: Optional[str]`
  - `read_declared() -> Optional[Declared]`
  - `write_declared(*, empno: str, emp_nm: Optional[str], verified: bool, declared_from: Optional[str]) -> Declared`
  - `clear_declared() -> None`
  - `SESSION_KEY = "declared"`

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/_auth/tests/test_self_id.py`:

```python
"""The declared identity's storage.

Everything here rides in Flask's signed session cookie. The signature is what
makes `verified` mean anything — a plaintext cookie would let the user flip it
— so these tests also pin that a tampered cookie degrades to "nobody declared"
rather than to a trusted identity.
"""

import pytest
from flask import Flask

from back_dev_home._auth.self_id import (
    SESSION_KEY,
    clear_declared,
    read_declared,
    write_declared,
)


@pytest.fixture
def app():
    app = Flask(__name__)
    app.secret_key = "test-key-not-the-real-one"
    return app


def test_nothing_declared_reads_as_none(app):
    with app.test_request_context("/"):
        assert read_declared() is None


def test_a_written_identity_reads_back(app):
    with app.test_request_context("/"):
        write_declared(
            empno="2067928", emp_nm="고대영", verified=True, declared_from="10.0.0.1"
        )
        assert read_declared() == {
            "empno": "2067928",
            "emp_nm": "고대영",
            "verified": True,
            "declared_from": "10.0.0.1",
        }


def test_clearing_removes_it(app):
    with app.test_request_context("/"):
        write_declared(empno="2067928", emp_nm="고대영", verified=True, declared_from=None)
        clear_declared()
        assert read_declared() is None


def test_clearing_when_nothing_is_declared_is_not_an_error(app):
    """The 'not me' link is reachable from a page whose session may already
    have expired; a KeyError there would 500 on a button that means 'undo'."""
    with app.test_request_context("/"):
        clear_declared()
        assert read_declared() is None


def test_a_row_without_an_empno_is_ignored(app):
    """Anything shaped wrong is nobody. A half-written session must not produce
    an identity with an empty id, which would log as a distinct 'user'."""
    from flask import session

    with app.test_request_context("/"):
        session[SESSION_KEY] = {"emp_nm": "고대영", "verified": True}
        assert read_declared() is None


def test_a_non_dict_payload_is_ignored(app):
    from flask import session

    with app.test_request_context("/"):
        session[SESSION_KEY] = "2067928"
        assert read_declared() is None


def test_verified_is_coerced_to_a_real_bool(app):
    """It is read back out of a JSON-ish store and then used in a security
    decision; a truthy string must not read as True."""
    from flask import session

    with app.test_request_context("/"):
        session[SESSION_KEY] = {"empno": "2067928", "verified": "no"}
        declared = read_declared()
        assert declared is not None
        assert declared["verified"] is False


def test_the_session_is_marked_permanent_on_write(app):
    """Without this the cookie is a browser-session cookie and the declared
    identity evaporates when the tab closes — a 30-day lifetime configured in
    the app factory would have no effect."""
    from flask import session

    with app.test_request_context("/"):
        write_declared(empno="2067928", emp_nm=None, verified=False, declared_from=None)
        assert session.permanent is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/_auth/tests/test_self_id.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'back_dev_home._auth.self_id'`

- [ ] **Step 3: Write the implementation**

Create `back_dev_home/_auth/self_id.py`:

```python
"""The identity a user typed in for themselves.

This is the third step of the identity chain: weaker than a cookie the company
infrastructure set, stronger than nothing. It lives in Flask's signed session
so the `verified` flag cannot be flipped by the person it describes.

The signature protects the flag, not the fact. That the identity is *declared*
is guaranteed structurally — it came out of the session rather than out of a
`LASTUSER` cookie — and structure is not forgeable by editing a value. Only
`verified` needs the signature, because it is a claim about a check that
happened elsewhere.

Every read is defensive. A session written by an older version of this code, a
half-written row, or a payload of the wrong type must read as "nobody
declared", never as a partially trusted identity: the callers of `read_declared`
use its result to name a person in the activity log.
"""

from __future__ import annotations

from typing import Optional, TypedDict

from flask import session

# The session key. Deliberately the only place this string appears — callers
# go through the three functions below so the storage can change without a
# grep across the app.
SESSION_KEY = "declared"


class Declared(TypedDict):
    """An identity its own subject typed in.

    `emp_nm` is the directory's name when `verified` is True and the name the
    user entered when it is False — see `verify.decide`. `declared_from` is the
    IP the declaration was made from, recorded so that one empno declared from
    many addresses (or many empnos from one) is visible.
    """

    empno: str
    emp_nm: Optional[str]
    verified: bool
    declared_from: Optional[str]


def read_declared() -> Optional[Declared]:
    """The declared identity on this request's session, or None.

    Returns None for every malformed shape rather than raising: this runs in
    the identity chain on every request, and an exception there answers
    index.html along with it.
    """
    raw = session.get(SESSION_KEY)
    if not isinstance(raw, dict):
        return None

    empno = str(raw.get("empno") or "").strip()
    if not empno:
        return None

    emp_nm = raw.get("emp_nm")
    declared_from = raw.get("declared_from")
    return {
        "empno": empno,
        "emp_nm": str(emp_nm).strip() or None if emp_nm else None,
        # `is True` rather than bool(): the value survives a round trip through
        # the session's JSON serializer, and a leftover string like "no" is
        # truthy. This flag gates a security-relevant display, so only a real
        # boolean True counts.
        "verified": raw.get("verified") is True,
        "declared_from": str(declared_from).strip() or None if declared_from else None,
    }


def write_declared(
    *,
    empno: str,
    emp_nm: Optional[str],
    verified: bool,
    declared_from: Optional[str],
) -> Declared:
    """Record a declared identity and return the stored shape.

    `session.permanent` is set here rather than in the app factory because it
    is a property of *this* session, and the 30-day lifetime the factory
    configures only applies to sessions marked permanent.
    """
    declared: Declared = {
        "empno": empno.strip(),
        "emp_nm": (emp_nm or "").strip() or None,
        "verified": bool(verified),
        "declared_from": (declared_from or "").strip() or None,
    }
    session[SESSION_KEY] = declared
    session.permanent = True
    return declared


def clear_declared() -> None:
    """Forget the declared identity. Safe when there is none."""
    session.pop(SESSION_KEY, None)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest back_dev_home/_auth/tests/test_self_id.py -q`
Expected: PASS — 8 passed

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(auth): store a self-declared identity in the signed session

Third step of the identity chain. Reads are defensive on every shape - a
malformed session reads as 'nobody declared' rather than a partly trusted
identity, because this runs in the app's first before_request where an
exception would answer index.html too. verified is compared with 'is True'
since the value round-trips through the session serializer and a leftover
string would be truthy.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- back_dev_home/_auth/self_id.py back_dev_home/_auth/tests/test_self_id.py
```

---

### Task 3: `is_admin_request()` — the one server-side boundary

**Files:**

- Modify: `back_dev_home/_auth/admin.py`
- Test: `back_dev_home/_auth/tests/test_admin.py` (create)

**Interfaces:**

- Consumes: `SOURCE_*` constants from Task 1.
- Produces: `is_admin_request() -> bool`, `_TRUSTED_SOURCES: frozenset[str]`. `is_admin(user_id)` keeps its current signature and behavior.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/_auth/tests/test_admin.py`:

```python
"""Admin is the only thing this feature enforces on the server.

The self-identification gate is client-side by design (spec §4), so the entire
security surface of the feature is the rule below: an identity the user typed
in for themselves can never be an admin, no matter which employee number they
typed. Everything else about a declared identity is attribution, not authority.
"""

import pytest
from flask import Flask, g

from back_dev_home._auth.admin import is_admin, is_admin_request
from back_dev_home._auth.provider import (
    SOURCE_ANONYMOUS,
    SOURCE_COOKIE,
    SOURCE_DECLARED,
    SOURCE_LOCAL,
    SOURCE_TOKEN,
)


@pytest.fixture
def app():
    return Flask(__name__)


@pytest.fixture(autouse=True)
def admin_allowlist(monkeypatch):
    """Pin the allowlist so the test does not depend on is_cloud() or on the
    developer's SKEWNONO_ADMIN_USERS."""
    monkeypatch.setenv("SKEWNONO_ADMIN_USERS", "2067928,LOCAL-DEV")
    from back_dev_home._auth import admin

    admin._parse_allowlist.cache_clear()
    yield
    admin._parse_allowlist.cache_clear()


def _request(app, user_id, source):
    ctx = app.test_request_context("/")
    ctx.push()
    g.user_id = user_id
    g.identity_source = source
    return ctx


@pytest.mark.parametrize("source", [SOURCE_COOKIE, SOURCE_TOKEN, SOURCE_LOCAL])
def test_trusted_sources_can_be_admin(app, source):
    ctx = _request(app, "2067928", source)
    try:
        assert is_admin_request() is True
    finally:
        ctx.pop()


def test_home_local_dev_keeps_admin(app):
    """The regression this refactor could introduce. `local-dev` arrives from
    the home provider's fallback, not from a cookie; if `local` were left out
    of the trusted set, every home developer would lose the admin panel and the
    symptom would be a bare 403 with nothing pointing at a source name."""
    ctx = _request(app, "local-dev", SOURCE_LOCAL)
    try:
        assert is_admin_request() is True
    finally:
        ctx.pop()


@pytest.mark.parametrize("source", [SOURCE_DECLARED, SOURCE_ANONYMOUS])
def test_untrusted_sources_can_never_be_admin(app, source):
    """Typing an admin's employee number into the form must not confer admin,
    even though `is_admin` alone would say yes to that id."""
    assert is_admin("2067928") is True
    ctx = _request(app, "2067928", source)
    try:
        assert is_admin_request() is False
    finally:
        ctx.pop()


def test_an_unknown_source_is_not_trusted(app):
    """The trusted set is a whitelist: a source added later is non-admin until
    someone deliberately adds it."""
    ctx = _request(app, "2067928", "some-future-source")
    try:
        assert is_admin_request() is False
    finally:
        ctx.pop()


def test_a_missing_source_is_not_trusted(app):
    """A code path that sets g.user_id without g.identity_source is a bug; it
    must fail closed rather than inherit admin."""
    ctx = app.test_request_context("/")
    ctx.push()
    g.user_id = "2067928"
    try:
        assert is_admin_request() is False
    finally:
        ctx.pop()


def test_a_trusted_source_with_a_non_admin_id_is_not_admin(app):
    ctx = _request(app, "1234567", SOURCE_COOKIE)
    try:
        assert is_admin_request() is False
    finally:
        ctx.pop()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/_auth/tests/test_admin.py -q`
Expected: FAIL — `ImportError: cannot import name 'is_admin_request'`

- [ ] **Step 3: Write the implementation**

Add to `back_dev_home/_auth/admin.py`, after `is_admin`:

```python
# Which identity sources may hold admin. A WHITELIST: a source added to the
# chain later is non-admin until it is deliberately added here.
#
# `local` is in the set because the home provider's fallback id, `local-dev`,
# is itself an admin id — and that provider is installed only when is_cloud()
# is false, so `local` cannot appear on the cloud at all.
#
# `declared` is out because the user typed it, and `anonymous` is out because
# it is shared. Those two exclusions are the entire server-side security
# boundary of the self-identification feature.
_TRUSTED_SOURCES = frozenset(
    {provider.SOURCE_TOKEN, provider.SOURCE_COOKIE, provider.SOURCE_LOCAL}
)


def is_admin_request() -> bool:
    """Is the CALLER of this request an admin?

    `is_admin` answers "is this id an admin", which is not the same question:
    a self-declared identity can carry an admin's employee number without
    having proved anything. Every admin gate uses this one; `is_admin` stays
    a pure id check for the places that genuinely have only an id.
    """
    if getattr(g, "identity_source", None) not in _TRUSTED_SOURCES:
        return False
    return is_admin(getattr(g, "user_id", None))
```

Add the import at the top of `admin.py`:

```python
from . import provider
```

Then change `require_admin` to use the new function:

```python
def require_admin(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_admin_request():
            return error_json("forbidden", "admin access required", 403)
        return view(*args, **kwargs)

    return wrapper
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest back_dev_home/_auth -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(auth): gate admin on the identity's source, not just its id

is_admin answers 'is this id an admin'; is_admin_request answers 'is the
caller one', which differs the moment an identity can be self-declared. The
trusted set is a whitelist so a source added later is non-admin by default.
local is trusted because home's local-dev fallback IS an admin id and the
provider that produces it is only installed when is_cloud() is false.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- back_dev_home/_auth/admin.py back_dev_home/_auth/tests/test_admin.py
```

---

### Task 4: The middleware owns the four-step chain

**Files:**

- Modify: `back_dev_home/_auth/middleware.py`
- Test: `back_dev_home/_auth/tests/test_middleware.py`

**Interfaces:**

- Consumes: `read_identity_cookie`, `SOURCE_*`, `IdentityProvider.fallback_identity` (Task 1); `read_declared` (Task 2); `is_admin_request` (Task 3).
- Produces: every request has `g.user_id` and `g.identity_source` set before any route runs.

- [ ] **Step 1: Write the failing test**

Add to `back_dev_home/_auth/tests/test_middleware.py`. The existing `client` fixture builds a cloud-shaped app; add a second one that exposes the source, and keep every existing test as-is:

```python
from back_dev_home._auth.provider import (
    LocalIdentityProvider,
    SOURCE_ANONYMOUS,
    SOURCE_COOKIE,
    SOURCE_DECLARED,
    SOURCE_LOCAL,
)
from back_dev_home._auth.self_id import write_declared


def _identity_app(provider, no_access_control_applied=True):
    """An app that reports whatever the identity chain decided."""
    app = Flask(__name__)
    app.secret_key = "test-key-not-the-real-one"
    install_identity_middleware(app, provider)

    @app.get("/api/whoami")
    def _whoami():
        return {
            "user_id": getattr(g, "user_id", None),
            "identity_source": getattr(g, "identity_source", None),
        }

    @app.post("/api/declare")
    def _declare():
        write_declared(
            empno="7654321", emp_nm="선언자", verified=False, declared_from="10.0.0.9"
        )
        return {"ok": True}

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def _spa(path: str):
        return SPA_MARK

    return app


def test_a_cookie_identity_is_tagged_cookie(no_access_control):
    client = _identity_app(CloudIdentityProvider()).test_client()
    client.set_cookie("LASTUSER", "2067928")
    body = client.get("/api/whoami").get_json()
    assert body == {"user_id": "2067928", "identity_source": SOURCE_COOKIE}


def test_no_cookie_on_the_cloud_is_tagged_anonymous(no_access_control):
    client = _identity_app(CloudIdentityProvider()).test_client()
    body = client.get("/api/whoami").get_json()
    assert body == {"user_id": "anonymous", "identity_source": SOURCE_ANONYMOUS}


def test_no_cookie_at_home_is_tagged_local(no_access_control):
    """Home's fallback must be distinguishable from a real cookie — that
    distinction is what lets `local` be trusted for admin while `anonymous`
    is not."""
    client = _identity_app(LocalIdentityProvider()).test_client()
    body = client.get("/api/whoami").get_json()
    assert body == {"user_id": "local-dev", "identity_source": SOURCE_LOCAL}


def test_a_declared_session_beats_the_fallback(no_access_control):
    client = _identity_app(CloudIdentityProvider()).test_client()
    client.post("/api/declare")
    body = client.get("/api/whoami").get_json()
    assert body == {"user_id": "7654321", "identity_source": SOURCE_DECLARED}


def test_a_cookie_beats_a_declared_session(no_access_control):
    """Precedence, in the direction that matters: infrastructure identity
    outranks a typed one, so a user who later receives a real cookie stops
    being their own declaration without having to clear anything."""
    client = _identity_app(CloudIdentityProvider()).test_client()
    client.post("/api/declare")
    client.set_cookie("LASTUSER", "2067928")
    body = client.get("/api/whoami").get_json()
    assert body == {"user_id": "2067928", "identity_source": SOURCE_COOKIE}


def test_a_declared_page_request_still_reaches_the_spa(no_access_control):
    """The invariant this whole module exists to protect, re-checked on the
    new branch: nothing added to the chain may answer a non-/api path."""
    client = _identity_app(CloudIdentityProvider()).test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert SPA_MARK in response.get_data(as_text=True)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest back_dev_home/_auth/tests/test_middleware.py -q`
Expected: FAIL — `identity_source` is `None`

- [ ] **Step 3: Write the implementation**

In `back_dev_home/_auth/middleware.py`, update the imports:

```python
from .admin import is_admin_request
from .errors import error_json
from .provider import (
    SOURCE_COOKIE,
    SOURCE_DECLARED,
    SOURCE_TOKEN,
    IdentityProvider,
    read_identity_cookie,
)
from .self_id import read_declared
```

In `_try_api_token`, set the source alongside the id (add one line after `g.user_id = row.owner_user_id`):

```python
    g.identity_source = SOURCE_TOKEN
```

In `_deny_if_blocked`, swap the admin check — the import of `is_admin` is replaced by `is_admin_request`:

```python
    # is_blocked before is_admin_request: non-X ids (nearly everyone)
    # short-circuit on a prefix check without touching the admin allowlist or
    # the exception store. is_admin_request rather than is_admin, because a
    # declared identity that typed an X-prefixed admin's number must not
    # inherit that admin's exemption from access control.
    if not is_blocked(user_id) or is_admin_request():
        return None
```

Replace `install_identity_middleware` with:

```python
def install_identity_middleware(app: Flask, provider: IdentityProvider) -> None:
    @app.before_request
    def _attach_identity():
        matched, response = _try_api_token()
        if matched:
            return response or _deny_if_blocked()

        # The chain, in precedence order. Infrastructure identity outranks a
        # typed one, so a user who is later given a real cookie stops being
        # their own declaration without having to clear anything.
        cookie = read_identity_cookie(request)
        if cookie:
            g.user_id = cookie
            g.identity_source = SOURCE_COOKIE
            return _deny_if_blocked()

        declared = read_declared()
        if declared:
            g.user_id = declared["empno"]
            g.identity_source = SOURCE_DECLARED
            return _deny_if_blocked()

        # Nobody was identified, so the phase decides what that means: a
        # stand-in developer at home, `anonymous` on the cloud. Both are real
        # identities from here on — the 401 below is unreachable while every
        # provider supplies a fallback, and is kept as the failsafe for one
        # that does not.
        user_id, source = provider.fallback_identity()
        if user_id:
            g.user_id = user_id
            g.identity_source = source
            return _deny_if_blocked()

        # Data is refused, but the page is not: this hook is the app's first
        # before_request, so returning a response here answers index.html and
        # every bundle with it, and the visitor gets a blank window instead of
        # a UI that could explain itself. Phase 3 shipped a redirect on this
        # line once and the browser looped between the app and SSO until it
        # gave up. Falling through hands the request to the SPA mount.
        if request.path.startswith("/api/"):
            return error_json(
                "unauthenticated", "member identity cookie missing", 401
            )
        return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest back_dev_home/_auth -q`
Expected: PASS. If `no_access_control` monkeypatches `middleware_mod.is_admin`, update it to patch `is_admin_request` instead.

- [ ] **Step 5: Run the full suite — this task moves a global**

Run: `.venv/bin/python -m pytest -q`
Expected: 1887 passed, 8 skipped. Any other failure is a caller that assumed `identify()`.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(auth): give the middleware the whole identity chain

Four steps in one readable place: API token, LASTUSER cookie, declared
session, per-phase fallback. Each sets g.identity_source alongside
g.user_id. Cookie beats declaration so a user who later receives a real
cookie stops being their own declaration without clearing anything.

The non-/api fall-through is unchanged and re-tested on the new branch:
this hook is the app's first before_request, and a response here answers
index.html along with it.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- back_dev_home/_auth/middleware.py back_dev_home/_auth/tests/test_middleware.py
```

---

### Task 5: `probe_member()` — telling "no row" from "no Redis"

`lookup_member()` returns the same bare record for four different failures, which is right for display and useless for verification. This adds an entry point that keeps the distinction, and rewrites `lookup_member` as the forgiving wrapper so the swallow-everything policy lives in exactly one place.

**Files:**

- Modify: `back_dev_home/_auth/directory.py`
- Test: `back_dev_home/_auth/tests/test_directory.py`

**Interfaces:**

- Consumes: nothing.
- Produces:
  - `class Probe(NamedTuple): member: Optional[Member]; status: str` with `status` in `{"found", "absent", "unavailable"}`
  - `probe_member(user_id: str) -> Probe`
  - `lookup_member(user_id: Optional[str]) -> Optional[Member]` — behavior unchanged for existing callers

- [ ] **Step 1: Write the failing test**

Add to `back_dev_home/_auth/tests/test_directory.py`:

```python
from back_dev_home._auth.directory import Probe, probe_member


def test_home_probes_as_unavailable(monkeypatch):
    """Home has no Redis, so it cannot verify anyone — and must say so rather
    than reporting the fabricated row as a directory hit."""
    monkeypatch.setattr(directory, "get_mode", lambda: "mock")
    directory.reset_cache()
    probe = probe_member("2067928")
    assert probe.status == "unavailable"
    assert probe.member is None


def test_lookup_member_still_returns_the_home_stand_in(monkeypatch):
    """The wrapper's contract is unchanged: GET /api/me keeps showing the
    fabricated name at home even though the probe says 'unavailable'."""
    monkeypatch.setattr(directory, "get_mode", lambda: "mock")
    directory.reset_cache()
    member = directory.lookup_member("2067928")
    assert member is not None
    assert member["emp_nm"] == "홍길동(2067928)"


def test_a_present_row_probes_as_found(monkeypatch):
    monkeypatch.setattr(directory, "get_mode", lambda: "office")
    monkeypatch.setattr(
        directory,
        "redis_client_or_none",
        lambda: _FakeRedis(b'{"emp_nm": "\\uace0\\ub300\\uc601", "dept_nm": "\\uacc4\\uce21"}'),
    )
    directory.reset_cache()
    probe = probe_member("2067928")
    assert probe.status == "found"
    assert probe.member is not None
    assert probe.member["emp_nm"] == "고대영"


def test_a_missing_row_probes_as_absent(monkeypatch):
    """The distinction the whole task exists for: absent is a real, ordinary
    outcome (contractors, service accounts) and must not read the same as an
    outage."""
    monkeypatch.setattr(directory, "get_mode", lambda: "office")
    monkeypatch.setattr(directory, "redis_client_or_none", lambda: _FakeRedis(None))
    directory.reset_cache()
    probe = probe_member("9999999")
    assert probe.status == "absent"
    assert probe.member is None


def test_an_unreachable_redis_probes_as_unavailable(monkeypatch):
    monkeypatch.setattr(directory, "get_mode", lambda: "office")
    monkeypatch.setattr(directory, "redis_client_or_none", lambda: _FakeRedis(_BOOM))
    directory.reset_cache()
    assert probe_member("2067928").status == "unavailable"


def test_an_unconfigured_redis_probes_as_unavailable(monkeypatch):
    monkeypatch.setattr(directory, "get_mode", lambda: "office")
    monkeypatch.setattr(directory, "redis_client_or_none", lambda: None)
    directory.reset_cache()
    assert probe_member("2067928").status == "unavailable"


def test_an_undecodable_row_probes_as_unavailable(monkeypatch):
    """A row we cannot parse means our assumption about the encoding is wrong.
    Rejecting the user for it would blame them for our bug, so it degrades the
    same way an outage does."""
    monkeypatch.setattr(directory, "get_mode", lambda: "office")
    monkeypatch.setattr(directory, "redis_client_or_none", lambda: _FakeRedis(b"not json"))
    directory.reset_cache()
    assert probe_member("2067928").status == "unavailable"
```

Add these helpers near the top of the test file if it does not already have equivalents:

```python
from back_dev_home._auth import directory
from back_dev_home._runtime.office_redis import STORE_ERRORS

_BOOM = object()


class _FakeRedis:
    """Returns `payload` from hget, or raises the store's own error type when
    handed the _BOOM sentinel."""

    def __init__(self, payload):
        self._payload = payload

    def hget(self, key, field):
        if self._payload is _BOOM:
            raise STORE_ERRORS[0]("redis is down")
        return self._payload
```

> `STORE_ERRORS` is `(redis.exceptions.RedisError, OSError)` — a tuple, so
> `STORE_ERRORS[0]("redis is down")` raises a real `RedisError` with no extra
> import (`_runtime/office_redis.py:138`).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest back_dev_home/_auth/tests/test_directory.py -q`
Expected: FAIL — `ImportError: cannot import name 'Probe'`

- [ ] **Step 3: Write the implementation**

In `back_dev_home/_auth/directory.py`, add the `Probe` type after `Member`:

```python
class Probe(NamedTuple):
    """What the directory could tell us about one employee number.

    `lookup_member` collapses every failure into the same bare record, which is
    correct for display — a directory miss must never cost anyone a page. But
    verification has to tell a missing row (reject or flag the person) from an
    unreachable directory (flag nothing, we simply cannot check). This type is
    that distinction, kept for the one caller that needs it.

    `member` is populated only when `status` is "found".
    """

    member: Optional[Member]
    status: str  # "found" | "absent" | "unavailable"
```

Add `NamedTuple` to the `typing` import.

Rewrite `_fetch` to return a `Probe`:

```python
def _fetch(user_id: str) -> Probe:
    # Mode, not is_cloud(). Home has REDIS_HOST set — it points at the office
    # Redis, which is unreachable from here — so "is the client configured"
    # answers yes and then every cold lookup burns the full socket timeout
    # (10s: 5s connect, one retry) before degrading.
    if get_mode() != "office":
        return Probe(None, "unavailable")

    client = redis_client_or_none()
    if client is None:
        logger.warning(
            "office mode but Redis is unconfigured; "
            "member names will be missing for every user"
        )
        return Probe(None, "unavailable")

    try:
        raw = client.hget(MEMBERS_KEY, user_id)
    except STORE_ERRORS as exc:
        logger.warning("member directory unreachable for %s: %s", user_id, exc)
        return Probe(None, "unavailable")

    if raw is None:
        # A real, ordinary outcome: contractors and service accounts hold a
        # LASTUSER cookie without a directory row. Not logged — it would be
        # every request from those users, forever.
        return Probe(None, "absent")

    try:
        return Probe(_decode(raw, user_id), "found")
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        # The one case that means our assumption about the value encoding is
        # wrong. Log it loudly enough to find, then degrade like an outage —
        # never like a missing row, which would blame the user for our bug.
        logger.warning(
            "member document for %s is not the expected JSON object (%s: %s); "
            "first bytes %r",
            user_id,
            type(exc).__name__,
            exc,
            raw[:32],
        )
        return Probe(None, "unavailable")
```

Rename the cache accordingly and add the public probe:

```python
@lru_cache(maxsize=1024)
def _cached(user_id: str, _bucket: int) -> Probe:
    """Cache keyed on (user, time bucket) so entries expire without a sweeper.

    The bucket is part of the key rather than a stored timestamp, so an expiry
    is a cache miss on a new key — no eviction pass, no lock, and a stale entry
    can never be served. lru_cache drops the superseded buckets once maxsize is
    reached.
    """
    return _fetch(user_id)


def probe_member(user_id: str) -> Probe:
    """What the directory knows about `user_id`, failures kept distinct.

    Only verification should call this. Everything that merely displays a name
    wants `lookup_member`, which cannot make the caller forget a branch.
    """
    return _cached(user_id, int(time.time() // _TTL_SECONDS))
```

Rewrite `lookup_member` as the wrapper:

```python
def lookup_member(user_id: Optional[str]) -> Optional[Member]:
    """The person behind a user id, or None if there is no user id.

    Never raises and never returns a half-built record: an unidentified caller
    gets None, and an identified one always gets at least their empno. This is
    the forgiving face of `probe_member` — every failure mode it distinguishes
    collapses to the same bare record here, so no caller has a "lookup failed"
    branch to forget.
    """
    if not user_id:
        return None
    # Home never reaches Redis, and gets a fabricated row so the enriched shape
    # is exercised before it meets the cloud. The probe reports "unavailable"
    # for the same case, because a fabricated row cannot verify anybody.
    if get_mode() != "office":
        return _home_member(user_id)
    return probe_member(user_id).member or bare_member(user_id)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest back_dev_home/_auth -q`
Expected: PASS — including every pre-existing `test_directory.py` test, since `lookup_member`'s contract did not change.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(auth): add probe_member so verification can see the failure

lookup_member returns the same bare record for no-Redis, no-hash, no-row
and undecodable-value, which is right for display and useless for a check
that must reject a missing row but accept an outage. probe_member keeps
the distinction; lookup_member becomes its forgiving wrapper so the
swallow-everything policy lives in one place.

An undecodable row degrades as 'unavailable', not 'absent' - it means our
assumption about the encoding is wrong, and rejecting the user for it
would blame them for our bug.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- back_dev_home/_auth/directory.py back_dev_home/_auth/tests/test_directory.py
```

---

### Task 6: The verification decision, as a pure function

Home has no directory, so the verification path would otherwise never execute here — the mock blind spot `CLAUDE.md` warns about. Extracting the whole §6.2 table into a function that takes a `Probe` makes every row directly testable without Redis, Flask, or a request.

**Files:**

- Create: `back_dev_home/_auth/verify.py`
- Test: `back_dev_home/_auth/tests/test_verify.py`

**Interfaces:**

- Consumes: `Probe`, `Member` (Task 5).
- Produces:
  - `class Decision(NamedTuple): accept: bool; verified: bool; emp_nm: Optional[str]; reason: str`
  - `names_match(entered: str, directory: Optional[str]) -> bool`
  - `decide(probe: Probe, entered_name: str) -> Decision`

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/_auth/tests/test_verify.py`:

```python
"""Verification, tested without a directory.

Home fabricates member rows, so if this logic lived in the route it would never
run here — and would meet a real `members` hash for the first time on the
cloud. Keeping it pure is what lets all four rows of the spec's §6.2 table be
checked on a laptop with no Redis.
"""

import pytest

from back_dev_home._auth.directory import Probe
from back_dev_home._auth.verify import decide, names_match

_MEMBER = {
    "empno": "2067928",
    "emp_nm": "고대영",
    "dept_nm": "계측기술팀",
    "organ_cd": "ORG",
    "upper_organ_nm": "제조기술",
}


def test_an_exact_name_is_accepted_and_verified():
    decision = decide(Probe(_MEMBER, "found"), "고대영")
    assert decision.accept is True
    assert decision.verified is True
    assert decision.emp_nm == "고대영"
    assert decision.reason == "match"


def test_the_directory_name_wins_over_the_entered_one():
    """The entered name is a check, not data: on success we store the
    directory's spelling, which arrives with dept and org attached."""
    decision = decide(Probe(_MEMBER, "found"), "  고대영  ")
    assert decision.emp_nm == "고대영"


def test_surrounding_whitespace_is_forgiven():
    assert names_match("  고대영 ", "고대영") is True


def test_internal_spacing_is_not_forgiven():
    """Two different people can differ only by an internal space; collapsing
    them would let one verify as the other."""
    assert names_match("고 대영", "고대영") is False


def test_a_wrong_name_is_rejected():
    decision = decide(Probe(_MEMBER, "found"), "홍길동")
    assert decision.accept is False
    assert decision.verified is False
    assert decision.reason == "mismatch"


def test_an_absent_row_is_accepted_unverified():
    """The 2026-07-31 revision. directory.py documents contractors and service
    accounts as holding a cookie without a row, so rejecting on absent locks
    out a population the code asserts exists."""
    decision = decide(Probe(None, "absent"), "홍길동")
    assert decision.accept is True
    assert decision.verified is False
    assert decision.reason == "absent"


def test_an_absent_row_keeps_the_entered_name():
    """Storing nothing would leave an employee number with no name at all,
    which defeats attribution — the point of the whole feature."""
    assert decide(Probe(None, "absent"), " 홍길동 ").emp_nm == "홍길동"


def test_an_unavailable_directory_is_accepted_unverified():
    decision = decide(Probe(None, "unavailable"), "홍길동")
    assert decision.accept is True
    assert decision.verified is False
    assert decision.reason == "unavailable"


def test_an_unavailable_directory_keeps_the_entered_name():
    assert decide(Probe(None, "unavailable"), "홍길동").emp_nm == "홍길동"


def test_only_a_name_mismatch_ever_rejects():
    """The single rejecting cell in the table. Stated as its own test so that
    widening rejection later has to delete an assertion that says why."""
    rejected = [
        decide(probe, "홍길동").accept
        for probe in (Probe(None, "absent"), Probe(None, "unavailable"))
    ]
    assert all(rejected)
    assert decide(Probe(_MEMBER, "found"), "홍길동").accept is False


def test_a_found_row_with_no_name_cannot_verify():
    """A partial directory row has an empno and nothing else; there is nothing
    to compare, so it must not silently pass as verified."""
    partial = {**_MEMBER, "emp_nm": None}
    decision = decide(Probe(partial, "found"), "고대영")
    assert decision.verified is False
    assert decision.accept is True
    assert decision.emp_nm == "고대영"


@pytest.mark.parametrize("entered", ["", "   "])
def test_an_empty_entered_name_never_verifies(entered):
    assert decide(Probe(_MEMBER, "found"), entered).verified is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/_auth/tests/test_verify.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'back_dev_home._auth.verify'`

- [ ] **Step 3: Write the implementation**

Create `back_dev_home/_auth/verify.py`:

```python
"""Does the name this person typed match the one the directory holds?

Deliberately pure — no Flask, no Redis, no request. Home fabricates member
rows, so verification would never execute here if it lived in the route, and
would meet a real `members` hash for the first time on the cloud. This is the
mock blind spot `CLAUDE.md` warns about, closed by making the logic testable
without the thing that is missing.

The table below is the spec's §6.2. Exactly one cell rejects.
"""

from __future__ import annotations

from typing import NamedTuple, Optional

from .directory import Probe


class Decision(NamedTuple):
    """What to do with a declaration.

    `emp_nm` is the name to STORE: the directory's spelling when we verified
    against it, the entered one otherwise. It is never None when `accept` is
    True and the user typed something, because an employee number with no name
    attached is exactly the unattributable traffic this feature exists to fix.
    """

    accept: bool
    verified: bool
    emp_nm: Optional[str]
    reason: str  # "match" | "mismatch" | "absent" | "unavailable"


def names_match(entered: str, directory: Optional[str]) -> bool:
    """Exact match after trimming the ends.

    Korean names have no case, so there is no case normalization to do. Internal
    spacing is NOT collapsed: two different people can differ by exactly that,
    and forgiving it would let one of them verify as the other.
    """
    if not directory:
        return False
    return entered.strip() == directory.strip()


def decide(probe: Probe, entered_name: str) -> Decision:
    """Map a directory probe plus the entered name onto an outcome.

    "Cannot check" and "checked and wrong" are opposite answers. Only the
    second rejects; the first accepts and flags, because refusing a person the
    directory simply could not tell us about would deny access on the strength
    of our own outage — or, for `absent`, on the strength of a row that
    `directory.py` itself documents as ordinarily missing for contractors and
    service accounts.
    """
    entered = entered_name.strip()

    if probe.status == "found":
        directory_name = probe.member["emp_nm"] if probe.member else None
        if names_match(entered, directory_name):
            return Decision(True, True, (directory_name or "").strip(), "match")
        if not directory_name:
            # A partial row: an empno and nothing to compare against. Treat it
            # like an unverifiable directory rather than a mismatch — there was
            # never a name here for the user to get wrong.
            return Decision(True, False, entered or None, "unavailable")
        return Decision(False, False, None, "mismatch")

    # absent | unavailable — nothing to compare against, so nothing to reject.
    return Decision(True, False, entered or None, probe.status)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest back_dev_home/_auth/tests/test_verify.py -q`
Expected: PASS — 13 passed

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(auth): decide verification in a pure function

Home fabricates member rows, so this logic would never execute here if it
lived in the route - it would meet a real members hash for the first time
on the cloud. Taking a Probe instead of a user id makes all four rows of
the spec table testable with no Redis and no request.

Exactly one cell rejects: the directory knew this person and the name was
wrong. 'Cannot check' and 'checked and wrong' are opposite answers.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- back_dev_home/_auth/verify.py back_dev_home/_auth/tests/test_verify.py
```

---

### Task 7: `/api/me` and `/api/identify`

**Files:**

- Modify: `back_dev_home/_auth/routes.py`
- Test: `back_dev_home/_auth/tests/test_me_route.py`, `back_dev_home/_auth/tests/test_identify_route.py` (create)

**Interfaces:**

- Consumes: `read_declared`/`write_declared`/`clear_declared` (Task 2), `is_admin_request` (Task 3), `probe_member` (Task 5), `decide` (Task 6).
- Produces:
  - `GET /api/me` → `{user_id, identity_source, is_admin, verified, member}`
  - `POST /api/identify` `{empno, emp_nm}` → 200 with the same shape, or 422
  - `DELETE /api/identify` → 200 with the same shape, now anonymous

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/_auth/tests/test_identify_route.py`:

```python
"""POST/DELETE /api/identify.

No carve-out in the identity gate: /api/identify is an /api/* path like any
other, and it is reachable because the cloud fallback gives every caller the
`anonymous` identity rather than refusing them. A gate with exemptions is how
this repository's last auth bug got in.
"""

import pytest
from flask import Flask

from back_dev_home._auth import routes as routes_mod
from back_dev_home._auth.directory import Probe
from back_dev_home._auth.middleware import install_identity_middleware
from back_dev_home._auth.provider import CloudIdentityProvider

_MEMBER = {
    "empno": "2067928",
    "emp_nm": "고대영",
    "dept_nm": "계측기술팀",
    "organ_cd": "ORG",
    "upper_organ_nm": "제조기술",
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(routes_mod, "is_blocked", lambda user_id: False, raising=False)
    app = Flask(__name__)
    app.secret_key = "test-key-not-the-real-one"
    install_identity_middleware(app, CloudIdentityProvider())
    app.register_blueprint(routes_mod.bp, url_prefix="/api")
    return app.test_client()


def _probe(monkeypatch, probe):
    monkeypatch.setattr(routes_mod, "probe_member", lambda user_id: probe)


def test_a_matching_name_is_accepted_and_verified(client, monkeypatch):
    _probe(monkeypatch, Probe(_MEMBER, "found"))
    response = client.post("/api/identify", json={"empno": "2067928", "emp_nm": "고대영"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["user_id"] == "2067928"
    assert body["identity_source"] == "declared"
    assert body["verified"] is True


def test_the_identity_survives_the_next_request(client, monkeypatch):
    """The session round trip — the declaration is worthless if it does not
    outlive the POST that made it."""
    _probe(monkeypatch, Probe(_MEMBER, "found"))
    client.post("/api/identify", json={"empno": "2067928", "emp_nm": "고대영"})
    body = client.get("/api/me").get_json()
    assert body["user_id"] == "2067928"
    assert body["identity_source"] == "declared"


def test_a_wrong_name_is_refused_with_422(client, monkeypatch):
    _probe(monkeypatch, Probe(_MEMBER, "found"))
    response = client.post("/api/identify", json={"empno": "2067928", "emp_nm": "홍길동"})
    assert response.status_code == 422


def test_a_refused_declaration_leaves_the_caller_anonymous(client, monkeypatch):
    _probe(monkeypatch, Probe(_MEMBER, "found"))
    client.post("/api/identify", json={"empno": "2067928", "emp_nm": "홍길동"})
    assert client.get("/api/me").get_json()["user_id"] == "anonymous"


def test_an_absent_row_is_accepted_unverified(client, monkeypatch):
    _probe(monkeypatch, Probe(None, "absent"))
    response = client.post("/api/identify", json={"empno": "9999999", "emp_nm": "홍길동"})
    assert response.status_code == 200
    assert response.get_json()["verified"] is False


def test_a_missing_empno_is_422(client, monkeypatch):
    _probe(monkeypatch, Probe(_MEMBER, "found"))
    response = client.post("/api/identify", json={"emp_nm": "고대영"})
    assert response.status_code == 422


def test_a_declared_identity_is_never_admin(client, monkeypatch):
    """The feature's only server-side boundary, checked end to end: typing the
    admin's employee number into the form must not produce an admin session."""
    monkeypatch.setenv("SKEWNONO_ADMIN_USERS", "2067928")
    from back_dev_home._auth import admin

    admin._parse_allowlist.cache_clear()
    _probe(monkeypatch, Probe(_MEMBER, "found"))
    body = client.post(
        "/api/identify", json={"empno": "2067928", "emp_nm": "고대영"}
    ).get_json()
    assert body["is_admin"] is False
    admin._parse_allowlist.cache_clear()


def test_delete_clears_the_declaration(client, monkeypatch):
    _probe(monkeypatch, Probe(_MEMBER, "found"))
    client.post("/api/identify", json={"empno": "2067928", "emp_nm": "고대영"})
    body = client.delete("/api/identify").get_json()
    assert body["user_id"] == "anonymous"
    assert client.get("/api/me").get_json()["identity_source"] == "anonymous"


def test_delete_with_nothing_declared_is_not_an_error(client):
    assert client.delete("/api/identify").status_code == 200


def test_the_declared_ip_is_recorded(client, monkeypatch):
    _probe(monkeypatch, Probe(_MEMBER, "found"))
    client.post(
        "/api/identify",
        json={"empno": "2067928", "emp_nm": "고대영"},
        environ_overrides={"REMOTE_ADDR": "10.251.122.42"},
    )
    from back_dev_home._auth.self_id import read_declared

    with client.session_transaction() as session:
        assert session["declared"]["declared_from"] == "10.251.122.42"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/_auth/tests/test_identify_route.py -q`
Expected: FAIL — 404 on `/api/identify`

- [ ] **Step 3: Write the implementation**

Replace `back_dev_home/_auth/routes.py`'s imports and add the routes:

```python
from flask import Blueprint, g, jsonify, request

from .admin import is_admin_request
from .directory import lookup_member, probe_member
from .self_id import clear_declared, read_declared, write_declared
from .verify import decide

bp = Blueprint("auth", __name__)


def _identity_payload():
    """The one shape every identity endpoint returns.

    /api/me, a successful declaration and a cleared declaration all answer with
    this, so the SPA has a single parser and no endpoint-specific branches.
    """
    user_id = g.user_id
    declared = read_declared()
    return {
        "user_id": user_id,
        "identity_source": getattr(g, "identity_source", None),
        # is_admin_request, NOT is_admin: the latter answers "is this id an
        # admin", which is True for a declared identity that typed an admin's
        # employee number. The server would refuse those calls anyway, but
        # rendering the admin surfaces at all invites the bug report.
        "is_admin": is_admin_request(),
        # Only meaningful for a declared identity; a cookie identity is not
        # "verified", it is authoritative.
        "verified": bool(declared and declared["verified"]),
        "member": lookup_member(user_id),
    }
```

Then `/me` becomes:

```python
@bp.get("/me")
def me():
    """The caller's identity, enriched from the member directory.

    Always reachable: every phase's provider supplies a fallback identity, so
    there is no unidentified caller for this endpoint to refuse. `member`
    always carries an `empno`; every other field is None when the directory has
    no row (see `directory.py`).
    """
    return jsonify(_identity_payload())
```

And the new endpoint:

```python
@bp.post("/identify")
def identify():
    """Accept an employee number and name the caller typed for themselves.

    No carve-out was added to the identity gate for this path. It does not need
    one: the cloud provider gives every caller `anonymous`, so an unidentified
    visitor reaches this route as a normal identified request. A gate with
    exemptions is how the Phase 3 redirect loop got in.
    """
    body = request.get_json(silent=True) or {}
    empno = str(body.get("empno") or "").strip()
    entered_name = str(body.get("emp_nm") or "").strip()

    if not empno:
        return (
            jsonify({"error": "invalid_input", "message": "사번을 입력해 주세요"}),
            422,
        )

    decision = decide(probe_member(empno), entered_name)
    if not decision.accept:
        # Deliberately the same message whatever the reason, so the response
        # is not a probe for which employee numbers the directory holds.
        return (
            jsonify(
                {
                    "error": "not_verified",
                    "message": "사번 또는 이름이 확인되지 않습니다",
                }
            ),
            422,
        )

    write_declared(
        empno=empno,
        emp_nm=decision.emp_nm,
        verified=decision.verified,
        declared_from=request.remote_addr,
    )
    # Re-point the request's own identity so the payload below describes the
    # caller they just became, not the anonymous one they arrived as.
    g.user_id = empno
    g.identity_source = "declared"
    return jsonify(_identity_payload())


@bp.delete("/identify")
def unidentify():
    """"본인이 아닙니다" — drop the declaration.

    Safe when there is none: this is reachable from a page whose session may
    already have expired, and an error on a button that means "undo" is worse
    than a no-op.
    """
    clear_declared()
    user_id, source = _current_app_fallback()
    g.user_id = user_id
    g.identity_source = source
    return jsonify(_identity_payload())
```

Add the small helper the DELETE needs, so the response describes who the caller is *now*:

```python
def _current_app_fallback():
    """The identity this phase gives a caller with no cookie and no session."""
    from .._runtime.env import is_cloud
    from .provider import CloudIdentityProvider, LocalIdentityProvider

    provider = CloudIdentityProvider() if is_cloud() else LocalIdentityProvider()
    return provider.fallback_identity()
```

> A cookie-identified caller who calls DELETE keeps their cookie identity on
> the *next* request, because the chain re-runs. The fallback above only
> describes this response. That is acceptable: the button is only shown to
> declared identities.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest back_dev_home/_auth -q`
Expected: PASS. Update `test_me_route.py` for the two new keys (`identity_source`, `verified`) if it asserts the payload exactly.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(auth): add POST/DELETE /api/identify and extend /api/me

One payload shape for every identity endpoint so the SPA has a single
parser. is_admin_request rather than is_admin, so a declared identity that
typed an admin's employee number does not get admin surfaces rendered for
it. Rejection uses one message for every reason, so the response is not a
probe for which employee numbers the directory holds.

No carve-out in the identity gate: the cloud fallback makes every caller
identified, so /api/identify is reachable as an ordinary request.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- back_dev_home/_auth/routes.py back_dev_home/_auth/tests/test_identify_route.py \
     back_dev_home/_auth/tests/test_me_route.py
```

---

### Task 8: `identity_source` in the activity log

Without this the log still shows one undifferentiated `anonymous` stream, which is the problem the whole feature exists to solve.

**Files:**

- Modify: `back_dev_home/_logging/activity.py`
- Test: `back_dev_home/_logging/tests/test_activity_middleware.py` (a `conftest.py` already sits beside it — reuse its app fixture rather than building another)

**Interfaces:**

- Consumes: `g.identity_source` (Task 4).
- Produces: every activity document carries an `identity_source` key.

- [ ] **Step 1: Write the failing test**

Add to the activity test module:

```python
def test_the_document_records_the_identity_source(app_ctx):
    """A log that cannot tell a declared identity from a cookie one is the
    problem this feature exists to fix: without this field, an infrastructure
    misconfiguration and a genuine anonymous visitor merge into one row."""
    from flask import g

    g.user_id = "2067928"
    g.identity_source = "declared"
    extra = activity._build_extra(
        event="request",
        status=200,
        ms=3,
        user_id="2067928",
        remote="10.0.0.1",
        feature=None,
        error_code=None,
        error_name=None,
    )
    assert extra["identity_source"] == "declared"


def test_a_missing_identity_source_records_none(app_ctx):
    """Startup probes and error paths can log before the chain ran; the field
    must be absent-as-None rather than raising inside the logger."""
    extra = activity._build_extra(
        event="request",
        status=500,
        ms=1,
        user_id=None,
        remote="-",
        feature=None,
        error_code=None,
        error_name=None,
    )
    assert extra["identity_source"] is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/_logging -q`
Expected: FAIL — `KeyError: 'identity_source'`

- [ ] **Step 3: Write the implementation**

In `_build_extra`, add one key to the returned dict, next to `user_id`:

```python
        "user_id": str(user_id) if user_id not in (None, "-") else None,
        # How we know who this is. `anonymous` traffic is only actionable if a
        # declared identity is distinguishable from an infrastructure one — a
        # log that merges them is exactly the silence this feature removes.
        "identity_source": getattr(g, "identity_source", None),
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest back_dev_home/_logging -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(logging): record identity_source on every activity document

An 'anonymous' row is only actionable if a declared identity is
distinguishable from an infrastructure-supplied one. Reads defensively so
paths that log before the identity chain ran record None instead of
raising inside the logger.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- back_dev_home/_logging/activity.py back_dev_home/_logging/tests/
```

---

### Task 9: Secret key, session lifetime, and conditional ProxyFix

**Files:**

- Modify: `back_dev_home/__init__.py`
- Test: `tests/test_app_factory_session.py` (create)

**Interfaces:**

- Consumes: nothing.
- Produces: `create_app()` raises `RuntimeError` under `is_cloud()` with no `SKEWNONO_SECRET_KEY`; `app.permanent_session_lifetime == timedelta(days=30)`; `ProxyFix` applied only when `SKEWNONO_TRUST_PROXY` is truthy.

- [ ] **Step 1: Write the failing test**

Create `tests/test_app_factory_session.py`:

```python
"""Boot-time configuration for the declared-identity session.

The signature on that session is the only thing making its `verified` flag
mean anything, so a missing key is not a warning — on the cloud it is a refusal
to start. Home keeps the fallback: there is nothing to forge there.
"""

from datetime import timedelta

import pytest

from back_dev_home import create_app


@pytest.fixture
def cloud(monkeypatch):
    monkeypatch.setattr("back_dev_home._runtime.env.is_cloud", lambda: True)


def test_the_cloud_refuses_to_boot_without_a_secret_key(monkeypatch, cloud):
    """Silent forgeability becomes a startup error, surfaced once at deploy
    rather than never."""
    monkeypatch.delenv("SKEWNONO_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SKEWNONO_SECRET_KEY"):
        create_app()


def test_a_blank_secret_key_is_treated_as_absent(monkeypatch, cloud):
    """`SKEWNONO_SECRET_KEY=` in a .env reads as "" — which is not None and
    would otherwise sail past a presence check into an unsigned session."""
    monkeypatch.setenv("SKEWNONO_SECRET_KEY", "   ")
    with pytest.raises(RuntimeError, match="SKEWNONO_SECRET_KEY"):
        create_app()


def test_the_cloud_boots_with_a_key(monkeypatch, cloud):
    monkeypatch.setenv("SKEWNONO_SECRET_KEY", "any-non-empty-value")
    app = create_app()
    assert app.secret_key == "any-non-empty-value"


def test_home_boots_without_one(monkeypatch):
    monkeypatch.delenv("SKEWNONO_SECRET_KEY", raising=False)
    app = create_app()
    assert app.secret_key


def test_the_session_lasts_thirty_days(monkeypatch):
    app = create_app()
    assert app.permanent_session_lifetime == timedelta(days=30)


def test_proxyfix_is_off_by_default(monkeypatch):
    """Trusting X-Forwarded-For while directly exposed lets anyone forge their
    own IP by setting a header — so it is opt-in, not detected."""
    monkeypatch.delenv("SKEWNONO_TRUST_PROXY", raising=False)
    app = create_app()
    assert not _has_proxyfix(app)


def test_proxyfix_is_applied_when_the_flag_is_set(monkeypatch):
    monkeypatch.setenv("SKEWNONO_TRUST_PROXY", "1")
    app = create_app()
    assert _has_proxyfix(app)


def _has_proxyfix(app) -> bool:
    from werkzeug.middleware.proxy_fix import ProxyFix

    return isinstance(app.wsgi_app, ProxyFix)
```

> `create_app()` loads `back_dev_home/.env`, which on this machine now sets
> `SKEWNONO_SECRET_KEY`. `monkeypatch.delenv` runs before `create_app`, but
> `load_dotenv` re-adds it — check whether `load_dotenv` is called with
> `override=False` (the default, which does NOT overwrite an existing var but
> DOES set a deleted one). If these tests prove flaky for that reason, patch
> `back_dev_home.load_dotenv` to a no-op in the fixture and note it.

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_app_factory_session.py -q`
Expected: FAIL — no `RuntimeError`; the factory currently defaults the key.

- [ ] **Step 3: Write the implementation**

In `back_dev_home/__init__.py`, replace the `app.secret_key` line with:

```python
    # The declared identity (self_id.py) rides in a signed session cookie, and
    # its `verified` flag is only a claim the signature makes credible. A
    # default key is a public constant in this repository, so on the cloud a
    # missing value is not a weak configuration — it is an unsigned session
    # that still looks signed. Refuse to start instead: the failure then
    # appears once, at deploy, rather than never.
    #
    # The gate asks whether a value was CHOSEN, not whether it is strong.
    secret = (os.environ.get("SKEWNONO_SECRET_KEY") or "").strip()
    if not secret:
        if is_cloud():
            raise RuntimeError(
                "SKEWNONO_SECRET_KEY is required on the cloud: it signs the "
                "self-identification session, whose `verified` flag is "
                "forgeable without it. Set any non-empty value in "
                "/project/workSpace/back_dev_home/.env and restart."
            )
        secret = "dev-only-not-for-prod"
    app.secret_key = secret

    # Only sessions marked permanent get a lifetime, and self_id.write_declared
    # marks them. 30 days matches the spec's §5.
    app.permanent_session_lifetime = timedelta(days=30)
```

Add the imports at the top of the file:

```python
from datetime import timedelta
```

Then, after `install_activity_logging(app)`, add:

```python
    # wsgi.ini exposes http-socket directly today, so request.remote_addr is
    # already the real client IP and trusting X-Forwarded-For would let anyone
    # forge their own address with a header. But wsgi.ini:20-24 documents the
    # nginx move, and making it would silently record every request as
    # 127.0.0.1 with no error. Opt-in, so the trust is a deployment decision
    # rather than something this code guesses.
    if (os.environ.get("SKEWNONO_TRUST_PROXY") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_app_factory_session.py -q`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: no regressions. `create_app()` is exercised by many tests; if any now fail on the secret key, they are running under a patched `is_cloud` and need `SKEWNONO_SECRET_KEY` set in their fixture.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(auth): require a secret key on the cloud, add 30-day sessions

app.secret_key defaulted to a constant committed to this repo, and the env
var was absent from .env - so the cloud would have signed sessions with a
public string and said nothing. Under is_cloud() a missing or blank value
now refuses the boot; home keeps the fallback since there is nothing to
forge there. The gate asks whether a value was chosen, not whether it is
strong.

ProxyFix is opt-in via SKEWNONO_TRUST_PROXY: while http-socket is exposed
directly, trusting X-Forwarded-For would let anyone forge their own IP.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- back_dev_home/__init__.py tests/test_app_factory_session.py
```

---

### Task 10: Frontend input helper and identity composable

**Files:**

- Create: `front-dev-home/app/utils/identityInput.ts`
- Create: `front-dev-home/app/utils/identityInput.test.ts`
- Create: `front-dev-home/app/composables/useIdentity.ts`

**Interfaces:**

- Consumes: `GET /api/me`, `POST /api/identify`, `DELETE /api/identify` (Task 7).
- Produces:
  - `normalizeEmpno(raw: string): string`
  - `validateIdentityInput(empno: string, empNm: string): string | null` — the error message, or null when valid
  - `useIdentity()` → `{ identity, pending, isAnonymous, refresh, identify, signOut }`

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/identityInput.test.ts`:

```ts
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { normalizeEmpno, validateIdentityInput } from './identityInput'

describe('normalizeEmpno', () => {
  it('trims surrounding whitespace', () => {
    assert.equal(normalizeEmpno('  2067928 '), '2067928')
  })

  it('strips inner spaces a copy-paste can carry', () => {
    assert.equal(normalizeEmpno('206 7928'), '2067928')
  })

  it('leaves an X-prefixed id intact', () => {
    // X-prefixed ids are real member ids that access control blocks later.
    // Mangling them here would turn a clear "blocked" screen into a confusing
    // "not found".
    assert.equal(normalizeEmpno(' x1234567 '), 'x1234567')
  })
})

describe('validateIdentityInput', () => {
  it('accepts a normal pair', () => {
    assert.equal(validateIdentityInput('2067928', '고대영'), null)
  })

  it('rejects an empty employee number', () => {
    assert.match(validateIdentityInput('', '고대영') ?? '', /사번/)
  })

  it('rejects a whitespace-only employee number', () => {
    assert.match(validateIdentityInput('   ', '고대영') ?? '', /사번/)
  })

  it('rejects an empty name', () => {
    assert.match(validateIdentityInput('2067928', '  ') ?? '', /이름/)
  })

  it('reports the employee number first when both are empty', () => {
    // One message at a time: the form shows a single error line, and the
    // employee number is the field the user fills first.
    assert.match(validateIdentityInput('', '') ?? '', /사번/)
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd front-dev-home && npm test`
Expected: FAIL — cannot find module `./identityInput`

- [ ] **Step 3: Write the helper**

Create `front-dev-home/app/utils/identityInput.ts`:

```ts
/**
 * Pure input handling for the self-identification form.
 *
 * Split out from the page because `npm test` runs `node --test` over pure
 * functions only — there is no component mounting harness in this repo, so
 * anything left inside a `.vue` file is verified by hand or not at all.
 */

/**
 * An employee number as the backend expects it.
 *
 * Inner spaces are removed because a copy-paste out of a directory or a chat
 * message routinely carries them, and the resulting lookup would miss for a
 * reason the user cannot see. Case is left alone: X-prefixed ids are real
 * member ids that access control blocks downstream, and normalizing them here
 * would turn a clear "blocked" screen into a confusing "not found".
 */
export const normalizeEmpno = (raw: string): string => raw.replace(/\s+/g, '')

/**
 * The error to show, or null when the pair is worth sending.
 *
 * Only presence is checked. Format is deliberately not: the authority on which
 * employee numbers exist is the `members` directory, and a client-side pattern
 * would eventually disagree with it — rejecting a real person on the strength
 * of a guess made here.
 */
export const validateIdentityInput = (empno: string, empNm: string): string | null => {
  if (!normalizeEmpno(empno)) return '사번을 입력해 주세요'
  if (!empNm.trim()) return '이름을 입력해 주세요'
  return null
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd front-dev-home && npm test`
Expected: PASS

- [ ] **Step 5: Write the composable**

Create `front-dev-home/app/composables/useIdentity.ts`:

```ts
/**
 * Who the SPA thinks the caller is.
 *
 * One `useState` cell shared by the route middleware, the identify page and
 * anything that greets the user by name — the middleware runs on every
 * navigation, so a per-caller fetch would put a request in front of each one.
 *
 * Not persisted: the identity's real home is the Flask session cookie, and a
 * localStorage copy could disagree with it after a logout in another tab.
 */

export interface Member {
  empno: string
  emp_nm: string | null
  dept_nm: string | null
  organ_cd: string | null
  upper_organ_nm: string | null
}

export type IdentitySource = 'token' | 'cookie' | 'declared' | 'local' | 'anonymous'

export interface Identity {
  user_id: string
  identity_source: IdentitySource | null
  is_admin: boolean
  verified: boolean
  member: Member | null
}

export const useIdentity = () => {
  const identity = useState<Identity | null>('identity', () => null)
  const pending = useState<boolean>('identity-pending', () => false)

  /** True only when the backend gave us the shared fallback id. A `declared`
   * identity is weak but attributable, so it is NOT anonymous. */
  const isAnonymous = computed(() => identity.value?.identity_source === 'anonymous')

  const refresh = async () => {
    pending.value = true
    try {
      identity.value = await $fetch<Identity>('/api/me')
    } catch {
      // A failed /api/me must not strand the SPA: leaving `identity` null lets
      // the middleware fall through rather than trapping the user on a gate it
      // cannot evaluate.
      identity.value = null
    } finally {
      pending.value = false
    }
  }

  /** Declare an identity. Returns null on success, or the server's message. */
  const identify = async (empno: string, empNm: string): Promise<string | null> => {
    try {
      identity.value = await $fetch<Identity>('/api/identify', {
        method: 'POST',
        body: { empno, emp_nm: empNm },
      })
      return null
    } catch (error: unknown) {
      const message = (error as { data?: { message?: string } })?.data?.message
      return message ?? '확인에 실패했습니다. 잠시 후 다시 시도해 주세요'
    }
  }

  const signOut = async () => {
    identity.value = await $fetch<Identity>('/api/identify', { method: 'DELETE' })
  }

  return { identity, pending, isAnonymous, refresh, identify, signOut }
}
```

- [ ] **Step 6: Typecheck and lint**

Run: `cd front-dev-home && npm run typecheck && npm run lint`
Expected: clean

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(identity): add the identity composable and input helpers

One useState cell shared by the middleware, the page and anything greeting
the user - the middleware runs per navigation, so a per-caller fetch would
put a request in front of each one. Deliberately not persisted: the real
home is the Flask session cookie, and a localStorage copy could disagree
after a logout in another tab.

Input validation checks presence only. The authority on which employee
numbers exist is the members directory; a client-side pattern would
eventually disagree and reject a real person on a guess.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- front-dev-home/app/utils/identityInput.ts \
     front-dev-home/app/utils/identityInput.test.ts \
     front-dev-home/app/composables/useIdentity.ts
```

---

### Task 11: The `/identify` page

**Files:**

- Create: `front-dev-home/app/pages/identify.vue`

**Interfaces:**

- Consumes: `useIdentity()`, `validateIdentityInput` (Task 10).
- Produces: a route at `/identify` accepting `?next=<path>`.

- [ ] **Step 1: Read the design language first**

Read `DESIGN.md` before writing any markup. Colors come from `--sk-*` tokens only — never inline hex. Where the code and `DESIGN.md` disagree, `DESIGN.md` wins.

- [ ] **Step 2: Write the page**

Create `front-dev-home/app/pages/identify.vue`:

```vue
<script setup lang="ts">
/**
 * Self-identification. Shown to a caller the infrastructure could not name.
 *
 * Deliberately not a login screen, and worded so: there is no password, no
 * account, and the result is weaker than a cookie identity. Presenting it as
 * authentication would promise a guarantee this layer does not make.
 */
import { validateIdentityInput, normalizeEmpno } from '~/utils/identityInput'

const route = useRoute()
const router = useRouter()
const { identify } = useIdentity()

const empno = ref('')
const empNm = ref('')
const error = ref<string | null>(null)
const submitting = ref(false)

/** Only same-origin paths: `next` arrives in the URL, so an absolute URL here
 * would make this form an open redirect. */
const nextPath = computed(() => {
  const raw = route.query.next
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//')
    ? value
    : '/'
})

const submit = async () => {
  error.value = validateIdentityInput(empno.value, empNm.value)
  if (error.value) return

  submitting.value = true
  error.value = await identify(normalizeEmpno(empno.value), empNm.value.trim())
  submitting.value = false

  if (!error.value) await router.replace(nextPath.value)
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center p-6">
    <UCard class="w-full max-w-md">
      <template #header>
        <h1 class="text-lg font-medium">사용자 확인</h1>
        <p class="mt-1 text-sm text-[var(--sk-ink-muted)]">
          접속하신 분을 확인할 수 없습니다. 사번과 이름을 입력해 주세요.
        </p>
      </template>

      <form class="space-y-4" @submit.prevent="submit">
        <UFormField label="사번" name="empno">
          <UInput
            v-model="empno"
            autofocus
            autocomplete="off"
            placeholder="2067928"
            :disabled="submitting"
          />
        </UFormField>

        <UFormField label="이름" name="emp_nm">
          <UInput
            v-model="empNm"
            autocomplete="off"
            placeholder="홍길동"
            :disabled="submitting"
          />
        </UFormField>

        <UAlert v-if="error" color="error" variant="subtle" :description="error" />

        <UButton type="submit" block :loading="submitting">확인</UButton>
      </form>

      <template #footer>
        <p class="text-xs text-[var(--sk-ink-muted)]">
          입력하신 정보는 활동 기록에 사용됩니다. 로그인 절차가 아니며,
          비밀번호는 필요하지 않습니다.
        </p>
      </template>
    </UCard>
  </div>
</template>
```

- [ ] **Step 3: Typecheck and lint**

Run: `cd front-dev-home && npm run typecheck && npm run lint`
Expected: clean. Confirm the NuxtUI component names against this repo's version — `UFormField` is v3; older code may use `UFormGroup`. Grep an existing form page before assuming.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(identity): add the /identify form

Worded as 'user confirmation', not login: there is no password and the
result is weaker than a cookie identity, so presenting it as
authentication would promise a guarantee this layer does not make.

next= is restricted to same-origin paths - it arrives in the URL, and an
absolute value would make the form an open redirect.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- front-dev-home/app/pages/identify.vue
```

---

### Task 12: The route middleware that sends anonymous callers to the form

**Files:**

- Create: `front-dev-home/app/middleware/identify.global.ts`

**Interfaces:**

- Consumes: `useIdentity()` (Task 10), the `/identify` route (Task 11).
- Produces: an anonymous caller landing on any route is redirected to `/identify?next=<their path>`.

- [ ] **Step 1: Write the middleware**

Create `front-dev-home/app/middleware/identify.global.ts`:

```ts
/**
 * Send a caller nobody could identify to the self-identification form.
 *
 * This gate is CLIENT-side on purpose. The server-side version of it would
 * have to live in Flask's first `before_request`, where returning a response
 * answers index.html and every bundle with it — the exact shape of the Phase 3
 * blank-window deploy. A Nuxt route middleware can only affect routing, so the
 * worst it can do is send someone to the wrong page.
 *
 * It is therefore UX, not a security boundary: `curl` bypasses it entirely.
 * The one rule that IS enforced server-side is that a declared identity can
 * never be an admin (`_auth/admin.py`).
 */
export default defineNuxtRouteMiddleware(async (to) => {
  // Server-side rendering is off for this app, but the middleware still runs
  // during prerender in some Nuxt paths; there is no session to consult there.
  if (import.meta.server) return

  if (to.path === '/identify') return

  const { identity, isAnonymous, refresh } = useIdentity()
  if (identity.value === null) await refresh()

  // A failed /api/me leaves identity null. Fall through rather than trapping
  // the user on a gate that could not evaluate them — the backend is the thing
  // that actually refuses data.
  if (identity.value === null) return
  if (!isAnonymous.value) return

  return navigateTo({ path: '/identify', query: { next: to.fullPath } })
})
```

- [ ] **Step 2: Typecheck and lint**

Run: `cd front-dev-home && npm run typecheck && npm run lint`
Expected: clean

- [ ] **Step 3: Verify by hand — there is no E2E suite**

Follow the `verify` skill. Start Flask (`.venv/bin/python index.py`) and Nuxt (`npm run dev`), then drive Playwright MCP:

1. **Home, default** — visit `http://localhost:3000/`. Identity is `local-dev` / `local`, so the form must NOT appear, and the admin surfaces must still be present. This is the regression from Task 3 seen end to end.
2. **Anonymous** — the home provider always supplies `local-dev`, so force the cloud path: set `SKEWNONO_ADMIN_USERS` aside and temporarily run Flask with the cloud provider, or clear the cookie and stub `/api/me` to return `identity_source: "anonymous"` in devtools. Confirm the redirect to `/identify?next=/`.
3. **Declare** — submit an employee number and any name. Home probes as `unavailable`, so it must be accepted with `verified: false`, and the app must land back on `next`.
4. **Reload** — the declared identity survives, since it is in the session cookie.
5. **Blank-screen check** — with the SPA running, confirm `GET /` still returns HTML (`curl -sI http://localhost:5050/`). A blank window here means something started answering page requests from the identity gate.

Save screenshots under `.playwright-mcp/screenshots/`.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(identity): redirect anonymous callers to /identify

Client-side on purpose. The server-side version lives in Flask's first
before_request, where returning a response answers index.html and every
bundle with it - the exact shape of the Phase 3 blank-window deploy. A
route middleware can only affect routing.

A failed /api/me falls through rather than trapping the user on a gate
that could not evaluate them; the backend is what actually refuses data.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- front-dev-home/app/middleware/identify.global.ts
```

---

### Task 13: Documentation

**Files:**

- Modify: `docs/deployment.md`
- Modify: `docs/datatables/members.txt`

(`back_dev_home/_auth/` has no README — the module docstrings carry that weight. Do not add one.)

**Interfaces:**

- Consumes: everything above.
- Produces: no code.

- [ ] **Step 1: Update `docs/deployment.md`**

Add `SKEWNONO_SECRET_KEY` to the cloud setup steps as a **required** item, in Korean with `~입니다.` / `~합니다.` endings, stating that the app refuses to start without it and that any non-empty value satisfies the check. Mention `SKEWNONO_TRUST_PROXY` in the same section: it must be set only if the app moves behind nginx, and setting it while `http-socket` is exposed directly lets a caller forge their own IP.

- [ ] **Step 2: Update `docs/datatables/members.txt`**

Record that the `members` hash is now read by two callers with different needs: `lookup_member` for display and `probe_member` for verification. Note the office-verify item that remains — the real proportion of employee numbers with no `members` row, which decides whether the `absent` row is eventually tightened from "accept unverified" back to a rejection. Mark it `OFFICE-VERIFY`.

- [ ] **Step 3: Lint**

Run: `npm run lint:md`
Expected: 0 errors

- [ ] **Step 4: Full suite and frontend gates**

Run:

```bash
.venv/bin/python -m pytest -q
cd front-dev-home && npm test && npm run typecheck && npm run lint
```

Expected: backend well above the 1887 baseline (this plan adds roughly 45 tests), frontend clean.

- [ ] **Step 5: Commit**

```bash
git commit -m "docs(auth): document the secret key requirement and members reads

SKEWNONO_SECRET_KEY is now a required cloud setting - the app refuses to
start without it - and SKEWNONO_TRUST_PROXY must stay unset until the app
actually moves behind nginx. members.txt records the two readers the hash
now has and keeps the OFFICE-VERIFY item for the real miss rate, which
decides whether 'absent' is ever tightened back to a rejection.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- docs/deployment.md docs/datatables/members.txt
```

---

## Spec Coverage

| Spec section | Task |
| --- | --- |
| §3 identity priority, `local` source | 1, 4 |
| §4 client-side gate | 12 |
| §5 signed session, 30-day lifetime | 2, 9 |
| §5.1 secret key required on cloud | 9 |
| §6.1 `probe_member`, `lookup_member` wrapper | 5 |
| §6.2 comparison rules, `absent` accepted, home branch | 6 |
| §7 `is_admin_request`, `_deny_if_blocked` | 3, 4 |
| §8 `declared_from`, conditional `ProxyFix` | 7, 9 |
| §9 component inventory | 1–12 |
| §10 data flow | 4, 7, 10, 11, 12 |
| §11 error handling | 7, 10, 11 |
| §12 test strategy | every task; hand-verification in 12 |
| §13 risks | 13 (documented), 9 (secret key resolved) |

## Open question for the reviewer

Task 7's `DELETE /api/identify` answers with the *fallback* identity even for a caller who also holds a `LASTUSER` cookie — their cookie identity returns on the next request, since the chain re-runs. The button is only shown to declared identities, so this should never be visible. If you would rather the response always describe the re-run chain exactly, the fix is to factor the chain out of `install_identity_middleware` into a function both it and the route call.
