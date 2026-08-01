# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
#
# NOT the place for the LLM API key or model list. Chat has two independent
# swap surfaces (see chat/MIGRATION.md):
#
#   Surface A - LLM gateway: env-only, in back_dev_home/.env:
#       CHAT_BASE_URL=http://<internal-llm-gateway>/v1   (client appends /chat/completions)
#       CHAT_API_KEY=<office bearer token>
#       CHAT_MODELS=[{"id":"<model-id>","label":"<picker text>"}, ...]
#   Surface B - thread storage: THIS file. Where threads/messages persist.
#
# Do NOT `cp` this file to office.py until storage is actually implemented:
# presence detection reads office.py's existence as "storage ready", so an
# unimplemented copy flips chat storage onto the stubs below and breaks the
# page. To TEST chat at the office, leave office.py absent — storage stays on
# the working SQLite mock and the CHAT_* env alone selects the internal gateway.
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
get_message_by_request = _not_connected
get_owned_message = _not_connected
append_user_message = _not_connected
set_scope_decision = _not_connected
complete_turn = _not_connected
put_feedback = _not_connected
delete_feedback = _not_connected
purge_expired = _not_connected
