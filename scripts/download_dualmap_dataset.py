#!/usr/bin/env python3
"""Download the public DualMap HM3D_collect SharePoint folder.

The downloader preserves the published directory structure, resumes partial
files, and verifies every completed file against the size reported by
SharePoint.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.parse import parse_qs, quote, urlparse


DEFAULT_SHARE_URL = (
    "https://hkustgz-my.sharepoint.com/:f:/g/personal/"
    "jjiang127_connect_hkust-gz_edu_cn/"
    "ErSvH_QPouBLsHE0AzZAw0oBQFqRIjdrEOxAHN7OBO0nHg?e=PvmkUo"
)


def run_curl(arguments: list[str], *, capture_output: bool = False) -> str:
    result = subprocess.run(
        ["curl", *arguments],
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture_output else None,
    )
    return result.stdout if capture_output else ""


class SharePointFolder:
    def __init__(self, share_url: str, cookie_file: Path) -> None:
        self.share_url = share_url
        self.cookie_file = cookie_file
        self.web_url = ""
        self.root_path = ""
        self.refresh_session()

    def refresh_session(self) -> None:
        effective_url = run_curl(
            [
                "--fail",
                "--silent",
                "--show-error",
                "--location",
                "--connect-timeout",
                "30",
                "--max-time",
                "120",
                "--cookie-jar",
                str(self.cookie_file),
                "--cookie",
                str(self.cookie_file),
                "--output",
                "/dev/null",
                "--write-out",
                "%{url_effective}",
                self.share_url,
            ],
            capture_output=True,
        )

        parsed = urlparse(effective_url)
        query = parse_qs(parsed.query)
        if "id" not in query:
            raise RuntimeError(f"Could not determine shared folder from {effective_url}")

        self.root_path = query["id"][0]
        path_parts = self.root_path.strip("/").split("/")
        if len(path_parts) < 2 or path_parts[0] != "personal":
            raise RuntimeError(f"Unexpected SharePoint folder path: {self.root_path}")
        web_path = "/" + "/".join(path_parts[:2])
        self.web_url = f"{parsed.scheme}://{parsed.netloc}{web_path}"

    def _folder_info(self, server_path: str) -> dict:
        escaped_path = quote(server_path.replace("'", "''"), safe="/")
        api_url = (
            f"{self.web_url}/_api/web/"
            f"GetFolderByServerRelativeUrl('{escaped_path}')"
            "?$expand=Folders,Files"
        )
        output = run_curl(
            [
                "--fail",
                "--silent",
                "--show-error",
                "--connect-timeout",
                "30",
                "--max-time",
                "120",
                "--cookie",
                str(self.cookie_file),
                "--header",
                "Accept: application/json;odata=nometadata",
                api_url,
            ],
            capture_output=True,
        )
        return json.loads(output)

    def list_files(self) -> list[dict]:
        files: list[dict] = []

        def visit(server_path: str) -> None:
            info = self._folder_info(server_path)
            for file_info in info.get("Files", []):
                server_url = file_info["ServerRelativeUrl"]
                relative_path = server_url[len(self.root_path) :].lstrip("/")
                files.append(
                    {
                        "relative_path": relative_path,
                        "server_url": server_url,
                        "size": int(file_info["Length"]),
                    }
                )
            for folder in info.get("Folders", []):
                visit(folder["ServerRelativeUrl"])

        visit(self.root_path)
        return sorted(files, key=lambda item: item["relative_path"])

    def download(self, server_url: str, output_file: Path) -> None:
        escaped_path = quote(server_url.replace("'", "''"), safe="/")
        download_url = (
            f"{self.web_url}/_api/web/"
            f"GetFileByServerRelativeUrl('{escaped_path}')/$value"
        )
        run_curl(
            [
                "--fail",
                "--location",
                "--show-error",
                "--progress-bar",
                "--connect-timeout",
                "30",
                "--retry",
                "10",
                "--retry-delay",
                "5",
                "--retry-all-errors",
                "--continue-at",
                "-",
                "--cookie",
                str(self.cookie_file),
                "--output",
                str(output_file),
                download_url,
            ]
        )


def format_size(size: int) -> str:
    return f"{size / 1024**3:.2f} GiB"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--share-url", default=DEFAULT_SHARE_URL)
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path("data/dualmap/HM3D_collect"),
    )
    parser.add_argument("--list-only", action="store_true")
    args = parser.parse_args()

    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="dualmap-sharepoint-") as temp_dir:
        source = SharePointFolder(args.share_url, Path(temp_dir) / "cookies.txt")
        files = source.list_files()
        total_size = sum(item["size"] for item in files)
        print(
            f"Found {len(files)} files ({format_size(total_size)}) in "
            f"{source.root_path}",
            flush=True,
        )

        manifest_path = destination / "download_manifest.json"
        manifest_path.write_text(json.dumps(files, indent=2) + "\n")
        if args.list_only:
            for item in files:
                print(f"{item['size']:>12}  {item['relative_path']}")
            return

        completed_size = 0
        for index, item in enumerate(files, start=1):
            relative_path = Path(item["relative_path"])
            expected_size = item["size"]
            target = destination / relative_path
            partial = target.with_name(target.name + ".part")
            target.parent.mkdir(parents=True, exist_ok=True)

            if target.exists() and target.stat().st_size == expected_size:
                completed_size += expected_size
                print(
                    f"[{index}/{len(files)}] Already complete: {relative_path}",
                    flush=True,
                )
                continue

            if target.exists():
                if partial.exists():
                    raise RuntimeError(
                        f"Both incomplete target and partial file exist: {target}"
                    )
                target.replace(partial)

            print(
                f"[{index}/{len(files)}] Downloading {relative_path} "
                f"({format_size(expected_size)})",
                flush=True,
            )

            for attempt in range(1, 4):
                try:
                    source.download(item["server_url"], partial)
                except subprocess.CalledProcessError:
                    if attempt == 3:
                        raise
                    print("Refreshing the SharePoint guest session...", flush=True)
                    time.sleep(5)
                    source.refresh_session()
                    continue

                actual_size = partial.stat().st_size
                if actual_size == expected_size:
                    break
                if actual_size > expected_size:
                    raise RuntimeError(
                        f"Downloaded file is larger than expected: {partial} "
                        f"({actual_size} > {expected_size})"
                    )
                print(
                    f"Partial file has {actual_size}/{expected_size} bytes; resuming...",
                    flush=True,
                )
            else:
                raise RuntimeError(f"Could not complete {relative_path}")

            if partial.stat().st_size != expected_size:
                raise RuntimeError(
                    f"Size verification failed for {partial}: "
                    f"expected {expected_size}, got {partial.stat().st_size}"
                )

            os.replace(partial, target)
            completed_size += expected_size
            print(
                f"Verified {relative_path}; total complete "
                f"{format_size(completed_size)}/{format_size(total_size)}",
                flush=True,
            )

    print(f"Download complete: {destination}", flush=True)


if __name__ == "__main__":
    main()
