import os

from back_dev_home import create_app

app = create_app()
application = app

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=True)
