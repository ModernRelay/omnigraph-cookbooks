"""Tests for the converter's rules: keys, callability, reference owners, the
definition ranges extents.mjs reads, and static members, read from an index of
a small project.

Run with: python3 -m unittest discover -s code-graph/sources/tests

The extents and static-member tests need Node.js and `npm ci` in
code-graph/sources/indexer; they skip without them unless
CODE_GRAPH_REQUIRE_NODE=1, as CI sets.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build_seed  # noqa: E402


class Keys(unittest.TestCase):
    def test_key_drops_scheme_package_and_version(self):
        self.assertEqual(build_seed.descriptors_of("scip-typescript npm hono 4.13.3 src/`hono.ts`/Hono#"),
                         "src/`hono.ts`/Hono#")

    def test_key_leaves_out_numbered_type_literals(self):
        # The number is the type literal's position in the file, so keeping it
        # would rename the member whenever a type literal is added above it.
        symbol = "scip-typescript npm hono 4.13.3 src/`types.ts`/Env#typeLiteral12:Bindings."
        self.assertEqual(build_seed.descriptors_of(symbol), "src/`types.ts`/Env#Bindings.")


class Callable(unittest.TestCase):
    # Hover texts and kinds from scip-typescript 0.6.2 on hono.
    CALLABLE = [
        ("function", False, "function compose(middleware: [[Function, unknown], ParamIndexMap | Params][]): void"),
        ("method", False, "(method) add(method: string, path: string, handler: T): void"),
        # A function initializer makes it callable, whatever the declared type.
        ("constant", True, "var getCookie: GetCookie"),
        ("variable", True, "var isOldBunVersion: () => boolean"),
        # A function behind a type assertion: `((props) => {...}) as FC`.
        ("constant", True, "var ErrorBoundary: FC<PropsWithChildren<{ fallback?: Child; }>>"),
        # A class field holding an arrow function.
        ("property", True, "(property) notFoundHandler: NotFoundHandler"),
        # Nested generics before the parameter list.
        ("constant", False, "var hc: <T extends Hono<any, any, any>, Prefix extends string = string>(baseUrl: Prefix)"),
        ("constant", False, "var verify: (token: string, publicKey: SignatureKey) => Promise<...>"),
        ("property", False, "(property) fire: () => void"),
        ("property", False, "(property) onError?: (() => void) | undefined"),
        # Hover text keeps one line, which can end inside the parameter list.
        ("property", False, "(property) fetch: (request: Request, env?: {} | E[\"Bindings\"] | undefined,"),
    ]
    NOT_CALLABLE = [
        ("constant", False, "var METHOD_NAME_ALL: \"ALL\""),
        # A type that is not a function type, with no function initializer.
        ("constant", False, "var ErrorBoundary: FC<PropsWithChildren<{ fallback?: Child; }>>"),
        # `match: typeof match = match` holds a function but is not written as one.
        ("property", False, "(property) match: typeof match<Router<T>, T>"),
        ("constant", False, "var ENCODINGS_ORDERED_KEYS: (\"br\" | \"zstd\" | \"gzip\")[]"),
        ("property", False, "(property) abortSubscribers: (() => void | Promise<void>)[]"),
        ("property", False, "(property) o: (Promise<string> | JSXNode | Child[]) & Record<\"vR\", unknown>"),
        ("property", False, "(property) res: Response | undefined"),
        ("class", True, "class Hono"),
        ("constant", False, None),
    ]

    def test_callable(self):
        for kind, ranged, sig in self.CALLABLE:
            with self.subTest(sig=sig):
                self.assertTrue(build_seed.is_callable(kind, ranged, sig))

    def test_not_callable(self):
        for kind, ranged, sig in self.NOT_CALLABLE:
            with self.subTest(sig=sig):
                self.assertFalse(build_seed.is_callable(kind, ranged, sig))


class ProjectPrefix(unittest.TestCase):
    """A project indexed from a parent directory, as VS Code's src/tsconfig.json is."""

    @staticmethod
    def documents(paths):
        from types import SimpleNamespace as NS
        docs, infos = [], {}
        for path, module in paths:
            symbol = f"scip-typescript npm vscode 1.146.0 {module}"
            infos[symbol] = NS(kind=29)
            docs.append(NS(relative_path=path, occurrences=[NS(roles=build_seed.DEFINITION, symbol=symbol)]))
        return docs, infos

    def test_the_folder_is_the_document_path_minus_the_module_path(self):
        docs, infos = self.documents([("src/vs/base/common/event.ts", "vs/base/common/`event.ts`/"),
                                      ("src/bootstrap-cli.ts", "`bootstrap-cli.ts`/")])
        self.assertEqual(build_seed.project_prefix(docs, infos), "src/")

    def test_a_project_at_the_root_has_none(self):
        docs, infos = self.documents([("src/router.ts", "src/`router.ts`/")])
        self.assertEqual(build_seed.project_prefix(docs, infos), "")

    def test_folders_that_disagree_are_refused(self):
        docs, infos = self.documents([("a/x.ts", "`x.ts`/"), ("b/c/y.ts", "`y.ts`/")])
        with self.assertRaises(ValueError):
            build_seed.project_prefix(docs, infos)

    def test_names_are_escaped_as_scip_spells_them(self):
        self.assertEqual(build_seed.escape_name("src"), "src")
        self.assertEqual(build_seed.escape_name("my dir"), "`my dir`")


