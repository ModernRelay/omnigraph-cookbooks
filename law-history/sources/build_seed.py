#!/usr/bin/env python3
"""Build law-history/seed.jsonl and examples/mcconnell-source.jsonl from the official documents.

documents.json pins every document by URL and SHA-256, and fetch.py downloads them.
Each document is checked against its pinned hash before anything is read, so the
same documents always give the same seed, byte for byte.

Every text version is taken from the code editions (or, for the one version no edition
prints, from the law that states it), every instruction from the public law that
gives it, and every source row carries the document's URL, fetch time and sha256.
Typography is normalised: curly and TeX-style quotes become straight quotes, and the
codifier's footnote markers are dropped. The script asserts each text, date and holding
against the documents.

    python3 law-history/sources/build_seed.py            # rewrite the seed files
    python3 law-history/sources/build_seed.py --check    # exit 1 if they differ from a fresh build

The checks on the two court reports read their text with pdftotext (poppler).
"""
import argparse, datetime, hashlib, html, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
COOKBOOK = os.path.dirname(HERE)
parser = argparse.ArgumentParser(description="Build the law-history seed from the pinned official documents.")
parser.add_argument("--documents", default=os.path.join(HERE, "documents"), help="directory fetch.py filled")
parser.add_argument("--check", action="store_true", help="compare a fresh build with the committed files; write nothing")
args = parser.parse_args()
DOCS = args.documents
OPEN = "9999-12-31"


def norm(s):
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    s = s.replace("``", '"').replace("''", '"').replace("`", "'")
    return re.sub(r"[ \t]+", " ", s).strip()

def clean(fragment):
    fragment = re.sub(r"<sup>.*?</sup>", "", fragment, flags=re.S)
    return norm(html.unescape(re.sub(r"<[^>]+>", "", fragment)))

def statute(name):
    t = open(os.path.join(DOCS, name), encoding="utf-8", errors="replace").read()
    body = re.search(r"<!-- field-start:statute -->(.*?)<!-- field-end:statute -->", t, re.S).group(1)
    return [clean(m.group(1)) for m in re.finditer(r'<p class="statutory-body[^"]*">(.*?)</p>', body, re.S)]

def law_text(name):
    t = open(os.path.join(DOCS, name), encoding="utf-8", errors="replace").read()
    return norm(re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("–", "-")))

def quote(law, start, end):
    """The passage of a public law from `start` up to, not including, `end`, without margin notes."""
    t = re.sub(r"<<NOTE:[^>]*>>\s*", "", law_text(law))
    t = re.sub(r"\[\[Page [^\]]*\]\]\s*", "", t)
    i = t.index(start)
    j = t.index(end, i + len(start))
    return t[i:j].strip()

def strip_label(text, label):
    assert text.startswith(label + " "), (label, text[:40])
    return text[len(label) + 1:]

rows = []
def node(node_type, **data):
    rows.append({"type": node_type, "data": {k: v for k, v in data.items() if v is not None}})
def edge(edge_type, src, dst, **data):
    row = {"edge": edge_type, "from": src, "to": dst}
    if data:
        row["data"] = data
    rows.append(row)


# ── Sources ─────────────────────────────────────────────────────────
MANIFEST = json.load(open(os.path.join(HERE, "documents.json")))["documents"]
for doc in MANIFEST:
    path = os.path.join(DOCS, doc["file"])
    if not os.path.exists(path):
        sys.exit(f"{doc['file']} is not in {DOCS}: run fetch.py first")
    with open(path, "rb") as f:
        got = hashlib.sha256(f.read()).hexdigest()
    if got != doc["sha256"]:
        sys.exit(f"{doc['file']} has sha256 {got}, not the pinned {doc['sha256']}: run fetch.py again")
if not shutil.which("pdftotext"):
    sys.exit("pdftotext is needed to check the court reports: install poppler")

def current_through(name):
    m = re.search(r"currentthrough:(\d{4})(\d{2})(\d{2})", open(os.path.join(DOCS, name), errors="replace").read())
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None

