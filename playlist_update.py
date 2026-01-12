
import os
import socket
import tempfile
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from datetime import timezone

def _to_raw_github_url(url: str) -> str:
	"""
	Convert GitHub UI URL to raw URL when applicable.
	- https://github.com/{owner}/{repo}/blob/{branch}/path -> https://raw.githubusercontent.com/{owner}/{repo}/{branch}/path
	- https://github.com/{owner}/{repo}/raw/{branch}/path -> https://raw.githubusercontent.com/{owner}/{repo}/{branch}/path
	- https://github.com/{owner}/{repo}/tree/{branch}/path is not a file; leave as-is
	- If already raw.githubusercontent.com, return unchanged.
	"""
	parsed = urllib.parse.urlparse(url)
	host = parsed.netloc.lower()

	if host == "raw.githubusercontent.com":
		return url

	if host == "github.com":
		parts = [p for p in parsed.path.split("/") if p]
		# Expect at least: owner, repo, (blob|raw), branch, path...
		if len(parts) >= 5 and parts[2] in ("blob", "raw"):
			owner, repo, _, branch = parts[:4]
			path_rest = "/".join(parts[4:])
			return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path_rest}"
		# If it's ".../main/..." without 'blob', some users copy the 'blob'less URL.
		# Best effort: detect common pattern and transform it.
		if len(parts) >= 4:
			owner, repo, branch = parts[:3]
			path_rest = "/".join(parts[3:])
			# Heuristic: if 'main' or 'master' looks like a branch name and there's a path
			if branch in ("main", "master") and path_rest:
				return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path_rest}"

	# Fallback: return original
	return url


def _http_head(url: str, timeout: float = 3.0):
	"""
	Perform a HEAD request (best-effort) and return (status, headers_dict).
	If HEAD is not allowed/supported, some servers may return 405; the caller can handle that.
	"""
	req = urllib.request.Request(url, method="HEAD")
	with urllib.request.urlopen(req, timeout=timeout) as resp:
		# Headers in http.client.HTTPMessage (case-insensitive)
		return resp.status, dict(resp.headers)


def _http_get_to_temp(url: str, timeout: float = 3.0) -> str:
	"""
	Download a URL to a temporary file and return the temp file path.
	Caller is responsible for deleting the file or moving it into place.
	"""
	req = urllib.request.Request(url, method="GET")
	with urllib.request.urlopen(req, timeout=timeout) as resp:
		fd, tmp_path = tempfile.mkstemp(prefix="net_sync_", suffix=".tmp")
		try:
			with os.fdopen(fd, "wb") as tmp:
				chunk = resp.read(8192)
				while chunk:
					tmp.write(chunk)
					chunk = resp.read(8192)
		except Exception:
			# Ensure temp file removed on failure
			try:
				os.remove(tmp_path)
			except OSError:
				pass
			raise
	return tmp_path


def _parse_http_datetime(value: str):
	"""
	Parse an HTTP-date like 'Last-Modified' into an aware datetime (UTC).
	Returns None if parsing fails.
	"""
	try:
		dt = parsedate_to_datetime(value)
		# Ensure timezone-aware in UTC
		if dt.tzinfo is None:
			dt = dt.replace(tzinfo=timezone.utc)
		return dt.astimezone(timezone.utc)
	except Exception:
		return None


def _get_local_mtime_utc(path: str):
	"""
	Get local file mtime as an aware UTC datetime.
	Returns None if file does not exist.
	"""
	if not os.path.exists(path):
		return None
	ts = os.path.getmtime(path)
	return datetime_from_timestamp_utc(ts)


def datetime_from_timestamp_utc(ts: float):
	"""Return an aware UTC datetime from a POSIX timestamp."""
	return __import__("datetime").datetime.fromtimestamp(ts, tz=timezone.utc)


def _files_differ(path_a: str, path_b: str, chunk_size: int = 65536) -> bool:
	"""
	Compare two files by content; returns True if they differ, False if identical.
	"""
	if os.path.getsize(path_a) != os.path.getsize(path_b):
		return True
	with open(path_a, "rb") as fa, open(path_b, "rb") as fb:
		while True:
			a = fa.read(chunk_size)
			b = fb.read(chunk_size)
			if not a and not b:
				return False
			if a != b:
				return True


