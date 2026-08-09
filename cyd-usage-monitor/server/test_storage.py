import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    from .storage import read_json, update_json
except ImportError:
    from storage import read_json, update_json


class StorageTests(unittest.TestCase):
    def test_concurrent_updates_do_not_lose_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "counter.json"

            def increment_many(_worker):
                for _ in range(50):
                    update_json(path, {"count": 0}, lambda payload: payload.update({"count": payload["count"] + 1}))

            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(increment_many, range(8)))

            self.assertEqual(read_json(path, {})["count"], 400)


if __name__ == "__main__":
    unittest.main()
