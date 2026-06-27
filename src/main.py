import logging

from src.app import AppConfig, LifelogApp
from src.database import init_database


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> None:
    configure_logging()
    init_database()

    app = LifelogApp(AppConfig())

    try:
        app.start()
        app.wait()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()


if __name__ == "__main__":
    main()
