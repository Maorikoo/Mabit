from concurrent.futures import ThreadPoolExecutor, as_completed
from django.core.management.base import BaseCommand
from instagram_scraper.scraper.instagram import scrape_instagram
from instagram_scraper.scraper.client import wait_for_pause_to_end, get_pause_remaining_seconds


class Command(BaseCommand):
    help = "Scrape Instagram profiles/stories for a list of usernames."

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, required=True, help="Path to a txt file with usernames (one per line).")
        parser.add_argument("--workers", type=int, default=6, help="Number of threads (default: 6).")
        parser.add_argument(
            "--blocked-retries",
            type=int,
            default=2,
            help="How many times to retry a username if temporarily blocked (default: 2).",
        )

    def handle(self, *args, **options):
        path = options["file"]
        workers = options["workers"]
        blocked_retries = options["blocked_retries"]

        with open(path, "r", encoding="utf-8") as f:
            usernames = [line.strip() for line in f if line.strip()]

        total_users = len(usernames)
        self.stdout.write(f"Loaded {total_users} usernames. Workers={workers}")

        results = {"ok": 0, "skipped": 0, "failed": 0}
        done_users = 0  # ✅ counts only final outcomes (OK/SKIP/FAIL)

        # retry budget per user
        retries_left = {u: blocked_retries for u in usernames}

        # attempt count per user (for logging)
        attempts = {u: 0 for u in usernames}

        # pending usernames queue
        pending = list(usernames)

        with ThreadPoolExecutor(max_workers=workers) as ex:
            while pending:
                # Respect any active pause before submitting more work
                remaining = get_pause_remaining_seconds()
                if remaining > 0:
                    self.stdout.write(self.style.WARNING(f"[PAUSE] Waiting {remaining}s before retrying..."))
                    wait_for_pause_to_end()

                # Submit up to `workers` jobs at a time
                batch = []
                while pending and len(batch) < workers:
                    u = pending.pop(0)
                    attempts[u] += 1
                    batch.append(u)

                future_map = {ex.submit(scrape_instagram, u): u for u in batch}

                for fut in as_completed(future_map):
                    u = future_map[fut]

                    try:
                        res = fut.result()
                        if not isinstance(res, dict):
                            results["failed"] += 1
                            done_users += 1
                            self.stdout.write(self.style.ERROR(
                                f"[{done_users}/{total_users}] [FAIL] {u}: bad result type"
                            ))
                            continue

                        profile = res.get("profile", "unknown")
                        sf = int(res.get("stories_found", 0) or 0)
                        ss = int(res.get("stories_saved", 0) or 0)

                        # ✅ BLOCKED -> retry without incrementing done_users
                        if profile == "blocked":
                            if retries_left.get(u, 0) > 0:
                                retries_left[u] -= 1
                                pause_s = res.get("pause_seconds", "?")
                                total_attempts_allowed = blocked_retries + 1
                                self.stdout.write(self.style.WARNING(
                                    f"[{done_users}/{total_users}] [BLOCKED] {u} "
                                    f"(attempt {attempts[u]}/{total_attempts_allowed}) -> pausing {pause_s}s, "
                                    f"will retry (left={retries_left[u]})"
                                ))
                                pending.append(u)
                                wait_for_pause_to_end()
                            else:
                                results["skipped"] += 1
                                done_users += 1
                                self.stdout.write(self.style.WARNING(
                                    f"[{done_users}/{total_users}] [SKIP] {u} blocked (no retries left)"
                                ))
                            continue

                        # ✅ FINAL OUTCOMES (increment done_users once per username)
                        if profile == "public":
                            results["ok"] += 1
                            done_users += 1
                            if sf == 0:
                                self.stdout.write(self.style.SUCCESS(
                                    f"[{done_users}/{total_users}] [OK] {u} public, no stories "
                                    f"(attempt {attempts[u]}/{blocked_retries + 1})"
                                ))
                            else:
                                self.stdout.write(self.style.SUCCESS(
                                    f"[{done_users}/{total_users}] [OK] {u} public, stories found={sf}, saved={ss} "
                                    f"(attempt {attempts[u]}/{blocked_retries + 1})"
                                ))

                        elif profile == "not_found":
                            results["skipped"] += 1
                            done_users += 1
                            self.stdout.write(self.style.WARNING(
                                f"[{done_users}/{total_users}] [SKIP] {u} not found "
                                f"(attempt {attempts[u]}/{blocked_retries + 1})"
                            ))

                        else:
                            results["skipped"] += 1
                            done_users += 1
                            self.stdout.write(self.style.WARNING(
                                f"[{done_users}/{total_users}] [SKIP] {u} is {profile} (skipping stories) "
                                f"(attempt {attempts[u]}/{blocked_retries + 1})"
                            ))

                    except Exception as e:
                        results["failed"] += 1
                        done_users += 1
                        self.stdout.write(self.style.ERROR(
                            f"[{done_users}/{total_users}] [FAIL] {u}: {e} "
                            f"(attempt {attempts[u]}/{blocked_retries + 1})"
                        ))

        self.stdout.write(f"Done. OK={results['ok']} SKIP={results['skipped']} FAIL={results['failed']}")
