from urllib.parse import urljoin
from utils.logger import get_logger

logger = get_logger()


def extract_job(job, config, page_url):
    try:
        fields = config["fields"]

        def safe_text(selector):
            el = job.query_selector(selector)
            return el.inner_text().strip() if el else None

        def safe_attr(selector, attr):
            el = job.query_selector(selector)
            return el.get_attribute(attr) if el else None

        title = safe_text(fields["title"])
        company = safe_text(fields["company"])
        location = safe_text(fields["location"])

        link = safe_attr(fields["link"], "href")
        image = safe_attr(fields["image"], "src")

        return {
            "title": title or "N/A",
            "company": company or "N/A",
            "location": location or "N/A",
            "link": urljoin(page_url, link) if link else None,
            "image": urljoin(page_url, image) if image else None,
        }

    except Exception as e:
        logger.error(f"Extractor failed: {e}")
        return None
