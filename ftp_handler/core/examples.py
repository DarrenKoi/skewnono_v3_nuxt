"""Worked examples for ftp_handler.core — the single-server FtpClient.

Not tests and not imported by anything; a copy-paste reference you run against a
real server. Each function is one self-contained use case. Fill in the
connection constants (or pass your own) and call the example you want.

One server, one connection, four ad-hoc ops (list / download / upload / remove).
For fanning out across many hosts, see ftp_handler/direct_downloader/examples.py.
"""

from ftp_handler.core import FtpClient

# ── connection constants — replace with your environment ────────────────────
HOST = "10.0.0.1"
USER = "ftpuser"
PASSWORD = "ftppass"


def example_list_names() -> None:
    """NLST: just the names in a directory (no type, no size, no time).

    Lowest common denominator — works on every server. ``pattern`` is an fnmatch
    glob on basenames.
    """
    with FtpClient(host=HOST, user=USER, password=PASSWORD) as ftp:
        for path in ftp.list_dir("/MEAS", pattern="*.dat"):
            print(path)


def example_split_dirs_and_files() -> None:
    """MLSD: subfolders and files separated, when the server supports it.

    Raises ftplib.error_perm on an old daemon that lacks MLSD — fall back to
    list_details (LIST) there.
    """
    with FtpClient(host=HOST, user=USER, password=PASSWORD) as ftp:
        entries = ftp.list_entries("/MEAS", pattern="*.dat")
        print("subfolders:", entries.dirs)   # every subfolder
        print("files:", entries.files)        # only *.dat


def example_list_with_sizes_and_times() -> None:
    """LIST: typed entries with size and a timezone-aware modified time.

    The broadly-compatible fallback — parses the server's ls -l / MS-DOS text.
    Times are interpreted as KST by default; pass tz= to override. Useful for
    "only pull files modified since X" logic.
    """
    with FtpClient(host=HOST, user=USER, password=PASSWORD) as ftp:
        for info in ftp.list_details("/MEAS", pattern="*.dat"):
            kind = "dir " if info.is_dir else "file"
            print(f"{kind} {info.modified}  {info.size}  {info.path}")


def example_download_one_file() -> None:
    """RETR a single file's bytes into memory."""
    with FtpClient(host=HOST, user=USER, password=PASSWORD) as ftp:
        data = ftp.download("/HITACHI/SYSFILE/LOG_RECIPE_EXE.log")
        print(f"got {len(data)} bytes")


def example_upload_one_file() -> None:
    """STOR bytes to a remote path (overwrites if it exists)."""
    with FtpClient(host=HOST, user=USER, password=PASSWORD) as ftp:
        ftp.upload("/INBOX/report.csv", b"col1,col2\n1,2\n")


def example_remove_one_file() -> None:
    """DELE a remote path."""
    with FtpClient(host=HOST, user=USER, password=PASSWORD) as ftp:
        ftp.remove("/MEAS/stale.dat")


def example_many_ops_one_connection() -> None:
    """All four operations over one reused connection — the point of the context
    manager. Discover, fetch, archive a copy back, then clean up."""
    with FtpClient(host=HOST, user=USER, password=PASSWORD) as ftp:
        for path in ftp.list_dir("/MEAS", pattern="*.dat"):
            data = ftp.download(path)
            ftp.upload(f"/PROCESSED/{path.rsplit('/', 1)[-1]}", data)
            ftp.remove(path)


if __name__ == "__main__":
    # Uncomment the example you want to run against your server.
    # example_list_names()
    # example_split_dirs_and_files()
    # example_list_with_sizes_and_times()
    pass
