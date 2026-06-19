from pathlib import Path

BASE_URL = "https://realpython.github.io/fake-jobs/"
PAGES_TO_SCRAPE = 2

OUTPUT_DIR = Path("data/output")
OUTPUT_FILE = OUTPUT_DIR / "data.csv"


SITE_CONFIG = {
    "fake_jobs": {
        "base_url": "https://realpython.github.io/fake-jobs/",
        "list_selector": ".card-content",
        "fields": {
            "title": "h2",
            "company": ".company",
            "location": ".location",
            "link": "h2 a",
            "image": "img"
        },
        "pagination_param": "?page="
    }
}
