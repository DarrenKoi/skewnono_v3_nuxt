# Context — equipment FTP collection

Glossary for the FTP fleet downloader and its two deployment paths. Terms only;
no implementation detail (that lives in `ftp_fleet_downloader.md`).

## Terms

### Fleet
The full set of equipment FTP servers polled in one scheduled run (~200+).

### Host
One equipment FTP server. Modeled as exactly one `HostSpec`. All files pulled
from a host in a run travel over **one** FTP connection, opened once and reused
for the directory listing and every file fetch, then closed. One host = one
spec = one connection. Pulling many files from a host needs no separate
function — they are listed on that host's single spec and fetched sequentially.

### Direct path
Deployment where the code doing FTP runs somewhere that can reach the equipment
servers directly (the Airflow worker). Uses streaming mode, so peak memory is
bounded by `concurrency × file size`, not total fleet size.

### Proxy path
Deployment for a firewalled client that cannot reach the equipment servers. The
client POSTs specs over HTTP to a Flask proxy on a firewall-free host; the proxy
does the real FTP and returns file bytes. Both paths are in use.

### Interchange seam (`FleetTransport`)
The contract that lets a call site swap Direct path for Proxy path by changing
one import line. Declared as the `FleetTransport` Protocol in
`direct_downloader/fleet_downloader.py`; both `FtpFleetDownloader` classes (direct
and the `proxy/proxy_downloader.py` HTTP client) satisfy it structurally, and a
conformance test asserts neither drifts. Every fleet operation is on the seam —
`download`, `list_dirs` (the Listing pass), `size_dirs`, `upload`, `mkdir`
(the Ensure-dir pass), and `delete` (the Removal pass) — and the proxy pair carries each over its own
`/<op>_sknn_v3` route, so a firewalled client gets the full workflow.

### File-size class
Whether a run's files are "small" (KB–few MB) or "large" (~10MB+). Drives the
memory and timeout safety analysis differently per path — the direct path
tolerates large files easily; the proxy path is sensitive to them.

### Single-server client
`FtpClient` (`core/client.py`): one host, one reused connection, ad-hoc
operations — `list_dir` (NLST, names only), `list_entries` (MLSD, subfolders
and files split into `DirEntries`), `list_details` (LIST, `FileInfo` with size
and tz-aware modified time), download / upload / remove / mkdir / rmdir. The
opposite scale from
the Fleet — no concurrency, no failure report; server errors propagate to the
caller. For notebooks and one-off scripts, not scheduled fleet runs.

### Listing command tiers
Three ways to list, in decreasing fidelity / increasing compatibility:
**MLSD** (`list_entries`) — typed, modern, the cleanest split of dirs vs files,
but newer equipment daemons may not support it. **LIST** (`list_details`) — the
broad fallback: parses the server's `ls -l`-style or MS-DOS/IIS text into typed
`FileInfo` with sizes and modified times. **NLST** (`list_dir`) — lowest common
denominator, names only, no type or time. LIST parsing covers two format
families (Unix and MS-DOS `%m-%d-%y %I:%M%p`); times are server-local wall clock
interpreted as KST by default, and the Unix year-less recent form infers the
year (rolling back if it lands in the future). Unrecognized lines are skipped;
each `FileInfo` keeps its `raw` line for diagnosing an uncovered format.

### Listing pass
The discovery step of a fleet run, run on its own ahead of any download:
`FtpFleetDownloader.list_dirs` (or the `list_fleet` helper) enumerates each
host's `listings` directories concurrently and returns a `ListingReport` of
`{host: [remote_path]}` — without fetching. For a large fleet where you must
"look before you download": inspect what's out there, then feed the chosen
paths back into `download` via `report.to_specs()`. Shares the Fleet's
concurrency, host-timeout, and per-host failure isolation.

### Ensure-dir pass
`FtpFleetDownloader.mkdir` (or `mkdir_fleet`) with `MkdirSpec(host, dirs)`: makes
each directory like `mkdir -p` — missing parents too, an existing directory
counts as success — so it runs before an `upload` to a new path. A refused MKD
is settled by CWD into that path, because FTP answers 550 both for "exists" and
for "denied".

### Removal pass
`FtpFleetDownloader.delete` (or `delete_fleet`) with `DeleteSpec(host, files,
dirs)`: DELE each file, then RMD each directory — empty directories only, no
recursive delete. A path already gone counts as success. A refusal is settled
by looking again (SIZE for a file, CWD for a directory), because FTP answers 550
both for "no such path" and for "denied".
