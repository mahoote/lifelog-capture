import logging

from src.app import LifelogApp
from src.configs.logging_config import configure_logging
from src.database import init_database


def main() -> None:
    configure_logging()
    init_database()

    app = LifelogApp()

    try:
        app.start()
        app.wait()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()


if __name__ == "__main__":
    main()
