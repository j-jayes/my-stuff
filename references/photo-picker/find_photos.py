"""Three candidate photos for each item with none. Run from home-inventory with uv run."""
import asyncio, base64, io, json, re, sqlite3, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, ".")

import httpx
from PIL import Image

from app.config import get_settings
from app.extract import find_product_pages
from app.scrape import extract_metadata

HERE = Path(__file__).parent
DB = HERE / "live-now7.sqlite"
OUT = HERE / "photo-options.json"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"}
SKIP = ("Purchase at At Graphiken", "Rapha item")
STOP = {"with", "and", "for", "the", "from", "book", "set", "pack", "piece", "new", "black", "white", "grey", "gray", "blue", "green", "red"}
BAD_IMG = re.compile(r"logo|placeholder|sprite|banner|favicon|icon", re.I)

settings = get_settings()


def words(text):
    return {w for w in re.findall(r"[a-zåäö0-9]{3,}", text.lower())} - STOP


def products():
    db = sqlite3.connect(DB)
    rows = db.execute(
        "select i.id, i.brand, i.name, c.name, i.gifted_at is not null from items i "
        "left join categories c on c.id=i.category_id where i.image_key is null"
    ).fetchall()
    grouped = {}
    for id_, brand, name, category, gifted in rows:
        if name.startswith(SKIP):
            continue
        key = ((brand or "").lower(), name.lower())
        p = grouped.setdefault(key, dict(ids=[], brand=brand, name=name, category=category, gifted=bool(gifted)))
        p["ids"].append(id_)
        p["gifted"] = p["gifted"] and bool(gifted)
    return list(grouped.values())


def note_for(p):
    name = re.sub(r"\(book\)", "book", p["name"])
    name = re.sub(r"\(.*?\)", "", name).strip()
    return " ".join(filter(None, [p["brand"], name]))


def matches(p, title):
    if not title:
        return False
    got = words(title)
    mine = words(p["name"])
    brand = words(p["brand"] or "")
    shared = len(mine & got)
    if brand and not (brand & got):
        return shared >= max(2, round(len(mine) * 0.6))
    return shared >= max(1, round(len(mine) * 0.4))


async def fetch_page(client, url):
    try:
        response = await client.get(url)
        response.raise_for_status()
        if "html" not in response.headers.get("content-type", ""):
            return None
        page = extract_metadata(response.text[:2_000_000], str(response.url))
        page.url = str(response.url)
        return page
    except Exception:
        return None


async def thumb(client, url):
    if BAD_IMG.search(url):
        return None
    try:
        response = await client.get(url)
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content))
        image.load()
    except Exception:
        return None
    width, height = image.size
    if min(width, height) < 180 or max(width, height) / min(width, height) > 2.4:
        return None
    image = image.convert("RGBA")
    ground = Image.new("RGB", image.size, "white")
    ground.paste(image, mask=image.split()[3])
    ground.thumbnail((260, 260))
    buffer = io.BytesIO()
    ground.save(buffer, "JPEG", quality=66)
    return base64.b64encode(buffer.getvalue()).decode()


async def options_from(p, urls, have):
    async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=UA) as client:
        pages = [x for x in await asyncio.gather(*(fetch_page(client, u) for u in urls)) if x]
        # A page that declares itself one product is a better source than a listing.
        pages.sort(key=lambda page: not page.is_product)
        for page in pages:
            if len(have) >= 3 or not matches(p, page.title):
                continue
            for image_url in page.image_urls[:3]:
                if image_url in {o["image_url"] for o in have}:
                    continue
                data = await thumb(client, image_url)
                if data:
                    host = re.sub(r"^www\.", "", httpx.URL(page.url).host)
                    have.append(dict(image_url=image_url, page=page.url, host=host, title=(page.title or "")[:90], thumb=data))
                    break


def search(p):
    note = note_for(p)
    have = []
    for query in (note, f"{note} product photo official"):
        urls = find_product_pages(query, settings, limit=8)
        asyncio.run(options_from(p, urls, have))
        if len(have) >= 3:
            break
    p["query"] = note
    p["options"] = have[:3]
    print(len(have[:3]), note[:60], flush=True)
    return p


def main():
    items = products()
    print(len(items), "products", flush=True)
    with ThreadPoolExecutor(6) as pool:
        done = list(pool.map(search, items))
    OUT.write_text(json.dumps(done, ensure_ascii=False))
    counts = [len(p["options"]) for p in done]
    print("done", {n: counts.count(n) for n in range(4)})


main()
