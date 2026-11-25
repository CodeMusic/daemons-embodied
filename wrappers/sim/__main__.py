"""Stand the simulated body up on this computer and draw it in a browser:

    python3 -m wrappers.sim            # then open http://127.0.0.1:8765/
    python3 -m wrappers.sim --port 9000

It lies there settled until something moves it. To watch it move, run the body check against it with the same
page: `python3 -m tools.bodycheck wrappers/sim --live --option page=8765`.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from embodied import wrapper


def main() -> int:
    parser = argparse.ArgumentParser(description="The simulated body, drawn in a browser page.")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    driver = wrapper.load(Path(__file__).parent).driver(page=args.port)
    driver.connect()
    print(f"The simulated body is at http://127.0.0.1:{args.port}/  (Ctrl-C to put it away)")  # DRAFT
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        driver.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
