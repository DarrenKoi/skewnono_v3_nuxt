"""Run fleet collection off the request thread in a long-lived web server.

``BackgroundJobs`` runs a (blocking) fleet download on a background thread so an
HTTP handler returns immediately and the result is polled later::

    from ftp_handler.web_app import BackgroundJobs, create_jobs_blueprint
"""

from .jobs import (
    BackgroundJobs,
    Job,
    create_jobs_blueprint,
    job_to_dict,
    summarize,
)

__all__ = [
    "BackgroundJobs",
    "Job",
    "summarize",
    "job_to_dict",
    "create_jobs_blueprint",
]
