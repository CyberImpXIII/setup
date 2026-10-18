"""The `## Fit` rule of `setup plans` (PLAN-architecture.md §6, §9 step 2; approved:
Jacob 2026-10-18).

A plan that creates a tool carries a fit report: a `## Fit` heading (level 2 to 4,
numbered or not, a parenthesis after it allowed) with a section under it that is
not empty, answering §6's questions (fits, duplicates, gives, costs), each with
evidence or `unknown`. Any plan may carry one; a plan that creates a tool must.

Which plans create a tool is read from the plan's own header, never guessed from
its prose: a line in the first 25, as the `**Status:` line is read,

    > **Creates:** `tools/example`

naming each tool's path in backticks. In each plan not done:

- one declaring `Creates` with no `## Fit` heading fails (`no-fit`);
- a `## Fit` section with nothing under it but blank lines fails (`empty-fit`);
- a `Creates` line naming no path in backticks fails (`no-path`).

A plan that creates a tool and does not declare it is not seen: the declaration is
the plan author's to write (PLAN-architecture §9 step 2; TODO.md)."""
import re

from setuplib import plans, rsids

TITLE = re.compile(r"^Fit(?:\s*\(.*\))?$")
CREATES_RX = re.compile(r"^>?\s*\*\*Creates:(?:\*\*)?\s*(.*)$")  # `**Creates:** ...` or `**Creates: ...**`
PATH_RX = re.compile(r"`([^`\s]+)`")
HEADER_LINES = 25  # as audit.STATUS_RX is read
KINDS = ("no-fit", "empty-fit", "no-path")


def read(text):
    """(creates [(line no, [paths])], fit [(line no, empty)]) of one plan."""
    lines = text.splitlines()
    live = set(rsids._unfenced(lines))
    creates = []
    for i in range(min(HEADER_LINES, len(lines))):
        m = CREATES_RX.match(lines[i]) if i in live else None
        if m:
            creates.append((i + 1, PATH_RX.findall(m.group(1))))
    heads, _ = plans._headings(lines)
    fit = []
    for k, (i, level, _num, title) in enumerate(heads):
        if 2 <= level <= 4 and TITLE.match(title):
            end = next((j for j, lv, _, _ in heads[k + 1:] if lv <= level), len(lines))
            body = [lines[j] for j in range(i + 1, end) if lines[j].strip()]
            fit.append((i + 1, not body))
    return creates, fit


def findings(named_texts):
    """(findings ["<file>:<line>: <kind>: <why>"], declaring [plan names that declare
    Creates], with_fit [plan names carrying a `## Fit` heading]) over [(file name,
    text)] of the plans not done."""
    out, declaring, with_fit = [], [], []
    for name, text in named_texts:
        creates, fit = read(text)
        if fit:
            with_fit.append(name)
        for n, empty in fit:
            if empty:
                out.append(f"{name}:{n}: empty-fit: the `## Fit` section answers §6's questions "
                           "(fits, duplicates, gives, costs), each with evidence or `unknown`")
        for n, paths in creates:
            if not paths:
                out.append(f"{name}:{n}: no-path: a `**Creates:**` line names each tool's path in backticks")
        if creates:
            declaring.append(name)
            if not fit:
                out.append(f"{name}:{creates[0][0]}: no-fit: a plan that creates a tool "
                           f"({', '.join(p for _, ps in creates for p in ps) or 'no path named'}) "
                           "carries a `## Fit` heading (PLAN-architecture §6)")
    return out, declaring, with_fit
