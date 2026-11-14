import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("account_ranges", Path(__file__).resolve().parents[1] / "tools/preserve-account-ranges.py")
account_ranges = importlib.util.module_from_spec(spec)
spec.loader.exec_module(account_ranges)


class AccountRanges(unittest.TestCase):
    def test_named_and_numeric_owners_exclude_declared_accounts(self):
        owners = account_ranges.account_owners('daemon:x:99:99::/:/bin/false\nperson:x:1001:100::/home/person:/bin/fish\n', {'daemon'})
        self.assertEqual(owners, {'person', '1001'})

    def test_preserve_arbitrary_existing_accounts(self):
        result = account_ranges.merge([], [("chosen-name", 165536, 65536)], {"chosen-name"})
        self.assertEqual(result, "chosen-name:165536:65536\n")

    def test_deleted_accounts_are_not_restored(self):
        self.assertEqual(account_ranges.merge([], [("removed", 100000, 65536)], set()), "")

    def test_existing_ranges_are_not_duplicated(self):
        value = ("person", 100000, 65536)
        self.assertEqual(account_ranges.merge([value], [value], {"person"}), "person:100000:65536\n")

    def test_conflicts_do_not_reassign_other_accounts(self):
        with self.assertRaises(ValueError):
            account_ranges.merge([("service", 100000, 65536)], [("person", 120000, 65536)], {"person"})

    def test_adjacent_ranges_do_not_conflict(self):
        result = account_ranges.merge([("service", 100000, 65536)], [("person", 165536, 65536)], {"person"})
        self.assertIn("person:165536:65536", result)

    def test_malformed_ranges_are_rejected(self):
        for text in ("person:100:0", "person:-1:100", "person:not-a-number:10", "bad"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                account_ranges.ranges(text)
