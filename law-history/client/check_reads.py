#!/usr/bin/env python3
"""Run every stored read of the law-history cookbook against a served graph and check
its rows against seed.md, through the Omnigraph Python client.

Load the seed into an empty graph first: the expected rows are those of a fresh
seed, before the add-a-case walkthrough. The defaults match the root README's
local setup: the gateway at https://localhost:8443, its CA under $OMNIGRAPH_HOME,
and the reader's token in OG_LOCAL_READER_TOKEN.

    python3 -m pip install -r law-history/client/requirements.txt
    python3 law-history/client/check_reads.py
    python3 law-history/client/check_reads.py --url https://graph.example --token-env MY_TOKEN --ca ca.pem
"""
import argparse
import asyncio
import os
import re
import ssl
import sys

import httpx
from omnigraph import Omnigraph, OmnigraphError

HERE = os.path.dirname(os.path.abspath(__file__))
DEBTOR = "11 U.S.C. § 1182(1)"


def col(rows, key):
    return [row[key] for row in rows]


# (stored read, parameters, what seed.md says it returns, a test of the rows)
CHECKS = [
    ("text_on", {"label": DEBTOR, "on": "2022-05-01"}, "version 3, the CARES sunset text",
     lambda r: col(r, "version") == ["tv-usc11-1182-1-3"]),
    ("text_on", {"label": DEBTOR, "on": "2021-01-15"}, "version 2, the $7,500,000 limit",
     lambda r: col(r, "version") == ["tv-usc11-1182-1-2"]),
    ("text_on", {"label": "2 U.S.C. § 441b(b)(2)", "on": "2010-01-21"}, "the text Citizens United read",
     lambda r: col(r, "version") == ["tv-feca-316-b-2-2"]),
    ("text_on", {"label": "2 U.S.C. § 441b(b)(2)", "on": "2020-01-01"}, "nothing: the old number names nothing since 2014",
     lambda r: r == []),
    ("text_on", {"label": "52 U.S.C. § 30118(b)(2)", "on": "2020-01-01"}, "the 2014 text",
     lambda r: col(r, "version") == ["tv-feca-316-b-2-3"]),
    ("text_on", {"label": "FECA § 316(b)(2)", "on": "2020-01-01"}, "the 2014 text, by the act's own number",
     lambda r: col(r, "version") == ["tv-feca-316-b-2-3"]),
    ("text_on", {"label": "52 U.S.C. § 30118(a)", "on": "1995-06-01"}, "nothing: before the record starts",
     lambda r: r == []),
    ("versions", {"label": DEBTOR}, "five versions, three distinct hashes",
     lambda r: len(r) == 5 and len(set(col(r, "v.text_sha256"))) == 3),
    ("version_sources", {"version": "tv-usc11-1182-1-3"}, "Pub. L. 116-136 and Pub. L. 117-5",
     lambda r: sorted(col(r, "s.slug")) == ["src-pl-116-136", "src-pl-117-5"]),
    ("later_law_reaching_back", {"label": DEBTOR, "event_on": "2022-05-01"}, "the 2022 change reaching back",
     lambda r: col(r, "c.slug") == ["chg-btatca-1182"]),
    ("later_law_reaching_back", {"label": DEBTOR, "event_on": "2019-12-01"}, "nothing",
     lambda r: r == []),
    ("changes_to", {"label": "52 U.S.C. § 30118(b)(2)"}, "BCRA § 203(a), BCRA § 214(d), the 2014 reclassification",
     lambda r: col(r, "c.slug") == ["chg-bcra-203a", "chg-bcra-214d", "chg-olrc-t52-30118"]),
    ("changes_to", {"label": DEBTOR}, "6 rows for 5 changes, one law modifying the CARES sunset",
     lambda r: len(r) == 6 and col(r, "m.role").count("modified") == 1),
    ("changes_between", {"from": "2020-01-01", "to": "2023-01-01"}, "5 changes",
     lambda r: len(r) == 5),
    ("citations", {"label": "2 U.S.C. § 441b"}, "the four numbers the section has carried",
     lambda r: set(col(r, "e.label")) == {"FECA § 321", "FECA § 316", "2 U.S.C. § 441b", "52 U.S.C. § 30118"}),
    ("cited_as_on", {"label": "2 U.S.C. § 441b(a)", "on": "2026-10-31"}, "today's code and act numbers",
     lambda r: set(col(r, "e.label")) == {"52 U.S.C. § 30118(a)", "FECA § 316(a)"}),
    ("cited_as_on", {"label": "2 U.S.C. § 441b", "on": "1978-01-01"}, "the numbers in use in 1978",
     lambda r: set(col(r, "e.label")) == {"FECA § 321", "2 U.S.C. § 441b"}),
    ("citations_from", {"version": "tv-feca-316-b-2-2"}, "section 431, cited today as 52 U.S.C. § 30101 and FECA § 301",
     lambda r: set(col(r, "cited_today_as")) == {"52 U.S.C. § 30101", "FECA § 301"}),
    ("renumberings", {}, "the 2014 reclassification",
     lambda r: col(r, "before") == ["tv-feca-316-b-2-2"]),
    ("held_invalid", {"label": "2 U.S.C. § 441b"}, "Citizens United",
     lambda r: col(r, "j.citation") == ["558 U.S. 310"]),
    ("held_invalid", {"label": "52 U.S.C. § 30118(a)"}, "nothing: the holding is on the section",
     lambda r: r == []),
    ("held_invalid_enclosing", {"label": "52 U.S.C. § 30118(a)"}, "Citizens United, on the enclosing section",
     lambda r: col(r, "j.citation") == ["558 U.S. 310"]),
    ("judgments_applying", {"label": "52 U.S.C. § 30118(b)(2)"}, "Citizens United, reading the 2002 text",
     lambda r: col(r, "version_read") == ["tv-feca-316-b-2-2"]),
    ("later_invalidations", {"citation": "558 U.S. 310"}, "nothing: no later judgment is recorded",
     lambda r: r == []),
    ("precedents_on_changed_text", {"on": "2026-10-31"}, "Citizens United read text no longer in force",
     lambda r: col(r, "version_on_date") == ["tv-feca-316-b-2-3"]),
    ("term_users", {"term": "small business debtor"}, "versions 1, 3 and 5 of § 1182(1)",
     lambda r: len(r) == 3),
    ("definition_reach", {"label": DEBTOR, "on": "2026-10-31"}, '"debtor", used by § 1182(2)',
     lambda r: col(r, "used_by") == ["prov-usc11-1182-2"]),
    ("search_text", {"q": "electioneering communication"}, "the 2002 or 2014 text of (b)(2) first",
     lambda r: bool(r) and r[0]["v.slug"] in ("tv-feca-316-b-2-2", "tv-feca-316-b-2-3")),
    ("laws", {}, "8 laws", lambda r: len(r) == 8),
    ("sources", {}, "21 sources, all open to commercial reuse",
     lambda r: len(r) == 21 and all(col(r, "s.commercial_reuse"))),
    ("coverage", {}, "5 provisions", lambda r: len(r) == 5),
    ("overlapping_versions", {}, "nothing", lambda r: r == []),
    ("versions_without_source", {}, "nothing", lambda r: r == []),
    ("changes_without_source", {}, "nothing", lambda r: r == []),
    ("holdings_to_review", {}, "nothing", lambda r: r == []),
]


