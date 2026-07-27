"""Entry point so the runbook command is `python -m scripts.deploy`.

The two halves of deployment live side by side in this package and are used at
opposite ends of the trip: `pack.py` runs at the office and writes the bundle,
`preflight_cloud.py` rides inside that bundle as `preflight.py` and runs on the
cloud host. Keeping them in one folder is what makes the second fact easy to
remember -- the checker is not a loose utility, it is cargo.
"""

import sys

from scripts.deploy.pack import main

if __name__ == "__main__":
    sys.exit(main())
