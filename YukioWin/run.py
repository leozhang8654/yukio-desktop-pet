#!/usr/bin/env python3
"""雪绪 · DeepSeek / Windows 版的入口：python run.py [参数]。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.platform == "win32" and getattr(sys, "frozen", False):
    import velopack
    velopack.App().set_auto_apply_on_startup(False).run()

from yukio.cli import main

if __name__ == "__main__":
    try:
        if len(sys.argv) == 4 and sys.argv[1] in ("--update-smoke", "--update-smoke-verify"):
            from yukio.update_smoke import run
            sys.exit(run(sys.argv[1:]))
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except BrokenPipeError:
        # 被 head 之类截断输出时安静退出。
        try:
            sys.stdout.close()
        except Exception:
            pass
        sys.exit(0)
