# 배포 오버레이 번들 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 영구 클라우드 파일과 자격 증명 값은 건드리지 않고, 변경 가능한 런타임 파일만 `/project/workSpace`에 덮어쓰는 배포 번들을 생성합니다.

**Architecture:** `pack.py`는 `index.py`와 `wsgi.ini`를 제외한 오버레이 번들을 만들고 로컬 산출물만 검증합니다. 번들에 실리는 `preflight.py`는 기존 `/project/workSpace`와 합쳐진 최종 상태에서 영구 파일, SPA, 의존성, `hcputil.auth.sso`를 검증합니다. 런타임 인증 로더도 동일한 SSO 모듈 경로만 사용합니다.

**Tech Stack:** Python 3.14, Flask, pytest, pathlib, shutil, importlib, Markdown

## Global Constraints

- 구현 기준 문서는 `docs/superpowers/specs/2026-07-31-deploy-overlay-bundle-design.md`입니다.
- `/project/workSpace/index.py`와 `/project/workSpace/wsgi.ini`는 영구 파일이며 번들에 포함하지 않습니다.
- 클라우드 `/project/workSpace`를 삭제하거나 교체하지 않고 번들 내용을 기존 경로에 덮어씁니다.
- `back_dev_home/.env`는 번들에 포함하고 존재 여부만 검사하며 내부 값은 읽거나 검증하지 않습니다.
- SSO 모듈 경로는 `hcputil.auth.sso`만 지원하고 `hcputil.auto.sso`는 지원하지 않습니다.
- 패커는 저장소 루트에서 `scripts/deploy/pack.py`를 직접 실행하는 방식을 문서화합니다.
- 둘 이상의 구현 파일을 수정하므로 실행 시 별도 git worktree를 사용합니다.
- 기존 작업 트리의 `.remember/` 변경은 수정, 스테이징, 커밋하지 않습니다.

---

### Task 1: 오버레이 패커와 자격 증명 비검사

**Files:**

- Modify: `tests/test_pack_deploy.py`
- Modify: `scripts/deploy/pack.py`

**Interfaces:**

- Consumes: `INCLUDED_ROOTS`, `run_preflight(repo_root, strict=False)`, `copy_bundle(repo_root, dest)`, `verify_bundle(dest)`
- Produces: `index.py`와 `wsgi.ini`를 제외하고 `.env` 값은 읽지 않는 오버레이 번들

- [ ] **Step 1: 영구 파일 제외와 `.env` 비검사 회귀 테스트를 작성합니다**

`tests/test_pack_deploy.py`에 다음 테스트를 추가합니다.

```python
def test_excludes_permanent_cloud_root_files():
    for name in ("index.py", "wsgi.ini"):
        assert name not in pack.INCLUDED_ROOTS


def test_preflight_does_not_require_permanent_cloud_root_files(tmp_path):
    root = _make_repo(tmp_path)
    (root / "index.py").unlink()
    (root / "wsgi.ini").unlink()

    assert pack.blocking_failures(pack.run_preflight(root)) == []


def test_preflight_does_not_inspect_env_values(tmp_path):
    root = _make_repo(tmp_path)
    (root / "back_dev_home" / ".env").write_text(
        "SKEWNONO_SECRET_KEY=dev-only-not-for-prod\n"
    )

    checks = pack.run_preflight(root)

    assert "secret_key" not in {check.name for check in checks}


def test_copy_omits_permanent_cloud_root_files(tmp_path):
    repo = _make_repo(tmp_path)
    dest = tmp_path / "bundle"

    pack.copy_bundle(repo, dest)

    assert not (dest / "index.py").exists()
    assert not (dest / "wsgi.ini").exists()
```

기존 `test_default_secret_key_is_advisory`와 `_read_env` 전용 테스트들은 삭제합니다.
이 테스트들은 제거할 자격 증명 파서의 동작을 고정하므로 새 계약과 충돌합니다.

- [ ] **Step 2: 새 테스트가 기존 코드에서 실패하는지 확인합니다**

Run:

```bash
.venv/bin/python -m pytest tests/test_pack_deploy.py -q
```

Expected: 영구 파일이 여전히 `INCLUDED_ROOTS`에 있고 `secret_key` 검사가 남아 있어 실패합니다.

- [ ] **Step 3: 패커를 최소 변경합니다**

`scripts/deploy/pack.py`의 `INCLUDED_ROOTS`를 다음과 같이 변경합니다.

```python
INCLUDED_ROOTS = (
    "back_dev_home",
    "front-dev-home/.output/public",
    "ops_store",
    "minio_handler",
    "ftp_handler",
)
```

