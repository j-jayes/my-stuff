"""Look a product up in IKEA's own search, rather than asking a model to remember its URL.

Worth a module of its own because IKEA is most of what is in this inventory, and because a
guessed IKEA URL fails in the worst possible way: the slug is right, the article number is
invented, and the site answers a redirect to its catalogue with a 200. The guess looks like a
success. Their search returns the real article number, and it accepts an article number as a
query too, which is exact when the owner has one off a receipt.

This is the unauthenticated endpoint ikea.com's own search box calls. We identify ourselves
honestly and ask for one product at a time.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass

import httpx

from app.scrape import colour_conflict

logger = logging.getLogger(__name__)

# se/en rather than se/sv: the same Swedish catalogue, prices and article numbers, but the
# product slugs come back in English, which is the language the owner's notes are in.
SEARCH_URL = "https://sik.search.blue.cdtapps.com/{locale}/search?c=sr&v=20250507"
# Their search finds nothing for a sentence. Eight words is enough for a name, a product type
# and a colour, which is what actually identifies an IKEA product.
QUERY_WORD_LIMIT = 8
# The number printed on an IKEA receipt and label: 203.427.24, and 20342724 in their URLs.
ARTICLE_NUMBER = re.compile(r"\b(\d{3}\.\d{3}\.\d{2}|\d{8})\b")
USER_AGENT = "my-stuff-inventory/0.1 (personal home inventory; +https://github.com/)"

# Enough to catch a wrong variant. Not a colour vocabulary — just the words IKEA puts in a
# slug, including the materials that stand in for a colour.
COLOURS = frozenset(
    {
        "white",
        "black",
        "grey",
        "gray",
        "red",
        "blue",
        "green",
        "yellow",
        "beige",
        "brown",
        "pink",
        "purple",
        "orange",
        "turquoise",
        "silver",
        "gold",
        "natural",
        "oak",
        "birch",
        "pine",
        "walnut",
        "bamboo",
        "anthracite",
    }
)


@dataclass(frozen=True)
class IkeaProduct:
    name: str
    item_no: str
    url: str
    image_url: str | None


def _words(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(c for c in folded if not unicodedata.combining(c)).casefold()
    return set(re.findall(r"[a-z0-9]+", folded))


def query_for(note: str) -> str:
    """A note trimmed to something a search box can use.

    Their search returns nothing at all for a sentence: "Ikea TERTIAL work lamp White metal
    work lamp fitted with a smart bulb." finds no product, while the first eight words of it
    find the right one. Cut at the first sentence end as well, since the second sentence is
    usually a description rather than a name.
    """
    article = ARTICLE_NUMBER.search(note)
    if article:
        # Exact, and it settles the variant. Searching "KLEPPSTAD bed frame white" returns a
        # KLEPPSTAD in the wrong size; 104.926.72 returns the one that was actually bought.
        return article.group(0)
    first = re.split(r"[.;\n]", note, maxsplit=1)[0]
    return " ".join(first.split()[:QUERY_WORD_LIMIT])


def matches(query: str, product: IkeaProduct) -> bool:
    """Is what came back actually the thing that was asked for?

    Their search always answers with its closest guess rather than nothing, and two of its
    guesses are dangerous. Asked for a white FORSÅ lamp it has returned the black one, and
    for a red VIHALS chair the yellow one — a photograph in the wrong colour is worse than no
    photograph, because it looks right. Asked for a FORSÅ lamp it has also returned a DVALA
    fitted sheet, which shares the word "white" with the query and nothing else that matters.

    So two things have to hold: the product's own name has to appear in the query, and any
    colour the query asked for must not be flatly contradicted by the one in the slug.
    """
    article = ARTICLE_NUMBER.fullmatch(query.strip())
    if article:
        # Asked by number, so the number is the whole of the answer: the product name will
        # not appear in the query and there is nothing else to check.
        return product.item_no == article.group(0).replace(".", "")

    name = product.name.split()[0] if product.name else ""
    if not name or _words(name) - _words(query):
        return False

    return not colour_conflict(query, product.url)


async def search(query: str, timeout: float, locale: str = "se/en", transport=None):
    """The first product IKEA's search returns for a query, or None.

    Never raises: an item without a photograph is a perfectly good outcome, and IKEA being
    slow or unavailable must not fail the suggestion it is part of.
    """
    payload = {
        "searchParameters": {"input": query, "type": "QUERY"},
        "isUserLoggedIn": False,
        "components": [
            {
                "component": "PRIMARY_AREA",
                "columns": 4,
                "types": {"main": "PRODUCT", "breakouts": []},
                "window": {"offset": 0, "size": 3},
            }
        ],
    }
    try:
        async with httpx.AsyncClient(
            timeout=timeout, headers={"User-Agent": USER_AGENT}, transport=transport
        ) as client:
            response = await client.post(SEARCH_URL.format(locale=locale), json=payload)
            response.raise_for_status()
            body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.info("IKEA search for %r failed: %s", query[:60], exc)
        return None

    for result in body.get("results") or []:
        for item in result.get("items") or []:
            product = item.get("product") or {}
            if not product.get("pipUrl"):
                continue
            name = " ".join(filter(None, [product.get("name"), product.get("typeName")]))
            return IkeaProduct(
                name=name.strip(),
                item_no=str(product.get("itemNo") or ""),
                url=product["pipUrl"],
                image_url=product.get("mainImageUrl") or None,
            )
    return None
