import sys

from expenses_tracker.cli import main as cli_main
from expenses_tracker.gui import main as gui_main
from expenses_tracker.logging_config import configure_logging, get_logger

configure_logging(level="INFO", log_dir="logs", json_format=True, console=True)
logger = get_logger("expenses_tracker")

if __name__ == "__main__":
    logger.info("Starting application", extra={"argv": sys.argv})
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        sys.argv.pop(1)
        raise SystemExit(cli_main())

    raise SystemExit(gui_main(sys.argv[1:]))
