from pathlib import Path
import json
import pandas as pd
from loguru import logger

from scraper.browser import start_browser
from scraper.crawler import crawl

PAGES_TO_SCRAPE = 3

CSV_FILE = Path("data/jobs.csv")
JSON_FILE = Path("data/jobs.json")


def export_jobs(jobs):
    CSV_FILE.parent.mkdir(exist_ok=True)

    df = pd.DataFrame(jobs)
    df.to_csv(CSV_FILE, index=False)

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)

    logger.success(f"Saved CSV → {CSV_FILE}")
    logger.success(f"Saved JSON → {JSON_FILE}")


def run():
    logger.info("🚀 Scraper starting...")

    playwright = None
    browser = None
    jobs = []

    try:
        playwright, browser, page = start_browser(headless=False)

        jobs = crawl(
            page=page,
            pages=PAGES_TO_SCRAPE,
        ) or []

        export_jobs(jobs)

        logger.success(f"Finished scraping {len(jobs)} jobs")
        return jobs

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return []

    finally:
        # 🔥 guaranteed cleanup (this is the real fix)
        try:
            if browser:
                browser.close()
        except Exception as e:
            logger.warning(f"Browser close failed: {e}")

        try:
            if playwright:
                playwright.stop()
        except Exception as e:
            logger.warning(f"Playwright stop failed: {e}")
