#!/usr/bin/env python3
"""Safe, dependency-free backup and publishing bridge for Mataroa."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import sys
import time
import uuid
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

API_ROOT = "https://mataroa.blog/api"
ROOT = Path.cwd().resolve()
API_TIMEOUT_SECONDS = 30
MAX_GET_ATTEMPTS = 3
MARKER_TEMPLATE = "<!-- mataroa-bridge-id: {bridge_id} -->"
MARKER_RE = re.compile(r"<!--\s*mataroa-bridge-id:\s*([0-9a-f]{32})\s*-->")
BRIDGE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class SyncError(RuntimeError):
    """Expected, user-actionable synchronization failure."""


def log(message: str) -> None:
    print(message, flush=True)


def require_api_key() -> str:
    key = os.environ.get("MATAROA_API_KEY", "").strip()
    if not key:
        raise SyncError(
            "Missing MATAROA_API_KEY. Add it under GitHub repository Settings → "
            "Secrets and variables → Actions. Never put the key in a file."
        )
    return key


def _decode_response(raw: bytes, endpoint: str) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SyncError(f"Mataroa returned an unexpected non-JSON response for {endpoint}.") from exc
    if not isinstance(data, dict):
        raise SyncError(f"Mataroa returned an unexpected response format for {endpoint}.")
    if data.get("ok") is False:
        # Do not print request headers or credentials. The API error body is kept short.
        details = str(data.get("error") or data.get("detail") or "API reported ok=false")[:300]
        raise SyncError(f"Mataroa API rejected {endpoint}: {details}")
    return data


def api_request(method: str, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call Mataroa API; retry only safe GET requests, never POST/PATCH/DELETE."""
    key = require_api_key()
    url = f"{API_ROOT}{endpoint}"
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "User-Agent": "mataroa-github-bridge/1.0",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    attempts = MAX_GET_ATTEMPTS if method.upper() == "GET" else 1

    for attempt in range(1, attempts + 1):
        request = Request(url, data=data, headers=headers, method=method.upper())
        try:
            with urlopen(request, timeout=API_TIMEOUT_SECONDS) as response:
                return _decode_response(response.read(), endpoint)
        except HTTPError as exc:
            body = exc.read(1000).decode("utf-8", errors="replace").strip()
            if method.upper() == "GET" and (exc.code == 429 or 500 <= exc.code <= 599) and attempt < attempts:
                time.sleep(attempt * 2)
                continue
            # Avoid dumping a full HTML error page into action logs.
            detail = re.sub(r"\s+", " ", body)[:250]
            suffix = f" Response: {detail}" if detail else ""
            raise SyncError(f"Mataroa API request failed ({method} {endpoint}, HTTP {exc.code}).{suffix}") from exc
        except URLError as exc:
            if method.upper() == "GET" and attempt < attempts:
                time.sleep(attempt * 2)
                continue
            if method.upper() != "GET":
                raise SyncError(
                    "The Mataroa publishing request had a network error, so its outcome may be uncertain. "
                    "The script will not blindly retry a POST. Check Mataroa for the article; if it exists, "
                    "rerun the workflow so the bridge marker can reconcile it. If it does not exist, rerun."
                ) from exc
            raise SyncError(f"Could not reach Mataroa API for {endpoint}: {exc.reason}") from exc
        except TimeoutError as exc:
            if method.upper() == "GET" and attempt < attempts:
                time.sleep(attempt * 2)
                continue
            if method.upper() != "GET":
                raise SyncError(
                    "The Mataroa publishing request timed out, so its outcome may be uncertain. "
                    "Check Mataroa before manually retrying. If the post exists, rerun the workflow to "
                    "reconcile it; if it does not exist, rerun."
                ) from exc
            raise SyncError(f"Mataroa API request timed out for {endpoint}.") from exc
    raise SyncError(f"Request failed after retries: {method} {endpoint}")


