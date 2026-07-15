"""Equipment FTP fleet collection, organized by purpose.

Four subpackages, each a re-export hub so call sites import the leaf name:

  - ``core``              — shared primitives: ``FtpClient`` (one server, the
                            ad-hoc list/download/upload/remove ops) and the NLST
                            normalizer both downloaders share. Stdlib only.
  - ``direct_downloader`` — talk to the FTP servers directly: ``FtpFleetDownloader``
                            (concurrent fan-out + ``list_dirs`` discovery) and the
                            archive→parse→index glue (``collect_fleet``).
  - ``proxy``             — the firewalled-client HTTP transport. The client
                            (``proxy_downloader``) re-exports a ``FtpFleetDownloader``
                            with the SAME surface as ``direct_downloader`` — swap
                            one import line to route through the proxy. The server
                            (``proxy.flask_proxy``) is imported explicitly so the
                            client never drags in ``flask``.
  - ``web_app``           — ``BackgroundJobs`` to run a fleet download off a web
                            request thread (non-blocking) and poll for the result.

The same-name seam, in one line::

    from ftp_handler.direct_downloader import FtpFleetDownloader   # direct FTP
    from ftp_handler.proxy             import FtpFleetDownloader   # via the proxy

Import the subpackage you need directly — a worker without ``flask`` / ``requests``
can still use ``core`` and ``direct_downloader``. The proxy pair is also designed
to be copied out flat (``flask_proxy.py`` / ``proxy_downloader.py`` beside
``fleet_downloader.py`` and ``listing.py``) and imported by bare name.
"""
