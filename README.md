# DocIngest

**Crawl technical documentation and turn it into clean Markdown and RAG-ready chunks.**

Raw documentation pages are full of navigation bars, footers, scripts, and sidebars.
When fed into an LLM or a retrieval pipeline, this noise wastes tokens and hurts
answer quality. DocIngest fetches documentation pages, strips the layout noise,
preserves the technical content (headings, code blocks with languages, tables, links),
and exports structured output ready for embedding.

## Features

- **Clean extraction:** isolates the main content area and converts it to Markdown,
  with per-site profiles for popular documentation frameworks
- **Site crawler:** async, same-domain crawling with depth limits, URL deduplication,
  and sitemap support
- **RAG-ready chunking:** heading-aware splitting that never breaks code blocks, with
  metadata (source URL, heading path, token count) exported as JSONL
- **Safe by design:** SSRF protection, robots.txt compliance, rate limiting, retries,
  and response size limits
- **Three interfaces:** FastAPI service, command-line tool, and Streamlit web UI
- **Production practices:** typed Python, 80%+ test coverage, CI with GitHub Actions,
  and a multi-stage, non-root Docker image

<!-- ## Results

Across N documentation sites, DocIngest reduced token count by **X%** while keeping
code blocks, tables, and links intact. -->

## Tech Stack

Python, FastAPI, httpx, BeautifulSoup, Markdownify, Typer, Streamlit, tiktoken,
Docker, GitHub Actions
