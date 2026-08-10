#!/usr/bin/env bash
#
# The single seam between the oc-* skills and the opencode CLI.
#
# Every safety property the skills claim is enforced here and nowhere else:
#
#   * Reviews run under `--agent plan`. That is a capability sandbox, not a
#     prompt convention -- opencode refuses write/edit tool calls outright, so
#     a delegated review cannot touch the shared working tree even if the
#     model misbehaves or a diff hunk carries a prompt injection. Verified:
#     `plan` returns a plan instead of creating a file, while still running
#     `git diff` and reading sources normally.
#
#   * A provider failure on Go retries on Zen. If both fail, each reason is
#     reported and the script exits non-zero. It NEVER falls back to a weaker
#     model -- a review that quietly ran on a different tier than you were
#     told is worse than one that visibly did not run.
#
#   * A timeout is NOT a provider failure and is not retried on Zen. Retrying
#     an identical slow prompt just doubles the wait before the same outcome.
#
# Three findings from measurement drive the shape of this script, none of
# which are obvious from the CLI's help text:
#
#   1. `--format json` DROPS the final assistant message once the model makes
#      tool calls. A review run returns step/tool events and no text at all.
#      The default format returns it reliably, so we use the default format
#      and take the session id from `opencode session list` instead.
#   2. `opencode run` reads the prompt from stdin when given no positional
#      argument. Passing it as argv instead risks E2BIG on a large diff,
#      exposes the whole prompt to any local user via `ps`, and lets a prompt
#      starting with `-` be parsed as a flag.
#   3. In default format, stdout carries ONLY the reply text; the banner and
#      any "Error: ..." go to stderr. So stdout is safe to capture directly.
#
# Usage:
#   oc.sh --tier heavy|medium|light [--session ID] [--label TEXT] < prompt.txt
#   oc.sh --model glm-5.2           [--session ID] [--label TEXT] < prompt.txt
#
# stdout  the model's reply text, and nothing else
# stderr  progress, elapsed time, OC_SESSION=<id>, and any error
#
# Exit: 0 ok | 1 provider/empty failure | 2 usage error | 124 timeout
#
set -uo pipefail

TIER=""
MODEL=""
SESSION=""
LABEL="opencode"

# Per-attempt ceiling in seconds. Generous on purpose: a heavy-tier review over
# a real diff legitimately takes minutes (measured: 194s for a single-file
# review on kimi-k3). The point is to bound a hang, not to rush a real run.
OC_TIMEOUT="${OC_TIMEOUT:-900}"

# ${2:-} rather than $2: with `set -u`, a flag given without a value would
# otherwise die on an unbound variable and exit 1, which the caller cannot tell
# apart from a provider failure.
need_value() {
  [ -n "$2" ] || { echo "oc.sh: $1 needs a value" >&2; exit 2; }
}

while [ $# -gt 0 ]; do
  case "$1" in
    --tier)    need_value "$1" "${2:-}"; TIER="$2";    shift 2 ;;
    --model)   need_value "$1" "${2:-}"; MODEL="$2";   shift 2 ;;
    --session) need_value "$1" "${2:-}"; SESSION="$2"; shift 2 ;;
    --label)   need_value "$1" "${2:-}"; LABEL="$2";   shift 2 ;;
    *) echo "oc.sh: unknown argument: $1" >&2; exit 2 ;;
  esac
done

# An empty --session is rejected above rather than ignored. Silently dropping it
# would start a FRESH session while the caller believed it was continuing one --
# for oc-discuss that means round 2 argues with a model that never saw round 1,
# and reports success.
case "$OC_TIMEOUT" in
  ''|*[!0-9]*)
    echo "oc.sh: OC_TIMEOUT must be a whole number of seconds, got '$OC_TIMEOUT'" >&2
    exit 2 ;;
esac

# Tier -> model. models.md carries the *reasoning* for the mapping; this is
# only the lookup.
if [ -n "$TIER" ]; then
  case "$TIER" in
    heavy)  MODEL="kimi-k3" ;;
    medium) MODEL="glm-5.2" ;;
    light)  MODEL="gpt-5.6-luna" ;;
    *) echo "oc.sh: unknown tier '$TIER' (want heavy|medium|light)" >&2; exit 2 ;;
  esac
fi

