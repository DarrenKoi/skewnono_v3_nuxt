"""Worked examples for ftp_handler.direct_downloader — concurrent fleet FTP.

Direct FTP (no proxy): use when the running process can reach the equipment
servers. To route the SAME calls through the HTTP proxy from a firewalled
client, swap the import to ``from ftp_handler.proxy import ...`` — see
ftp_handler/proxy/examples.py. Not tests; a copy-paste reference.
"""

from ftp_handler.direct_downloader import (
    FtpFleetDownloader,
    HostSpec,
    ListDir,
    UploadFile,
    UploadSpec,
    build_host_specs,
    collect_fleet,
    download_fleet,
    group_files_by_host,
    list_fleet,
    put_bytes_to_minio,
    put_parquet_to_minio,
    put_pickle_to_minio,
    save_to_dir,
    size_fleet,
    specs_from_hosts,
    upload_fleet,
    upload_specs_from_hosts,
)

USER = "ftpuser"
PASSWORD = "ftppass"
# In production this list comes from an Airflow Variable — see
# example_fleet_specs_from_config.
FLEET_HOSTS = ["10.0.0.1", "10.0.0.2", "10.0.0.3"]


def example_download_known_paths() -> None:
    """Pull fixed, known paths from every host concurrently.

    ``files`` are RETR'd directly with no listing — for append-only logs whose
    paths you already know. One connection per host, opened once and reused.
    """
    specs = [
        HostSpec(host, files=["/HITACHI/SYSFILE/LOG_RECIPE_EXE.log"])
        for host in FLEET_HOSTS
    ]
    report = FtpFleetDownloader(user=USER, password=PASSWORD).download(specs)

    print(f"ok={report.ok} ng={report.ng} failure_ratio={report.failure_ratio:.2f}")
    for f in report.files:
        print(f.host, f.remote_path, len(f.data))
    for x in report.failures:
        print("FAILED", x.host, x.remote_path, x.error)


def example_per_host_paths_from_dataframe() -> None:
    """Build specs from a DataFrame where each row is one (IP, file) to fetch.

    The common "I have a measurement-history table, pull each row's file" case.
    The same eqp_ip recurs across many rows, so group_files_by_host folds them
    into one HostSpec per host — one reused FTP connection per host, not one per
    file. Composing the remote path from the row's columns is the single caller
    line below; group_files_by_host takes plain (host, path) pairs so this layer
    never imports pandas. Credentials are shared across the whole fleet here:
    user "hitachi", password "hid".
    """
    import pandas as pd

    df_meas_hist = pd.DataFrame(
        [
            {"eqp_ip": "10.0.0.1", "class_name": "CLSA", "idw_name": "W1", "idp_name": "P100"},
            {"eqp_ip": "10.0.0.1", "class_name": "CLSA", "idw_name": "W1", "idp_name": "P101"},
            {"eqp_ip": "10.0.0.2", "class_name": "CLSB", "idw_name": "W2", "idp_name": "P200"},
        ]
    )

    specs = group_files_by_host(
        (
            row.eqp_ip,
            f"/HITACHI/DEVICE/HD/{row.class_name}/data/{row.idw_name}/{row.idp_name}.idp",
        )
        for row in df_meas_hist.itertuples(index=False)
    )
    report = FtpFleetDownloader(user="hitachi", password="hid").download(specs)

    print(f"ok={report.ok} ng={report.ng}")
    for f in report.files:
        print(f.host, f.remote_path, len(f.data))


