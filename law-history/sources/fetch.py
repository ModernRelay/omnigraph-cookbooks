#!/usr/bin/env python3
"""Download the official documents behind the law-history seed and check each one.

documents.json pins every document by URL and SHA-256. A document is kept only if
its bytes hash to the pinned value; a file already present with the right hash is
not downloaded again. A different hash means the publisher now serves different
bytes, and the script refuses the document rather than build from it.

    python3 law-history/sources/fetch.py                 # into law-history/sources/documents/
    python3 law-history/sources/fetch.py --into DIR
    python3 law-history/sources/fetch.py --only src-pl-117-5
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
USER_AGENT = "omnigraph-cookbooks law-history fetch (+https://github.com/ModernRelay/omnigraph-cookbooks)"
ATTEMPTS = 3
PAUSE_SECONDS = 1.0


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url):
    """The response body, retrying network errors and 5xx answers."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code < 500 or attempt == ATTEMPTS:
                raise
        except urllib.error.URLError:
            if attempt == ATTEMPTS:
                raise
        time.sleep(2 * attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--into", default=os.path.join(HERE, "documents"), help="directory for the documents")
    parser.add_argument("--only", nargs="+", metavar="SLUG", help="fetch only these Source slugs")
    args = parser.parse_args()

    documents = json.load(open(os.path.join(HERE, "documents.json")))["documents"]
    if args.only:
        unknown = set(args.only) - {d["slug"] for d in documents}
        if unknown:
            sys.exit(f"unknown slugs: {', '.join(sorted(unknown))}")
        documents = [d for d in documents if d["slug"] in args.only]
    os.makedirs(args.into, exist_ok=True)

    failures = []
    for i, doc in enumerate(documents):
        path = os.path.join(args.into, doc["file"])
        if os.path.exists(path) and sha256_file(path) == doc["sha256"]:
            print(f"ok      {doc['file']} (already present)")
            continue
        if i:
            time.sleep(PAUSE_SECONDS)
        try:
            body = download(doc["url"])
        except (urllib.error.URLError, OSError) as error:
            failures.append(f"{doc['file']}: {doc['url']}: {error}")
            print(f"FAILED  {doc['file']}: {error}")
            continue
        got = hashlib.sha256(body).hexdigest()
        if got != doc["sha256"]:
            failures.append(f"{doc['file']}: {doc['url']} now serves {len(body)} bytes with sha256 {got}, "
                            f"not the pinned {doc['sha256']}")
            print(f"REFUSED {doc['file']}: different bytes from the pinned document")
            continue
        handle, temporary = tempfile.mkstemp(dir=args.into, prefix=".fetch-")
        with os.fdopen(handle, "wb") as f:
            f.write(body)
        os.replace(temporary, path)
        print(f"fetched {doc['file']} ({len(body)} bytes)")

    if failures:
        print("\n" + "\n".join(failures), file=sys.stderr)
        sys.exit(f"{len(failures)} of {len(documents)} documents not fetched")
    print(f"{len(documents)} documents in {args.into}, every one matching its pinned sha256")


if __name__ == "__main__":
    main()
