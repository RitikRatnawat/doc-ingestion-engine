# DocIngest: Step-by-Step Phase Guide

Follow the phases in order. Every phase has numbered steps, the code or commands to use, a **Verify** check, and a suggested commit message. Do not move on until Verify passes.

**Prerequisites:** Python 3.11+, Git, Docker, a GitHub account, a code editor.

---

### Target project structure
```text
doc-ingestion-engine/
├── src/docingest/
│   ├── __init__.py
│   ├── config.py          # settings (pydantic-settings)
│   ├── fetcher.py         # httpx client, retries, robots, SSRF guard
│   ├── extractor.py       # clean HTML -> Markdown
│   ├── profiles.py        # per-site selector profiles
│   ├── crawler.py         # same-domain BFS crawler
│   ├── chunker.py         # heading-aware chunking + metadata
│   ├── models.py          # pydantic models (Page, Chunk, CrawlResult)
│   ├── security.py        # URL validation, private-IP blocking
│   └── cli.py             # Typer CLI
├── api/main.py            # FastAPI app
├── ui/app.py              # Streamlit client calling the API
├── tests/
│   ├── fixtures/          # saved HTML from real doc sites
│   ├── test_extractor.py
│   ├── test_fetcher.py
│   ├── test_security.py
│   ├── test_crawler.py
│   ├── test_chunker.py
│   └── test_api.py
├── benchmarks/run_benchmark.py
├── docs/                  # architecture diagram, demo GIF
├── Dockerfile             # multi-stage, non-root
├── docker-compose.yml     # api + ui
├── pyproject.toml         # deps, ruff, mypy, pytest config
├── .pre-commit-config.yaml
├── .github/workflows/ci.yml
└── README.md
```

---

## Phase 0: Project Setup

**Goal:** A professional repo skeleton with tooling that runs before any real code exists.

1. Create the folder and repo:
   ```bash
   mkdir doc-ingestion-engine && cd doc-ingestion-engine
   git init
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   ```
2. Create the layout:
   ```bash
   mkdir -p src/docingest tests/fixtures benchmarks docs ui .github/workflows
   touch src/docingest/__init__.py tests/__init__.py
   ```
3. Create `pyproject.toml`:
   ```toml
   [build-system]
   requires = ["hatchling"]
   build-backend = "hatchling.build"

   [project]
   name = "docingest"
   version = "0.1.0"
   description = "Crawl technical docs and convert them to clean Markdown and RAG-ready chunks"
   requires-python = ">=3.11"
   dependencies = [
     "httpx>=0.27", "beautifulsoup4>=4.12", "lxml>=5", "markdownify>=0.11.6",
     "pydantic>=2.6", "pydantic-settings>=2.2", "fastapi>=0.110",
     "uvicorn[standard]>=0.29", "typer>=0.12", "tiktoken>=0.7",
   ]

   [project.optional-dependencies]
   ui  = ["streamlit>=1.32"]
   dev = ["pytest>=8", "pytest-cov", "pytest-asyncio", "respx", "ruff", "mypy", "pre-commit"]

   [project.scripts]
   docingest = "docingest.cli:app"

   [tool.hatch.build.targets.wheel]
   packages = ["src/docingest"]

   [tool.pytest.ini_options]
   asyncio_mode = "auto"
   testpaths = ["tests"]

   [tool.ruff]
   line-length = 100
   src = ["src", "tests"]
   [tool.ruff.lint]
   select = ["E", "F", "I", "B", "UP"]

   [tool.mypy]
   strict = true
   plugins = ["pydantic.mypy"]
   [[tool.mypy.overrides]]
   module = ["markdownify.*"]
   ignore_missing_imports = true
   ```
4. Install in editable mode:
   ```bash
   pip install -e ".[dev,ui]"
   ```
5. Add `.gitignore` (`.venv/`, `__pycache__/`, `.mypy_cache/`, `.pytest_cache/`, `.coverage`, `out/`, `*.jsonl`) and an MIT `LICENSE`.
6. Add `.pre-commit-config.yaml`:
   ```yaml
   repos:
     - repo: https://github.com/astral-sh/ruff-pre-commit
       rev: v0.5.0
       hooks:
         - id: ruff
           args: [--fix]
         - id: ruff-format
   ```
   Then run `pre-commit install`.