def list_posts() -> list[dict[str, Any]]:
    response = api_request("GET", "/posts/")
    posts = response.get("post_list")
    if not isinstance(posts, list):
        raise SyncError("Mataroa's /posts/ response did not contain a post_list array.")
    valid_posts: list[dict[str, Any]] = []
    for index, post in enumerate(posts):
        if not isinstance(post, dict) or not isinstance(post.get("slug"), str) or not post["slug"]:
            raise SyncError(f"Mataroa returned an invalid post item at index {index}; no files were written.")
        valid_posts.append(post)
    return valid_posts


def filename_for_slug(slug: str) -> str:
    # quote() encodes slashes and backslashes so a remote slug can never create a subdirectory.
    encoded = quote(slug, safe="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.~")
    if encoded in {"", ".", ".."}:
        encoded = quote(slug, safe="-_") or "empty-slug"
    return encoded + ".md"


def scalar_to_text(raw: str) -> str:
    value = raw.strip()
    if value.startswith('"'):
        try:
            decoded = json.loads(value)
            if isinstance(decoded, str):
                return decoded
        except json.JSONDecodeError:
            pass
    if value.startswith("'"):
        try:
            decoded = ast.literal_eval(value)
            if isinstance(decoded, str):
                return decoded
        except (ValueError, SyntaxError):
            pass
    return value


