"""CLAUDE.md's "Keeping these rules in sync" list is a documented list of files,
so it is checked both ways against the workspace top level's own list: every
copy the top level names (other than this one) is named here, every one named
here exists and is named there.

Workspace only: a lone clone has no top level two folders up to compare with.
That case is SKIPPED with the reason, never passed silently. The top level is
found by its CLAUDE.md carrying the section, not by anything of the layer's."""
import re
import unittest

from tests.helpers import ROOT

TOP = (ROOT / "../..").resolve()
SELF = ROOT.relative_to(TOP).as_posix() + "/CLAUDE.md" if ROOT.is_relative_to(TOP) else None
SECTION_RX = re.compile(r"^## Keeping these rules in sync\n(.*?)(?=^## |\Z)", re.M | re.S)
PATH_RX = re.compile(r"`([^`]*CLAUDE\.md)`")


def sync_paths(md_text):
    m = SECTION_RX.search(md_text)
    return None if m is None else PATH_RX.findall(m.group(1))


class SyncList(unittest.TestCase):
    def test_own_section_names_the_top_level_and_not_itself(self):
        mine = sync_paths((ROOT / "CLAUDE.md").read_text())
        self.assertIsNotNone(mine, "CLAUDE.md has no 'Keeping these rules in sync' section")
        self.assertIn("../../CLAUDE.md", mine)
        self.assertNotIn("CLAUDE.md", mine, "a copy does not list itself")
        self.assertNotIn(f"../../{SELF}", mine, "a copy does not list itself")

    def test_list_matches_the_top_level_both_ways(self):
        top_md = TOP / "CLAUDE.md"
        theirs_raw = sync_paths(top_md.read_text()) if top_md.is_file() else None
        if not theirs_raw:
            self.skipTest(f"lone clone: {top_md} has no 'Keeping these rules in sync' list to compare with")
        self.assertIn(SELF, theirs_raw, "the top level list does not name this repo at all")
        theirs = {"../../CLAUDE.md"} | {f"../../{p}" for p in theirs_raw if p != SELF}
        mine = set(sync_paths((ROOT / "CLAUDE.md").read_text()))
        self.assertEqual(sorted(mine - theirs), [], "named here but not by the top level")
        self.assertEqual(sorted(theirs - mine), [], "named by the top level but missing here")
        for p in sorted(mine):
            self.assertTrue((ROOT / p).is_file(), f"{p} is named but does not exist")
