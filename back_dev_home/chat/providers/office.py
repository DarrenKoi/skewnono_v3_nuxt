"""Office chat store hookup point (OpenSearch). Not yet connected."""


def _not_connected(*args, **kwargs):
    raise NotImplementedError(
        "The chat office adapter has not been connected. "
        "Configure the approved chat data platform before selecting office mode."
    )


create_thread = _not_connected
list_threads = _not_connected
get_thread = _not_connected
rename_thread = _not_connected
delete_thread = _not_connected
append_message = _not_connected
purge_expired = _not_connected
