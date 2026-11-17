"""Tests for the converter's rules that need no index: keys and callability.

Run with: python3 -m unittest discover -s code-graph/sources/tests
"""

import sys
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
        # A range means the initializer is a function, whatever the declared type.
        ("constant", True, "var getCookie: GetCookie"),
        ("variable", True, "var isOldBunVersion: () => boolean"),
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
        # A function constant behind a type assertion gets no range from the indexer.
        ("constant", False, "var ErrorBoundary: FC<PropsWithChildren<{ fallback?: Child; }>>"),
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


if __name__ == "__main__":
    unittest.main()
