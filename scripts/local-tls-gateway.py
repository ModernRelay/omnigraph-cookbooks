#!/usr/bin/env python3
"""Serve a local omnigraph-server over HTTPS for the CLI.

The 0.14 CLI sends bearer tokens only over HTTPS; plain HTTP is allowed only
to an anonymous loopback server. This gateway terminates TLS on a loopback
port and relays bytes unchanged to the server's loopback listener, so a local
server keeps its token-selected actors and policies. It is for local demos and
tests on one machine, never a deployment.

On first use it creates a private CA and a localhost certificate with
`openssl` in $OMNIGRAPH_HOME/local-tls (~/.omnigraph/local-tls when unset).
Point the CLI target's `transport.tls.ca` at the printed CA file.
"""

import argparse
import asyncio
import os
from pathlib import Path
import ssl
import subprocess
import sys


def ensure_certificates(directory: Path) -> tuple[Path, Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    ca, ca_key = directory / "ca.pem", directory / "ca.key"
    cert, key = directory / "localhost.pem", directory / "localhost.key"
    if all(path.exists() for path in (ca, cert, key)):
        return ca, cert, key
    openssl = ["openssl"]
    run = lambda *args: subprocess.run([*openssl, *args], check=True, capture_output=True)
    run("req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
        "-keyout", str(ca_key), "-out", str(ca), "-days", "365", "-subj", "/CN=OmniGraph cookbook local CA",
        "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign")
    csr = directory / "localhost.csr"
    run("req", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
        "-keyout", str(key), "-out", str(csr), "-subj", "/CN=localhost")
    extensions = directory / "localhost.ext"
    extensions.write_text("basicConstraints=critical,CA:FALSE\n"
                          "keyUsage=critical,digitalSignature\n"
                          "extendedKeyUsage=serverAuth\n"
                          "subjectAltName=DNS:localhost,IP:127.0.0.1\n")
    run("x509", "-req", "-in", str(csr), "-CA", str(ca), "-CAkey", str(ca_key), "-CAcreateserial",
        "-out", str(cert), "-days", "365", "-extfile", str(extensions))
    for path in (ca_key, key):
        os.chmod(path, 0o600)
    csr.unlink()
    return ca, cert, key


async def relay(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, ssl.SSLError):
        pass
    finally:
        writer.close()


async def serve(listen: tuple[str, int], upstream: tuple[str, int], context: ssl.SSLContext) -> None:
    async def handle(client_reader, client_writer):
        try:
            upstream_reader, upstream_writer = await asyncio.open_connection(*upstream)
        except OSError:
            client_writer.close()
            return
        await asyncio.gather(relay(client_reader, upstream_writer), relay(upstream_reader, client_writer))

    server = await asyncio.start_server(handle, *listen, ssl=context)
    async with server:
        await server.serve_forever()


def address(value: str) -> tuple[str, int]:
    host, _, port = value.rpartition(":")
    if host not in ("127.0.0.1", "localhost", "::1", "[::1]"):
        raise argparse.ArgumentTypeError(f"{value}: only loopback addresses are allowed")
    return host.strip("[]"), int(port)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--listen", type=address, default=("127.0.0.1", 8443), help="HTTPS address (default 127.0.0.1:8443)")
    parser.add_argument("--upstream", type=address, default=("127.0.0.1", 8080), help="server address (default 127.0.0.1:8080)")
    home = Path(os.environ.get("OMNIGRAPH_HOME") or Path.home() / ".omnigraph")
    parser.add_argument("--certs", type=Path, default=home / "local-tls",
                        help="certificate directory (default $OMNIGRAPH_HOME/local-tls)")
    args = parser.parse_args()
    ca, cert, key = ensure_certificates(args.certs)
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(cert, key)
    print(f"https://localhost:{args.listen[1]} -> http://{args.upstream[0]}:{args.upstream[1]} (CA {ca})", flush=True)
    try:
        asyncio.run(serve(args.listen, args.upstream, context))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
