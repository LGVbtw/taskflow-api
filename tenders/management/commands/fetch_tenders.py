import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from tenders.models import Tender

BASE_URL = "https://www.e-marchespublics.com/appel-offre"
USER_AGENT = "Mozilla/5.0 (TaskflowBot)"


def normalize_deadline(value: str):
    if not value:
        return None
    cleaned = value.replace("à", " ").replace("h", ":").replace("H", ":").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    try:
        naive = datetime.strptime(cleaned, "%d/%m/%Y %H:%M")
    except ValueError:
        return None
    return timezone.make_aware(naive, timezone.get_current_timezone())


def extract_source_id(href: str, title: str) -> str:
    if not href:
        return f"missing-{hash(title)}"
    path = urlparse(href).path.strip("/")
    parts = path.split("/")
    if len(parts) >= 2 and parts[-1].isdigit():
        return f"{parts[-2]}-{parts[-1]}"
    return path or title[:50]


def parse_cards(html: str) -> Iterable[dict]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div#result-panel div.box")
    for card in cards:
        title_el = card.select_one(".box-header-title .texttruncate")
        title = title_el.get_text(strip=True) if title_el else ""
        buyer = card.select_one(".box-body-top span")
        buyer_site_link = card.select_one(".body-top-action a")
        location_p = card.select_one(".body-middle .col1 p")
        cat_proc_p = card.select_one(".body-middle .col1 p:nth-of-type(2)")
        deadline_p = card.select_one(".body-middle .col3 p")
        deadline_value = card.select_one(".body-middle .col3 p span")
        links = card.select(".box-footer a.notice-a")

        cat_proc_text = cat_proc_p.get_text(" ", strip=True) if cat_proc_p else ""
        category, procedure = None, None
        if "-" in cat_proc_text:
            left, right = cat_proc_text.split("-", 1)
            category = left.strip()
            procedure = right.strip()
        else:
            category = cat_proc_text

        deadline_label = deadline_p.get_text(" ", strip=True) if deadline_p else ""
        deadline_clean = deadline_value.get_text(strip=True) if deadline_value else ""

        notice_links = {}
        for link in links:
            label = link.get_text(strip=True)
            notice_links[label.lower()] = link.get("href")

        href_example = links[0].get("href") if links else None
        source_id = extract_source_id(href_example, title)

        yield {
            "source_id": source_id,
            "title": title,
            "buyer_name": buyer.get_text(strip=True) if buyer else "",
            "buyer_location": location_p.get_text(" ", strip=True) if location_p else "",
            "category": category or "",
            "procedure": procedure or "",
            "deadline_label": deadline_label,
            "deadline_at": normalize_deadline(deadline_clean),
            "buyer_site_url": buyer_site_link.get("href") if buyer_site_link else "",
            "notice_links": notice_links,
            "metadata": {
                "raw_deadline": deadline_clean,
            },
            "raw_html": card.prettify(),
        }


class Command(BaseCommand):
    help = "Scrape e-marchespublics listings and persist them locally."

    def add_arguments(self, parser):
        parser.add_argument("--pages", type=int, default=1, help="Number of pages to fetch")
        parser.add_argument("--notice-type", default="AAPC", help="Notice type to fetch (AAPC, ATTRIB, etc.)")
        parser.add_argument("--from-file", dest="from_file", help="Parse tenders from an offline HTML file")

    def handle(self, *args, **options):
        pages = options["pages"]
        notice_type = options["notice_type"]
        from_file = options.get("from_file")

        if from_file:
            html = Path(from_file).read_text(encoding="utf-8")
            total = self._persist_html(html)
            self.stdout.write(self.style.SUCCESS(f"Imported {total} tenders from {from_file}"))
            return

        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        total_imported = 0
        for page in range(1, pages + 1):
            params = {"page": page}
            if notice_type:
                params["notice_type"] = notice_type
            response = session.get(BASE_URL, params=params, timeout=30)
            if response.status_code != 200:
                raise CommandError(f"Failed to fetch page {page}: HTTP {response.status_code}")
            total_imported += self._persist_html(response.text)
        self.stdout.write(self.style.SUCCESS(f"Imported/updated {total_imported} tenders"))

    def _persist_html(self, html: str) -> int:
        count = 0
        for payload in parse_cards(html):
            defaults = payload.copy()
            defaults.pop("source_id")
            Tender.objects.update_or_create(source_id=payload["source_id"], defaults=defaults)
            count += 1
        return count
