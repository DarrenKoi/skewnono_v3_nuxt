"""ftp_handler.proxy 사용 예제 — 방화벽 안 클라이언트를 위한 HTTP 전송 방식.

두 대의 장비에서 절반씩 실행된다:
  - 서버(SERVER): FTP 서버에 접근 가능한 사내 호스트에서 flask_proxy 실행.
  - 클라이언트(CLIENT): 방화벽에 막힌 PC. 프록시에는 닿지만 FTP 서버에는 못
    닿는다. proxy.FtpFleetDownloader를 direct 버전과 똑같이 사용한다.

클라이언트 쪽 인터페이스는 direct_downloader와 완전히 동일하다 — 유일한 차이는
import 줄뿐이라, 호출부는 다른 변경 없이 전송 방식만 바꿀 수 있다.
테스트가 아니라 복사해 붙여 쓰는 참고용 코드다.
"""

# 클라이언트 쪽: direct 다운로더와 같은 이름들을 HTTP 너머로 사용한다.
from pathlib import Path, PurePosixPath

from ftp_handler.proxy import (
    FtpFleetDownloader,
    HostSpec,
    ListDir,
    UploadFile,
    UploadSpec,
    image_sidecar_target,
    save_image_with_sidecar,
    save_to_dir,
    specs_from_hosts,
    upload_specs_from_hosts,
)

USER = "ftpuser"
PASSWORD = "ftppass"
FLEET_HOSTS = ["10.0.0.1", "10.0.0.2", "10.0.0.3"]


def example_run_the_proxy_server() -> None:
    """서버 절반 — FTP 서버에 닿을 수 있는, 방화벽 없는 호스트에서 실행한다.

    기존 Flask 앱에 블루프린트를 붙이거나 단독으로 실행한다. 인증 없음: 신뢰하는
    단일 사용자뿐이라 FTP_PROXY_TOKEN은 설정하지 않으며 모든 요청이 그대로 통과한다.
    장비 FTP 계정은 프록시 호스트의 FTP_PROXY_FTP_USER /
    FTP_PROXY_FTP_PASSWORD 환경 변수로 설정한다. 다만 포트가 신뢰할 수 없는
    네트워크에 노출되지 않게만 하라(파일 바이트가 이 연결을 평문으로 오간다).

        from ftp_handler.proxy.flask_proxy import ftp_proxy_sknn_v3
        app.register_blueprint(ftp_proxy_sknn_v3)
    """
    from ftp_handler.proxy.flask_proxy import create_app

    create_app().run(host="0.0.0.0", port=8080)


def example_download_through_proxy() -> None:
    """클라이언트 절반 — direct 다운로더의 대체재로 HTTP 너머에서 동작한다.

    프록시 위치는 proxy_downloader.py 상단의 모듈 상수 PROXY_URL로 지정한다(생성자
    인자가 아니다 — 그래야 생성자 시그니처가 direct 다운로더와 똑같아서 import 한
    줄만 바꿔도 깨지지 않는다). 토큰 없음: 프록시는 인증 없이 동작한다. on_file은
    여전히 여기 클라이언트에서 실행되므로 save_to_dir는 파일을 로컬 PC에 떨군다.
    user/password 인자는 direct와 같은 호출 모양을 유지하지만 HTTP body로 보내지
    않으며, 실제 로그인은 프록시 호스트의 환경 변수 계정을 사용한다.

        # proxy_downloader.py 상단에서 한 번만 편집:
        # PROXY_URL = "http://proxy.host:8080"
    """
    specs = [HostSpec(host, listings=[ListDir("/MEAS", "*.dat")]) for host in FLEET_HOSTS]
    dl = FtpFleetDownloader(user=USER, password=PASSWORD)   # 프록시 위치는 PROXY_URL 상수
    report = dl.download(specs, on_file=save_to_dir(r"C:\eqp_downloads"))
    print(f"ok={report.ok} ng={report.ng}")


def example_upload_through_proxy() -> None:
    """클라이언트 절반 — 메모리상의 바이트를 프록시 너머로 원격 FTP에 올린다.

    ``UploadFile``은 디스크 파일이 아니라 raw ``bytes``를 받는다. 클라이언트가
    바이트를 base64로 실어 보내면 프록시가 풀어서 STOR한다. download의 ``request_batch``
    와 동일한 배치 방식으로 프록시 쪽 메모리를 제한한다(ADR 0001, 요청 방향에 적용).
    download과 마찬가지로 import 한 줄만 바꾸면 direct 버전과 동일하게 쓸 수 있다.
    """
    payload = b"col_a,col_b\n1,2\n"  # 예: df.to_csv().encode(); 디스크를 거치지 않음
    specs = upload_specs_from_hosts(
        FLEET_HOSTS, files=[UploadFile("/INBOX/report.csv", payload)]
    )
    dl = FtpFleetDownloader(user=USER, password=PASSWORD)   # 프록시 위치는 PROXY_URL 상수
    report = dl.upload(specs)
    print(f"ok={report.ok} ng={report.ng}")


