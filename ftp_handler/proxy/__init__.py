"""HTTP-proxy FTP fleet download — the firewalled-client transport.

The two halves run on different machines:
  - ``proxy_downloader`` (client) runs where FTP egress is blocked; it needs
    ``requests``. Its ``FtpFleetDownloader`` is a drop-in for
    ``ftp_handler.direct_downloader.FtpFleetDownloader`` — same names, HTTP
    transport. That client surface is what this package re-exports::

        from ftp_handler.proxy import FtpFleetDownloader

  - ``flask_proxy`` (server) runs on a firewall-free host and needs ``flask``.
    It is NOT imported here so importing the client never drags in ``flask``;
    reach it explicitly::

        from ftp_handler.proxy.flask_proxy import create_app, ftp_proxy_sknn_v3
"""

from .proxy_downloader import (
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
    "specs_from_hosts",
    "group_files_by_host",
    "upload_specs_from_hosts",
]
