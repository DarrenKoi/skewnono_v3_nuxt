"""Worked examples for ftp_handler.web_app — non-blocking fleet runs in a server.

A fleet download blocks for the whole run; calling it inside a request handler
ties up the worker. BackgroundJobs runs it on a background thread so the request
returns at once and the result is polled later. Not tests; a copy-paste
reference. Single-process scope — see the web_app/jobs.py docstring for the
multi-worker caveat.
"""

from ftp_handler.direct_downloader import (
    FtpFleetDownloader,
    build_host_specs,
    save_to_dir,
)
from ftp_handler.web_app import BackgroundJobs, create_jobs_blueprint

USER = "ftpuser"
PASSWORD = "ftppass"


def example_fire_and_poll() -> None:
    """Kick a fleet run off the calling thread, then poll until it finishes."""
    import time

    jobs = BackgroundJobs()
    dl = FtpFleetDownloader(user=USER, password=PASSWORD)
    specs = build_host_specs([{"host": "10.0.0.1", "files": ["/log.txt"]}])

    job_id = jobs.submit(lambda: dl.download(specs))   # returns immediately
    while jobs.get(job_id).status == "running":
        time.sleep(0.5)

    job = jobs.get(job_id)
    print("status:", job.status, "error:", job.error)
    if job.status == "done":
        print("ok:", job.result.ok, "ng:", job.result.ng)


def example_flask_app_with_job_routes() -> None:
    """Wire the runner into a Flask app: POST to start, GET to poll.

    ``start`` lives in your app (it knows how to build specs / credentials) and
    just calls jobs.submit(...). The blueprint handles the HTTP plumbing.

        POST /fleet/jobs  {"fleet": [...], "dest": "/data/eqp"}  -> 202 {"job_id"}
        GET  /fleet/jobs/<job_id>                                -> 200 status
    """
    from flask import Flask

    app = Flask(__name__)
    jobs = BackgroundJobs()

    def start(body: dict) -> str:
        specs = build_host_specs(body["fleet"])
        dl = FtpFleetDownloader(user=USER, password=PASSWORD)
        on_file = save_to_dir(body["dest"]) if body.get("dest") else None
        return jobs.submit(lambda: dl.download(specs, on_file=on_file))

    app.register_blueprint(create_jobs_blueprint(jobs, start=start))
    app.run(host="0.0.0.0", port=5000)


def example_scheduled_run_needs_no_jobs() -> None:
    """If the run is purely SCHEDULED (no HTTP trigger), skip BackgroundJobs.

    An APScheduler job already runs on its own thread and never blocks a request,
    so call download() directly from the scheduled function.

        from apscheduler.schedulers.background import BackgroundScheduler
        sched = BackgroundScheduler()
        dl = FtpFleetDownloader(user=USER, password=PASSWORD)
        specs = build_host_specs([...])
        sched.add_job(lambda: dl.download(specs), "interval", minutes=30)
        sched.start()
    """
    print(example_scheduled_run_needs_no_jobs.__doc__)


if __name__ == "__main__":
    # example_fire_and_poll()
    # example_flask_app_with_job_routes()
    pass
