import time
from app.services.scraper_service import ScraperService
from app.services.job_service import JobService


class JobWorker:

    def __init__(self, db, users):
        self.db = db
        self.users = users

        self.scraper = ScraperService()
        self.job_service = JobService(db)

    def run(self):
        """
        Infinite worker loop
        """

        print("🚀 Job Worker Started...")

        while True:

            try:
                # 1. Scrape jobs
                jobs = self.scraper.fetch_jobs()

                # 2. Process + score jobs
                processed_jobs = self.job_service.process_jobs(
                    jobs,
                    [u["preferences"] for u in self.users]
                )

                # 3. Send alerts
                self.job_service.trigger_alerts(
                    processed_jobs,
                    self.users
                )

                # 4. Save jobs
                self.job_service.save_jobs(processed_jobs)

                print(f"✅ Cycle complete: {len(processed_jobs)} jobs processed")

            except Exception as e:
                print(f"❌ Worker error: {e}")

            # wait before next cycle
            time.sleep(60)
