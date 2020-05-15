"""
Compare wines and rank the most convenient ones.
"""
import csv
from tannico.models import Session
from tannico.models.wine import Wine
from typing import Optional, Dict
import logging
import datetime as dt


class Comparator:
    def __init__(
        self,
        outfile: str,
        max_diff: float = 0,
        base_lang: str = "eng",
        compare_lang: str = "ita",
        today: Optional[dt.date] = None,
    ):
        self._outfile = outfile
        self._today = today or dt.date.today()
        self._max_diff = max_diff
        self._preferred_lang = base_lang
        self._compare_lang = compare_lang
        self._session = None
        self.log = logging.getLogger(__name__)

    def _get_dict_wines(self, lang) -> Dict[str, Wine]:
        return {
            w.key: w
            for w in self._session.query(Wine)  # type: ignore
            .filter_by(date=self._today, lang=lang)
            .all()
        }

    def compare(self):
        """Compare wines according to their prices."""
        self._session = Session()
        preferred_lang_wines: Dict[str, Wine] = self._get_dict_wines(
            self._preferred_lang
        )
        self.log.info(f"Preferred lang wines size: {len(preferred_lang_wines)}")
        other_lang_wines: Dict[str, Wine] = self._get_dict_wines(self._compare_lang)
        self.log.info(f"Other lang wines size: {len(other_lang_wines)}")

        # Remove wines that are NOT in common
        for unique in other_lang_wines.keys() ^ preferred_lang_wines.keys():
            other_lang_wines.pop(unique, None)
            preferred_lang_wines.pop(unique, None)
        self.log.info(f"There are {len(preferred_lang_wines)} wines in common")
        to_buy_wines: Dict[str, Wine] = {
            w: preferred_lang_wines[w]
            for w in preferred_lang_wines
            if preferred_lang_wines[w].price - other_lang_wines[w].price
            <= self._max_diff
        }
        with open(self._outfile, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    "name",
                    "producer",
                    "bottle_size",
                    f"price_{self._compare_lang}",
                    f"price_{self._preferred_lang}",
                    "diff",
                    "awards",
                    f"url_{self._compare_lang}",
                    f"url_{self._preferred_lang}",
                ]
            )
            for key in to_buy_wines:
                wine = preferred_lang_wines[key]
                awards = (
                    preferred_lang_wines[key].awards or other_lang_wines[key].awards
                )
                diff = round(
                    preferred_lang_wines[key].price - other_lang_wines[key].price, 2
                )
                self.log.warning(
                    f"Wine: {wine.name} - {wine.producer} - {wine.bottle_size}: "
                    f"price in {self._compare_lang}: {other_lang_wines[key].price} "
                    f"price in {self._preferred_lang}: {preferred_lang_wines[key].price} "
                    f"diff: {diff} "
                    f"awards: {awards} "
                    f"{self._compare_lang}: url: {other_lang_wines[key].url} "
                    f"{self._preferred_lang}: url: {preferred_lang_wines[key].url} "
                )
                writer.writerow(
                    [
                        wine.name,
                        wine.producer,
                        wine.bottle_size,
                        other_lang_wines[key].price,
                        preferred_lang_wines[key].price,
                        diff,
                        awards,
                        other_lang_wines[key].url,
                        preferred_lang_wines[key].url,
                    ]
                )
