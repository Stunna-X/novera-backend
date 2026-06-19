from scraper.extractor import extract_job
from utils.logger import get_logger

logger = get_logger()


def crawl(page, config, pages=1):
    results = []

    base_url = config["base_url"]
    selector = config["list_selector"]
    pagination = config["pagination_param"]

    for i in range(pages):
        url = f"{base_url}{pagination}{i+1}"
        logger.info(f"🌐 Crawling: {url}")

        page.goto(url)
        page.wait_for_timeout(2000)

        jobs = page.query_selector_all(selector)

        logger.info(f"Found {len(jobs)} jobs")

        for job in jobs:
            data = extract_job(job, config, page.url)
            if data:
                results.append(data)

    return results