def example_per_host_paths_with_provenance() -> None:
    """Carry extra DataFrame columns alongside each file for downstream tracking.

    Same fan-in as example_per_host_paths_from_dataframe, but df_meas_hist also
    has columns you need *later* (lot_id, recipe, ...) — they have nothing to do
    with the download itself, you just want them attached to each file when you
    store or index it. Keep them in a side dict keyed by (eqp_ip, remote_path):
    that pair is exactly what a FileResult / on_file carries back, so it's the
    natural join key. The metadata stays local (it never enters a HostSpec, so
    it never hits the proxy wire). No helper needed — one loop builds both the
    download pairs and the lookup.
    """
    import pandas as pd

    df_meas_hist = pd.DataFrame(
        [
            {"eqp_ip": "10.0.0.1", "class_name": "CLSA", "idw_name": "W1",
             "idp_name": "P100", "lot_id": "LOT777", "recipe": "R1"},
            {"eqp_ip": "10.0.0.2", "class_name": "CLSB", "idw_name": "W2",
             "idp_name": "P200", "lot_id": "LOT888", "recipe": "R2"},
        ]
    )

    pairs: list[tuple[str, str]] = []
    meta_by_key: dict[tuple[str, str], object] = {}
    for row in df_meas_hist.itertuples(index=False):
        path = f"/HITACHI/DEVICE/HD/{row.class_name}/data/{row.idw_name}/{row.idp_name}.idp"
        pairs.append((row.eqp_ip, path))
        meta_by_key[(row.eqp_ip, path)] = row  # keep the whole row, or pick columns

    specs = group_files_by_host(pairs)
    report = FtpFleetDownloader(user="hitachi", password="hid").download(specs)

    for f in report.files:
        m = meta_by_key[(f.host, f.remote_path)]  # join back to the source row
        print(f.host, m.lot_id, m.recipe, len(f.data))


def example_listing_then_download() -> None:
    """The "look before you download" pass for a large fleet.

    Step 1 lists each host's measurement dir concurrently (no fetching) so you
    can see the volume; step 2 feeds the discovered paths straight back into
    download via to_specs(). The decision in between is where you'd apply a
    threshold, a date filter, a cap, etc. specs_from_hosts wraps a plain IP list
    when every host shares the same directories.
    """
    discover = specs_from_hosts(FLEET_HOSTS, listings=[ListDir("/MEAS", "*.dat")])
    dl = FtpFleetDownloader(user=USER, password=PASSWORD)

    listing = dl.list_dirs(discover)
    print(f"discovered {listing.total_paths} files across {listing.ok} hosts")

    # ... decide what's worth pulling here ...
    report = dl.download(listing.to_specs())
    print(f"downloaded ok={report.ok} ng={report.ng}")


def example_estimate_size_before_download() -> None:
    """Estimate the in-memory RAM cost of a fleet run before pulling any bytes.

    size_dirs resolves the same paths download would (fixed files + whatever the
    listings discover) and asks each server its file size via the FTP SIZE
    command — no file is transferred. report.total_bytes is the peak RAM a
    collect-mode download of this exact set would hold at once; by_host() shows
    where the weight sits. Feed the measured set straight into download via
    to_specs() so you size and pull exactly the same files.
    """
    specs = specs_from_hosts(FLEET_HOSTS, listings=[ListDir("/MEAS", "*.dat")])
    dl = FtpFleetDownloader(user=USER, password=PASSWORD)

    sizing = dl.size_dirs(specs)
    mib = sizing.total_bytes / 1024**2
    print(f"{sizing.ok} files, {mib:.1f} MiB total across {len(sizing.by_host())} hosts")
    print("heaviest hosts:", sorted(sizing.by_host().items(), key=lambda kv: -kv[1])[:5])

    # Budget check: only pull into memory if it fits; otherwise stream to disk.
    if sizing.total_bytes < 500 * 1024**2:
        report = dl.download(sizing.to_specs())            # safe to hold in RAM
    else:
        report = dl.download(sizing.to_specs(), on_file=save_to_dir("/data/eqp"))
    print(f"downloaded ok={report.ok} ng={report.ng}")

    # One-call form: size_fleet(specs, user=..., password=...)
    _ = size_fleet(specs, user=USER, password=PASSWORD, max_concurrency=16)


def example_streaming_to_disk() -> None:
    """Stream a large fleet to disk with bounded RAM.

    Passing on_file hands each file off the moment it lands and then drops it, so
    peak memory stays at concurrency x file size, not the sum of the fleet.
    save_to_dir writes to dest/<host>/<remote path>.
    """
    specs = [HostSpec(host, listings=[ListDir("/MEAS", "*.dat")]) for host in FLEET_HOSTS]
    dl = FtpFleetDownloader(user=USER, password=PASSWORD)
    report = dl.download(specs, on_file=save_to_dir("/data/eqp_downloads"))
    print(f"wrote {report.ok} files, {report.ng} failures")


