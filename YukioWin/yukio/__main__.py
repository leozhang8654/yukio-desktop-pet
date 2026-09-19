import sys

from .cli import main

try:
    sys.exit(main())
except KeyboardInterrupt:
    sys.exit(130)
except BrokenPipeError:
    sys.exit(0)