def source_data(doc):
    data = {"slug": doc["slug"], "title": doc["title"], "kind": doc["kind"], "publisher": doc["publisher"], "url": doc["url"],
            "current_through": current_through(doc["file"]) if doc["kind"] == "code_edition" and "-title-" not in doc["slug"] else None,
            "fetched_at": doc["fetched_at"], "sha256": doc["sha256"], "licence": doc["licence"], "commercial_reuse": doc["commercial_reuse"]}
    return {k: v for k, v in data.items() if v is not None}

for doc in MANIFEST:
    if doc["use"] == "seed":
        node("Source", **source_data(doc))
examples = [{"type": "Source", "data": source_data(doc)} for doc in MANIFEST if doc["use"] == "example"]

# ── Jurisdiction and instruments ────────────────────────────────────
node("Jurisdiction", slug="jur-us", name="United States (federal)", level="national")
INSTRUMENTS = [
    ("ins-usc-11", "code", "Title 11, United States Code (Bankruptcy)", "11 U.S.C.", "1978-11-06"),
    ("ins-feca", "act", "Federal Election Campaign Act of 1971", "Pub. L. 92-225", "1972-02-07"),
    ("ins-bcra", "act", "Bipartisan Campaign Reform Act of 2002", "Pub. L. 107-155", "2002-03-27"),
    ("ins-olrc-t52", "editorial", "Editorial reclassification creating Title 52, Voting and Elections", "52 U.S.C. (editorial reclassification)", None),
    ("ins-sbra", "act", "Small Business Reorganization Act of 2019", "Pub. L. 116-54", "2019-08-23"),
    ("ins-cares", "act", "Coronavirus Aid, Relief, and Economic Security Act", "Pub. L. 116-136", "2020-03-27"),
    ("ins-cbrea", "act", "COVID-19 Bankruptcy Relief Extension Act of 2021", "Pub. L. 117-5", "2021-03-27"),
    ("ins-btatca", "act", "Bankruptcy Threshold Adjustment and Technical Corrections Act", "Pub. L. 117-151", "2022-06-21"),
]
for slug, kind, title, citation, enacted in INSTRUMENTS:
    node("Instrument", slug=slug, kind=kind, title=title, citation=citation, enacted_on=enacted)
    edge("InstrumentOf", slug, "jur-us")
assert "Approved March 27, 2002" in law_text("pl-107-155.html")
assert "Approved August 23, 2019" in law_text("pl-116-54.html")
assert "Approved March 27, 2020" in law_text("pl-116-136.html")
assert "Approved March 27, 2021" in law_text("pl-117-5.html")
assert "Approved June 21, 2022" in law_text("pl-117-151.html")
assert "This title was enacted by Pub. L. 95-598, title I, §101, Nov. 6, 1978" in law_text("usc-11-title-2024.html")

# ── Provisions ──────────────────────────────────────────────────────
PROVISIONS = [
    ("prov-feca-301", "section", "Definitions", "ins-feca"),
    ("prov-feca-316", "section", "Contributions or expenditures by national banks, corporations, or labor organizations", "ins-feca"),
    ("prov-feca-316-a", "subsection", "In general", "ins-feca"),
    ("prov-feca-316-b-2", "paragraph", None, "ins-feca"),
    ("prov-usc11-1182", "section", "Definitions", "ins-usc-11"),
    ("prov-usc11-1182-1", "paragraph", "Debtor", "ins-usc-11"),
    ("prov-usc11-1182-2", "paragraph", "Debtor in possession", "ins-usc-11"),
]
for slug, kind, heading, ins in PROVISIONS:
    node("Provision", slug=slug, kind=kind, heading=heading)
    edge("ProvisionOf", slug, ins)
for child, parent, start in (("prov-feca-316-a", "prov-feca-316", "1976-05-11"), ("prov-feca-316-b-2", "prov-feca-316", "1976-05-11"),
                             ("prov-usc11-1182-1", "prov-usc11-1182", "2019-08-23"), ("prov-usc11-1182-2", "prov-usc11-1182", "2019-08-23")):
    edge("PartOf", child, parent, valid_from=start, valid_to=OPEN)

