from __future__ import annotations

from dataclasses import dataclass, asdict
from email.utils import parsedate_to_datetime
import re
import xml.etree.ElementTree as ET

import requests


class AlertsServiceError(Exception):
    pass


@dataclass
class AlertItem:
    source: str
    title: str
    description: str
    country: str
    level: str
    event_type: str
    published_at: str
    link: str

    def to_dict(self) -> dict:
        return asdict(self)


class AlertsService:
    GDACS_RSS_URL = "https://www.gdacs.org/xml/rss.xml"
    REQUEST_TIMEOUT = 12
    DEFAULT_LIMIT = 8

    DEFAULT_COUNTRIES = (
        "Poland", "Belarus", "Ukraine", "Moldova", "Romania", "Czech", "Slovakia",
        "Lithuania", "Latvia", "Estonia", "Italy", "Germany", "France", "Spain",
        "Portugal", "Netherlands", "Belgium", "Austria", "Switzerland", "Ireland",
        "United Kingdom", "Norway", "Sweden", "Finland", "Denmark", "Greece",
        "Hungary", "Croatia", "Slovenia", "Serbia", "Bosnia", "Montenegro",
        "Albania", "North Macedonia", "Bulgaria", "Kazakhstan",
        "Armenia", "Azerbaijan", "Georgia", "Kyrgyzstan", "Tajikistan", "Uzbekistan",
        "Turkmenistan",
    )

    def fetch_alerts(self, limit: int = DEFAULT_LIMIT) -> list[AlertItem]:
        xml_text = self._fetch_gdacs_rss()
        return self._parse_gdacs_rss(xml_text, limit=limit)

    def _fetch_gdacs_rss(self) -> str:
        try:
            response = requests.get(self.GDACS_RSS_URL, timeout=self.REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            raise AlertsServiceError("Unable to reach GDACS alert feed.") from exc

        if response.status_code != 200:
            raise AlertsServiceError("GDACS alert feed returned an unexpected status.")

        return response.text

    def _parse_gdacs_rss(self, xml_text: str, limit: int) -> list[AlertItem]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise AlertsServiceError("GDACS alert feed is not valid XML.") from exc

        channel = root.find("channel")
        if channel is None:
            return []

        alerts: list[AlertItem] = []

        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            description = (item.findtext("description") or "").strip()
            link = (item.findtext("link") or "").strip()
            published_raw = (item.findtext("pubDate") or "").strip()

            if not self._matches_target_region(title, description):
                continue

            country = self._extract_country(title)
            event_type = self._extract_event_type(link)
            level = self._extract_level(title)
            published_at = self._format_pub_date(published_raw)

            alerts.append(AlertItem(
                source="GDACS",
                title=title or "Unnamed alert",
                description=description,
                country=country,
                level=level,
                event_type=event_type,
                published_at=published_at,
                link=link,
            ))

            if len(alerts) >= max(1, limit):
                break

        return alerts

    def _matches_target_region(self, title: str, description: str) -> bool:
        text = f"{title} {description}".lower()
        return any(country.lower() in text for country in self.DEFAULT_COUNTRIES)

    def _extract_country(self, title: str) -> str:
        match = re.search(r"\bin\s+([^.,]+)", title, flags=re.IGNORECASE)
        if not match:
            return "Unknown"
        return match.group(1).strip()

    def _extract_event_type(self, link: str) -> str:
        match = re.search(r"eventtype=([A-Z]+)", link)
        code = match.group(1) if match else "UNK"
        labels = {
            "EQ": "Earthquake",
            "FL": "Flood",
            "WF": "Wildfire",
            "TC": "Tropical Cyclone",
            "DR": "Drought",
            "VO": "Volcano",
        }
        return labels.get(code, code)

    def _extract_level(self, title: str) -> str:
        if " red " in f" {title.lower()} ":
            return "red"
        if " orange " in f" {title.lower()} ":
            return "orange"
        if " green " in f" {title.lower()} ":
            return "green"
        return "unknown"

    def _format_pub_date(self, pub_date: str) -> str:
        if not pub_date:
            return ""
        try:
            dt = parsedate_to_datetime(pub_date)
            return dt.strftime("%Y-%m-%d %H:%M UTC")
        except (TypeError, ValueError, IndexError):
            return pub_date