def parse_markdown_file(path: Path) -> tuple[dict[str, str], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise SyncError(f"{path.as_posix()} is not valid UTF-8. Save it as UTF-8 and try again.") from exc
    except OSError as exc:
        raise SyncError(f"Could not read {path.as_posix()}: {exc}") from exc

    if not text.startswith("---\n"):
        raise SyncError(f"{path.as_posix()} must start with a metadata block beginning with ---.")
    closing = text.find("\n---\n", 4)
    if closing < 0:
        raise SyncError(f"{path.as_posix()} has no closing --- metadata delimiter.")

    raw_header = text[4:closing]
    metadata: dict[str, str] = {}
    for line_number, line in enumerate(raw_header.splitlines(), start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise SyncError(f"Invalid metadata line in {path.as_posix()} at line {line_number}: {line}")
        key, value = line.split(":", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
            raise SyncError(f"Invalid metadata key in {path.as_posix()} at line {line_number}: {key!r}")
        if key in metadata:
            raise SyncError(f"Duplicate metadata key {key!r} in {path.as_posix()}.")
        metadata[key] = scalar_to_text(value)

    body = text[closing + len("\n---\n"):]
    # A blank line after the closing delimiter is formatting, not the first character of the post.
    body = body.lstrip("\n")
    return metadata, body


def render_markdown(metadata: dict[str, Any], body: str) -> str:
    lines = ["---"]
    for key, value in metadata.items():
        if value is None:
            value = ""
        lines.append(f"{key}: {json.dumps(str(value), ensure_ascii=False)}")
    lines.extend(["---", body])
    return "\n".join(lines)


def write_if_changed(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == content:
                return False
        except UnicodeDecodeError:
            # Replace corrupted/non-text archive with a valid generated UTF-8 copy.
            pass
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def backup_posts() -> None:
    posts = list_posts()  # Validate the full API response before writing anything.
    output_dir = ROOT / "posts"
    planned: dict[Path, str] = {}
    for post in posts:
        slug = str(post["slug"])
        title = str(post.get("title") or "")
        body_value = post.get("body")
        body = body_value if isinstance(body_value, str) else ""
        published_at = "" if post.get("published_at") is None else str(post.get("published_at"))
        url = str(post.get("url") or "")
        metadata = {
            "mataroa_sync_version": "1",
            "title": title,
            "slug": slug,
            "published_at": published_at,
            "url": url,
        }
        file_path = output_dir / filename_for_slug(slug)
        if file_path in planned:
            raise SyncError(f"Two Mataroa slugs map to the same archive path: {file_path.name}. No files were written.")
        planned[file_path] = render_markdown(metadata, body)

    changed = 0
    for path, content in planned.items():
        changed += int(write_if_changed(path, content))
    # Deliberately do not remove files absent from the current API response: they may be useful archive history.
    log(f"Backup complete: {len(posts)} Mataroa posts checked; {changed} file(s) added or updated.")
    log("Archived files absent from Mataroa were left untouched.")


def validate_draft_path(raw_path: str) -> Path:
    if not raw_path or "\\" in raw_path:
        raise SyncError("Enter a repository-relative path such as drafts/2026-10-28-my-note.md.")
    posix = PurePosixPath(raw_path)
    if posix.is_absolute() or len(posix.parts) < 2 or posix.parts[0] != "drafts" or ".." in posix.parts:
        raise SyncError("The publishing input must point to a file inside drafts/.")
    if posix.suffix.lower() != ".md":
        raise SyncError("Only Markdown (.md) drafts can be published.")
    candidate = ROOT.joinpath(*posix.parts)
    drafts_root = (ROOT / "drafts").resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(drafts_root)
    except ValueError as exc:
        raise SyncError("The selected draft resolves outside drafts/; publishing was stopped.") from exc
    if candidate.is_symlink():
        raise SyncError("Symbolic links are not allowed in drafts/.")
    if not resolved.is_file():
        raise SyncError(f"Draft not found: {raw_path}. Check the path and commit the draft first.")
    return resolved


def validate_date(value: str, path: Path) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise SyncError(
            f"Invalid published_at value in {path.as_posix()}: {value!r}. Use YYYY-MM-DD, for example 2026-10-28."
        ) from exc
    if parsed.isoformat() != value:
        raise SyncError(f"published_at must use YYYY-MM-DD format in {path.as_posix()}.")
    return value


def validate_new_post_draft(path: Path, metadata: dict[str, str], body: str) -> tuple[str, str]:
    title = metadata.get("title", "").strip()
    if not title:
        raise SyncError(f"{path.as_posix()} needs a non-empty title field.")
    if "\n" in title or "\r" in title:
        raise SyncError("The title must be a single line.")
    if "slug" in metadata or "url" in metadata:
        raise SyncError(
            "This first version only creates NEW posts. Remove slug/url metadata from this draft; "
            "edit existing articles directly on Mataroa so Mataroa remains authoritative."
        )
    if not body.strip():
        raise SyncError(f"{path.as_posix()} has an empty body; publishing was stopped to avoid an accidental blank post.")
    published_at = metadata.get("published_at", "").strip()
    if not published_at:
        published_at = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    else:
        published_at = validate_date(published_at, path)
    return title, published_at


def prepare_publish(raw_path: str) -> None:
    """Validate a draft and persist an id before calling the non-idempotent POST API."""
    path = validate_draft_path(raw_path)
    metadata, body = parse_markdown_file(path)
    validate_new_post_draft(path, metadata, body)
    bridge_id = metadata.get("mataroa_bridge_id", "").strip()
    if not bridge_id:
        metadata["mataroa_bridge_id"] = uuid.uuid4().hex
        changed = write_if_changed(path, render_markdown(metadata, body))
        if changed:
            log(f"Prepared {raw_path}: saved a stable publishing ID before contacting Mataroa.")
    elif not BRIDGE_ID_RE.fullmatch(bridge_id):
        raise SyncError(f"Invalid mataroa_bridge_id in {raw_path}; expected 32 lowercase hexadecimal characters.")
    else:
        log(f"Draft is valid and already has a stable publishing ID: {raw_path}.")


def find_post_by_marker(posts: list[dict[str, Any]], bridge_id: str) -> dict[str, Any] | None:
    marker = MARKER_TEMPLATE.format(bridge_id=bridge_id)
    for post in posts:
        body = post.get("body")
        if isinstance(body, str) and marker in body:
            return post
    return None


def ensure_body_marker(body: str, bridge_id: str) -> str:
    desired = MARKER_TEMPLATE.format(bridge_id=bridge_id)
    other_markers = [match.group(1) for match in MARKER_RE.finditer(body)]
    if other_markers and any(existing != bridge_id for existing in other_markers):
        raise SyncError(
            "This draft contains a publishing marker from another post. Remove the old "
            "'mataroa-bridge-id' HTML comment from the body before publishing it as a new post."
        )
    if desired in body:
        return body
    return body.rstrip() + "\n\n" + desired + "\n"


def published_at_from_post(post: dict[str, Any], fallback: str) -> str:
    value = post.get("published_at")
    if isinstance(value, str) and value:
        return value
    return fallback


def publish_new_post(raw_path: str) -> None:
    path = validate_draft_path(raw_path)
    metadata, body = parse_markdown_file(path)
    title, published_at = validate_new_post_draft(path, metadata, body)
    bridge_id = metadata.get("mataroa_bridge_id", "").strip()
    if not BRIDGE_ID_RE.fullmatch(bridge_id):
        raise SyncError("The draft has no valid publishing ID. The prepare step must run first; retry this workflow.")

    published_dir = ROOT / "published"
    archive_path = published_dir / path.name
    if archive_path.exists():
        raise SyncError(
            f"{archive_path.relative_to(ROOT).as_posix()} already exists. Refusing to overwrite it. "
            "Choose a new filename for a new article."
        )

    # Idempotency check: if a previous run created the post but failed before its Git commit,
    # the marker lets this run reconcile it instead of POSTing a duplicate.
    existing = find_post_by_marker(list_posts(), bridge_id)
    if existing is not None:
        log(f"Found an existing Mataroa post with this draft's marker; skipping POST to avoid a duplicate.")
        post = existing
        final_body = str(post.get("body") or "")
    else:
        final_body = ensure_body_marker(body, bridge_id)
        payload = {"title": title, "body": final_body, "published_at": published_at}
        try:
            response = api_request("POST", "/posts/", payload)
        except SyncError as original_error:
            # POST outcome can be uncertain after a network/5xx error. Reconcile before failing.
            try:
                recovered = find_post_by_marker(list_posts(), bridge_id)
            except SyncError:
                recovered = None
            if recovered is None:
                raise original_error
            log("Recovered the post created by a previous/uncertain request; skipping another POST.")
            post = recovered
            final_body = str(post.get("body") or final_body)
        else:
            if response.get("ok") is not True:
                # If the API response shape is ambiguous, check for the marker before giving up.
                recovered = find_post_by_marker(list_posts(), bridge_id)
                if recovered is None:
                    raise SyncError("Mataroa did not confirm that the post was created. No automatic retry was attempted.")
                post = recovered
                final_body = str(post.get("body") or final_body)
            else:
                post = response
                if not isinstance(post.get("slug"), str) or not post.get("slug"):
                    # A malformed response is not retried blindly; the next run performs marker reconciliation.
                    raise SyncError(
                        "Mataroa may have created the post but returned no slug. Check the blog, then rerun the "
                        "workflow; the stable marker is designed to prevent duplicates."
                    )

    slug = str(post.get("slug") or "")
    url = str(post.get("url") or "")
    if not slug:
        raise SyncError("The matching Mataroa post was found but had no slug; manual inspection is required.")
    # Keep a copy of the published source in-repo; the scheduled backup also stores the canonical API body in posts/.
    published_metadata = {
        "title": str(post.get("title") or title),
        "slug": slug,
        "published_at": published_at_from_post(post, published_at),
        "url": url,
        "mataroa_bridge_id": bridge_id,
    }
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(archive_path))
    write_if_changed(archive_path, render_markdown(published_metadata, final_body))
    log("Publish completed.")
    log(f"Title: {published_metadata['title']}")
    log(f"URL: {url or '(Mataroa API did not return a URL)'}")
    log(f"GitHub record: {archive_path.relative_to(ROOT).as_posix()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mataroa ↔ GitHub safe blog backup/publishing bridge")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("backup", help="Back up all Mataroa posts to posts/ without deleting old archive files")
    prepare_parser = subparsers.add_parser("prepare-publish", help="Validate draft and persist a stable ID before POST")
    prepare_parser.add_argument("--draft", required=True, help="Repository-relative Markdown path under drafts/")
    publish_parser = subparsers.add_parser("publish", help="Publish one new draft and move it to published/")
    publish_parser.add_argument("--draft", required=True, help="Repository-relative Markdown path under drafts/")
    args = parser.parse_args(argv)
    try:
        if args.command == "backup":
            backup_posts()
        elif args.command == "prepare-publish":
            prepare_publish(args.draft)
        elif args.command == "publish":
            publish_new_post(args.draft)
        return 0
    except SyncError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