if [ -z "$MODEL" ]; then
  echo "oc.sh: need --tier or --model" >&2
  exit 2
fi

# The explicit XXXXXX suffix keeps this working under GNU coreutils as well as
# BSD/macOS mktemp; without it GNU errors out, every path below ends up empty,
# and the script misreports the cause as "empty prompt on stdin".
PROMPT_FILE="$(mktemp -t oc_prompt.XXXXXX)"
OUT="$(mktemp -t oc_out.XXXXXX)"
ERR="$(mktemp -t oc_err.XXXXXX)"
# Presence of this file is the watchdog's own record that it fired. Inferring a
# timeout from exit status alone cannot distinguish our SIGTERM from opencode
# exiting 143 for its own reasons, which would skip the Zen retry on what was
# really a provider failure.
TIMEOUT_FLAG="$(mktemp -t oc_timeout.XXXXXX)"
WATCHDOG=""

# INT/TERM as well as EXIT. On a bare EXIT trap, a Ctrl-C or a parent killing a
# slow run leaves the watchdog subshell orphaned; OC_TIMEOUT seconds later it
# fires `kill` at a PID the OS may have recycled onto an unrelated process.
cleanup() {
  [ -n "$WATCHDOG" ] && kill "$WATCHDOG" 2>/dev/null
  rm -f "$PROMPT_FILE" "$OUT" "$ERR" "$TIMEOUT_FLAG"
}
trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM
# mktemp *creates* the file, and its existence is the signal, so clear it now.
# attempt() clears it again before each try; this covers the path where
# is_timeout is consulted before any attempt runs.
rm -f "$TIMEOUT_FLAG"

# Buffer stdin to a file rather than a shell variable: it keeps a large diff
# out of argv entirely, and lets the Zen retry re-read the same prompt.
cat > "$PROMPT_FILE"
if [ ! -s "$PROMPT_FILE" ]; then
  echo "oc.sh: empty prompt on stdin" >&2
  exit 2
fi

# A unique title makes the session findable afterwards. `opencode run -c`
# continues the *last* session globally, which races when two reviews run in
# parallel; looking up our own title does not.
#
# Each ATTEMPT gets its own tag, not just each invocation: a Go attempt can
# register its title and then fail, so a shared tag would leave two sessions
# with the same title and the lookup could return the dead one while the reply
# text came from Zen.
ATTEMPT_N=0
CUR_TAG=""

# opencode paints stderr with ANSI colour and pads it with blank lines, so a
# naive `tail -1` reports an empty reason.
clean_err() {
  sed $'s/\033\[[0-9;]*[A-Za-z]//g' "$ERR" | grep -v '^[[:space:]]*$'
}

diagnose() {
  local msg
  msg="$(clean_err | grep -i 'error' | tail -1)"
  [ -z "$msg" ] && msg="$(clean_err | tail -1)"
  if [ -z "$msg" ]; then
    msg="no diagnostic from opencode (often an unrecognised model id -- check: opencode models)"
  fi
  printf '%s' "$msg"
}

# One attempt against one fully-qualified model id.
attempt() {
  local qualified="$1"
  ATTEMPT_N=$((ATTEMPT_N + 1))
  CUR_TAG="octag-$$-${RANDOM}-${ATTEMPT_N}"
  rm -f "$TIMEOUT_FLAG"

  local -a args=(run --agent plan -m "$qualified" --title "$CUR_TAG")
  [ -n "$SESSION" ] && args+=(-s "$SESSION")

  opencode "${args[@]}" <"$PROMPT_FILE" >"$OUT" 2>"$ERR" &
  local pid=$!

  # Both streams must be redirected, not just silenced for tidiness: a
  # background subshell still holding the inherited stdout keeps a command
  # substitution -- SID=$(oc.sh ...) -- blocked for the full OC_TIMEOUT even
  # after opencode has already exited. Detaching it is what makes this script
  # safe to call from $( ), which is how the skills consume the session id.
  #
  # SIGKILL escalation matters because a single SIGTERM is not a guarantee:
  # if the CLI stalls inside its own signal handler, `wait` would block
  # forever -- the exact hang the watchdog exists to prevent.
  # Kill first, flag second: flagging before the kill means a run that finishes
  # in the gap is reported as a timeout and its (expensive) reply thrown away.
  ( sleep "$OC_TIMEOUT"
    kill -TERM "$pid" 2>/dev/null && touch "$TIMEOUT_FLAG"
    sleep 10
    kill -KILL "$pid" 2>/dev/null
  ) >/dev/null 2>&1 &
  WATCHDOG=$!

  # 2>/dev/null suppresses bash's own "Terminated: 15" job notice when the
  # watchdog kills opencode; that notice is noise in a skill's transcript and
  # is not the diagnostic we report.
  wait "$pid" 2>/dev/null
  local status=$?

  kill "$WATCHDOG" 2>/dev/null
  wait "$WATCHDOG" 2>/dev/null
  WATCHDOG=""
  return $status
}

