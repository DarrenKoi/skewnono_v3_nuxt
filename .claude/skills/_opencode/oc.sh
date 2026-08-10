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

while [ $# -gt 0 ]; do
  case "$1" in
    --tier)    TIER="$2";    shift 2 ;;
    --model)   MODEL="$2";   shift 2 ;;
    --session) SESSION="$2"; shift 2 ;;
    --label)   LABEL="$2";   shift 2 ;;
    *) echo "oc.sh: unknown argument: $1" >&2; exit 2 ;;
  esac
done

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

PROMPT_FILE="$(mktemp -t oc_prompt)"
OUT="$(mktemp -t oc_out)"
ERR="$(mktemp -t oc_err)"
# Presence of this file is the watchdog's own record that it fired. Inferring a
# timeout from exit status alone cannot distinguish our SIGTERM from opencode
# exiting 143 for its own reasons, which would skip the Zen retry on what was
# really a provider failure.
TIMEOUT_FLAG="$(mktemp -t oc_timeout)"
trap 'rm -f "$PROMPT_FILE" "$OUT" "$ERR" "$TIMEOUT_FLAG"' EXIT
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
  ( sleep "$OC_TIMEOUT"
    touch "$TIMEOUT_FLAG"
    kill -TERM "$pid" 2>/dev/null
    sleep 10
    kill -KILL "$pid" 2>/dev/null
  ) >/dev/null 2>&1 &
  local watchdog=$!

  # 2>/dev/null suppresses bash's own "Terminated: 15" job notice when the
  # watchdog kills opencode; that notice is noise in a skill's transcript and
  # is not the diagnostic we report.
  wait "$pid" 2>/dev/null
  local status=$?

  kill "$watchdog" 2>/dev/null
  wait "$watchdog" 2>/dev/null
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

attempt "opencode-go/$MODEL"
STATUS=$?
USED="opencode-go/$MODEL"

is_timeout && fail_timeout "$USED"

GO_DIAG=""
if [ $STATUS -ne 0 ]; then
  GO_DIAG="$(diagnose)"
  echo "[$LABEL] opencode-go failed: $GO_DIAG" >&2
  echo "[$LABEL] retrying on Zen" >&2
  attempt "opencode/$MODEL"
  STATUS=$?
  USED="opencode/$MODEL"
  is_timeout && fail_timeout "$USED"
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

# A zero exit with no text is the dangerous case: the caller would format an
# empty review as if the model had found nothing wrong.
#
# This is common enough to be worth one retry rather than one failure. Measured
# on both glm-5.2 and kimi-k3: a tool-using run ends with an empty final step
# (reason "unknown", 0 tokens) while every tool call succeeded. It is transient,
# so the same prompt usually answers on the second try.
if [ ! -s "$OUT" ]; then
  echo "[$LABEL] empty final message from $USED; retrying once" >&2
  attempt "$USED"
  STATUS=$?
  is_timeout && fail_timeout "$USED"
fi

if [ ! -s "$OUT" ]; then
  echo "[$LABEL] returned no text twice (empty final message). Last reason: $(diagnose)" >&2
  echo "[$LABEL] Treating as failure rather than reporting an empty review." >&2
  exit 1
fi

cat "$OUT"

SID="$(opencode session list 2>/dev/null | grep -F "$CUR_TAG" | awk '{print $1}' | head -1)"
[ -z "$SID" ] && SID="$SESSION"

echo "[$LABEL] done via $USED in $((SECONDS-STARTED))s" >&2
[ -n "$SID" ] && echo "OC_SESSION=$SID" >&2

exit 0
