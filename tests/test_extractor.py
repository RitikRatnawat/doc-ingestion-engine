"""Module to test the PageExtracter class and its methods."""

import re
from pathlib import Path

from src.docingest import PageExtracter

fixtures = Path(__file__).parent / "fixtures"


def test_code_language_detected():
    """Test that the _code_language method correctly detects the programming language from a <pre> tag."""

    html = """
    <html>
        <body>
            <pre class="language-python"><code>print("Hello, World!")</code></pre>
        </body>
    </html>
    """

    page = PageExtracter().extract(html, base_url="http://example.com")
    assert "```python" in page.markdown, "The programming language should be detected as Python."


def test_nav_and_footer_removed():
    """Test that <nav> and <footer> elements are removed from the markdown output."""

    html = """
    <nav>MENU</nav>
    <main>
        <h1>Hi</h1>
        <p>body</p>
    </main>
    <footer>FOOT</footer>
    """

    page = PageExtracter().extract(html, base_url="http://example.com")

    assert "<nav>" not in page.markdown, "Navigation should be removed from the markdown."
    assert "<footer>" not in page.markdown, "Footer should be removed from the markdown"


def test_title_inside_article_header_removed():
    """Test that the title inside an <article> header is removed from the markdown output."""

    html = """
    <article>
        <header>
            <h1>Title</h1>
        </header>
        <p>text</p>
    </article>
    """

    page = PageExtracter().extract(html, base_url="http://example.com")

    assert "<header>" not in page.markdown, "Header should be removed from the markdown."
    assert "Title" not in page.markdown, "Title should be removed from the markdown."


def test_input_and_button_elements_removed():
    """Test that <input> and <button> elements are removed from the markdown output."""

    html = """
    <input type="text" placeholder="Enter your name">
    <button>Click me</button>
    """

    page = PageExtracter().extract(html, base_url="http://example.com")

    assert "<input>" not in page.markdown, "Input elements should be removed from the markdown."
    assert "<button>" not in page.markdown, "Button elements should be removed from the markdown."


def test_real_page_title_not_empty():
    """Test that a real page extraction results in a non-empty title."""

    html = (fixtures / "python_json.html").read_text(encoding="utf-8")
    page = PageExtracter().extract(html, base_url="https://docs.python.org/3/library/json.html")

    assert page.title is not None and len(page.title) > 0, "Real Page Title should not be empty"


def test_real_page_url_not_empty():
    """Test that a real page extraction results in a non-empty URL."""

    html = (fixtures / "python_json.html").read_text(encoding="utf-8")
    page = PageExtracter().extract(html, base_url="https://docs.python.org/3/library/json.html")

    assert page.url is not None and len(page.url) > 0, "Real Page url should not be empty"


def test_real_page_not_empty():
    """Test that a real page extraction does not result in an empty markdown output."""

    html = (fixtures / "python_json.html").read_text(encoding="utf-8")
    page = PageExtracter().extract(html, base_url="https://docs.python.org/3/library/json.html")

    assert len(page.markdown) > 1000, "Extracted Content should not be empty"


def test_relative_urls():
    """Test that a relative urls is replaced by absolute urls"""

    html = """
    <div>
        <a href="/tests/path">Run the Test</a>
        <a href="/tests/results">See Test results</a>
    <div>
    """

    page = PageExtracter().extract(html, "https://www.testexample.com")
    print(page)

    assert (
        "https://www.testexample.com/tests/path" in page.markdown
    ), "Relative URLs should be replaced by Absolute URLs"
    assert (
        "https://www.testexample.com/tests/results" in page.markdown
    ), "Relative URLs should be replaced by Absolute URLs"


def test_images_cleaned_up():
    """Test the images are removed from the main content"""

    html = """
    <div class="image1">
        <h3>Image showing a Developer</h3>
        <img src="/path/to/image/1">
    </div>
    <div class="image2">
        <h3>Image showing a Codebase</h3>
        <img src="/path/to/image/2">
    </div>
    """

    page = PageExtracter().extract(html, "https://www.testexample.com")

    assert "/path/to/image/1" not in page.markdown, "Images should be removed from the Main Content"
    assert "/path/to/image/2" not in page.markdown, "Images should be removed from the Main Content"
    assert (
        "Image showing a Developer" in page.markdown
    ), "Text with the Images should not be removed from the Main Content"
    assert (
        "Image showing a Codebase" in page.markdown
    ), "Text with the Images should not be removed from the Main Content"


def test_tables_handled():
    "Test whether the tables in the pages are handled correctly"

    html = (fixtures / "beautifulsoup_quickstart.html").read_text(encoding="utf-8")

    page = PageExtracter().extract(html, "https://beautiful-soup-4.readthedocs.io/en/latest/")

    assert re.search(r"^\|(\s*-+\s*\|)+$", page.markdown, re.MULTILINE), "HTML tables should be markdownify"


def test_admonition_handling():
    """Test whether the admonitions are handled correctly or not"""

    html = """
    <div class="note admonition">
        <p class="admonition-title">reStructuredText directives</p>
        <p><code class="docutils literal notranslate"><span class="pre">toctree</span></code> 
        is a reStructuredText <em class="dfn">directive</em>, a very versatile piece
        of markup.  Directives can have arguments, options and content.</p>
        <p><em>Arguments</em> are given directly after the double colon following the
        directive's name.  Each directive decides whether it can have arguments, and
        how many.</p>
        <p><em>Options</em> are given after the arguments, in form of a “field list”.  The
        <code class="docutils literal notranslate"><span class="pre">maxdepth</span></code> 
        is such an option for the <code class="docutils literal notranslate">
        <span class="pre">toctree</span></code> directive.</p>
        <p><em>Content</em> follows the options or arguments after a blank line.  Each
        directive decides whether to allow content, and what to do with it.</p>
        <p>A common gotcha with directives is that <strong>the first line of the content must
        be indented to the same level as the options are</strong>.</p>
    </div>
    """

    page = PageExtracter().extract(html, "https://www.testexample.com")

    assert "**reStructuredText directives:**" in page.markdown, "Admonition Title should be in strong text"
    assert re.search(r">", page.markdown, re.MULTILINE), "Content should be in blockquotes"
