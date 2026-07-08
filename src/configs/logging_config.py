import logging


class ColorLevelFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[90m",      # gray
        logging.INFO: "\033[32m",       # green
        logging.WARNING: "\033[33m",    # yellow
        logging.ERROR: "\033[31m",      # red
        logging.CRITICAL: "\033[35m",   # magenta
    }

    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, self.RESET)

        original_levelname = record.levelname
        record.levelname = f"{color}{record.levelname}{self.RESET}"

        try:
            return super().format(record)
        finally:
            record.levelname = original_levelname


def configure_logging() -> None:
    log_format = "%(asctime)s %(levelname)s %(name)s: %(message)s"

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(ColorLevelFormatter(log_format))

    file_handler = logging.FileHandler("lifelog.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format))

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[
            console_handler,
            file_handler,
        ],
        force=True,
    )

    logging.getLogger().setLevel(logging.DEBUG)
