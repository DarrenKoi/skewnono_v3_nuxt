# contrib

동료가 소유하는 작업 공간 백엔드가 들어오는 자리입니다. `contrib/<slug>/` 한 폴더가
기능 하나이고, 이 아래의 패키지는 **fail-soft** 로 로드됩니다. import 가 실패하거나
`bp` 가 없으면 그 패키지만 건너뛰고 나머지는 정상 부팅합니다. 건너뛴 목록은
`app.config["SKEWNONO_CONTRIB_FAILED"]` 와 부팅 로그에 남습니다. 절차는
[`docs/contributing/in-repo/README.md`](../../docs/contributing/in-repo/README.md) 입니다.
