"""Module for extracting text and metadata from HTML content and converting it to markdown."""

from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as md

from .logger import logger
from .models import Page


class PageExtracter:
    """Class to handle the extraction of text from a Webpage and markdown conversion."""

    def __init__(self) -> None:
        """Constructor for the PageExtracter class."""

        logger.debug("Initializing PageExtracter and loading configuration from 'config/extracter.json'.")
        with open("config/extracter.json") as f:
            self.config = json.load(f)

        logger.debug("Configuration loaded successfully.")
        self.__main_candidates = self.config.get("MAIN_CANDIDATES", [])
        self.__noise_candidates = self.config.get("NOISE_CANDIDATES", [])

    def _code_language(self, pre: Tag) -> str:
        """Extracts the programming language from a <pre> tag.

        Args:
            pre (Tag): A BeautifulSoup Tag object representing a <pre> element.

        Returns:
            str: The programming language extracted from the <pre> tag or an empty string
        """

        # Get all the nodes
        logger.debug(f"Extracting code language from <pre> tag: {pre}")

        nodes: list[Tag] = []
        for node in [
            pre.parent.parent if pre.parent and pre.parent.parent else None,
            pre.parent,
            pre,
            *pre.find_all("code", limit=1),
        ]:
            if isinstance(node, Tag):
                nodes.append(node)

        # Iterate through the nodes to find the language
        for node in nodes:
            # check if the node has a class attribute
            if node and node.has_attr("class"):
                # Iterate through the classes of the node to find a language class
                for cls in map(str, node.get("class")):
                    if cls.startswith(("language-", "lang-", "highlight-")):
                        return cls.split("-", 1)[-1]

            language = node.get("data-lang") if node else None
            if isinstance(language, str):
                return language

        # If no language class is found, return an empty string
        logger.debug("No code language found in <pre> tag.")
        return ""

    def _get_main_content(self, soup: BeautifulSoup) -> Tag:
        """Extracts the main content of the webpage based on the configured main candidates.

        Args:
            soup (BeautifulSoup): A BeautifulSoup object representing the parsed HTML content.

        Returns:
            Tag: A BeautifulSoup Tag object representing the main content of the webpage.
        """

        logger.debug("Extracting main content from the webpage.")
        for selector in self.__main_candidates:
            main_content = soup.select_one(selector)
            if main_content:
                return main_content

        # If no main content is found, return the entire body
        logger.debug("No main content found using the configured selectors. Returning the entire body.")
        return soup.body or soup

    def remove_noise(self, main_content: Tag, base_url: str) -> None:
        """Remove unnecessary elements and noise from the content

        Args:
            main_content (Tag): Extracted Main Content
        """

        # Remove noise elements from the main content
        logger.debug("Removing noise elements from the main content.")
        for selector in self.__noise_candidates:
            for noise in main_content.select(selector):
                noise.decompose()

        # Resolving the relative urls
        logger.debug("Resolving relative URLs in the main content.")
        for a in main_content.select("a[href]"):
            a["href"] = str(urljoin(base_url, str(a["href"])))

        # Cleaning up the Images, wll be handled separately
        logger.debug("Removing images from the main content.")
        for img in main_content.select("img"):
            img.decompose()

        # Handling Admonitions like Key points, Stick notes, etc,
        logger.debug("Handling admonitions in the main content.")
        for box in main_content.select("div.admonition, .admonition"):
            title = box.select_one(".admonition-title")
            label = title.get_text(strip=True) if title else "Note"

            if title:
                title.decompose()

            box.replace_with(
                BeautifulSoup(
                    f"<blockquote><strong>{label}:</strong> {box.get_text(' ', strip=True)}</blockquote>", "lxml"
                ).blockquote
            )

    def extract(self, html: str, base_url: str) -> Page:
        """Extract text and metadata from the given HTML content and convert it to markdown.

        Args:
            html (str): HTML content of the webpage.
            base_url (str): Base URL of the webpage.

        Returns:
            Page: A Page object containing the extracted text, metadata, and markdown content.
        """

        logger.info(f"Extracting content for the Webpage: {base_url}")
        soup = BeautifulSoup(html, "lxml")

        logger.info("Extracting title from the Webpage.")
        title_tag = soup.find("title") or soup.find("h1")
        title = title_tag.get_text(" ", strip=True) if title_tag else base_url
        logger.debug(f"Extracted title: {title}")

        logger.info("Extracting main content from the Webpage.")
        main_content = self._get_main_content(soup)
        self.remove_noise(main_content, base_url)
        logger.debug("Noise removed and main content cleaned.")

        # Convert the cleaned main content to markdown
        logger.info("Converting main content to markdown.")
        markdown = md(
            str(main_content),
            heading_style="ATX",
            bullets="-",
            code_language_callback=self._code_language,
        )
        markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()
        markdown = re.sub(r"¶", "", markdown).strip()
        logger.debug("Markdown conversion completed.")

        return Page(title=title, url=base_url, markdown=markdown)
