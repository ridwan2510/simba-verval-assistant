from __future__ import annotations

import html as html_module
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def clean_text(value) -> str:
    if value is None:
        return ""

    text = html_module.unescape(str(value))
    text = re.sub(r"<[^>]*>", "", text)
    text = html_module.unescape(text)
    text = text.replace("\xa0", " ")

    return " ".join(text.split())


def abs_url(base_url: str, href: str | None) -> str:
    if not href:
        return ""

    href = str(href).strip()

    if not href:
        return ""

    return urljoin(
        base_url.rstrip("/") + "/",
        href,
    )


def extract_first_href(html_fragment: str | None) -> str:
    if not html_fragment:
        return ""

    soup = BeautifulSoup(
        str(html_fragment),
        "html.parser",
    )

    element = soup.find(href=True)

    if not element:
        return ""

    return (
        element.get("href")
        or ""
    ).strip()


def extract_data_file(html_fragment: str | None) -> str:
    if not html_fragment:
        return ""

    soup = BeautifulSoup(
        str(html_fragment),
        "html.parser",
    )

    element = soup.find(
        attrs={"data-file": True}
    )

    if not element:
        return ""

    return html_module.unescape(
        str(
            element.get("data-file")
            or ""
        )
    ).strip()


def extract_data_name(html_fragment: str | None) -> str:
    if not html_fragment:
        return ""

    soup = BeautifulSoup(
        str(html_fragment),
        "html.parser",
    )

    element = soup.find(
        attrs={"data-name": True}
    )

    if not element:
        return ""

    return clean_text(
        element.get("data-name")
    )
