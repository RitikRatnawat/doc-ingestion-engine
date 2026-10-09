"""Module to test the PageExtracter class and its methods."""

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

    assert page.title is not None and len(page.title) > 0


def test_real_page_url_not_empty():
    """Test that a real page extraction results in a non-empty URL."""

    html = (fixtures / "python_json.html").read_text(encoding="utf-8")
    page = PageExtracter().extract(html, base_url="https://docs.python.org/3/library/json.html")

    assert page.url is not None and len(page.url) > 0


def test_real_page_not_empty():
    """Test that a real page extraction does not result in an empty markdown output."""

    html = (fixtures / "python_json.html").read_text(encoding="utf-8")
    page = PageExtracter().extract(html, base_url="https://docs.python.org/3/library/json.html")

    assert len(page.markdown) > 1000
