"""Check the local preparation boundary without a bucket or credentials."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
COOKBOOKS = ("industry-intel", "pharma-intel", "second-brain", "vc-os", "dev-graph")


class PrepareConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = os.environ.get("OMNIGRAPH_BIN") or shutil.which("omnigraph")
        if not cls.binary:
            raise RuntimeError("Install OmniGraph 0.13 or set OMNIGRAPH_BIN")
        cls.binary = str(Path(cls.binary).resolve())
        version = subprocess.check_output([cls.binary, "--version"], text=True)
        if not version.startswith("omnigraph 0.13."):
            raise RuntimeError(f"Tests require OmniGraph 0.13; got {version.strip()}")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="railway-config-test-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.shim = self.directory / "bin"
        self.shim.mkdir()
        self.log = self.directory / "calls"
        wrapper = self.shim / "omnigraph"
        wrapper.write_text(
            '#!/bin/sh\n'
            'printf "%s\\n" "$@" >> "$OMNIGRAPH_TEST_CALLS"\n'
            '[ "$#" = 4 ] && [ "$1:$2:$3" = cluster:validate:--config ] || exit 99\n'
            'exec "$OMNIGRAPH_TEST_BINARY" "$@"\n'
        )
        wrapper.chmod(0o755)
        self.environment = {
            "PATH": f"{self.shim}{os.pathsep}{os.environ['PATH']}",
            "OMNIGRAPH_HOME": str(self.directory / "operator"),
            "OMNIGRAPH_CLUSTER_URI": "s3://unreachable-test-bucket/cluster",
            "OMNIGRAPH_TEST_BINARY": self.binary,
            "OMNIGRAPH_TEST_CALLS": str(self.log),
        }

    def prepare(self, cookbook, output):
        return subprocess.run(
            ["sh", str(ROOT / "deploy/railway/scripts/prepare-config.sh"), cookbook, str(output)],
            env=self.environment,
            text=True,
            capture_output=True,
            timeout=30,
        )

    def test_every_cookbook_is_valid_and_preparation_only_validates(self):
        for cookbook in COOKBOOKS:
            with self.subTest(cookbook=cookbook):
                output = self.directory / cookbook
                result = self.prepare(cookbook, output)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(
                    set(path.name for path in output.iterdir()),
                    {"cluster.yaml", "schema.pg", "queries", "policies"},
                )
                self.assertIn(
                    "storage: 's3://unreachable-test-bucket/cluster'",
                    (output / "cluster.yaml").read_text(),
                )
        calls = self.log.read_text().splitlines()
        self.assertEqual(len(calls), 4 * len(COOKBOOKS))
        for index in range(0, len(calls), 4):
            self.assertEqual(calls[index:index + 3], ["cluster", "validate", "--config"])

    def test_existing_directory_and_unknown_cookbook_leave_inputs_alone(self):
        marker = self.directory / "keep"
        marker.write_text("do not overwrite")
        result = self.prepare("industry-intel", self.directory)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(), "do not overwrite")
        result = self.prepare("../industry-intel", self.directory / "new")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.directory / "new").exists())
        self.assertFalse(self.log.exists())

    def test_control_characters_and_non_s3_roots_refuse_before_output(self):
        for uri in ("file:///tmp/graph", "s3://bucket", "s3://bucket/ok\npolicies: null"):
            with self.subTest(uri=uri):
                self.environment["OMNIGRAPH_CLUSTER_URI"] = uri
                result = self.prepare("industry-intel", self.directory / "new")
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.directory / "new").exists())
        self.assertFalse(self.log.exists())

    def test_storage_scalar_is_quoted(self):
        self.environment["OMNIGRAPH_CLUSTER_URI"] = "s3://bucket/it's-fine"
        output = self.directory / "quoted"
        result = self.prepare("industry-intel", output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("storage: 's3://bucket/it''s-fine'", (output / "cluster.yaml").read_text())

    def test_runtime_has_no_automatic_apply_or_unlock(self):
        # These are deployment safety properties, separate from config preparation.
        self.assertFalse((ROOT / "railway.toml").exists())
        self.assertFalse((ROOT / "railway.json").exists())
        dockerfile = (ROOT / "deploy/railway/Dockerfile").read_text()
        command = next(line[4:] for line in dockerfile.splitlines() if line.startswith("CMD "))
        args = json.loads(command)
        self.assertEqual(args[:2], ["sh", "-c"])
        self.assertTrue(args[2].startswith("exec omnigraph-server --cluster "))
        self.assertNotIn("force-unlock", args[2])
        self.assertNotIn("cluster apply", args[2])
        self.assertNotIn("COPY ", dockerfile)
        self.assertIn('/readyz"', dockerfile)


if __name__ == "__main__":
    unittest.main()