# ── Designations ────────────────────────────────────────────────────
credit = law_text("usc-2-441b-2000.html")
assert "formerly §321, as added Pub. L. 94-283, title I, §112(2), May 11, 1976" in credit
assert "renumbered §316 and amended Pub. L. 96-187, title I, §§105(5), 112(d), Jan. 8, 1980" in credit
table = law_text("olrc-t52-table.html")
assert "2:441b 52:30118 Pub. L. 92-225, title III, § 316" in table and "2:431 52:30101 Pub. L. 92-225, title III, § 301, Feb. 7, 1972" in table
assert "the transfers occurred on September 1, 2014, after which the new Code citations were effective" in law_text("olrc-t52-index.html")
RECLASS = "2014-09-01"
DESIGNATIONS = [
    # slug, label, system, positive_law, provision, from, to, evidence
    ("des-feca-321", "FECA § 321", "act", None, "prov-feca-316", "1976-05-11", "1980-01-08", ["src-usc-2-441b-2000"]),
    ("des-feca-316", "FECA § 316", "act", None, "prov-feca-316", "1980-01-08", OPEN, ["src-usc-2-441b-2000"]),
    ("des-feca-316-a", "FECA § 316(a)", "act", None, "prov-feca-316-a", "1980-01-08", OPEN, ["src-usc-2-441b-2000"]),
    ("des-feca-316-b-2", "FECA § 316(b)(2)", "act", None, "prov-feca-316-b-2", "1980-01-08", OPEN, ["src-usc-2-441b-2000", "src-pl-107-155"]),
    ("des-2usc-441b", "2 U.S.C. § 441b", "code", False, "prov-feca-316", "1976-05-11", RECLASS, ["src-usc-2-441b-2000", "src-olrc-t52-table"]),
    ("des-2usc-441b-a", "2 U.S.C. § 441b(a)", "code", False, "prov-feca-316-a", "1976-05-11", RECLASS, ["src-usc-2-441b-2000"]),
    ("des-2usc-441b-b-2", "2 U.S.C. § 441b(b)(2)", "code", False, "prov-feca-316-b-2", "1976-05-11", RECLASS, ["src-usc-2-441b-2000", "src-pl-107-155"]),
    ("des-52usc-30118", "52 U.S.C. § 30118", "code", False, "prov-feca-316", RECLASS, OPEN, ["src-usc-52-30118-2014", "src-olrc-t52-table", "src-usc-52-title-2014"]),
    ("des-52usc-30118-a", "52 U.S.C. § 30118(a)", "code", False, "prov-feca-316-a", RECLASS, OPEN, ["src-usc-52-30118-2014"]),
    ("des-52usc-30118-b-2", "52 U.S.C. § 30118(b)(2)", "code", False, "prov-feca-316-b-2", RECLASS, OPEN, ["src-usc-52-30118-2014"]),
    ("des-feca-301", "FECA § 301", "act", None, "prov-feca-301", "1972-02-07", OPEN, ["src-olrc-t52-table"]),
    ("des-2usc-431", "2 U.S.C. § 431", "code", False, "prov-feca-301", "1972-02-07", RECLASS, ["src-olrc-t52-table"]),
    ("des-52usc-30101", "52 U.S.C. § 30101", "code", False, "prov-feca-301", RECLASS, OPEN, ["src-olrc-t52-table"]),
    ("des-11usc-1182", "11 U.S.C. § 1182", "code", True, "prov-usc11-1182", "2019-08-23", OPEN, ["src-usc-11-1182-2019", "src-usc-11-title-2024"]),
    ("des-11usc-1182-1", "11 U.S.C. § 1182(1)", "code", True, "prov-usc11-1182-1", "2019-08-23", OPEN, ["src-usc-11-1182-2019", "src-usc-11-title-2024"]),
    ("des-11usc-1182-2", "11 U.S.C. § 1182(2)", "code", True, "prov-usc11-1182-2", "2019-08-23", OPEN, ["src-usc-11-1182-2019", "src-usc-11-title-2024"]),
]
for slug, label, system, positive, prov, start, end, evidence in DESIGNATIONS:
    node("Designation", slug=slug, label=label, system=system, positive_law=positive)
    edge("Designates", slug, prov, valid_from=start, valid_to=end)
    for src in evidence:
        edge("DesignationEvidence", slug, src)

