"""Run the full offline regression suite with the available event-loop backend."""
import asyncio
import unittest
from pathlib import Path
try:
    import uvloop
except ImportError:
    pass
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

if __name__ == '__main__':
    suite=unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parents[1]/'tests'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
