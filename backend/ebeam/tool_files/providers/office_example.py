"""Office adapter: a direct FTP connection to the tool.

Direct only. A Windows office PC cannot reach tool FTP and needs the proxy
transport (ticket 06); until then it answers 503 tool_unreachable there.
"""

from ftp_handler.core import FtpClient

from backend.ebeam.tool_files.resolve import Tool


def open_client(tool: Tool) -> FtpClient:
    return FtpClient(
        host=tool.host,
        user=tool.user,
        password=tool.password,
        port=tool.port,
        timeout=tool.timeout,
        encoding=tool.encoding,
    )