# ── Text versions ───────────────────────────────────────────────────
def sha(text): return hashlib.sha256(text.encode()).hexdigest()

def subsection_a(name):
    first = statute(name)[0]
    return first[4:] if first.startswith("(a) ") else first

def paragraph(name, label, startswith):
    hits = [p for p in statute(name) if p.startswith(f"{label} {startswith}")]
    assert len(hits) == 1, (name, label, startswith, hits)
    return strip_label(hits[0], label)

def debtor_definition(name):
    ps = statute(name)
    i = next(k for k, p in enumerate(ps) if p.startswith("(1) Debtor"))
    j = next(k for k, p in enumerate(ps) if p.startswith("(2) Debtor in possession"))
    return strip_label("\n".join(ps[i:j]), "(1)")

a_text = {name: subsection_a(name) for name in ("usc-2-441b-2000.html", "usc-2-441b-2006.html", "usc-2-441b-2012.html", "usc-52-30118-2014.html", "usc-52-30118-2024.html")}
assert len(set(a_text.values())) == 1, "subsection (a) must be unchanged across every edition"
b2 = {name: paragraph(name, "(2)", "For purposes of this section") for name in a_text}
assert b2["usc-2-441b-2006.html"] == b2["usc-2-441b-2012.html"] and b2["usc-52-30118-2014.html"] == b2["usc-52-30118-2024.html"]
assert "section 431 of this title" in b2["usc-2-441b-2006.html"] and "section 30101 of this title" in b2["usc-52-30118-2014.html"]
assert "electioneering communication" not in b2["usc-2-441b-2000.html"]
assert "or for any applicable electioneering communication, but shall not include" in b2["usc-2-441b-2006.html"]
assert b2["usc-52-30118-2014.html"] == b2["usc-2-441b-2006.html"].replace("section 431 of this title", "section 30101 of this title")
d = {y: debtor_definition(f"usc-11-1182-{y}.html") for y in range(2019, 2025)}
assert d[2019] == d[2024] == 'Debtor.—The term "debtor" means a small business debtor.'
assert d[2020] == d[2021] and d[2022] == d[2023] and d[2020] != d[2022]
sunset = quote("pl-116-136.html", "(5) Sunset.", "(b) Bankruptcy Relief.")
assert '"(1) Debtor.--The term \'debtor\' means a small business debtor."' in sunset
dip = {y: paragraph(f"usc-11-1182-{y}.html", "(2)", "Debtor in possession") for y in range(2019, 2025)}
assert len(set(dip.values())) == 1

