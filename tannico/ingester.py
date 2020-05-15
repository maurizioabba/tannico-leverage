"""
Perform ingestion of data from a set of pages.
"""
from bs4 import BeautifulSoup
from collections.abc import Iterable
import logging
import requests
import datetime as dt
from typing import List, TypeVar, Dict

from tannico.models import Session
from tannico.models.wine import Wine

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import FlushError


class InvalidPage(Exception):
    """Exception raised when the page is invalid."""


class RequestTimeout(Exception):
    """Exception raised when request timed-out."""


class ServerUnavailable(Exception):
    """Exception raised when we had 3 consecutive timeouts."""


T = TypeVar("T", bound="CategoryCrawler")


class CategoryCrawler(Iterable):
    """
    An iterator-like object that returns wines of the specific category.

    A category must be a qualified base URL.
    The CategoryCrawler will request new pages from the base URL according to data received, and
    iterate over the wines parsed.
    """

    def __init__(
        self, category: str, lang: str, max_page: int = 0, max_timeout: int = 3
    ):
        self._category = category
        self._lang = lang
        self._today = dt.date.today()
        self._max_page = max_page
        self._max_timeout = max_timeout
        self.log = logging.getLogger(__name__)

    def __iter__(self):
        """The crawler is an iterator itself."""
        current_page = 1
        timeout_counter = 0
        while True:
            try:
                page = self.get_page(current_page)
                for w in self.parse_page(page):
                    yield w
            except InvalidPage:
                break
            except RequestTimeout:
                timeout_counter += 1
                if timeout_counter > self._max_timeout:
                    raise ServerUnavailable("Server timed out too many times")
                continue
            timeout_counter = 0
            current_page += 1
            if self._max_page and current_page > self._max_page:
                self.log.info(f"Reached max page {current_page}>{self._max_page}")
                break

    def get_page(self, current_page: int):
        """
        Get a page of a specific category.

        Raise InvalidPage if the returned page does not have any more page.
        """
        base_url = self._category
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/80.0.3987.149 Safari/537.36"
            )
        }
        payload = {"is_ajax_product_list": "true", "p": str(current_page)}
        self.log.info(f"requesting url {base_url} page {current_page}")
        try:
            r = requests.get(base_url, params=payload, headers=headers, timeout=30)
        except requests.exceptions.ReadTimeout:
            self.log.warning(f"Read timeout received on page {current_page}")
            raise RequestTimeout()
        self.log.debug(f"request sent {r.url} returned status code {r.status_code}")
        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError:
            raise InvalidPage()
        return r.text

    def parse_page(self, page: str):
        """Parse a page in a series of wines."""
        if "There are no products matching the selection" in page:
            raise InvalidPage()
        elif "Non ci sono prodotti corrispondenti alla selezione." in page:
            raise InvalidPage()
        soup = BeautifulSoup(page, "html.parser")
        items = soup.find_all("article", {"class": "productItem"})
        if not items:
            raise InvalidPage()
        for item in items:
            try:
                info = item.find("div", {"class": "productItem__info"})
                url = info.find("a")["href"]
                name = info.find("h4", {"class": "productItem__title"}).string
                if "Charity Box" in name or "bottiglie + libro" in name:
                    continue
                producer = info.find("p", {"class": "productItem__brand"}).string
                price = info.find("span", {"class": "new-price"}).string
                if not price:
                    price = info.find("span", {"class": "price"}).string
                awards = item.find("ul", {"class": "productItem__awards"})
                awards = awards.find_all("li") if awards else []
                yield Wine.parse(
                    name=name,
                    price=price,
                    producer=producer,
                    awards=awards,
                    url=url,
                    today=self._today,
                    lang=self._lang,
                )
            except Exception as e:
                self.log.warning(f"error ({str(e)}) parsing item {item}, skip")


class Ingester:
    def __init__(self):
        self.log = logging.getLogger(__name__)

    def crawl(
        self, lang: str, category_list: List[str], max_page: int = 0
    ) -> Dict[str, Wine]:
        session = Session()
        all_wines: Dict[str, Wine] = {}
        for category in category_list:
            wines: Dict[str, Wine] = {}
            self.log.info(
                f"Starting crawling lang {lang} category {category} max page {max_page}"
            )
            crawler = CategoryCrawler(category, lang, max_page)
            for w in crawler:
                if w.is_interesting():
                    old_wine = wines.get(w.key, w)
                    # Keep the one that is less expensive
                    w.url = w.url if w.price < old_wine.price else old_wine.url
                    w.price = min(old_wine.price, w.price)
                    wines[w.key] = w
                self.log.debug(f"parsed wine: {w} (total number {len(wines)})")
            for w in wines.values():
                try:
                    session.add(w)
                    session.flush()
                except (IntegrityError, FlushError):
                    self.log.error(f"Integrity error for wine {w}")
                    session.rollback()
                    existing = (
                        session.query(Wine)
                        .filter_by(
                            name=w.name,
                            date=w.date,
                            lang=w.lang,
                            producer=w.producer,
                            bottle_size=w.bottle_size,
                        )
                        .one()
                    )
                    self.log.info(f"Existing wine: {existing}")

            session.commit()
            self.log.info(
                f"Lang: {lang} Category: {category} stored {len(wines)} wines"
            )
            all_wines.update(wines)
        return all_wines