다음을 삭제합니다.

```python
DEFAULT_SECRET_KEY = "dev-only-not-for-prod"
```

```python
def _read_env(path: Path) -> dict[str, str]:
    ...


def _as_the_app_reads_it(value: str) -> str:
    ...
```

`run_preflight()`의 `secret_key` 검사 블록을 삭제하고 `env_present` 차단 검사는
그대로 유지합니다. `verify_bundle()`에서는 다음 로컬 산출물 검사를 삭제합니다.

```python
for name in ("index.py", "wsgi.ini"):
    if not (dest / name).is_file():
        failures.append(f"missing {dest / name}")
```

`RUNBOOK`의 첫 단계는 폴더 교체가 아니라 오버레이임을 명시합니다.

```text
Copy this bundle's contents over the existing `/project/workSpace/`.
Do not delete or replace `/project/workSpace`: its permanent `index.py`
and `wsgi.ini` are intentionally not included in this bundle.
```

두 번째 preflight 설명은 고정된 SSO 경로를 사용합니다.

```text
Run preflight again. Imports should now resolve, including the
cloud-image-provided `hcputil.auth.sso`.
```

마지막 안내는 다음 의미로 바꿉니다.

```text
Next: overlay the contents of <dest>/ onto the existing
/project/workSpace/ then read DEPLOY.md
```

- [ ] **Step 4: 패커 테스트가 통과하는지 확인합니다**

Run:

```bash
.venv/bin/python -m pytest tests/test_pack_deploy.py -q
```

Expected: 모든 `test_pack_deploy.py` 테스트가 통과합니다.

- [ ] **Step 5: 패커 변경을 커밋합니다**

```bash
git add scripts/deploy/pack.py tests/test_pack_deploy.py
git commit -m "refactor(deploy): produce an overlay bundle"
```

---

### Task 2: 클라우드 preflight의 고정 SSO 경로와 `.env` 비검사

**Files:**

- Modify: `tests/test_preflight_cloud.py`
- Modify: `scripts/deploy/preflight_cloud.py`

**Interfaces:**

- Consumes: `check_layout(root)`, `check_imports()`, `check_config(root)`
- Produces: 최종 `/project/workSpace` 상태를 검사하되 `.env` 값은 읽지 않고 `hcputil.auth.sso`만 요구하는 `preflight.py`

- [ ] **Step 1: preflight 계약 테스트를 먼저 변경합니다**

`tests/test_preflight_cloud.py`의 양쪽 철자 허용 테스트를 다음 두 테스트로
교체합니다.

```python
def test_imports_accept_hcputil_auth_sso(monkeypatch):
    monkeypatch.setattr(preflight_cloud, "RUNTIME_PACKAGES", ())
    pkg = types.ModuleType("hcputil")
    pkg.__path__ = []
    sub = types.ModuleType("hcputil.auth")
    sub.__path__ = []
    sso = types.ModuleType("hcputil.auth.sso")
    sso.SSO = object
    monkeypatch.setitem(sys.modules, "hcputil", pkg)
    monkeypatch.setitem(sys.modules, "hcputil.auth", sub)
    monkeypatch.setitem(sys.modules, "hcputil.auth.sso", sso)

    failures, notes = preflight_cloud.check_imports()

    assert failures == []
    assert notes == ["hcputil resolved as hcputil.auth.sso"]


def test_imports_reject_auto_typo(monkeypatch):
    monkeypatch.setattr(preflight_cloud, "RUNTIME_PACKAGES", ())
    attempted = []

    def missing(name):
        attempted.append(name)
        raise ImportError(name)

    monkeypatch.setattr(preflight_cloud.importlib, "import_module", missing)

    failures, _notes = preflight_cloud.check_imports()

    assert attempted == ["hcputil.auth.sso"]
    assert any("hcputil.auth.sso" in failure for failure in failures)
```

기존 `test_config_warns_on_default_secret_key`는 다음 테스트로 교체합니다. 잘못된
UTF-8 바이트는 파일 존재 검사에는 영향을 주지 않지만 내용을 읽는 기존 구현은
`UnicodeDecodeError`를 발생시키므로 비검사 계약을 직접 증명합니다.

```python
def test_config_does_not_read_env_contents(bundle):
    env_path = bundle / "back_dev_home" / ".env"
    env_path.write_bytes(b"\xff")

    assert preflight_cloud.check_config(bundle) == ([], [])
```

`test_config_fails_when_env_missing`과 `check_layout()`의 `index.py`/`wsgi.ini`
검사는 그대로 유지합니다. 이 검사는 오버레이 후 최종 클라우드 상태를 대상으로
합니다.

