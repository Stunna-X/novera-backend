import requests
from datetime import datetime


class ScraperService:
    def fetch_jobs(self):
        """
        Simulated job scraper (replace later with real sources like LinkedIn, Indeed, etc.)
        """
        raw_jobs = [
            {
                "title": "Backend Engineer",
                "company": "TechCorp",
                "location": "Remote",
                "url": "https://example.com/job/1",
            },
            {
                "title": "Frontend Developer React",
                "company": "StartupX",
                "location": "London",
                "url": "https://example.com/job/2",
            },
        ]

        return [self._normalize(job) for job in raw_jobs]

    def _normalize(self, job: dict):
        return {
            "title": job["title"].strip(),
            "company": job["company"].strip(),
            "location": job["location"].strip(),
            "url": job["url"],
            "created_at": datetime.utcnow()
        }
