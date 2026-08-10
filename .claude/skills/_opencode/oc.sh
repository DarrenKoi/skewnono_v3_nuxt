#!/usr/bin/env bash
#
# The single seam between the oc-* skills and the opencode CLI.
#
# Every safety property the skills claim is enforced here and nowhere else:
#
#   * Reviews run under `--agent plan`. That is a capability sandbox, not a
#     prompt convention -- opencode refuses write/edit tool calls outright,
#     so a delegated review cannot touch the shared working tree even if the
#     model misbehaves or a diff hunk carries a prompt injection. Verified:
#     `plan` will happily run `git diff` but returns a plan instead of a file.
#
#   * A Go-plan failure retries the same model on Zen. A Zen failure is
#     reported and the script exits non-zero. It NEVER falls back to a
#     weaker model -- a review that quietly ran on the wrong tier is worse
#     than one that visibly did not run.
#
#   * The session id is echoed to stderr so oc-discuss can continue one
#     specific thread. `opencode run -c` continues the *last* session
#     globally, which races when two debates overlap; explicit ids do not.
#
# Usage:
#   oc.sh --tier heavy|medium|light [--session ID] [--label TEXT] < prompt.txt
#   oc.sh --model glm-5.2           [--session ID] [--label TEXT] < prompt.txt
#
# The prompt is read from stdin so it can be arbitrarily long without
# fighting the shell over quoting.
#
# stdout  the model's reply text, and nothing else (safe to capture)
# stderr  tier choice, cost, OC_SESSION=<id>, and any error
#
set -uo pipefail

TIER=""
MODEL=""
SESSION=""
LABEL="opencode"

# Per-attempt ceiling in seconds. Generous, because a heavy-tier review over a
# large diff legitimately takes minutes; the point is to bound a hang, not to
# rush a real run.
OC_TIMEOUT="${OC_TIMEOUT:-600}"

while [ $# -gt 0 ]; do
  case "$1" in
    --tier)    TIER="$2";    shift 2 ;;
    --model)   MODEL="$2";   shift 2 ;;
    --session) SESSION="$2"; shift 2 ;;
    --label)   LABEL="$2";   shift 2 ;;
    *) echo "oc.sh: unknown argument: $1" >&2; exit 2 ;;
  esac
done

# Tier -> model. Kept in sync with models.md, which carries the *reasoning*
# for the mapping; this is only the lookup.
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

PROMPT="$(cat)"
if [ -z "${PROMPT// }" ]; then
  echo "oc.sh: empty prompt on stdin" >&2
  exit 2
fi

RAW="$(mktemp -t oc_raw)"
ERR="$(mktemp -t oc_err)"
trap 'rm -f "$RAW" "$ERR"' EXIT