- [ ] **Step 2: 새 preflight 테스트가 실패하는지 확인합니다**

Run:

```bash
.venv/bin/python -m pytest tests/test_preflight_cloud.py -q
```

Expected: `auto` 전용 stub이 아직 허용되고 잘못된 UTF-8 `.env`를 읽으려 하므로 실패합니다.

- [ ] **Step 3: preflight 구현을 최소 변경합니다**

`scripts/deploy/preflight_cloud.py`에서 다음 상수를 사용합니다.

```python
HCPUTIL_PATH = "hcputil.auth.sso"
```

`check_imports()`의 SSO 검사를 단일 import로 바꿉니다.

```python
try:
    importlib.import_module(HCPUTIL_PATH)
except ImportError as exc:
    failures.append(
        f"IMPORT {HCPUTIL_PATH} unavailable ({exc}). "
        "This is supplied by the cloud image, NOT by requirements.txt. "
        "Without it create_app() raises and uwsgi refuses to start."
    )
else:
    notes.append(f"hcputil resolved as {HCPUTIL_PATH}")
```

`DEFAULT_SECRET_KEY`, `_parse_env()`와 `.env` 내용 읽기/secret 경고를 삭제합니다.
`check_config()`은 다음 존재 검사만 수행합니다.

```python
def check_config(root: Path) -> tuple[list[str], list[str]]:
    env_path = root / "back_dev_home" / ".env"
    if not env_path.is_file():
        return (
            [
                f"MISSING {env_path} — create_app() calls load_dotenv on this path; "
                "without it the app boots unconfigured."
            ],
            [],
        )
    return [], []
```

- [ ] **Step 4: preflight 테스트가 통과하는지 확인합니다**

Run:

```bash
.venv/bin/python -m pytest tests/test_preflight_cloud.py -q
```

Expected: 모든 `test_preflight_cloud.py` 테스트가 통과합니다.

- [ ] **Step 5: preflight 변경을 커밋합니다**

```bash
git add scripts/deploy/preflight_cloud.py tests/test_preflight_cloud.py
git commit -m "fix(deploy): use the confirmed cloud SSO module"
```

---

### Task 3: 런타임 인증 로더의 SSO 오타 제거

**Files:**

- Modify: `back_dev_home/_auth/tests/test_provider.py`
- Modify: `back_dev_home/_auth/provider.py`

**Interfaces:**

- Consumes: `_load_sso_class()`
- Produces: `hcputil.auth.sso.SSO`만 반환하고 다른 철자를 시도하지 않는 런타임 로더

- [ ] **Step 1: 런타임 로더 테스트를 고정 경로 계약으로 변경합니다**

`back_dev_home/_auth/tests/test_provider.py`의 fixture를 `auth` 경로만 설치하도록
단순화합니다.

```python
@pytest.fixture
def stub_hcputil_auth(monkeypatch):
    pkg = types.ModuleType("hcputil")
    pkg.__path__ = []
    sub = types.ModuleType("hcputil.auth")
    sub.__path__ = []
    sso_mod = types.ModuleType("hcputil.auth.sso")
    sso_mod.SSO = _FakeSSO
    monkeypatch.setitem(sys.modules, "hcputil", pkg)
    monkeypatch.setitem(sys.modules, "hcputil.auth", sub)
    monkeypatch.setitem(sys.modules, "hcputil.auth.sso", sso_mod)
```

기존 세 테스트를 다음 계약으로 교체합니다.

```python
def test_loads_auth_sso(stub_hcputil_auth):
    assert _load_sso_class() is _FakeSSO


def test_does_not_fall_back_to_auto_typo(monkeypatch):
    attempted = []

    def missing(name):
        attempted.append(name)
        raise ImportError(name)

    monkeypatch.setattr(
        "back_dev_home._auth.provider.importlib.import_module",
        missing,
    )

    with pytest.raises(ImportError, match=r"hcputil\.auth\.sso"):
        _load_sso_class()

    assert attempted == ["hcputil.auth.sso"]
```

- [ ] **Step 2: 새 런타임 로더 테스트가 실패하는지 확인합니다**

Run:

```bash
.venv/bin/python -m pytest back_dev_home/_auth/tests/test_provider.py -q
```

Expected: 기존 로더가 `hcputil.auto.sso`로 fallback하므로 두 번째 테스트가 실패합니다.

- [ ] **Step 3: 런타임 로더를 단일 import로 변경합니다**

`back_dev_home/_auth/provider.py`의 `_load_sso_class()`를 다음 구현으로 바꿉니다.

