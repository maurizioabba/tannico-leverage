"""The model in use in the DB."""
import logging
import re
import os
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
import datetime as dt
from typing import List
from typing import Tuple

from tannico.models import engine

Base = declarative_base()

log = logging.getLogger(__name__)


class _ParseHelper:
    EUR_TO_GBP = None

    @staticmethod
    def parse_price(price: str) -> float:
        """Normalize price according to the currency."""
        if _ParseHelper.EUR_TO_GBP is None:
            _ParseHelper.EUR_TO_GBP = float(os.environ["EUR_TO_GBP"])

        price = price.strip()

        if price.startswith("£"):
            # GBP prices are "£X,YYY.XX"
            price = price[1:].replace(",", "")
            return round(float(price), 2)
        else:
            # EUR prices are "X.YYY,XX €"
            price = price[:-2].replace(".", "").replace(",", ".")
            return round(float(price) * _ParseHelper.EUR_TO_GBP, 2)

    SIZES = {r"(0.375l)": 0.375, r"[mM]agnum": 1.5, r"[Jj][ée]roboam": 3}

    @staticmethod
    def parse_bottle_size(name: str) -> Tuple[str, float]:
        """If the bottle size is in the name, strip it from the name."""
        bottle_size = 0.75
        r = re.search(r"\((\d+) bottiglie\)", name)
        if r:
            bottle_size = 0.75 * int(r.group(1))
        else:
            for size in _ParseHelper.SIZES:
                r = re.search(size, name)
                if r:
                    bottle_size = _ParseHelper.SIZES[size]
                    break
        if r:
            start, stop = r.span()
            name = name[:start] + name[stop:]
        return name.strip(), bottle_size

    UNICODE_TRANSLATE_TABLE = dict(
        [(ord(x), ord(y)) for x, y in zip("‘’´“”–-", "'''\"\"--")]
    )

    @staticmethod
    def normalize(item: str):
        """Normalize quotes and dashes to ASCII counterparts and lowercase."""
        return item.translate(_ParseHelper.UNICODE_TRANSLATE_TABLE).lower()


class Wine(Base):  # type: ignore
    """
    A single wine.

    The price is expressed in GBP.
    """

    __tablename__ = "wine"

    name = sa.Column(sa.String, primary_key=True)
    date = sa.Column(sa.Date, primary_key=True)
    lang = sa.Column(sa.String, primary_key=True)
    producer = sa.Column(sa.String, primary_key=True)
    bottle_size = sa.Column(sa.Float, primary_key=True)
    price = sa.Column(sa.Float, nullable=False)
    url = sa.Column(sa.String, nullable=False)
    awards = sa.Column(sa.Boolean)

    def __repr__(self):
        return (
            "Wine: "
            f"name: {self.name}, "
            f"producer: {self.producer}, "
            f"size: {self.bottle_size}, "
            f"price: {self.price}, "
            f"awards: {self.awards}, "
            f"url: {self.url}"
        )

    def is_interesting(self):
        """A wine is interesting if its bottle size is 0.75."""
        # TODO
        return True

    @property
    def key(self):
        """The key is determined by name, producer, bottle_size."""
        return f"{self.name}_{self.producer}_{self.bottle_size}"

    @classmethod
    def parse(
        cls,
        name: str,
        price: str,
        producer: str,
        awards: List[str],
        url: str,
        today: dt.date,
        lang: str,
    ):
        """Parse a wine raw components and return a Wine."""
        log.debug(
            "Parsing from: "
            f"name: {name}, "
            f"producer: {producer}, "
            f"price: {price}, "
            f"awards: {awards}, "
            f"url: {url}"
        )
        name = _ParseHelper.normalize(name.strip().rstrip("."))
        name, bottle_size = _ParseHelper.parse_bottle_size(name)
        producer = _ParseHelper.normalize(producer.strip())
        r = re.search(rf"[-,] {producer}", name)
        if r:
            name = name[: r.span()[0]].strip()
        price = _ParseHelper.parse_price(price)
        awards = awards != []

        return cls(
            name=name,
            price=price,
            date=today,
            lang=lang,
            producer=producer,
            awards=awards,
            bottle_size=bottle_size,
            url=url,
        )


Base.metadata.create_all(engine)
