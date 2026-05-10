import os

from back_dev_home import create_app
from back_dev_home._runtime.env import is_cloud

app = create_app()
application = app

if __name__ == "__main__":
    cloud = is_cloud()
    host = "0.0.0.0" if cloud else "127.0.0.1"
    app.run(host=host, port=int(os.environ.get("PORT", 5000)), debug=not cloud)
