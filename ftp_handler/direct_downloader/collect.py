"""Glue between the FTP fleet downloader and your storage + processing.

Deliberately free of orchestrator, ``minio``, and ``opensearch`` imports: the
archive, parse, and index steps are passed in as callables, so this module is
unit-testable with plain fakes and the DAG decides which concrete clients to
use. That keeps the DAG thin and this layer portable.

NOTE: the orchestrator's product name is intentionally not spelled out
anywhere in this file. Its DAG-discovery scanner imports any source file
containing both that name and "dag" as a *standalone* module, which breaks
this package's relative imports ("attempted relative import with no known
parent package"). Keep the literal name out of here.

The data flow for one file, inside ``collect_fleet``'s ``on_file`` callback —
this is the "room to process before sending to ops" you asked about:

    raw bytes  --archive-->  MinIO  (key returned)
    raw bytes  --parse---->  list[dict]  (YOUR processing lives here)
    list[dict] --index---->  OpenSearch  (minio_key stamped on each doc)

archive runs first so you never index a record whose raw source wasn't stored.
A raise from any step is caught per-file by the downloader and recorded as that
file's failure — it never aborts the other files or hosts.
"""

from typing import Callable

from .fleet_downloader import (
    DownloadReport,
    FtpFleetDownloader,
    HostSpec,
    ListDir,
)

# Turn one downloaded file into zero or more OpenSearch documents. This is the
# processing seam: parse the bytes, derive fields, decide _id, etc.
ParseFn = Callable[[str, str, bytes], list[dict]]
# Archive the raw bytes; return the storage key to stamp onto each doc.
ArchiveFn = Callable[[str, str, bytes], str]
# Ship the processed docs (e.g. OSDoc.bulk_index).
IndexFn = Callable[[list[dict]], None]


def build_host_specs(fleet: list[dict]) -> list[HostSpec]:
    """Turn runtime config into HostSpec objects.

    ``fleet`` is the deserialized JSON from the orchestrator Variable, e.g.::

        [
          {"host": "10.0.0.1",
           "files": ["/HITACHI/SYSFILE/LOG_RECIPE_EXE.log"],
           "listings": [{"remote_dir": "/MEAS", "pattern": "*.dat"}]},
          ...
        ]
    """
    specs: list[HostSpec] = []
    for entry in fleet:
        listings = [
            ListDir(remote_dir=item["remote_dir"], pattern=item.get("pattern"))
            for item in entry.get("listings", [])
        ]
        specs.append(
            HostSpec(
                host=entry["host"],
                files=list(entry.get("files", [])),
                listings=listings,
            )
        )
    return specs


def collect_fleet(
    specs: list[HostSpec],
    *,
    user: str,
    password: str,
    archive: ArchiveFn,
    parse: ParseFn,
    index: IndexFn,
    **tuning: object,
) -> DownloadReport:
    """Download the fleet and, per file, archive → parse → index in-memory.

    Streams each file through ``on_file`` so peak RAM stays bounded by
    concurrency x file size, not the whole fleet. ``tuning`` (port,
    max_concurrency, connect_timeout, host_timeout, passive) is forwarded to
    FtpFleetDownloader.
    """

    def on_file(host: str, remote_path: str, data: bytes) -> None:
        key = archive(host, remote_path, data)
        docs = parse(host, remote_path, data)
        for doc in docs:
            doc["minio_key"] = key
        if docs:
            index(docs)

    downloader = FtpFleetDownloader(user=user, password=password, **tuning)  # type: ignore[arg-type]
    return downloader.download(specs, on_file=on_file)