SEC_REFS = "section 13 or 15(d) of the Securities Exchange Act of 1934 (15 U.S.C. 78m, 78o(d))"
VERSIONS = [
    # slug, provision, text, from, to, from_is_record_start, evidence, unresolved
    ("tv-feca-316-a-1", "prov-feca-316-a", a_text["usc-2-441b-2000.html"], "2001-01-02", OPEN, True,
     ["src-usc-2-441b-2000", "src-usc-2-441b-2006", "src-usc-2-441b-2012", "src-usc-52-30118-2014", "src-usc-52-30118-2024"], None),
    ("tv-feca-316-b-2-1", "prov-feca-316-b-2", b2["usc-2-441b-2000.html"], "2001-01-02", "2002-11-06", True,
     ["src-usc-2-441b-2000"], ["section 79l(h) of title 15"]),
    ("tv-feca-316-b-2-2", "prov-feca-316-b-2", b2["usc-2-441b-2006.html"], "2002-11-06", RECLASS, False,
     ["src-usc-2-441b-2006", "src-usc-2-441b-2012"], ["section 79l(h) of title 15"]),
    ("tv-feca-316-b-2-3", "prov-feca-316-b-2", b2["usc-52-30118-2014.html"], RECLASS, OPEN, False,
     ["src-usc-52-30118-2014", "src-usc-52-30118-2024"], ["section 79l(h) of title 15"]),
    ("tv-usc11-1182-1-1", "prov-usc11-1182-1", d[2019], "2020-02-19", "2020-03-27", False, ["src-usc-11-1182-2019", "src-pl-116-54"], None),
    ("tv-usc11-1182-1-2", "prov-usc11-1182-1", d[2020], "2020-03-27", "2022-03-27", False,
     ["src-usc-11-1182-2020", "src-usc-11-1182-2021", "src-pl-116-136"], [SEC_REFS, "section 3 of the Securities Exchange Act of 1934 (15 U.S.C. 78c)"]),
    ("tv-usc11-1182-1-3", "prov-usc11-1182-1", d[2019], "2022-03-27", "2022-06-21", False, ["src-pl-116-136", "src-pl-117-5"], None),
    ("tv-usc11-1182-1-4", "prov-usc11-1182-1", d[2022], "2022-06-21", "2024-06-21", False,
     ["src-usc-11-1182-2022", "src-usc-11-1182-2023", "src-pl-117-151"], [SEC_REFS]),
    ("tv-usc11-1182-1-5", "prov-usc11-1182-1", d[2024], "2024-06-21", OPEN, False, ["src-usc-11-1182-2024", "src-pl-117-151"], None),
    ("tv-usc11-1182-2-1", "prov-usc11-1182-2", dip[2019], "2020-02-19", OPEN, False,
     ["src-usc-11-1182-2019", "src-usc-11-1182-2024", "src-pl-116-54"], ["section 1185(a) of this title"]),
]
for slug, prov, text, start, end, record_start, evidence, unresolved in VERSIONS:
    node("TextVersion", slug=slug, text=text, in_force_from=start, in_force_to=end, from_is_record_start=record_start,
         text_sha256=sha(text), unresolved_citations=unresolved)
    edge("VersionOf", slug, prov)
    for src in evidence:
        edge("TextEvidence", slug, src)
edge("Cites", "tv-feca-316-b-2-2", "prov-feca-301", as_written="section 431 of this title")
edge("Cites", "tv-feca-316-b-2-3", "prov-feca-301", as_written="section 30101 of this title")