```python
def _load_sso_class():
    """Return the cloud image's confirmed SSO class."""
    module_path = "hcputil.auth.sso"
    try:
        return importlib.import_module(module_path).SSO
    except ImportError as exc:
        raise ImportError(
            f"{module_path} is not importable; "
            "the cloud image must provide this SSO module."
        ) from exc
```

`auto` 철자의 불확실성을 설명하는 기존 docstring과 주석은 제거합니다.

- [ ] **Step 4: 런타임 인증 테스트가 통과하는지 확인합니다**

Run:

```bash
.venv/bin/python -m pytest back_dev_home/_auth/tests/test_provider.py -q
```

Expected: 모든 provider 테스트가 통과합니다.

- [ ] **Step 5: 런타임 인증 변경을 커밋합니다**

```bash
git add back_dev_home/_auth/provider.py back_dev_home/_auth/tests/test_provider.py
git commit -m "fix(auth): remove the invalid SSO module fallback"
```

---

### Task 4: 배포 문서와 전체 검증

**Files:**

- Modify: `docs/deployment.md`
- Modify: `CLAUDE.md`

**Interfaces:**

- Consumes: Task 1의 오버레이 번들 계약, Task 2/3의 `hcputil.auth.sso` 계약
- Produces: 실제 사무실 PC와 클라우드 절차에 일치하는 단일 배포 안내

- [ ] **Step 1: 공식 배포 문서를 오버레이 절차로 수정합니다**

`docs/deployment.md`에서 다음 내용을 반영합니다.

- 패킹 명령은 저장소 루트에서 직접 실행하는
  `.venv/bin/python scripts/deploy/pack.py`로 표기합니다.
- `dist/skewnono-<타임스탬프>/` 폴더 자체로 `/project/workSpace`를 교체하지 않고,
  폴더 **내용**을 기존 `/project/workSpace`에 덮어쓴다고 명시합니다.
- `/project/workSpace/index.py`와 `/project/workSpace/wsgi.ini`는 영구 파일이며
  번들에 포함되지 않는다고 포함/제외 표에 기록합니다.
- `preflight.py`는 오버레이 후 두 영구 파일의 존재를 검사한다고 설명합니다.
- `hcputil.auth.sso`만 클라우드 이미지가 제공하며 `auto` 철자 설명은 삭제합니다.
- `SKEWNONO_SECRET_KEY` 값 경고가 사라지는지 확인하는 행을 삭제하고,
  `back_dev_home/.env` 존재 여부만 검사한다고 설명합니다.

`CLAUDE.md`의 Phase 3 명령과 전달 문장을 다음 의미로 바꿉니다.

```text
Pack at the office with `python scripts/deploy/pack.py` (after building the
frontend), then overlay the bundle contents onto the existing
`/project/workSpace/` on the cloud host.
```

- [ ] **Step 2: Markdown과 정적 일관성을 검증합니다**

Run:

```bash
npm run lint:md
rg -n "hcputil\\.auto\\.sso|어떤 철자|SKEWNONO_SECRET_KEY.*경고|통째로 클라우드" \
  scripts/deploy back_dev_home/_auth docs/deployment.md CLAUDE.md \
  tests/test_preflight_cloud.py back_dev_home/_auth/tests/test_provider.py
git diff --check
```

Expected: Markdown 오류가 없고, `rg`는 결과가 없으며, whitespace 오류가 없습니다.
과거 설계/계획 문서는 당시 기록이므로 검색 범위에서 의도적으로 제외합니다.

- [ ] **Step 3: 배포 관련 집중 테스트를 실행합니다**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_pack_deploy.py \
  tests/test_preflight_cloud.py \
  back_dev_home/_auth/tests/test_provider.py \
  -q
```

Expected: 모든 집중 테스트가 통과합니다.

- [ ] **Step 4: 전체 백엔드 회귀 테스트를 실행합니다**

Run:

```bash
.venv/bin/python -m pytest tests back_dev_home -q
```

Expected: 전체 백엔드 테스트가 통과합니다.

- [ ] **Step 5: 문서 변경을 커밋합니다**

```bash
git add CLAUDE.md docs/deployment.md
git commit -m "docs(deploy): document the cloud overlay workflow"
```

- [ ] **Step 6: 구현 커밋과 작업 트리 상태를 최종 확인합니다**

Run:

```bash
git status --short
git log -4 --oneline
git diff HEAD~4 --check
```

Expected: 구현 worktree가 깨끗하고, 계획된 패커/preflight/auth/docs 커밋만
최근 이력에 있으며, diff whitespace 오류가 없습니다.