# Ask the watchdog whether it fired, rather than inferring it from a signal
# exit status that opencode could also produce on its own.
is_timeout() { [ -f "$TIMEOUT_FLAG" ]; }

echo "[$LABEL] model=$MODEL${TIER:+ (tier=$TIER)}${SESSION:+ session=$SESSION} timeout=${OC_TIMEOUT}s" >&2
STARTED=$SECONDS

# Single home for the timeout exit, so the two call sites cannot drift apart.
fail_timeout() {
  echo "[$LABEL] timed out after ${OC_TIMEOUT}s on $1." >&2
  echo "[$LABEL] Not retrying -- a timeout is not a provider fault, so the" >&2
  echo "[$LABEL] same prompt would just be waited on twice." >&2
  echo "[$LABEL] Raise the ceiling with OC_TIMEOUT=<seconds> if the task is genuinely long." >&2
  exit 124
}

# One provider, end to end: run it, and if it comes back successful-but-empty,
# retry once before giving up on it.
#
# The empty case is worth a retry rather than a failure. Measured on both
# glm-5.2 and kimi-k3: a tool-using run ends with an empty final step (reason
# "unknown", 0 tokens) while every tool call succeeded. It is transient.
#
# Returns 0 success | 124 timeout | 3 empty twice | other = opencode's status.
# `is_timeout` is only consulted when the run actually failed: opencode exiting
# 0 with a full reply is a success even if the watchdog was mid-flight.
try_provider() {
  local qualified="$1"
  local st

  attempt "$qualified"; st=$?
  [ $st -ne 0 ] && is_timeout && return 124
  [ $st -ne 0 ] && return $st

  if [ ! -s "$OUT" ]; then
    echo "[$LABEL] empty final message from $qualified; retrying once" >&2
    attempt "$qualified"; st=$?
    [ $st -ne 0 ] && is_timeout && return 124
    [ $st -ne 0 ] && return $st
    [ -s "$OUT" ] || return 3
  fi
  return 0
}

USED="opencode-go/$MODEL"
try_provider "$USED"
STATUS=$?
[ $STATUS -eq 124 ] && fail_timeout "$USED"

GO_DIAG=""
if [ $STATUS -ne 0 ]; then
  # An empty reply is a failure of this provider like any other, so it falls
  # through to Zen rather than dead-ending on Go.
  if [ $STATUS -eq 3 ]; then
    GO_DIAG="empty final message twice"
  else
    GO_DIAG="$(diagnose)"
  fi
  echo "[$LABEL] opencode-go failed: $GO_DIAG" >&2
  echo "[$LABEL] retrying on Zen" >&2

  USED="opencode/$MODEL"
  try_provider "$USED"
  STATUS=$?
  [ $STATUS -eq 124 ] && fail_timeout "$USED"
fi

if [ $STATUS -ne 0 ]; then
  local_diag="$(diagnose)"
  [ $STATUS -eq 3 ] && local_diag="empty final message twice"
  {
    echo "[$LABEL] FAILED on both providers for model '$MODEL'."
    echo "[$LABEL]   opencode-go: $GO_DIAG"
    echo "[$LABEL]   opencode:    $local_diag"
    echo "[$LABEL] Not downgrading to another tier -- rerun with an explicit --model."
  } >&2
  exit 1
fi

cat "$OUT"

SID="$(opencode session list 2>/dev/null | grep -F "$CUR_TAG" | awk '{print $1}' | head -1)"
[ -z "$SID" ] && SID="$SESSION"

echo "[$LABEL] done via $USED in $((SECONDS-STARTED))s" >&2
[ -n "$SID" ] && echo "OC_SESSION=$SID" >&2

exit 0
