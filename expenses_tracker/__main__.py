import sys

from expenses_tracker.cli import main as cli_main
from expenses_tracker.gui import main as gui_main


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        sys.argv.pop(1)
        raise SystemExit(cli_main())

    raise SystemExit(gui_main())
