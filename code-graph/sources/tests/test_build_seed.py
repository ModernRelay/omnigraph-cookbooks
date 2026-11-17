"""Tests for the converter's rules that need no index: keys, callability,
reference owners, and the definition ranges extents.mjs reads.

Run with: python3 -m unittest discover -s code-graph/sources/tests

The extents tests need Node.js and `npm ci` in code-graph/sources/indexer; they
skip without them unless CODE_GRAPH_REQUIRE_NODE=1, as CI sets.
"""

import os
import shutil
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


if __name__ == "__main__":
    unittest.main()
