# 배포 오버레이 번들 설계

## 목적

`scripts/deploy/pack.py`가 클라우드의 기존 `/project/workSpace`를 교체하는
독립형 번들이 아니라, 해당 경로에 덮어쓰는 오버레이 번들을 생성하도록 합니다.
클라우드의 `/project/workSpace/index.py`는 영구 파일이며 배포마다 변경하거나
다시 패킹하지 않습니다.

## 배포 계약

- 로컬 패킹 시 기존 `dist/skewnono-<타임스탬프>/` 출력은 새 결과로 교체합니다.
- 생성된 번들의 내용은 기존 클라우드 `/project/workSpace`에 덮어씁니다.
- 클라우드 `/project/workSpace` 자체를 삭제하거나 통째로 교체하지 않습니다.
- `/project/workSpace/index.py`는 클라우드에 계속 존재해야 합니다.
- `wsgi.ini`와 애플리케이션 코드, 빌드된 SPA 등 변경 가능한 런타임 파일은
  계속 번들에 포함합니다.

## 패커 변경

- `index.py`를 `INCLUDED_ROOTS`에서 제외합니다.
- 로컬 패킹 전 검사는 저장소의 `index.py` 존재 여부를 요구하지 않습니다.
- 로컬 번들 구조 검사는 번들 안의 `index.py` 존재 여부를 요구하지 않습니다.
- 클라우드용 `preflight.py`는 실행 위치인 `/project/workSpace/index.py`를 계속
  검사합니다. 영구 파일이 실제로 유실된 경우 uWSGI 시작 전에 차단해야 하기
  때문입니다.

## 자격 증명 처리

- 패커는 `back_dev_home/.env` 내부 값을 읽거나
  `SKEWNONO_SECRET_KEY`를 검증하지 않습니다.
- `back_dev_home/.env` 파일의 존재 여부는 계속 차단 검사로 유지합니다.
  Flask가 시작할 때 이 파일을 로드하기 때문입니다.
- `.env`와 다른 런타임 자격 증명 파일은 현재와 같이 번들에 포함합니다.

## 오류 처리

- 번들 생성에 필요한 파일이나 디렉터리가 없으면 패킹을 차단합니다.
- 클라우드에서 영구 `index.py`가 없으면 `preflight.py`가 기동을 차단합니다.
- 자격 증명의 값이나 정책 적합성은 패커와 `preflight.py`의 검사 대상에서
  제외합니다.

## 검증

- 패커 단위 테스트에서 `index.py`가 번들에 포함되지 않는지 확인합니다.
- 로컬 번들 검증이 `index.py` 없이 통과하는지 확인합니다.
- 클라우드 preflight 테스트는 `/project/workSpace/index.py`가 없을 때 계속
  실패하는지 확인합니다.
- 패커 검사 결과에 `secret_key` 항목이 없고 `.env` 존재 검사는 유지되는지
  확인합니다.
- 배포 문서가 기존 `/project/workSpace`에 덮어쓰는 절차를 설명하는지
  확인합니다.
