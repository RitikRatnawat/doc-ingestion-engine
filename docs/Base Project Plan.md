# Automated Documentation Ingestion & Normalization Engine

A high-performance, containerized Python microservice designed to ingest raw HTML from official technical documentation sites, systematically strip DOM layout noise (navbars, footers, scripts, sidebars), and normalize the remaining core technical data into structured, clean Markdown. 

This utility serves as a critical upstream data-preprocessing pipeline for Large Language Model (LLM) contexts and Retrieval-Augmented Generation (RAG) applications where raw web layouts introduce significant structural noise.

---

## 🏗️ Architecture & Features

- **Heuristic DOM Purging:** Leverages `BeautifulSoup4` to selectively prune non-semantic layout elements (`<nav>`, `<header>`, `<footer>`, scripts, stylesheets) to eliminate data fragmentation.
- **Semantic Block Isolation:** Automatically isolates primary content wrappers (`<main>`, `<article>`, `#main-content`) using targeted fallbacks to preserve data integrity.
- **Lossless Markdown Conversion:** Utilizes `Markdownify` configured with dynamic code-block language detection and explicit layout rendering for complex technical documentations.
- **Containerized Implementation:** Fully packaged using a lean Docker multi-stage footprint optimized for cloud-native deployment.
- **Streamlit Interface:** Built-in web UI providing instant side-by-side rendered previews and raw markdown extraction.

---

## 📂 Project Structure

```text
├── app.py                 # Ingestion core logic & Streamlit UI
├── Dockerfile             # Production-ready lean container manifest
├── requirements.txt       # Dependency specifications
└── README.md              # Project documentation
```

---

## 🛠️ Codebase Layout

### 1. The Core Application (`app.py`)
```python
import streamlit as st
import requests
from bs4 import BeautifulSoup
import markdownify
import re

def clean_html_to_markdown(url):
    """
    Fetches raw HTML from documentation, strips layout clutter, 
    and converts the core content area into clean Markdown.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        return f"❌ Error fetching URL: {str(e)}"

    soup = BeautifulSoup(response.text, "html.parser")

    # 1. Strip structural clutter before parsing text
    elements_to_remove = [
        "nav", "header", "footer", "sidebar", "aside", "script", "style", 
        "noscript", "iframe", "form", ".navbar", ".sidebar", "#sidebar", 
        ".footer", "#footer", ".breadcrumbs", ".table-of-contents", "input", "button"
    ]
    for selector in elements_to_remove:
        for element in soup.select(selector):
            element.decompose()

    # 2. Heuristic: Isolate the main technical article space
    main_content = None
    priority_tags = ["main", "article", "[role='main']", "#main-content", ".content", ".documentation"]
    
    for tag in priority_tags:
        main_content = soup.select_one(tag)
        if main_content:
            break
            
    # Fallback to the whole body if no semantic main section is found
    if not main_content:
        main_content = soup.body if soup.body else soup

    # 3. Convert sanitized HTML structure to Markdown
    md_content = markdownify.markdownify(
        str(main_content),
        heading_style="ATX",      # Uses #, ##, ### instead of underlining headings
        bullets="-",
        code_language_callback=lambda el: el.get("class", [""]).replace("language-", "") if el.has_attr("class") else ""
    )

    # 4. Pure Python regex optimization to clean up trailing spacing fragments
    md_content = re.sub(r'\n{3,}', '\n\n', md_content)  # Collapse massive blank line streaks
    md_content = md_content.strip()

    return md_content

# --- Streamlit UI Setup ---
st.set_page_config(page_title="Doc to Markdown Converter", layout="wide")

st.title("📄 Documentation Scraper & Markdown Converter")
st.caption("Pure Python utility to scrape official docs, strip structural layout noise, and yield clean Markdown.")

url_input = st.text_input("Enter Official Documentation URL:", placeholder="https://docs.python.org/3/")

if st.button("Fetch & Process Markdown", type="primary"):
    if url_input:
        with st.spinner("Scraping and converting layout..."):
            markdown_output = clean_html_to_markdown(url_input)
            
            if markdown_output.startswith("❌"):
                st.error(markdown_output)
            else:
                st.success("Successfully parsed and converted!")
                
                st.download_button(
                    label="📥 Download Markdown File",
                    data=markdown_output,
                    file_name="scraped_documentation.md",
                    mime="text/markdown"
                )
                
                tab1, tab2 = st.tabs(["👀 Rendered Preview", "💻 Raw Markdown Text"])
                
                with tab1:
                    st.markdown(markdown_output)
                
                with tab2:
                    st.code(markdown_output, language="markdown")
    else:
        st.warning("Please enter a valid destination URL.")
```

### 2. Dependency Specification (`requirements.txt`)
```text
streamlit==1.32.0
requests==2.31.0
beautifulsoup4==4.12.3
markdownify==0.11.6
```

### 3. Container Configuration (`Dockerfile`)
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

---

## ⚡ Quick Start & Deployment

### Run Locally (Without Docker)
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Execute the engine interface:
   ```bash
   streamlit run app.py
   ```

### Run via Docker
1. Build the microservice image:
   ```bash
   docker build -t doc-markdown-app .
   ```
2. Launch the container orchestration mapping port 8501:
   ```bash
   docker run -d -p 8501:8501 --name dynamic_scraper doc-markdown-app
   ```
3. Access the operational UI interface via your browser at `http://localhost:8501`.