async def check(og):
    declared = set(re.findall(r"^query (\w+)\(", open(os.path.join(HERE, "..", "queries", "law.gq")).read(), re.M))
    unchecked = declared - {name for name, *_ in CHECKS}
    failures = [f"no check for the stored read {name}" for name in sorted(unchecked)]
    for name, params, expected, test in CHECKS:
        try:
            result = await og.queries.invoke(name, params=params, expect_mutation=False)
        except OmnigraphError as error:
            if error.status in (0, 401, 403):
                raise  # no answer, or this token may not read: no later read can pass either
            failures.append(f"{name} {params}: {type(error).__name__} {error.code}: {error}")
            print(f"FAIL {name} {params}: {error.code}")
            continue
        rows = result["rows"]
        try:
            passed = test(rows)
        except (KeyError, IndexError, TypeError) as error:
            passed = False
            expected += f" (rows lack {error})"
        print(f"{'ok  ' if passed else 'FAIL'} {name} {params}: {len(rows)} rows")
        if not passed:
            failures.append(f"{name} {params}: expected {expected}; got {rows}")
    return failures


async def main():
    home = os.environ.get("OMNIGRAPH_HOME")
    parser = argparse.ArgumentParser(description="Check the law-history stored reads against seed.md.")
    parser.add_argument("--url", default="https://localhost:8443", help="server root")
    parser.add_argument("--graph", default="law")
    parser.add_argument("--token-env", default="OG_LOCAL_READER_TOKEN", help="variable holding a reader's token")
    parser.add_argument("--ca", help="CA certificate to trust, such as the local gateway's "
                                     "(default: $OMNIGRAPH_HOME/local-tls/ca.pem when it exists)")
    args = parser.parse_args()
    if args.ca is None and home and os.path.exists(os.path.join(home, "local-tls", "ca.pem")):
        args.ca = os.path.join(home, "local-tls", "ca.pem")
    if args.ca and not os.path.exists(args.ca):
        sys.exit(f"no CA certificate at {args.ca}")
    token = os.environ.get(args.token_env)
    if not token:
        sys.exit(f"set {args.token_env} to a token that may invoke the stored reads")
    transport = None
    if args.ca:
        transport = httpx.AsyncHTTPTransport(verify=ssl.create_default_context(cafile=args.ca))
    try:
        async with Omnigraph(args.url, graph_id=args.graph, token=token, transport=transport) as og:
            failures = await check(og)
    except OmnigraphError as error:
        sys.exit(f"{args.url}: {type(error).__name__}: {error}")
    if failures:
        print("\n" + "\n".join(failures), file=sys.stderr)
        sys.exit(f"{len(failures)} of {len(CHECKS)} checks failed")
    print(f"all {len(CHECKS)} checks of the {len({name for name, *_ in CHECKS})} stored reads match seed.md")


if __name__ == "__main__":
    asyncio.run(main())