7. Add a smoke test `tests/test_smoke.py`:
   ```python
   def test_import():
       import docingest
       assert docingest
   ```
8. Create a stub `README.md` with just the project title and one sentence.

**Verify:** `pytest`, `ruff check .`, and `mypy src` all run without errors.

**Commit:** `chore: project scaffold with tooling`

---

## Phase 1: Core Extractor Module

**Goal:** Move the logic out of the UI into pure, typed, network-free functions, and fix the original bugs.

1. Create `src/docingest/models.py`:
   ```python
   from pydantic import BaseModel

   class Page(BaseModel):
       url: str
       title: str
       markdown: str
   ```
2. Save 3 real HTML pages as test fixtures (do this once, then tests never touch the network):
   ```bash
   curl -sL https://docs.python.org/3/library/json.html -o tests/fixtures/python_json.html
   curl -sL https://developer.mozilla.org/en-US/docs/Web/HTTP/Overview -o tests/fixtures/mdn_http.html
   curl -sL https://flask.palletsprojects.com/en/stable/quickstart/ -o tests/fixtures/flask_quickstart.html
   ```
3. Create `src/docingest/extractor.py`. Key design changes from the original: **pick the main container first, then clean inside it**, so a legitimate `<header>` or title inside an article is never deleted, and nav/footer outside it disappear automatically.
   ```python
   from __future__ import annotations

   import re

   from bs4 import BeautifulSoup, Tag
   from markdownify import markdownify

   from .models import Page

   MAIN_CANDIDATES = [
       "main", "article", "[role='main']", "#main-content", "#content",
       ".content", ".documentation", ".document",
   ]
   NOISE_INSIDE_MAIN = [
       "script", "style", "noscript", "iframe", "svg", "button", "input", "form",
   ]
   FALLBACK_NOISE = ["nav", "header", "footer", "aside"] + NOISE_INSIDE_MAIN

   def _code_language(pre: Tag) -> str:
       nodes: list[Tag] = [pre, *pre.find_all("code", limit=1)]
       for node in nodes:
           for cls in node.get("class", []):
               if cls.startswith(("language-", "highlight-", "lang-")):
                   return cls.split("-", 1)[1]
           lang = node.get("data-lang")
           if isinstance(lang, str):
               return lang
       return ""

   def _pick_main(soup: BeautifulSoup) -> Tag:
       for selector in MAIN_CANDIDATES:
           found = soup.select_one(selector)
           if found:
               return found
       body = soup.body or soup
       for selector in FALLBACK_NOISE:
           for el in body.select(selector):
               el.decompose()
       return body

   def extract(html: str, base_url: str) -> Page:
       soup = BeautifulSoup(html, "lxml")
       title_tag = soup.find("h1") or soup.find("title")
       title = title_tag.get_text(" ", strip=True) if title_tag else base_url

       main = _pick_main(soup)
       for selector in NOISE_INSIDE_MAIN:
           for el in main.select(selector):
               el.decompose()

       md = markdownify(
           str(main),
           heading_style="ATX",
           bullets="-",
           code_language_callback=_code_language,
       )
       md = re.sub(r"\n{3,}", "\n\n", md).strip()
       return Page(url=base_url, title=title, markdown=md)
   ```
