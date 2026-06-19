class ScoringService:

    def score_job(self, job: dict, preferences: dict) -> float:

        score = 0.0

        title = job.get("data", {}).get("title", "").lower()
        location = job.get("data", {}).get("location", "").lower()

        keywords = [k.lower() for k in preferences.get("keywords", [])]
        preferred_location = preferences.get("location", "").lower()
        remote = preferences.get("remote", False)

        # keyword match
        for keyword in keywords:
            if keyword in title:
                score += 0.6

        # location match
        if preferred_location and preferred_location in location:
            score += 0.3

        # remote boost
        if remote and "remote" in location:
            score += 0.1

        # role boost
        if any(word in title for word in ["engineer", "developer", "backend", "frontend"]):
            score += 0.05

        return min(round(score, 2), 1.0)