def example_swap_direct_for_proxy() -> None:
    """이 분리 구조의 핵심: import 한 줄만 바꾸면 전송 방식이 바뀐다.

        # direct (방화벽 없는 호스트):
        from ftp_handler.direct_downloader import FtpFleetDownloader
        # 프록시 경유 (방화벽 안 클라이언트):
        from ftp_handler.proxy import FtpFleetDownloader

    아래의 모든 것 — specs, download(), report, on_file — 은 완전히 동일하다.
    """
    specs = [HostSpec(host, files=["/HITACHI/SYSFILE/LOG_RECIPE_EXE.log"]) for host in FLEET_HOSTS]
    report = FtpFleetDownloader(user=USER, password=PASSWORD).download(specs)
    print(report.grouped().keys())


def example_download_images_with_cond(
    host: str = "10.0.0.1",
    parent: str = "/IMAGES",
    dest: str | Path = r"C:\eqp_downloads",
) -> tuple[list[Path], list[Path]]:
    """이미지(``*01AP.jpeg``)와 그 사이드카 cond.txt를 짝지어 받아 로컬에 저장한다.

    고정 규칙: 각 이미지에는 "." + 이미지 파일명으로 된 하위 폴더가 있고 그 안에
    cond.txt가 있다(예: ``S09_M0047-01AP.jpeg`` → ``.S09_M0047-01AP.jpeg/cond.txt``).
    먼저 ``list_dirs``로 이미지 이름만 탐색하고(가져오지 않음), 각 이미지에 대해
    cond.txt 경로를 규칙으로 만들어 둘을 함께 RETR한다. 저장은 ``save_image_with_sidecar``
    에 맡긴다 — 이미지는 ``dest`` 바로 아래, cond.txt는 원래의 사이드카 폴더를 살려
    충돌 없이 떨군다(직접 ``on_file``을 짤 필요 없음).

    반환값은 서로 독립된 두 리스트 ``(image_paths, cond_paths)``다 — 하나는 받은
    이미지 경로들, 다른 하나는 받은 cond.txt 경로들이다(인덱스로 짝지어져 있지 않다).
    로컬 경로는 다운로드 후 ``image_sidecar_target``(저장에 쓰인 바로 그 매핑)으로
    되계산하며, 실제로 받은 파일만 담는다(``report.files``로 성공 여부 판정 → RETR
    550으로 빠진 파일은 제외). 둘 다 탐색 순서를 따른다. 이미지와 cond는 파일명 스템이
    같으니, 짝이 필요하면 이름으로 다시 맞출 수 있다.
    """
    base = Path(dest)
    dl = FtpFleetDownloader(user=USER, password=PASSWORD)   # 프록시 위치는 PROXY_URL 상수

    def cond_for(image_path: str) -> str:
        p = PurePosixPath(image_path)
        return str(p.with_name(f".{p.name}") / "cond.txt")

    # 1. 이미지 탐색(이름만, 가져오지 않음). 재현 가능한 순서를 위해 정렬한다.
    #    fnmatch의 ``*``는 셸 글롭과 달리 앞 점(.)도 매칭하므로 ``*01AP.jpeg``는
    #    실제 이미지 ``c.jpeg``뿐 아니라 사이드카 폴더 ``.c.jpeg``까지 함께 잡는다.
    #    점으로 시작하는 항목(=사이드카 폴더)은 여기서 걸러야 cond 경로에 점이
    #    겹치지(``..c.jpeg``) 않는다 — 실제 이미지명은 점으로 시작하지 않는다.
    listing = dl.list_dirs(
        specs_from_hosts([host], listings=[ListDir(parent, "*01AP.jpeg")])
    )
    discovered = sorted(
        (l.host, img)
        for l in listing.listings
        for img in l.paths
        if not PurePosixPath(img).name.startswith(".")
    )

    # 2. 호스트당 한 spec: 이미지 + 그 cond.txt를 고정 경로로 묶는다.
    by_host: dict[str, list[str]] = {}
    for h, img in discovered:
        by_host.setdefault(h, []).extend((img, cond_for(img)))
    specs = [HostSpec(host=h, files=files) for h, files in by_host.items()]

    # 3. 저장은 헬퍼에 맡긴다. 어떤 파일이 실제로 내려왔는지는 report.files로 안다.
    report = dl.download(specs, on_file=save_image_with_sidecar(base))
    ok = {(f.host, f.remote_path) for f in report.files}

    # 4. 받은 파일만 골라 이미지 / cond 두 개의 독립 리스트로 나눈다(탐색 순서 유지).
    #    로컬 경로는 저장에 쓰인 것과 같은 매핑(image_sidecar_target)으로 되계산한다.
    image_paths: list[Path] = []
    cond_paths: list[Path] = []
    for h, img in discovered:
        if (h, img) in ok:
            image_paths.append(image_sidecar_target(base, img))
        cond_rp = cond_for(img)
        if (h, cond_rp) in ok:
            cond_paths.append(image_sidecar_target(base, cond_rp))
    return image_paths, cond_paths