4. Write tests in `tests/test_extractor.py`:
   ```python
   from pathlib import Path
   from docingest.extractor import extract

   FIX = Path(__file__).parent / "fixtures"

   def test_code_language_detected():
       html = '<main><pre class="language-python"><code>print(1)</code></pre></main>'
       assert "```python" in extract(html, "https://x.dev").markdown

   def test_nav_and_footer_removed():
       html = "<nav>MENU</nav><main><h1>Hi</h1><p>body</p></main><footer>FOOT</footer>"
       md = extract(html, "https://x.dev").markdown
       assert "MENU" not in md and "FOOT" not in md and "body" in md

   def test_title_inside_article_header_kept():
       html = "<article><header><h1>Title</h1></header><p>text</p></article>"
       assert "Title" in extract(html, "https://x.dev").markdown

   def test_real_page_not_empty():
       html = (FIX / "python_json.html").read_text(encoding="utf-8")
       page = extract(html, "https://docs.python.org/3/library/json.html")
       assert len(page.markdown) > 1000
   ```
5. Add `tests/test_smoke.py` cleanup if redundant, then run everything.

**Verify:** All tests pass offline (disconnect Wi-Fi and run `pytest`). Open the Markdown output of each fixture and read it once.

**Commit:** `feat: typed extractor with fixed language detection and main-first cleaning`

---

## Phase 2: Robust Cleaning and Fidelity

**Goal:** Output that is genuinely good on real doc sites, not just on toy HTML.

1. **Resolve relative URLs.** Add to `extract()` after choosing `main`:
   ```python
   from urllib.parse import urljoin

   for a in main.select("a[href]"):
       a["href"] = urljoin(base_url, a["href"])
   for img in main.select("img[src]"):
       img["src"] = urljoin(base_url, img["src"])
   ```
2. **Strip doc-site junk** inside `main`. Add these selectors to a new list `DOC_JUNK`:
   `a.headerlink`, `.copybtn`, `button.copy`, `.edit-this-page`, `.theme-edit-this-page`, `[aria-label='Copy']`, `.toctree-wrapper`, `.breadcrumbs`, `.pagination-nav`.
   Loop and `decompose()` them the same way as noise.
3. **Per-site profiles.** Create `src/docingest/profiles.py`:
   ```python
   PROFILES: dict[str, dict[str, list[str]]] = {
       "docs.python.org":        {"main": ["div[role='main']"], "remove": [".headerlink"]},
       "developer.mozilla.org":  {"main": ["article"],          "remove": [".bc-table", ".prev-next"]},
       "react.dev":              {"main": ["article"],          "remove": []},
   }

   def profile_for(host: str) -> dict[str, list[str]]:
       return PROFILES.get(host, {"main": [], "remove": []})
   ```
   In `_pick_main`, try profile `main` selectors first, then the generic list. Apply profile `remove` selectors after.
4. **Tables:** Markdownify handles simple tables. Add a fixture with a table and assert the pipe syntax appears. If a table has merged cells, leave it as is and note it under Limitations.
5. **Admonitions** (Sphinx `div.admonition`, Docusaurus `.admonition`): convert to blockquotes with a bold label. Pre-process before markdownify:
   ```python
   for box in main.select("div.admonition, .admonition"):
       title = box.select_one(".admonition-title")
       label = title.get_text(strip=True) if title else "Note"
       if title:
           title.decompose()
       box.replace_with(BeautifulSoup(
           f"<blockquote><strong>{label}:</strong> {box.get_text(' ', strip=True)}</blockquote>",
           "lxml").blockquote)
   ```
6. **Post-processing:** collapse blank lines (already done), strip trailing spaces per line, and remove an immediately repeated heading.
7. **Add 5 or more fixtures** from different frameworks (Sphinx, MkDocs, Docusaurus, plain HTML, MDN). For each, add a **snapshot test**: store the expected output in `tests/snapshots/<name>.md` and compare. Regenerate a snapshot deliberately when you improve output, never casually.

**Verify:** Open 5 outputs side by side with the live pages. No nav text, no "Copy" strings, links are absolute, code fences have languages.

**Commit:** `feat: url resolution, site profiles, admonitions, snapshot tests`

---

## Phase 3: Fetch Layer (Safe and Polite)

**Goal:** Fetch pages without being a security risk or a bad citizen.

1. **Create `src/docingest/security.py`** (SSRF guard):
   ```python
   import ipaddress
   import socket
   from urllib.parse import urlparse

   class UnsafeURLError(ValueError):
       pass

   def validate_url(url: str) -> None:
       parts = urlparse(url)
       if parts.scheme not in {"http", "https"}:
           raise UnsafeURLError(f"Scheme not allowed: {parts.scheme!r}")
       if not parts.hostname:
           raise UnsafeURLError("Missing host")
       try:
           infos = socket.getaddrinfo(parts.hostname, parts.port or 443)
       except socket.gaierror as exc:
           raise UnsafeURLError(f"Cannot resolve host: {exc}") from exc
       for info in infos:
           ip = ipaddress.ip_address(info[4][0])
           if (ip.is_private or ip.is_loopback or ip.is_link_local
                   or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
               raise UnsafeURLError(f"Blocked address: {ip}")
   ```
2. **Write security tests first** (`tests/test_security.py`):
   ```python
   import pytest
   from docingest.security import UnsafeURLError, validate_url

   @pytest.mark.parametrize("url", [
       "http://localhost/", "http://127.0.0.1/", "http://169.254.169.254/latest/meta-data/",
       "http://10.0.0.5/", "file:///etc/passwd", "ftp://example.com/",
   ])
   def test_blocked(url):
       with pytest.raises(UnsafeURLError):
           validate_url(url)
   ```
3. **Create `src/docingest/fetcher.py`.** Key rules: manual redirect handling so every hop is re-validated, a size cap, a content-type check, and retries with backoff.
   ```python
   from __future__ import annotations

   import asyncio
   from urllib.parse import urljoin

   import httpx

   from .security import validate_url

   USER_AGENT = "docingest/0.1 (+https://github.com/<you>/doc-ingestion-engine)"
   MAX_BYTES = 5_000_000
   MAX_REDIRECTS = 5

   class FetchError(RuntimeError):
       pass

   async def fetch_html(url: str, client: httpx.AsyncClient, retries: int = 3) -> tuple[str, str]:
       """Return (final_url, html). Validates every redirect hop."""
       delay = 1.0
       last_exc: Exception | None = None
       for _attempt in range(retries):
           try:
               return await _fetch_once(url, client)
           except (httpx.TransportError, FetchError) as exc:
               last_exc = exc
               await asyncio.sleep(delay)
               delay *= 2
       raise FetchError(f"Failed after {retries} attempts: {last_exc}")

   async def _fetch_once(url: str, client: httpx.AsyncClient) -> tuple[str, str]:
       for _hop in range(MAX_REDIRECTS + 1):
           validate_url(url)
           async with client.stream("GET", url, follow_redirects=False,
                                    headers={"User-Agent": USER_AGENT}) as resp:
               if resp.is_redirect:
                   url = urljoin(url, resp.headers["location"])
                   continue
               if resp.status_code >= 500:
                   raise FetchError(f"Server error {resp.status_code}")
               resp.raise_for_status()
               if "html" not in resp.headers.get("content-type", ""):
                   raise FetchError("Not an HTML response")
               body = bytearray()
               async for chunk in resp.aiter_bytes():
                   body.extend(chunk)
                   if len(body) > MAX_BYTES:
                       raise FetchError("Response too large")
               return url, bytes(body).decode(resp.encoding or "utf-8", errors="replace")
       raise FetchError("Too many redirects")
   ```
4. **robots.txt.** Add `src/docingest/robots.py`:
   ```python
   from urllib.parse import urlparse
   from urllib.robotparser import RobotFileParser
   import httpx

   class RobotsCache:
       def __init__(self, client: httpx.AsyncClient, user_agent: str):
           self._client, self._ua = client, user_agent
           self._parsers: dict[str, RobotFileParser] = {}

       async def allowed(self, url: str) -> bool:
           p = urlparse(url)
           origin = f"{p.scheme}://{p.netloc}"
           if origin not in self._parsers:
               rp = RobotFileParser()
               try:
                   r = await self._client.get(f"{origin}/robots.txt", timeout=10)
                   rp.parse(r.text.splitlines() if r.status_code == 200 else [])
               except httpx.HTTPError:
                   rp.parse([])
               self._parsers[origin] = rp
           return self._parsers[origin].can_fetch(self._ua, url)
   ```
5. **Per-domain rate limit:** a simple `asyncio.Lock` plus `last_request_time` per host, sleeping so that requests to one host are at least 0.5 s apart. Put it in the crawler's page-fetch wrapper.
6. **Mock tests with `respx`** (no real network): test a 500-then-200 sequence (retry works), a redirect to `http://127.0.0.1` (blocked), an oversized body (rejected), and a `text/plain` response (rejected).
7. **Honest known limitation to write down:** validating DNS before connecting does not fully stop DNS rebinding. Note it in Limitations, and for a production hardening step mention connecting to the pinned IP or using an egress proxy.
8. **Optional:** Playwright fallback behind `--render-js` in a separate extra (`pip install "docingest[js]"`), used only when extracted Markdown is under ~200 characters.

**Verify:** Security and fetcher tests pass. Manually try `docingest`-style fetches of `http://localhost:8000` and confirm they are refused.

**Commit:** `feat: safe fetcher with SSRF guard, robots.txt, retries`

---

## Phase 4: Crawler

**Goal:** From one page to a whole documentation section.

1. **URL normalization helper** in `src/docingest/crawler.py`:
   ```python
   from urllib.parse import urldefrag, urlparse, urlunparse

   def normalize(url: str) -> str:
       url, _ = urldefrag(url)
       p = urlparse(url)
       path = p.path.rstrip("/") or "/"
       return urlunparse((p.scheme, p.netloc.lower(), path, "", p.query, ""))
   ```
2. **Link extraction:** from the cleaned page HTML, collect `a[href]`, resolve with `urljoin`, drop `mailto:`/`javascript:`, drop file extensions like `.pdf .zip .png`.
3. **Scope rule:** a link is in scope if it has the same host as the start URL **and** starts with the path prefix (default: the start URL's directory, overridable with `--prefix`). Add `--include`/`--exclude` regex options.
4. **Level-by-level BFS with concurrency:**
   ```python
   async def crawl(start_url, *, max_depth=2, max_pages=50, prefix=None, concurrency=5):
       sem = asyncio.Semaphore(concurrency)
       seen = {normalize(start_url)}
       frontier, pages = [start_url], []
       async with httpx.AsyncClient(timeout=15) as client:
           robots = RobotsCache(client, USER_AGENT)

           async def grab(u):
               async with sem:
                   if not await robots.allowed(u):
                       return u, None
                   try:
                       return await fetch_html(u, client)
                   except Exception:
                       return u, None

           for depth in range(max_depth + 1):
               frontier = frontier[: max_pages - len(pages)]
               if not frontier:
                   break
               results = await asyncio.gather(*(grab(u) for u in frontier))
               next_frontier = []
               for final_url, html in results:
                   if html is None:
                       continue
                   pages.append(extract(html, final_url))
                   if depth < max_depth:
                       for link in extract_links(html, final_url):
                           n = normalize(link)
                           if n not in seen and in_scope(n, start_url, prefix):
                               seen.add(n)
                               next_frontier.append(n)
               frontier = next_frontier
       return pages
   ```
   Log failures instead of silently swallowing them (use the `logging` module and collect a `failed` list for the report).
5. **Sitemap support (optional but impressive):** try `{origin}/sitemap.xml`; if present, seed the frontier from its `<loc>` entries that match the prefix.
6. **Output writer** (`write_site(pages, out_dir)`):
   - one `.md` file per page, filename derived from the URL path (`library/json.md`)
   - `index.json` listing `url`, `title`, `file`, `sha256` of content, `crawled_at`
7. **Tests:** mock a 4-page fake site with `respx` including a cycle (A links to B, B links back to A), a duplicate link with a `#fragment`, an off-domain link, and a `.pdf` link. Assert exactly 4 pages are produced with no duplicates and no off-domain fetches.

**Verify:** Real crawl: `max_depth=1, max_pages=20` on a docs section produces a clean folder and a valid `index.json`.

**Commit:** `feat: async same-domain crawler with dedupe and index output`

---

## Phase 5: RAG Chunking and Export

**Goal:** The feature that makes the project relevant to LLM work.

1. **Add the Chunk model** to `models.py`:
   ```python
   class Chunk(BaseModel):
       id: str
       source_url: str
       page_title: str
       heading_path: list[str]
       text: str
       token_count: int
       chunk_index: int
       content_hash: str
   ```
2. **Token counter** in `chunker.py`:
   ```python
   import tiktoken
   _enc = tiktoken.get_encoding("cl100k_base")

   def count_tokens(text: str) -> int:
       return len(_enc.encode(text))
   ```
3. **Split by heading while respecting code fences.** The crucial detail: a `#` inside a fenced code block is not a heading.
   ```python
   import re

   HEADING = re.compile(r"^(#{1,6})\s+(.*)$")

   def split_sections(md: str) -> list[tuple[list[str], str]]:
       sections, stack, buf, in_fence = [], [], [], False
       for line in md.splitlines():
           if line.strip().startswith("```"):
               in_fence = not in_fence
           m = None if in_fence else HEADING.match(line)
           if m:
               if buf:
                   sections.append((list(stack), "\n".join(buf).strip()))
                   buf = []
               level = len(m.group(1))
               stack = stack[: level - 1] + [m.group(2).strip()]
           buf.append(line)
       if buf:
           sections.append((list(stack), "\n".join(buf).strip()))
       return [(p, t) for p, t in sections if t]
   ```
4. **Enforce size limits.** For each section:
   - if `count_tokens(text) > max_tokens` (default 500), split on blank lines into paragraphs and pack greedily, **never splitting inside a code fence** (treat a whole fenced block as one unit; if one block alone exceeds the limit, keep it whole and mark it oversized).
   - if a section is under `min_tokens` (default 80), merge it into the next section with the same parent heading.
   - optional overlap: repeat the last paragraph of the previous chunk at the start of the next.
5. **Prefix the heading path to the chunk text** when embedding (e.g. `Install > Linux\n\n...`). It improves retrieval a lot, and you can measure it in Phase 10.
6. **Chunk id** = first 12 characters of `sha256(source_url + heading_path + text)`, so re-crawls are deduplicable.
7. **JSONL exporter:** one JSON object per line via `chunk.model_dump_json()`.
8. **Tests:**
   - a `#` comment inside a Python code block does not create a heading
   - no chunk contains an unbalanced number of ``` fences
   - every chunk has non-empty `source_url` and `heading_path`
   - total text across chunks reconstructs the page content (nothing lost)
9. **Mini retrieval demo** (`examples/query_demo.py`): embed chunks with a small local model (`sentence-transformers`, `all-MiniLM-L6-v2`), store in an in-memory FAISS or Chroma index, ask 3 questions, print the top chunk with its source URL. This gives you a demo GIF and a concrete talking point.

**Verify:** Chunk a real page, open the JSONL, and confirm headings, code blocks, and metadata look right.

**Commit:** `feat: heading-aware chunker with metadata and jsonl export`

---

## Phase 6: API, CLI, and UI

**Goal:** One engine, three interfaces.

1. **FastAPI app** at `src/docingest/api.py`:
   ```python
   import uuid
   from fastapi import BackgroundTasks, FastAPI, HTTPException
   from pydantic import BaseModel, HttpUrl

   app = FastAPI(title="DocIngest", version="0.1.0")
   JOBS: dict[str, dict] = {}   # in-memory; note this in Limitations

   class ConvertRequest(BaseModel):
       url: HttpUrl

   class CrawlRequest(BaseModel):
       url: HttpUrl
       max_depth: int = 1
       max_pages: int = 25
       chunk: bool = True

   @app.get("/health")
   def health():
       return {"status": "ok"}

   @app.post("/convert")
   async def convert(req: ConvertRequest):
       # fetch_html -> extract -> return Page; map UnsafeURLError -> 400, FetchError -> 502
       ...

   @app.post("/crawl", status_code=202)
   async def crawl_endpoint(req: CrawlRequest, bg: BackgroundTasks):
       job_id = uuid.uuid4().hex
       JOBS[job_id] = {"status": "running"}
       bg.add_task(run_crawl_job, job_id, req)
       return {"job_id": job_id}

   @app.get("/jobs/{job_id}")
   def job(job_id: str):
       if job_id not in JOBS:
           raise HTTPException(404, "Unknown job")
       return JOBS[job_id]
   ```
   `run_crawl_job` calls the crawler and chunker, then stores `{"status": "done", "pages": n, "chunks": [...]}` or `{"status": "failed", "error": ...}`.
2. **Map errors to status codes:** invalid or unsafe URL gives 400, upstream failure gives 502, unknown job gives 404, oversized request gives 422. Never return raw stack traces.
3. **Add a hard cap** on `max_pages` (for example 200) and `max_depth` (for example 3) in the request validator so a public deployment cannot be abused.
4. **Typer CLI** at `src/docingest/cli.py`:
   ```python
   import asyncio, typer
   app = typer.Typer(help="DocIngest CLI")

   @app.command()
   def convert(url: str, out: str = "page.md"): ...

   @app.command()
   def crawl(url: str, depth: int = 1, max_pages: int = 25,
             out: str = "./out", chunks: bool = True): ...
   ```
5. **Streamlit UI** (`ui/app.py`) becomes a thin client: it calls `POST /convert` and `POST /crawl` using `requests`, polls `/jobs/{id}`, and keeps the rendered/raw tabs plus a chunk table and JSONL download. Read the API base URL from an env var `DOCINGEST_API`.
6. **API tests** with `fastapi.testclient.TestClient` and mocked fetchers: `/health`, a successful `/convert`, a blocked URL returns 400, an unknown job returns 404.

**Verify:** `uvicorn docingest.api:app --reload`, open `http://localhost:8000/docs`, and run a convert and a crawl from the Swagger page. Run the same from the CLI.

**Commit:** `feat: fastapi service, typer cli, streamlit client`

---

## Phase 7: Testing and Coverage

**Goal:** Evidence of quality.

1. Run `pytest --cov=docingest --cov-report=term-missing`.
2. Fill gaps: look at lines marked missing and add tests for error branches (timeouts, bad HTML, empty main, oversized responses).
3. Make sure **no test uses the real network**. Search for `httpx.AsyncClient(` in tests and confirm each is under `respx.mock`.
4. Add edge-case fixtures: an empty page, a page with only navigation, malformed HTML, a non-UTF-8 page.
5. Add `--cov-fail-under=80` to the pytest config so CI enforces it.
6. Run `mypy src` in strict mode and fix every error.

**Verify:** Coverage at or above 80%, mypy clean, ruff clean.

**Commit:** `test: raise coverage to 80%+ and enforce in config`

---

## Phase 8: Containerization

**Goal:** A small, safe, genuinely multi-stage image.

1. **`Dockerfile`:**
   ```dockerfile
   # ---- build stage ----
   FROM python:3.12-slim AS builder
   WORKDIR /build
   RUN python -m venv /opt/venv
   ENV PATH="/opt/venv/bin:$PATH"
   COPY pyproject.toml README.md ./
   COPY src ./src
   RUN pip install --no-cache-dir .

   # ---- runtime stage ----
   FROM python:3.12-slim
   RUN useradd --create-home --uid 1000 app
   COPY --from=builder /opt/venv /opt/venv
   ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1
   USER app
   WORKDIR /home/app
   EXPOSE 8000
   HEALTHCHECK --interval=30s --timeout=5s \
     CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
   CMD ["uvicorn", "docingest.api:app", "--host", "0.0.0.0", "--port", "8000"]
   ```
2. **`.dockerignore`:** `.venv`, `.git`, `tests`, `benchmarks`, `__pycache__`, `*.md` except README.
3. **UI image** (`ui/Dockerfile`): a small image that installs only `streamlit` and `requests`, and runs `streamlit run app.py`.
4. **`docker-compose.yml`:**
   ```yaml
   services:
     api:
       build: .
       ports: ["8000:8000"]
     ui:
       build: ./ui
       ports: ["8501:8501"]
       environment:
         DOCINGEST_API: http://api:8000
       depends_on: [api]
   ```
5. Verify non-root: `docker compose exec api whoami` prints `app`.
6. Record the image size (`docker images`) for the README.

**Verify:** `docker compose up --build` gives a working API at `:8000/docs` and UI at `:8501`.

**Commit:** `build: multi-stage non-root docker image and compose`

---

## Phase 9: CI/CD

**Goal:** Automatic quality gates on every push and PR.

1. Create `.github/workflows/ci.yml`:
   ```yaml
   name: CI
   on: [push, pull_request]
   jobs:
     test:
       runs-on: ubuntu-latest
       strategy:
         matrix:
           python: ["3.11", "3.12"]
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with: { python-version: "${{ matrix.python }}" }
         - run: pip install -e ".[dev]"
         - run: ruff check .
         - run: ruff format --check .
         - run: mypy src
         - run: pytest --cov=docingest --cov-report=xml
     docker:
       runs-on: ubuntu-latest
       needs: test
       steps:
         - uses: actions/checkout@v4
         - run: docker build -t docingest .
   ```
2. Push to GitHub, open a PR, and confirm the checks run.
3. Enable **branch protection** on `main`: require the CI checks to pass before merging.
4. Add status and coverage badges to the README.
5. **Optional:** publish the image to GHCR on version tags; enable Dependabot (`.github/dependabot.yml`) for pip and GitHub Actions.
6. **Optional deployment:** deploy the API to Render, Fly.io, or Railway using the Dockerfile. Set the page and depth caps low on a public instance and put a note in the README.

**Verify:** A green CI badge, and a deliberately failing test blocks the PR.

**Commit:** `ci: github actions for lint, types, tests, docker build`

---

## Phase 10: Benchmarks and Documentation

**Goal:** Replace adjectives with measured numbers, and package the project for recruiters.

1. **Create `benchmarks/run_benchmark.py`.** For 10 documentation URLs (mix of Sphinx, MkDocs, Docusaurus, MDN, plain HTML):
   - fetch raw HTML, count tokens with tiktoken
   - extract Markdown, count tokens
   - compute `reduction = 1 - md_tokens / raw_tokens`
   - time extraction (milliseconds per page)
   - write results to `benchmarks/results.csv`
2. **Crawl throughput:** crawl one docs section with `max_pages=50` and compute pages per second (state the concurrency and rate-limit settings you used).
3. **Optional retrieval evaluation (strongest bullet):**
   - write 20 questions whose answers are in a docs section, with the expected source page for each
   - embed chunks from (a) raw-HTML text and (b) your cleaned heading-aware chunks
   - for each question, check whether the correct page appears in the top 3 results
   - report hit rate for both
4. **Write the README** with these sections in order:
   1. One-line pitch and badges
   2. The problem (why raw HTML hurts RAG), with a before/after example
   3. Demo GIF (record with a screen recorder: crawl a site, show the JSONL, run a query)
   4. Features
   5. Architecture diagram (draw.io or Mermaid) and a short component description
   6. Quick start (pip, Docker, CLI, API examples with `curl`)
   7. Benchmark table with your real numbers
   8. Design decisions (heading-aware vs fixed-size chunking, main-first cleaning, SSRF approach, why per-site profiles)
   9. **Limitations** (JS-rendered sites, login-gated docs, in-memory job store, DNS rebinding caveat, tables with merged cells)
   10. Roadmap and license
5. Add `docs/architecture.md` and a short `CONTRIBUTING.md`.
6. Tag a release: `git tag v0.1.0 && git push --tags`, and create a GitHub Release with notes.
7. Pin the repo on your GitHub profile and add the project to your resume using the bullets in the first plan file.

**Verify:** Someone who has never seen the project can run it from the README in under 5 minutes, and every number in the README comes from a file in `benchmarks/`.

**Commit:** `docs: benchmarks, architecture, readme, v0.1.0`

---

## Final Checklist

- [ ] Phases 0 to 10 complete, each committed separately (clean history)
- [ ] Zero network use in tests; 80%+ coverage; CI green
- [ ] SSRF tests prove localhost, metadata IP, and private redirects are blocked
- [ ] README numbers are real and reproducible
- [ ] Demo GIF or live link in the README
- [ ] Limitations section is honest
- [ ] Repo pinned, release tagged

## Common Pitfalls

- **Skipping fixtures and testing against live sites:** tests will flake and CI will fail randomly.
- **Writing the README last and from memory:** record real numbers as you go.
- **Overbuilding stretch goals before Phase 5 works:** chunking and the benchmark matter more than any extra feature.
- **Spoofing a browser User-Agent:** keep the honest one; it is part of the "polite crawler" story.
