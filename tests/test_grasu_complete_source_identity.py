"""Check promotion against frozen source hashes, not numerical or RTL equivalence."""

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1] / "kernels/grasu_complete"


class SourceIdentityTests(unittest.TestCase):
    def test_only_documented_binding_changes(self):
        provenance = json.loads((ROOT / "provenance.json").read_text())
        self.assertEqual(len(provenance["files"]), 11)
        for record in provenance["files"]:
            with self.subTest(path=record["path"]):
                contents = (ROOT / record["path"]).read_text()
                for transform in reversed(record["transforms"]):
                    before, after = transform["before"], transform["after"]
                    if after:
                        self.assertEqual(contents.count(after), 1)
                        contents = contents.replace(after, before)
                    else:
                        anchor = '#ifndef CACHE_BANK_REGISTERED'
                        # Undo the removed mandatory-token guard at its original location.
                        self.assertEqual(contents.count(anchor), 1)
                        contents = contents.replace(anchor, before + anchor)
                self.assertEqual(hashlib.sha256(contents.encode()).hexdigest(), record["origin_sha256"])


if __name__ == "__main__":
    unittest.main()