def example_stream_to_minio_raw() -> None:
    """Archive each file's RAW bytes to MinIO, unchanged, with bounded RAM.

    The simplest sink: put_bytes_to_minio returns an on_file callback that PUTs
    the downloaded bytes straight to MinIO via client.put — no parse, no
    serialization. Each file is uploaded the moment it lands, so nothing hits
    local disk and peak memory stays at concurrency x file size. Objects land at
    <host>/<remote path> by default; the ``key`` arg below partitions by host
    and KST date so old data is easy to list and purge later. ``then`` could
    chain a parse + OpenSearch index call to archive AND process in one pass.

    Reach for this to keep equipment logs/.dat files byte-for-byte. For parsed
    values use example_stream_to_minio_pickle / _parquet instead.
    """
    from datetime import datetime
    from pathlib import PurePosixPath
    from zoneinfo import ZoneInfo

    from minio_handler import MinioObject

    day = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")

    def key(host: str, remote_path: str) -> str:
        return f"eqp/{host}/{day}/{PurePosixPath(remote_path).name}"

    mc = MinioObject(bucket="eqp-logs")  # reads MinIO env vars
    specs = specs_from_hosts(FLEET_HOSTS, listings=[ListDir("/MEAS", "*.dat")])
    report = FtpFleetDownloader(user=USER, password=PASSWORD).download(
        specs, on_file=put_bytes_to_minio(mc, key=key)
    )

    print(f"stored ok={report.ok} ng={report.ng}")
    for x in report.failures:  # an upload raise is isolated to its file
        print("FAILED", x.host, x.remote_path, x.error)


def example_stream_to_minio_pickle() -> None:
    """Download in-memory, process, and upload each file to MinIO as pickle.

    The end-to-end "FTP → process → object storage" pass with bounded RAM:
    put_pickle_to_minio returns an on_file callback, so each file is fetched,
    run through your transform (bytes → a live Python object), pickled, and
    PUT to MinIO the moment it lands — nothing hits local disk and peak memory
    stays at concurrency x file size. MinioObject is injected (ftp_handler never
    imports minio); minio-py's object client is thread-safe, so one shared
    instance is fine across the per-host worker threads. Objects land at
    <host>/<remote path>.pkl by default.

    Reach for pickle when the parsed value isn't a clean table (nested dict,
    custom object). For tabular data prefer example_stream_to_minio_parquet.
    """
    from minio_handler import MinioObject

    def parse(host: str, remote_path: str, data: bytes) -> dict:
        # YOUR processing: bytes -> any Python object. Toy example here.
        return {"host": host, "path": remote_path, "raw_len": len(data)}

    mc = MinioObject()  # reads MinIO env vars; bucket/prefix from config
    specs = specs_from_hosts(FLEET_HOSTS, listings=[ListDir("/MEAS", "*.dat")])
    report = FtpFleetDownloader(user=USER, password=PASSWORD).download(
        specs, on_file=put_pickle_to_minio(mc, parse)
    )

    print(f"stored ok={report.ok} ng={report.ng}")
    for x in report.failures:  # a parse/upload raise is isolated to its file
        print("FAILED", x.host, x.remote_path, x.error)


def example_stream_to_minio_parquet() -> None:
    """Same streaming pass, but parse to a DataFrame and store as parquet.

    put_parquet_to_minio's transform must return a pd.DataFrame; it's serialized
    to parquet (pyarrow) and PUT via client.put_dataframe. Objects land at
    <host>/<remote path>.parquet. The ``key`` arg overrides the default layout —
    here we drop the source extension and partition by host so the lake reads as
    one dataset. ``then`` could chain an OpenSearch index call after each upload.
    """
    import pandas as pd

    from minio_handler import MinioObject

    def parse_to_frame(host: str, remote_path: str, data: bytes) -> pd.DataFrame:
        # YOUR real parser builds the frame from the measurement bytes.
        return pd.DataFrame({"host": [host], "raw_len": [len(data)]})

    def key(host: str, remote_path: str) -> str:
        name = remote_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        return f"meas/host={host}/{name}.parquet"

    mc = MinioObject()
    specs = specs_from_hosts(FLEET_HOSTS, listings=[ListDir("/MEAS", "*.dat")])
    report = FtpFleetDownloader(user=USER, password=PASSWORD).download(
        specs, on_file=put_parquet_to_minio(mc, parse_to_frame, key=key)
    )
    print(f"stored ok={report.ok} ng={report.ng}")


def example_one_call_helpers() -> None:
    """For callers that just want a function, not an object."""
    specs = [HostSpec(host, listings=[ListDir("/MEAS", "*.dat")]) for host in FLEET_HOSTS]
    listing = list_fleet(specs, user=USER, password=PASSWORD, max_concurrency=16)
    report = download_fleet(listing.to_specs(), user=USER, password=PASSWORD)
    print(report.ok, report.ng)