# Where a failure reason actually lives depends on the output format, which is
# the kind of thing you only learn by looking:
#
#   default format  ->  "Error: Model is disabled" on stderr
#   --format json   ->  {"type":"error",...} on STDOUT, stderr empty
#
# We always use JSON, so stdout is the primary source and stderr is the
# fallback for failures that happen before the event stream starts.
json_error() {
  grep '^{' "$RAW" 2>/dev/null | jq -rs '
    [ .[]
      | select(.type == "error")
      | (.error.data.message // .error.name // "unknown error")
    ] | last // ""
  ' 2>/dev/null
}

# opencode paints stderr with ANSI colour and pads it with blank lines, so a
# naive `tail -1` reports an empty reason.
clean_err() {
  sed $'s/\033\[[0-9;]*[A-Za-z]//g' "$ERR" | grep -v '^[[:space:]]*$'
}

# One line saying why the attempt that just ran failed.
diagnose() {
  local msg
  msg="$(json_error)"
  [ -z "$msg" ] && msg="$(clean_err | tail -1)"
  if [ -z "$msg" ]; then
    msg="no diagnostic from opencode (usually an unrecognised model id -- check: opencode models)"
  fi
  printf '%s' "$msg"
}

# One attempt against one fully-qualified model id. Returns opencode's exit
# code; leaves JSON events in $RAW and diagnostics in $ERR.
#
# The watchdog is not paranoia: an unrecognised model id makes `opencode run
# --format json` hang forever rather than erroring (measured -- it sat for
# 3m20s producing nothing). macOS ships no coreutils `timeout`, so we run
# opencode in the background and race it against a sleeper.
attempt() {
  local qualified="$1"
  local -a args=(run --agent plan --format json -m "$qualified")
  [ -n "$SESSION" ] && args+=(-s "$SESSION")

  opencode "${args[@]}" "$PROMPT" >"$RAW" 2>"$ERR" &
  local pid=$!

  # Both streams must be redirected, not just silenced for tidiness: a
  # background subshell that still holds the inherited stdout keeps a
  # command substitution -- `SID=$(oc.sh ...)` -- blocked for the full
  # OC_TIMEOUT even after opencode has already exited. Detaching it here is
  # what makes the wrapper safe to call from `$( )`, which is how every
  # skill calls it.
  ( sleep "$OC_TIMEOUT"; kill -TERM "$pid" 2>/dev/null ) >/dev/null 2>&1 &
  local watchdog=$!

  wait "$pid"
  local status=$?

  kill "$watchdog" 2>/dev/null
  wait "$watchdog" 2>/dev/null

  # 143 == SIGTERM, i.e. the watchdog fired.
  if [ $status -eq 143 ]; then
    echo "[$LABEL] timed out after ${OC_TIMEOUT}s on $qualified" >&2
  fi
  return $status
}

echo "[$LABEL] model=$MODEL${TIER:+ (tier=$TIER)}${SESSION:+ session=$SESSION}" >&2

attempt "opencode-go/$MODEL"
STATUS=$?
USED="opencode-go/$MODEL"

GO_DIAG=""
if [ $STATUS -ne 0 ]; then
  # $RAW is overwritten by the retry, so capture the reason before it goes.
  GO_DIAG="$(diagnose)"
  echo "[$LABEL] opencode-go failed: $GO_DIAG" >&2
  echo "[$LABEL] retrying on Zen" >&2
  attempt "opencode/$MODEL"
  STATUS=$?
  USED="opencode/$MODEL"
fi

if [ $STATUS -ne 0 ]; then
  {
    echo "[$LABEL] FAILED on both providers for model '$MODEL'."
    echo "[$LABEL]   opencode-go: $GO_DIAG"
    echo "[$LABEL]   opencode:    $(diagnose)"
    echo "[$LABEL] Not downgrading to another tier -- rerun with an explicit --model."
  } >&2
  exit 1
fi

# opencode streams text as repeated events sharing one part id, so take the
# last version of each part rather than concatenating every delta.
JSON_ONLY="$(grep '^{' "$RAW" || true)"

if [ -z "$JSON_ONLY" ]; then
  echo "[$LABEL] no JSON events returned; raw output follows" >&2
  cat "$ERR" >&2
  exit 1
fi

REPLY="$(printf '%s\n' "$JSON_ONLY" | jq -rs '
  [ .[] | select(.type == "text") ]
  | group_by(.part.id)
  | map(last)
  | .[]
  | .part.text
')"

# A zero exit with no text is the dangerous case: the caller would format an
# empty review as if the model had found nothing wrong. Treat it as failure.
if [ -z "${REPLY// }" ]; then
  echo "[$LABEL] returned no text. Reason: $(diagnose)" >&2
  exit 1
fi

printf '%s\n' "$REPLY"

SID="$(printf '%s\n' "$JSON_ONLY" | jq -rs 'map(.sessionID) | map(select(. != null)) | last // ""')"
COST="$(printf '%s\n' "$JSON_ONLY" | jq -rs '
  [ .[] | select(.type == "step_finish") | .part.cost // 0 ] | add // 0
')"

echo "[$LABEL] done via $USED  cost=\$$COST" >&2
[ -n "$SID" ] && echo "OC_SESSION=$SID" >&2

exit 0