def sync_remote_file(
	url: str,
	local_filename: str = None,
	timeout: float = 3.0,
) -> tuple[bool, str]:
	"""
	Check a remote file and update the local file if the remote is newer.

	Parameters
	----------
	url : str
		The URL to check. If it is a GitHub UI URL, it will be converted to a raw URL.
	local_filename : str, optional
		Path to the local file. If None, inferred from the URL’s last path segment,
		created in the current working directory.
	timeout : float, optional
		Network timeout (seconds). Defaults to 3.0 seconds.

	Returns
	-------
	(updated, message) : (bool, str)
		updated=True if the local file was replaced with newer content; False otherwise.
		message describes what happened.

	Behavior
	--------
	- Makes a HEAD request to read 'Last-Modified'. If present, compares with local mtime.
	- If remote is newer (strictly greater), downloads and atomically replaces the local file.
	- If 'Last-Modified' is missing or HEAD not allowed, downloads to temp and compares contents;
	  replaces only if they differ.
	- If the local file does not exist, downloads it.
	- Times out after `timeout` seconds on network operations.
	"""
	raw_url = _to_raw_github_url(url)

	# Determine local path
	if local_filename is None:
		name = os.path.basename(urllib.parse.urlparse(raw_url).path) or "downloaded.file"
		local_path = os.path.abspath(name)
	else:
		local_path = os.path.abspath(local_filename)

	# --- Early guard: if local file does not exist, download it immediately ---
	if not os.path.exists(local_path):
		try:
			tmp_path = _http_get_to_temp(raw_url, timeout=timeout)
		except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
			return (False, f"Network unavailable or timed out after {timeout}s while initial download: {e}")
		os.replace(tmp_path, local_path)
		return (True, "Local file missing; downloaded new file from remote.")

	try:
		# First try HEAD to get Last-Modified
		try:
			status, headers = _http_head(raw_url, timeout=timeout)
		except urllib.error.HTTPError as e:
			# Some servers reject HEAD (405, etc.) -> fall back to GET path
			status, headers = e.code, dict(e.headers or {})
		except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
			return (False, f"Network unavailable or timed out after {timeout}s: {e}")

		if status >= 400:
			# If HEAD failed, try fallback by downloading and comparing content
			# Only proceed to GET if we have no local file or need to check.
			if not os.path.exists(local_path):
				# Try to GET (may still fail on network)
				try:
					tmp_path = _http_get_to_temp(raw_url, timeout=timeout)
				except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
					return (False, f"Remote HEAD error {status} and download failed/timed out after {timeout}s: {e}")
				# Move into place
				os.replace(tmp_path, local_path)
				return (True, f"Downloaded new file (HEAD {status}, no local file previously).")
			else:
				# Local exists; attempt GET to check content freshness
				try:
					tmp_path = _http_get_to_temp(raw_url, timeout=timeout)
				except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
					return (False, f"Remote HEAD error {status} and download failed/timed out after {timeout}s: {e}")
				try:
					if _files_differ(local_path, tmp_path):
						os.replace(tmp_path, local_path)
						return (True, f"Replaced local file (HEAD {status}, content differed).")
					else:
						os.remove(tmp_path)
						return (False, f"No update needed (HEAD {status}, content identical).")
				except Exception as ex:
					# Clean temp if still present
					try:
						if os.path.exists(tmp_path):
							os.remove(tmp_path)
					except OSError:
						pass
					raise ex

		# If we got headers, try Last-Modified comparison
		last_mod_hdr = headers.get("Last-Modified")
		if last_mod_hdr:
			remote_dt = _parse_http_datetime(last_mod_hdr)
		else:
			remote_dt = None

		local_dt = _get_local_mtime_utc(local_path)

		# If we have a local file and a remote last-modified, compare timestamps
		if local_dt is not None and remote_dt is not None:
			if remote_dt <= local_dt:
				return (False, "No update needed (remote is not newer than local).")
			# else remote is newer: download and replace
			try:
				tmp_path = _http_get_to_temp(raw_url, timeout=timeout)
			except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
				return (False, f"Timed out or failed to download after {timeout}s: {e}")
			os.replace(tmp_path, local_path)
			return (True, "Remote file was newer; replaced local file.")

		# If no local file exists, download it
		if local_dt is None:
			try:
				tmp_path = _http_get_to_temp(raw_url, timeout=timeout)
			except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
				return (False, f"Network unavailable or timed out after {timeout}s: {e}")
			os.replace(tmp_path, local_path)
			return (True, "No local file; downloaded new file.")

		# If Last-Modified not available, fallback to content comparison
		if remote_dt is None:
			try:
				tmp_path = _http_get_to_temp(raw_url, timeout=timeout)
			except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
				return (False, f"Timed out or failed to download after {timeout}s: {e}")
			try:
				if _files_differ(local_path, tmp_path):
					os.replace(tmp_path, local_path)
					return (True, "Last-Modified missing; content differed, replaced local file.")
				else:
					os.remove(tmp_path)
					return (False, "Last-Modified missing; content identical, no update needed.")
			except Exception as ex:
				try:
					if os.path.exists(tmp_path):
						os.remove(tmp_path)
				except OSError:
					pass
				raise ex

		# Default no-op (shouldn’t reach here)
		return (False, "No action taken.")
	except Exception as e:
		return (False, f"Error: {e}")
