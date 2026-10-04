"""CLAUDE.md's "Keeping these rules in sync" list is a documented list of files,
so it is checked both ways against the workspace top level's own list: every
copy the top level names (other than this one) is named here, every one named
here exists and is named there.

The live comparison is workspace only: a lone clone (or a mutant copy under
.mutants/) has no top level two folders up to compare with. That case is
SKIPPED with the reason, never passed silently. The comparison itself is the
pure function `list_problems`, proven both ways on planted texts that run
anywhere, so its mutant goes red in a copy too. The top level is found by its
CLAUDE.md carrying the section, not by anything of the layer's."""
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


def list_problems(mine_text, top_text, self_rel):
    """Every way this copy's list and the top level's disagree, as sentences; [] when
    they agree both ways. Paths here are relative to this repo (../../x), the top
    level's to the top (x); this repo names the top as ../../CLAUDE.md."""
    mine_raw, theirs_raw = sync_paths(mine_text), sync_paths(top_text)
    if mine_raw is None:
        return ["this CLAUDE.md has no 'Keeping these rules in sync' section"]
    if not theirs_raw or self_rel not in theirs_raw:
        return ["the top level list does not name this repo at all"]
    theirs = {"../../CLAUDE.md"} | {f"../../{p}" for p in theirs_raw if p != self_rel}
    mine = set(mine_raw)
    return ([f"{p}: named here but not by the top level" for p in sorted(mine - theirs)]
            + [f"{p}: named by the top level but missing here" for p in sorted(theirs - mine)])


def _section(*paths):
    return "# x\n\n## Keeping these rules in sync\n\n" + ", ".join(f"`{p}`" for p in paths) + "\n\n## Next\n"


class Comparison(unittest.TestCase):
    """The comparison on planted lists, both directions: runs anywhere."""
    SELF_REL = "tools/me/CLAUDE.md"

    def test_equal_lists_agree(self):
        mine = _section("../../CLAUDE.md", "../../a/CLAUDE.md")
        top = _section("a/CLAUDE.md", self.SELF_REL)
        self.assertEqual(list_problems(mine, top, self.SELF_REL), [])

    def test_a_copy_only_the_top_names_is_caught(self):
        mine = _section("../../CLAUDE.md")
        top = _section("a/CLAUDE.md", self.SELF_REL)
        self.assertEqual(list_problems(mine, top, self.SELF_REL),
                         ["../../a/CLAUDE.md: named by the top level but missing here"])

    def test_a_copy_only_this_one_names_is_caught(self):
        mine = _section("../../CLAUDE.md", "../../a/CLAUDE.md", "../../b/CLAUDE.md")
        top = _section("a/CLAUDE.md", self.SELF_REL)
        self.assertEqual(list_problems(mine, top, self.SELF_REL),
                         ["../../b/CLAUDE.md: named here but not by the top level"])

    def test_a_top_that_does_not_name_this_repo_is_caught(self):
        mine = _section("../../CLAUDE.md", "../../a/CLAUDE.md")
        top = _section("a/CLAUDE.md")
        self.assertTrue(list_problems(mine, top, self.SELF_REL))


class SyncList(unittest.TestCase):
    def test_own_section_names_the_top_level_and_not_itself(self):
        mine = sync_paths((ROOT / "CLAUDE.md").read_text())
        self.assertIsNotNone(mine, "CLAUDE.md has no 'Keeping these rules in sync' section")
        self.assertIn("../../CLAUDE.md", mine)
        self.assertNotIn("CLAUDE.md", mine, "a copy does not list itself")
        self.assertNotIn(f"../../{SELF}", mine, "a copy does not list itself")

    def test_list_matches_the_top_level_both_ways(self):
        top_md = TOP / "CLAUDE.md"
        top_text = top_md.read_text() if top_md.is_file() else ""
        if not sync_paths(top_text):
            self.skipTest(f"lone clone: {top_md} has no 'Keeping these rules in sync' list to compare with")
        mine_text = (ROOT / "CLAUDE.md").read_text()
        self.assertEqual(list_problems(mine_text, top_text, SELF), [])
        for p in sorted(sync_paths(mine_text)):
            self.assertTrue((ROOT / p).is_file(), f"{p} is named but does not exist")
