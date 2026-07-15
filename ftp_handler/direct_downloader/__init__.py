"""Direct FTP fleet download — talk to the equipment servers with no proxy.

Use this when the running process can reach the FTP servers directly (an
Airflow worker, a firewall-free Flask host). The public ``FtpFleetDownloader``
surface here is identical to ``ftp_handler.proxy`` — swap the import line to
route through the HTTP proxy instead, nothing else changes::

    from ftp_handler.direct_downloader import FtpFleetDownloader   # direct
    from ftp_handler.proxy             import FtpFleetDownloader   # via proxy
"""

from .collect import build_host_specs, collect_fleet
from .fleet_downloader import (
    DownloadReport,
    FileResult,
    FileSize,
    FtpFleetDownloader,
    HostFailure,
    HostListing,
    HostSpec,
    ListDir,
    ListingReport,
    OnFile,
    SizingReport,
    UploadFile,
    UploadReport,
    UploadResult,
    UploadSpec,
    download_fleet,
    group_files_by_host,
    list_fleet,
    put_bytes_to_minio,
    put_parquet_to_minio,
    put_pickle_to_minio,
    image_sidecar_target,
    local_target,
    save_image_with_sidecar,
    save_to_dir,
    size_fleet,
    specs_from_hosts,
    upload_fleet,
    upload_specs_from_hosts,
)

__all__ = [
    "FtpFleetDownloader",
    "download_fleet",
    "list_fleet",
    "size_fleet",
    "upload_fleet",
    "HostSpec",
    "ListDir",
    "DownloadReport",
    "FileResult",
    "FileSize",
    "HostFailure",
    "HostListing",
    "ListingReport",
    "SizingReport",
    "OnFile",
    "UploadFile",
    "UploadSpec",
    "UploadResult",
    "UploadReport",
    "image_sidecar_target",
    "local_target",
    "save_image_with_sidecar",
    "save_to_dir",
    "put_bytes_to_minio",
    "put_pickle_to_minio",
    "put_parquet_to_minio",
    "specs_from_hosts",
    "group_files_by_host",
    "upload_specs_from_hosts",
    "build_host_specs",
    "collect_fleet",
]