def get_date_key_for_sorting(folder_name: str) -> str:
    """정렬 키 — 당신의 기존 함수로 교체하라(여기서는 자리표시자).

    날짜 기반 폴더명(예: ``"20260615"``)을 받아 정렬용 키를 돌려준다. 아래
    ``pick_latest_folder``가 이 키로 폴더를 내림차순 정렬해 가장 최신 폴더를 고른다.
    """
    return folder_name


def pick_latest_folder(folders: list[str]) -> str:
    """날짜 기반 폴더 경로들 중 가장 최신 폴더 경로를 돌려준다.

    당신의 기존 패턴 ``sorted(folders, key=get_date_key_for_sorting, reverse=True)[0]``
    을 그대로 따른다 — 키로 내림차순 정렬한 뒤 첫 번째(=최신)를 고른다. ``list_dirs``는
    이름이 아니라 전체 원격 경로(예: ``/IMAGES/20260615``)를 돌려주므로, 키에는 마지막
    이름 성분만(``PurePosixPath(p).name``) 넘긴다 — 전체 경로/바 이름 어느 쪽을 받아도
    동작한다. ``folders``가 비어 있으면 호출 전에 거른다(여기서는 ``IndexError``).
    """
    return sorted(
        folders,
        key=lambda p: get_date_key_for_sorting(PurePosixPath(p).name),
        reverse=True,
    )[0]


def example_download_latest_images_with_cond(
    host: str = "10.0.0.1",
    root: str = "/IMAGES",
    dest: str | Path = r"C:\eqp_downloads",
) -> tuple[list[Path], list[Path | None]]:
    """``root`` 아래 최신 날짜 폴더를 고른 뒤 그 안의 이미지+cond.txt를 받는다.

    이미지 폴더로 들어가기 전에, 날짜 기반 폴더들을 먼저 나열하고 ``pick_latest_folder``
    (기존 정렬 로직 ``sorted(folders, key=get_date_key_for_sorting, reverse=True)[0]``)로
    최신 폴더를 고른다. 그 폴더를 ``parent``로 삼아 ``example_download_images_with_cond``에
    위임하므로, 이미지(``*01AP.jpeg``)와 사이드카 cond.txt 처리는 그대로 재사용된다.

    반환값은 ``example_download_images_with_cond``와 동일한 인덱스 정렬
    ``(image_paths, cond_paths)``다. ``root``에 폴더가 하나도 없으면 빈 리스트 둘을
    돌려준다.
    """
    dl = FtpFleetDownloader(user=USER, password=PASSWORD)   # 프록시 위치는 PROXY_URL 상수

    # 1. root 아래 항목을 나열한다(이름만, 가져오지 않음). 날짜 폴더만 있다고 가정.
    listing = dl.list_dirs(specs_from_hosts([host], listings=[ListDir(root, None)]))
    folders = [p for l in listing.listings for p in l.paths]
    if not folders:
        return [], []

    # 2. 기존 정렬 키로 내림차순 정렬해 최신 폴더를 고른다(폴더명 기준).
    latest = pick_latest_folder(folders)

    # 3. 최신 폴더로 들어가 이미지+cond.txt를 받는다(위 함수 재사용).
    return example_download_images_with_cond(host, latest, dest)


if __name__ == "__main__":
    # example_run_the_proxy_server()      # 프록시 호스트에서
    # example_download_through_proxy()    # 방화벽 안 클라이언트에서
    # images, conds = example_download_images_with_cond()
    # images, conds = example_download_latest_images_with_cond()
    pass