def example_tuning_for_large_fleet() -> None:
    """Constructor knobs for a ~300-host run.

    max_concurrency caps simultaneous connections (and, in memory mode, peak RAM
    ~= concurrency x file size). connect_timeout abandons a dead/black-holed host
    fast; host_timeout backstops a host that connects then stalls mid-transfer.
    passive=False is the escape hatch when a worker on a different subnet needs
    active mode.
    """
    specs = [HostSpec(host, listings=[ListDir("/MEAS", "*.dat")]) for host in FLEET_HOSTS]
    dl = FtpFleetDownloader(
        user=USER,
        password=PASSWORD,
        max_concurrency=24,
        connect_timeout=8.0,
        host_timeout=60.0,
        passive=True,
    )
    print(f"discovered {dl.list_dirs(specs).total_paths} files")


def example_upload_in_memory_to_fleet() -> None:
    """Push in-memory bytes to many hosts — no disk file required.

    ``UploadFile`` takes raw ``bytes`` (here a CSV built in memory), which go
    straight to STOR via an in-memory buffer; nothing is written to local disk.
    ``upload_specs_from_hosts`` is the upload counterpart to
    ``specs_from_hosts``: same file(s) to every host. Per-host AND per-file
    failure isolation, same concurrency knobs as download.
    """
    payload = b"col_a,col_b\n1,2\n"  # e.g. df.to_csv().encode(); never hits disk
    specs = upload_specs_from_hosts(
        FLEET_HOSTS, files=[UploadFile("/INBOX/report.csv", payload)]
    )
    report = FtpFleetDownloader(user=USER, password=PASSWORD).upload(specs)

    print(f"uploaded ok={report.ok} ng={report.ng}")
    for x in report.failures:
        print("FAILED", x.host, x.remote_path, x.error)


def example_upload_different_files_per_host() -> None:
    """Different bytes to different hosts in one concurrent run."""
    specs = [
        UploadSpec("10.0.0.1", files=[UploadFile("/INBOX/a.cfg", b"host-1 config")]),
        UploadSpec("10.0.0.2", files=[UploadFile("/INBOX/b.cfg", b"host-2 config")]),
    ]
    report = upload_fleet(specs, user=USER, password=PASSWORD)
    print(report.grouped())  # {host: [remote_path, ...]}


def example_fleet_specs_from_config() -> None:
    """Build specs from deserialized JSON (e.g. an Airflow Variable)."""
    fleet = [
        {
            "host": "10.0.0.1",
            "files": ["/HITACHI/SYSFILE/LOG_RECIPE_EXE.log"],
            "listings": [{"remote_dir": "/MEAS", "pattern": "*.dat"}],
        },
        {"host": "10.0.0.2", "listings": [{"remote_dir": "/MEAS", "pattern": "*.dat"}]},
    ]
    print([s.host for s in build_host_specs(fleet)])


def example_collect_archive_parse_index() -> None:
    """Download the fleet and, per file, archive → parse → index in memory.

    The three steps are callables you supply, so this stays free of minio /
    opensearch imports. archive runs first (never index a record whose raw source
    wasn't stored); a raise from any step fails just that file. Replace the fakes
    with MinioObject.put, your parser, and OSDoc.bulk_index.
    """
    def archive(host: str, remote_path: str, data: bytes) -> str:
        return f"raw/{host}{remote_path}"  # e.g. MinioObject(...).put(key, data)

    def parse(host: str, remote_path: str, data: bytes) -> list[dict]:
        return [{"host": host, "path": remote_path, "raw_len": len(data)}]

    def index(docs: list[dict]) -> None:
        print("would index", docs)  # e.g. OSDoc(...).bulk_index("meas_index", docs)

    specs = [HostSpec(host, listings=[ListDir("/MEAS", "*.dat")]) for host in FLEET_HOSTS]
    report = collect_fleet(
        specs, user=USER, password=PASSWORD, archive=archive, parse=parse, index=index
    )
    print(f"processed ok={report.ok} ng={report.ng}")


if __name__ == "__main__":
    # Uncomment the example you want to run against your servers.
    # example_listing_then_download()
    # example_collect_archive_parse_index()
    pass
