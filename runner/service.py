"""Hidden Scheduled Task entrypoint. Fatal errors remain visible in local log."""
import sys
import traceback
from .core import DEFAULT_STATE, Queue
from .worker import Worker

DEFAULT_STATE.mkdir(parents=True,exist_ok=True)
with (DEFAULT_STATE/'service.log').open('a',encoding='utf-8',buffering=1) as log:
    sys.stdout=log;sys.stderr=log
    try: Worker(Queue()).run()
    except BaseException:
        traceback.print_exc();raise SystemExit(1)
