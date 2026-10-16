"""The office template opens a direct FtpClient on the resolved tool's account."""

from ftp_handler.core import FtpClient

from backend.ebeam.tool_files.providers import office_example as office
from backend.ebeam.tool_files.resolve import Tool


def test_open_client_builds_a_direct_ftp_client_for_the_resolved_tool():
    tool = Tool(
        eqp_id="HCDX303",
        fab_name="M11A",
        tool_type="cd-sem",
        host="10.0.0.7",
        user="verity",
        password="pw",
        port=2121,
        timeout=8.0,
        encoding="latin-1",
    )

    client = office.open_client(tool)

    assert isinstance(client, FtpClient)
    assert (client.host, client.user, client.password, client.port, client.timeout, client.encoding) == (
        "10.0.0.7",
        "verity",
        "pw",
        2121,
        8.0,
        "latin-1",
    )