# ── Changes ─────────────────────────────────────────────────────────
D = datetime.date.fromisoformat
assert D("2019-08-23") + datetime.timedelta(days=180) == D("2020-02-19")   # SBRA § 5: 180 days after enactment
bcra = re.sub(r"<<NOTE:[^>]*>>\s*", "", law_text("pl-107-155.html"))
title_ii = bcra.index("TITLE II--", 2000); assert title_ii < bcra.index("SEC. 203.") < bcra.index("SEC. 214.") < bcra.index("TITLE III--", title_ii)
BCRA_BASIS = quote("pl-107-155.html", "(4) Provisions not to apply to runoff elections.", "(b) Soft Money of National Political Parties.")
assert "title II," in BCRA_BASIS
BCRA_APPLIES = quote("pl-107-155.html", "shall take effect on November 6, 2002, but shall not apply", "(b) Soft Money of National Political Parties.")
cares = quote("pl-116-136.html", "SEC. 1113. BANKRUPTCY.", "(b) Bankruptcy Relief.")
assert not re.search(r"(?i)effective date|take effect", cares), "§ 1113(a) states no effective date"
btatca_h = quote("pl-117-151.html", "(h) Effective Date; Applicability.", "(i) Sunsets.")
assert "(1) In general.--Subsections (b) and (c) and the amendments made by subsections (b) and (c) shall take effect on the date of enactment" in btatca_h
assert "The amendments made by subsection (g) shall take effect as if enacted on October 1, 2021" in btatca_h
note_2006 = law_text("usc-2-441b-2006.html")
assert "not applicable with respect to runoff elections, recounts, or election contests resulting from elections held prior to Nov. 6, 2002" in note_2006
codification = 'Section was formerly classified to section 441b of Title 2, The Congress, prior to editorial reclassification and renumbering as this section.'
assert codification in law_text("usc-52-30118-2014.html")
CHANGES = [
    ("chg-sbra-1182", "insert", "Pub. L. 116-54, § 2(a)",
     quote("pl-116-54.html", "(a) In General.--Chapter 11 of title 11", '"SUBCHAPTER V'),
     "2019-08-23", "2020-02-19", quote("pl-116-54.html", "SEC. 5. EFFECTIVE DATE.", "SEC. 6."), None, None, "official_version",
     [("ins-sbra", "made")], [], ["tv-usc11-1182-1-1", "tv-usc11-1182-2-1"], ["src-pl-116-54", "src-usc-11-1182-2019"]),
    ("chg-cares-1182", "substitute", "Pub. L. 116-136, div. A, title I, § 1113(a)(1)",
     quote("pl-116-136.html", "(1) In general.--Section 1182(1) of title 11", '"(1) Debtor.--The term'),
     "2020-03-27", "2020-03-27", "Section 1113(a) states no effective date for paragraph (1), so it took effect on enactment, 27 March 2020; paragraph (3) limits it to cases commenced on or after that date.",
     "2020-03-27", quote("pl-116-136.html", "(3) Application of amendment.", "(4) Technical corrections."), "official_version",
     [("ins-cares", "made")], ["tv-usc11-1182-1-1"], ["tv-usc11-1182-1-2"], ["src-pl-116-136", "src-usc-11-1182-2020"]),
    ("chg-cares-sunset-1182", "sunset", "Pub. L. 116-136, div. A, title I, § 1113(a)(5), as amended by Pub. L. 117-5, § 2(a)(1)",
     quote("pl-116-136.html", "(5) Sunset.--On the date", '"(1) Debtor.--The term \'debtor\' means a small business debtor."'),
     "2020-03-27", "2022-03-27",
     "Two years after enactment on 27 March 2020: Pub. L. 117-5, § 2(a)(1), " + quote("pl-117-5.html", "in subsection (a)(5) (11 U.S.C. 1182 note), by striking", "; and (2)"),
     None, None, "law_text",
     [("ins-cares", "made"), ("ins-cbrea", "modified")], ["tv-usc11-1182-1-2"], ["tv-usc11-1182-1-3"], ["src-pl-116-136", "src-pl-117-5"]),
    ("chg-btatca-1182", "substitute", "Pub. L. 117-151, § 2(d)",
     quote("pl-117-151.html", "(d) Definition of Debtor.--Section 1182(1)", '"(1) Debtor.--The term'),
     "2022-06-21", "2022-06-21", "Section 2(h) states effective dates only for subsections (b), (c) and (g), so subsection (d) took effect on enactment, 21 June 2022; section 2(h)(2) makes it reach back to cases commenced on or after 27 March 2020.",
     "2020-03-27", quote("pl-117-151.html", "(2) Retroactive application of certain amendments.", "(3) Effective date of technical corrections"), "official_version",
     [("ins-btatca", "made")], ["tv-usc11-1182-1-3"], ["tv-usc11-1182-1-4"], ["src-pl-117-151", "src-usc-11-1182-2022"]),
    ("chg-btatca-sunset-1182", "sunset", "Pub. L. 117-151, § 2(i)(1)(B)",
     quote("pl-117-151.html", "(i) Sunsets.--", "(2) Amounts."),
     "2022-06-21", "2024-06-21", "Two years after enactment on 21 June 2022, as § 2(i)(1) states.",
     None, None, "official_version",
     [("ins-btatca", "made")], ["tv-usc11-1182-1-4"], ["tv-usc11-1182-1-5"], ["src-pl-117-151", "src-usc-11-1182-2024"]),
    ("chg-bcra-203a", "amend", "Pub. L. 107-155, § 203(a)",
     quote("pl-107-155.html", "(a) In General.--Section 316(b)(2) of the Federal Election Campaign Act", "(b) Applicable Electioneering Communication."),
     "2002-03-27", "2002-11-06", BCRA_BASIS,
     None, BCRA_APPLIES,
     "official_version",
     [("ins-bcra", "made")], ["tv-feca-316-b-2-1"], ["tv-feca-316-b-2-2"], ["src-pl-107-155", "src-usc-2-441b-2006"]),
    ("chg-bcra-214d", "amend", "Pub. L. 107-155, § 214(d)",
     quote("pl-107-155.html", "(d) Meaning of Contribution or Expenditure for the Purposes of Section 316.", "TITLE III--MISCELLANEOUS"),
     "2002-03-27", "2002-11-06", BCRA_BASIS,
     None, BCRA_APPLIES,
     "official_version",
     [("ins-bcra", "made")], ["tv-feca-316-b-2-1"], ["tv-feca-316-b-2-2"], ["src-pl-107-155", "src-usc-2-441b-2006"]),
    ("chg-olrc-t52-30118", "reclassify", "Editorial reclassification, Title 52 (2 U.S.C. § 441b to 52 U.S.C. § 30118)",
     codification,
     None, RECLASS, "For the online version of the United States Code, the transfers occurred on September 1, 2014, after which the new Code citations were effective.",
     None, None, "official_version",
     [("ins-olrc-t52", "made")], ["tv-feca-316-b-2-2"], ["tv-feca-316-b-2-3"], ["src-olrc-t52", "src-olrc-t52-table", "src-usc-52-30118-2014"]),
]
for slug, kind, locator, instruction, enacted, in_force, basis, applies_from, applies, verification, made, before, after, evidence in CHANGES:
    node("Change", slug=slug, kind=kind, locator=locator, instruction=instruction, enacted_on=enacted, in_force_on=in_force,
         in_force_basis=basis, applies_from_event=applies_from, applies_text=applies, verification=verification)
    for ins, role in made:
        edge("MadeBy", slug, ins, role=role)
    for v in before:
        edge("ChangedFrom", slug, v)
    for v in after:
        edge("ChangedTo", slug, v)
    for src in evidence:
        edge("ChangeEvidence", slug, src)

