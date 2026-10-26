"""VeritySEM / Provision FTP 서버가 디스크 여유 공간을 알려 주는지 확인 (읽기 전용).

아래 TARGETS 에 IP / 계정 / 비밀번호를 채우고:  python ftp_space_probe.py
클라우드에 붙여 넣은 사본에만 계정을 채우세요. 이 저장소 사본에는 절대 채우지 않습니다.
테스트가 끝나면 클라우드 사본을 지우세요 (비밀번호가 들어 있습니다).
원본 절차: scripts/probes/probe_ftp_server_info.md
"""

import ftplib

# (이름, IP, 계정, 비밀번호) -- 필요한 만큼 줄을 추가/삭제
TARGETS = [
    ("VeritySEM", "0.0.0.0", "user", "password"),
    ("Provision", "0.0.0.0", "user", "password"),
]
DIRS = ["/D_Drive", "/C_Drive"]
PORT = 21
TIMEOUT = 8

# 정보 조회 명령만 보냅니다 (파일 생성/삭제 명령 없음).
COMMANDS = ["SYST", "FEAT", "HELP", "HELP SITE", "STAT", "AVBL", "SITE DF", "SITE DISKFREE"]
DIR_COMMANDS = ["AVBL {d}", "SITE DF {d}", "SITE DISKFREE {d}"]
FREE_SPACE_PREFIXES = ("AVBL", "SITE DF", "SITE DISKFREE")


def probe(name, host, user, password):
    print(f"==== {name} {host}")
    ftp = ftplib.FTP(timeout=TIMEOUT, encoding="latin-1")
    try:
        print(f"  welcome: {ftp.connect(host, PORT, TIMEOUT)}")
        ftp.login(user, password)
        cmds = COMMANDS + [c.format(d=d) for d in DIRS for c in DIR_COMMANDS]
        answered = []
        for cmd in cmds:
            try:
                reply, ok = ftp.sendcmd(cmd), True
            except (ftplib.error_perm, ftplib.error_reply) as exc:  # 5xx = 미지원, 그 자체가 답
                reply, ok = str(exc), False
            print(f"  {'OK  ' if ok else 'FAIL'} {cmd!r}\n        " + reply.replace("\r", "").replace("\n", "\n        "))
            if ok and cmd.startswith(FREE_SPACE_PREFIXES):
                answered.append(cmd)
        if answered:
            print(f"  => 여유 공간 명령 응답 있음: {', '.join(answered)}")
        else:
            print("  => 여유 공간 명령 응답 없음 (FTP 만으로는 불가, 장비 쪽 예약 작업 필요)")
    except Exception as exc:  # 한 대가 실패해도 다음 장비 계속
        print(f"  FAIL {type(exc).__name__}: {exc}")
    finally:
        ftp.close()


if __name__ == "__main__":
    for target in TARGETS:
        probe(*target)
