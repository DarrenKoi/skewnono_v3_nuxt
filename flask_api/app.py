import os

from . import app


if __name__ == '__main__':
  app.run(
    host=os.getenv('FLASK_HOST', '127.0.0.1'),
    port=int(os.getenv('FLASK_PORT', '5000')),
    debug=os.getenv('FLASK_DEBUG') == '1'
  )