# ── Defined terms ───────────────────────────────────────────────────
node("DefinedTerm", slug="term-small-business-debtor", term="small business debtor", defined_at="11 U.S.C. § 101(51D)")
node("DefinedTerm", slug="term-debtor-subchapter-v", term="debtor", defined_at=None)
node("DefinedTerm", slug="term-debtor-in-possession", term="debtor in possession", defined_at=None)
node("DefinedTerm", slug="term-contribution-or-expenditure", term="contribution or expenditure", defined_at=None)
for v in ("tv-usc11-1182-1-1", "tv-usc11-1182-1-2", "tv-usc11-1182-1-3", "tv-usc11-1182-1-4", "tv-usc11-1182-1-5"):
    edge("Defines", v, "term-debtor-subchapter-v", scope="Subchapter V of chapter 11 of title 11 (\"In this subchapter\")")
for v in ("tv-usc11-1182-1-1", "tv-usc11-1182-1-3", "tv-usc11-1182-1-5"):
    assert "small business debtor" in dict((s, t) for s, _, t, *_ in VERSIONS)[v]
    edge("Uses", v, "term-small-business-debtor")
edge("Defines", "tv-usc11-1182-2-1", "term-debtor-in-possession", scope="Subchapter V of chapter 11 of title 11 (\"In this subchapter\")")
edge("Uses", "tv-usc11-1182-2-1", "term-debtor-subchapter-v")
for v in ("tv-feca-316-b-2-1", "tv-feca-316-b-2-2", "tv-feca-316-b-2-3"):
    edge("Defines", v, "term-contribution-or-expenditure", scope="This section and section 79l(h) of title 15")
edge("Uses", "tv-feca-316-a-1", "term-contribution-or-expenditure")

# ── Judgment ────────────────────────────────────────────────────────
def pdf_pages(name):
    text = subprocess.run(["pdftotext", "-layout", os.path.join(DOCS, name), "-"], capture_output=True, text=True, check=True).stdout
    return [norm(re.sub(r"\s+", " ", page)) for page in text.split("\f")]

