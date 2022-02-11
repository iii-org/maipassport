from gunicorn.app.base import Application, Config
import gunicorn
from gunicorn import glogging
from gunicorn.workers import sync


class GUnicornFlaskApplication(Application):
    def __init__(self, app):
        self.usage, self.callable, self.prog, self.app = None, None, None, app

    def run(self, **options):
        self.cfg = Config()
        [self.cfg.set(key, value) for key, value in options.items()]
        return Application.run(self)

    load = lambda self:self.app


def app(environ, start_response):
    data = "Hello, World!\n"
    start_response("200 OK", [
        ("Content-Type", "text/plain"),
        ("Content-Length", str(len(data)))
    ])

    return iter(data)


if __name__ == "__main__":
    gunicorn_app = GUnicornFlaskApplication(app)
    gunicorn_app.run(
        worker_class="gunicorn.workers.sync.SyncWorker"
    )