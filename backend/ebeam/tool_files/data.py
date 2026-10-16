"""SWAP SURFACE for tool-files provider selection.

What swaps is the FTP connection itself: both adapters return a context
manager with ``core.FtpClient``'s surface (``home``, ``list_details``,
``download``). Resolution, path checks and error mapping stay in shared code,
so the mock exercises them exactly as the office does.
"""

from backend._runtime.data_provider import get_data_provider
from backend.ebeam.tool_files.resolve import Tool


def open_client(tool: Tool):
    if get_data_provider("tool_files") == "office":
        from backend.ebeam.tool_files.providers.office import open_client as opener
    else:
        from backend.ebeam.tool_files.providers.mock import open_client as opener
    return opener(tool)