citizens_united = pdf_pages("citizens-united-558us310.pdf")
holding = "Section 441b's restrictions on corporate independent expenditures are therefore invalid and cannot be applied to Hillary."
assert holding in citizens_united[55], "the holding must be on page 365 (the 56th page of the PDF)"
assert "No. 08–205" in citizens_united[0] and "Decided January 21, 2010" in citizens_united[0]
node("Judgment", slug="jud-citizens-united", title="Citizens United v. Federal Election Commission",
     court="Supreme Court of the United States", citation="558 U.S. 310", docket="No. 08-205", decided_on="2010-01-21")
edge("JudgmentEvidence", "jud-citizens-united", "src-us-reports-558-310")
edge("Applied", "jud-citizens-united", "tv-feca-316-a-1")
edge("Applied", "jud-citizens-united", "tv-feca-316-b-2-2")
edge("HeldInvalid", "jud-citizens-united", "prov-feca-316", scope="in_part", holding=holding, locator="558 U.S. at 365",
     effective_from="2010-01-21", review_status="human_reviewed")

# The add-a-case walkthrough in README.md records McConnell from its report and quotes
# the sentence of Citizens United that overrules it.
overrule = ("Given our conclusion we are further required to overrule the part of McConnell that upheld "
            "BCRA § 203's extension of § 441b's restrictions on corporate independent expenditures.")
assert overrule in citizens_united[55] and overrule in open(os.path.join(COOKBOOK, "README.md"), encoding="utf-8").read()
mcconnell = pdf_pages("mcconnell-540us93.pdf")
assert "No. 02-1674." in mcconnell[0] and "Decided December 10, 2003" in mcconnell[0]

# ── Coverage ────────────────────────────────────────────────────────
node("Coverage", slug="cov-feca-316", covered_from="2001-01-02", covered_to="2025-01-06", method="official_versions",
     note="Subsection (a) and paragraph (b)(2) only, from the 2000 edition (current through 2 January 2001) to the 2024 edition (current through 6 January 2025). Earlier text, and any change after 6 January 2025, is not recorded.")
node("Coverage", slug="cov-feca-301", covered_from="1972-02-07", covered_to="2025-01-06", method="designations_only",
     note="Citations only, from the Law Revision Counsel's Title 52 reclassification table; no text is recorded.")
node("Coverage", slug="cov-usc11-1182", covered_from="2019-08-23", covered_to="2025-01-06", method="official_versions",
     note="Paragraphs (1) and (2) from the 2019 edition to the 2024 edition (current through 6 January 2025). Paragraph (1) from 27 March to 21 June 2022 is recorded from the sunset clause of Pub. L. 116-136 as extended by Pub. L. 117-5; no annual edition prints that text.")
for cov, prov in (("cov-feca-316", "prov-feca-316-a"), ("cov-feca-316", "prov-feca-316-b-2"), ("cov-feca-301", "prov-feca-301"),
                  ("cov-usc11-1182", "prov-usc11-1182-1"), ("cov-usc11-1182", "prov-usc11-1182-2")):
    edge("CoverageOf", cov, prov)


def render(records):
    return "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)

outputs = {os.path.join(COOKBOOK, "seed.jsonl"): render(rows),
           os.path.join(COOKBOOK, "examples", "mcconnell-source.jsonl"): render(examples)}
nodes = sum(1 for r in rows if "type" in r); edges = len(rows) - nodes
if args.check:
    stale = [path for path, text in outputs.items()
             if not os.path.exists(path) or open(path, encoding="utf-8").read() != text]
    if stale:
        sys.exit("differs from a fresh build: " + ", ".join(os.path.relpath(path, COOKBOOK) for path in stale))
    print(f"{nodes} nodes, {edges} edges: seed.jsonl and the example source match a fresh build")
else:
    for path, text in outputs.items():
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    print(f"{nodes} nodes, {edges} edges -> seed.jsonl, examples/mcconnell-source.jsonl")