class Owner(unittest.TestCase):
    MODULE = ((0, 0, 40, 0), "src/`language.ts`/")
    TABLE = ((10, 0, 14, 2), "src/`language.ts`/detectors.")
    FUNCTION = ((20, 0, 30, 1), "src/`language.ts`/detectLanguage().")

    def test_innermost_range_owns_the_reference(self):
        scopes = [self.MODULE, self.TABLE, self.FUNCTION]
        # `cookie: detectFromCookie` inside the table belongs to the table, not the module.
        self.assertEqual(build_seed.owner(scopes, (11, 10, 11, 26)), "src/`language.ts`/detectors.")
        self.assertEqual(build_seed.owner(scopes, (22, 4, 22, 13)), "src/`language.ts`/detectLanguage().")
        self.assertEqual(build_seed.owner(scopes, (35, 0, 35, 5)), "src/`language.ts`/")

    def test_a_tie_goes_to_the_range_that_ends_first(self):
        outer = ((5, 0, 9, 0), "outer")
        inner = ((5, 0, 7, 0), "inner")
        self.assertEqual(build_seed.owner([outer, inner], (6, 0, 6, 3)), "inner")
        self.assertEqual(build_seed.owner([inner, outer], (6, 0, 6, 3)), "inner")

    def test_a_reference_outside_every_range_has_no_owner(self):
        self.assertIsNone(build_seed.owner([self.TABLE], (2, 0, 2, 4)))


INDEXER = Path(build_seed.HERE) / "indexer"
HAVE_NODE = bool(shutil.which("node")) and (INDEXER / "node_modules" / "typescript").is_dir()


@unittest.skipUnless(HAVE_NODE or os.environ.get("CODE_GRAPH_REQUIRE_NODE") == "1",
                     "needs Node.js and `npm ci` in code-graph/sources/indexer")
class Extents(unittest.TestCase):
    SOURCE = """\
const detectFromCookie = (c) => c
export const detectors = {
  cookie: detectFromCookie,
}
const ErrorBoundary: FC = ((props) => props) as FC
let a = 1, b = detectors
const { cookie } = detectors
let later
export class Hono {
  #router = new Router()
  static name: string
  get req() {
    return new HonoRequest()
  }
  set req(value) {}
  fetch = (request) => this.#router
}
"""

    def extents(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "src").mkdir()
            Path(root, "src", "a.ts").write_text(self.SOURCE, encoding="utf-8")
            return build_seed.read_extents(root, ["src/a.ts"])

    def test_definitions_without_an_indexer_range(self):
        got = {(line, char): value for (path, line, char), value in self.extents().items()}
        self.assertEqual(got, {
            (0, 6): ((0, 0, 0, 33), True),          # the indexer gives this one a range too
            # A table of functions covers its whole statement, so its entries belong to it.
            (1, 13): ((1, 0, 3, 1), False),
            (4, 6): ((4, 0, 4, 50), True),           # a function behind a type assertion
            # A statement with two declarations gives each its own.
            (5, 4): ((5, 4, 5, 9), False),
            (5, 11): ((5, 11, 5, 24), False),
            # Class fields, private ones from the `#`, and both accessors.
            (9, 2): ((9, 2, 9, 24), False),
            (10, 9): ((10, 2, 10, 21), False),
            (11, 6): ((11, 2, 13, 3), False),
            (14, 6): ((14, 2, 14, 19), False),
            (15, 2): ((15, 2, 15, 35), True),
        })


