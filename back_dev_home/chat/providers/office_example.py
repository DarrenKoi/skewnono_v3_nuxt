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
# DECISION (RAG 측 확인 2026-08-28): office thread storage IS the SQLite
# provider. Do NOT `cp` this file to office.py — presence detection reads
# office.py's existence as "storage ready" and would flip storage onto the
# stubs below. At the office and on the cloud, leave office.py absent and
# point SKEWNONO_CHAT_DB at a persistent path OUTSIDE the deploy overlay
# (the pack prunes *.db so a bundle never replaces the cloud's threads, but
# the default back_dev_home/chat/chat.db still lives inside the overlaid
# tree). The retention purge stays the mock's list-time purge; the checklist
# in MIGRATION.md "Office retention job rollout" applies only if storage
# ever moves to a multi-host store.
"""Office chat store hookup point — unused: SQLite is the office store."""


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
