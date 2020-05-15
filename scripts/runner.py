"""
Run a single instance of tannico.
"""
import argparse
import logging
import json
import os
import datetime as dt

from tannico.ingester import Ingester
from tannico.comparator import Comparator


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ita", help="The list of italian pages", default="ita.json")
    parser.add_argument("--eng", help="The list of english pages", default="eng.json")
    parser.add_argument(
        "--rate", help="EUR to GBP change rate", type=float, default=0.86
    )
    parser.add_argument(
        "--max-page", help="Maximum number of pages to visit", type=int, default=0
    )
    parser.add_argument(
        "--max-diff",
        help="Maximum price difference (as ENG-ITA)",
        type=float,
        default=0,
    )
    parser.add_argument(
        "-d",
        "--debug",
        help="Print lots of debugging statements",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
        default=logging.WARNING,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Be verbose",
        action="store_const",
        dest="loglevel",
        const=logging.INFO,
    )
    parser.add_argument(
        "--out", help="CSV Output file", default=f"output_{dt.date.today()}.csv"
    )
    parser.add_argument(
        "--no-ingest",
        help="Prevent ingestion and run comparison only",
        action="store_true",
        default=False,
    )
    return parser


def main():
    parser = get_args()
    args = parser.parse_args()
    os.environ["EUR_TO_GBP"] = str(args.rate)
    logging.basicConfig(level=args.loglevel)
    if not args.no_ingest:
        ingester = Ingester()
        for lang in {"ita", "eng"}:
            conf = json.load(open(getattr(args, lang)))
            categories = conf["categories"]
            ingester.crawl(lang, categories, args.max_page)
    comparator = Comparator(args.out, max_diff=args.max_diff)
    comparator.compare()


if __name__ == "__main__":
    main()