@unittest.skipUnless(HAVE_NODE or os.environ.get("CODE_GRAPH_REQUIRE_NODE") == "1",
                     "needs Node.js and `npm ci` in code-graph/sources/indexer")
class SeveralDefinitions(unittest.TestCase):
    """Symbols scip-typescript defines more than once: static members, which
    have kinds of their own and share a symbol with an instance member of the
    same name, and overloaded functions, whose signatures and implementation
    share one symbol."""
    SOURCE = """\
export class Color {
  static readonly white = new Color()
  static fromHex(hex: string): Color { return new Color() }
  static equals(a: Color, b: Color): boolean { return a.equals(b) }
  equals(other: Color): boolean { return other === this }
}
export function same(a: Color, b: Color): boolean { return Color.equals(a, b) }
export function parse(): Color { return Color.fromHex('#fff') }
"""
    OVERLOADED = """\
export function size(x: string): number
export function size(x: number[]): number
export function size(x: string | number[]): number {
  return x.length
}
"""

    def build(self, files: dict) -> list:
        with tempfile.TemporaryDirectory() as root:
            Path(root, "src").mkdir()
            for name, text in files.items():
                Path(root, "src", name).write_text(text, encoding="utf-8")
            Path(root, "tsconfig.json").write_text('{"include": ["src"]}', encoding="utf-8")
            index = Path(root, "index.scip")
            subprocess.run([str(INDEXER / "node_modules" / ".bin" / "scip-typescript"), "index",
                            "--no-progress-bar", "--output", str(index)], cwd=root, check=True, capture_output=True)
            return build_seed.build(str(index), root, "0" * 40, "https://example.com/r.git", [])

    def test_static_members_are_definitions(self):
        rows = self.build({"color.ts": self.SOURCE})
        kinds = {r["data"]["symbol"]: r["data"]["kind"] for r in rows if r.get("type") == "Symbol"}
        self.assertEqual(kinds.get("src/`color.ts`/Color#fromHex()."), "method")
        self.assertEqual(kinds.get("src/`color.ts`/Color#white."), "property")
        # The two methods named equals share a key, so they are one definition.
        self.assertEqual(kinds.get("src/`color.ts`/Color#equals()."), "method")
        refs = {(r["from"], r["to"]) for r in rows if r.get("edge") == "References"}
        self.assertIn(("src/`color.ts`/same().", "src/`color.ts`/Color#equals()."), refs)
        self.assertIn(("src/`color.ts`/parse().", "src/`color.ts`/Color#fromHex()."), refs)

    def test_an_overloads_implementation_is_part_of_its_definition(self):
        def symbol(source):
            rows = self.build({"size.ts": source})
            key = "src/`size.ts`/size()."
            data = next(r["data"] for r in rows if r.get("type") == "Symbol" and r["data"]["symbol"] == key)
            where = next(r["data"] for r in rows if r.get("type") == "Location" and r["data"]["symbol"] == key)
            return data, where
        data, where = symbol(self.OVERLOADED)
        self.assertTrue(data["callable"])
        # The definition runs from the first signature to the end of the body.
        self.assertEqual((where["line"], where["end_line"]), (1, 5))
        # A change in the implementation alone changes the digest.
        changed, _ = symbol(self.OVERLOADED.replace("x.length", "x.length + 1"))
        self.assertNotEqual(data["digest"], changed["digest"])

    # Two definitions on one line, after a character UTF-16 counts as two units.
    SHARED_LINE = 'export const mark = "\U0001F600"; export function f() { return 1 } export function g() { return 2 }\n'

    def digests(self, source: str) -> dict:
        return {r["data"]["name"]: r["data"]["digest"] for r in self.build({"two.ts": source})
                if r.get("type") == "Symbol" and r["data"]["callable"]}

    def test_a_digest_covers_its_own_columns_only(self):
        before = self.digests(self.SHARED_LINE)
        after = self.digests(self.SHARED_LINE.replace("return 2", "return 3"))
        self.assertEqual(before["f"], after["f"])
        self.assertNotEqual(before["g"], after["g"])

    def test_a_call_after_a_wide_character_is_a_call(self):
        rows = self.build({"call.ts": 'export function f() {}\nexport function h() { const s = "\U0001F600"; f() }\n'})
        edge = next(r["data"] for r in rows if r.get("edge") == "References"
                    and r["from"] == "src/`call.ts`/h()." and r["to"] == "src/`call.ts`/f().")
        self.assertTrue(edge["call"])


if __name__ == "__main__":
    unittest.main()
