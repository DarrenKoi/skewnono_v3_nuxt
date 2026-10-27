Reviewed `be541289cef776d0d875d23bf682748980ead4ad` against the direct client.

### [blocker] Encoding failures lose a put's leftover temp path and can change exception type
- where: ftp_handler/proxy/proxy_client.py:178; ftp_handler/proxy/flask_proxy.py:456
- failing input: STOR succeeds, rename raises UnicodeDecodeError on an undecodable FTP reply, and cleanup DELE is refused. Direct put raises UnicodeDecodeError with temp_path and __notes__; proxy put raises UnicodeDecodeError without either, although its .part file remains. Reproduced through the Flask bridge. The route includes temp_path, but the encoding branch raises before attaching it. Also, upload of a path outside the configured charset raises UnicodeEncodeError directly but becomes UnicodeDecodeError through this same mapping.
- fix: Preserve encode versus decode errors in the wire format, reconstruct the matching exception, and apply temp_path/notes restoration to encoding errors too. Add parity cases for both failures.

### [should] A lost write response body escapes the promised ProxyError mapping
- where: ftp_handler/proxy/proxy_client.py:168; ftp_handler/proxy/proxy_client.py:190
- failing input: requests.post returns streamed headers, then the connection breaks while resp.json() reads either the 200 confirmation or a 422 error body. These reads are outside the RequestException handler. In-memory responses raising requests.ConnectionError reproduced a bare ConnectionError for both statuses, rather than ProxyError. A write may already have completed, so callers handling the documented ProxyError outcome miss this case.
- fix: Catch requests.RequestException around response-body reads and translate it to ProxyError, retaining response closure. Test body failure after headers, rather than only post() failing before a response exists.

### [should] Default write calls can wait forever for the HTTP proxy
- where: ftp_handler/proxy/proxy_client.py:154; ftp_handler/proxy/proxy_client.py:274
- failing input: remove('/in/a') with the default timeout=8.0 sends requests timeout=(8.0, None), as confirmed in memory. If the HTTP connection is accepted but the proxy stalls before its response, the caller waits indefinitely. upload, mkdir, rmdir and put without a deadline take the same path. The envelope's FTP socket timeout cannot bound a stalled HTTP proxy, including one that already performed the write.
- fix: Give writes an explicit finite HTTP wait budget, allowing for the FTP work, and report expiry as ProxyError with an unknown write outcome. Add a test asserting a finite read timeout for default write calls; the existing bridge records but never enforces timeouts.

Validation: the permitted unittest command passed all 87 tests, with PYTHONDONTWRITEBYTECODE=1. Additional in-memory checks reproduced the encoding information loss and response-body exception leak and inspected the actual write timeout arguments. Malformed op/path/base64 inputs are rejected before invoking the FTP write method. No repository files were edited, staged or committed.
Not checked: live FTP servers, deployed proxy/uWSGI, or real network timing. The timeout finding is based on the supplied requests arguments, not a live hang test.
Verdict: Fix the three findings before relying on direct/proxy write parity and its documented failure handling.

## 2차 확인

Reviewed `2a9a29df626fc9523503901d795a5f5972fc19fe`.
- Finding 1: resolved. Encoding errors now preserve encode/decode type and receive the shared temp_path/__notes__ restoration; the new parity tests cover the original failure cases.
- Finding 2: resolved. Both 200 and 422 response-body RequestException paths now produce ProxyError and close the response; the new body-loss test exercises both statuses.
- Finding 3: resolved under the clarified policy. remove/mkdir/rmdir now use a finite HTTP read timeout; upload and put without a deadline deliberately retain the documented unbounded wait. Without a minimum transfer rate or a progress protocol, no fixed file-transfer wait safely bounds all valid STOR operations, so that part of the original recommendation is withdrawn.

No new correctness issue introduced by this commit was found.
Validation: the same three unittest modules passed all 91 tests with PYTHONDONTWRITEBYTECODE=1; no repository files were modified.
Not checked: live FTP, deployed proxy/uWSGI, or real network timing; upload and put without a deadline can still wait indefinitely by the accepted policy.
Verdict: All three original findings are resolved within the clarified scope; no new blocker found.
