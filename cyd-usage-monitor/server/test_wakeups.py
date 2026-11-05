import datetime as dt
import json
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

try:
    from .wakeups import WakeupAdapter, WakeupError, WakeupStore, MIN_INTERVAL, next_occurrence
except ImportError:
    from wakeups import WakeupAdapter, WakeupError, WakeupStore, MIN_INTERVAL, next_occurrence


class WakeupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = dt.datetime(2026, 11, 4, 12, tzinfo=dt.timezone.utc).timestamp()
        self.store = WakeupStore(self.temp.name, lambda: self.now, lambda: self.now)
        self.profiles = [{"id": "codex-0123456789", "provider": "codex", "label": "Personal"}]
        self.sent = []
        self.reading = {"account_identity": "account@example.invalid", "identity_verified": True,
                        "quota_valid": True, "weekly_remaining_pct": 50, "window_state": "idle", "window_reset_at": None}
        self.adapter = WakeupAdapter("luna", "low", self.send, self.preflight, True, catalogue=[{"id":"luna","label":"Luna","reasoning_levels":["low","medium"]}])
        self.adapters = {"codex": self.adapter}
        self.store.set_capabilities(self.adapters)
        self.store.set_enabled(True)

    def save_schedule(self, payload):
        self.store.set_capabilities(self.adapters)
        return self.store.save_schedule(dict(payload, provider_settings=payload.get("provider_settings", {"codex":{"model":"luna","reasoning":"low"}})))

    def preflight(self, profile):
        return dict(self.reading, collected_at=self.now)

    def send(self, profile, prompt, attempt_id):
        self.sent.append((profile["id"], prompt, attempt_id))
        return {"state": "sent"}

    def queue(self, key="a" * 32, ids=None):
        self.store.set_capabilities(self.adapters)
        return self.store.enqueue_now(ids or [self.profiles[0]["id"]], key, {"codex":{"model":"luna","reasoning":"low"}})

    def run_job(self):
        return self.store.process_due(self.profiles, self.adapters)

    def test_custom_prompt_is_durable_and_idempotency_includes_exact_text(self):
        settings = {"codex": {"model": "luna", "reasoning": "low"}}
        prompt = 'Say "OK" once.\nDo not use tools; $literal `text`.'
        job = self.store.enqueue_now([self.profiles[0]["id"]], "custom" * 6, settings, prompt)
        self.assertTrue(self.store.enqueue_now([self.profiles[0]["id"]], "custom" * 6, settings, prompt)["duplicate"])
        with self.assertRaises(WakeupError):
            self.store.enqueue_now([self.profiles[0]["id"]], "custom" * 6, settings, "different")
        self.store = WakeupStore(self.temp.name, lambda: self.now, lambda: self.now)
        self.run_job()
        self.assertEqual(self.sent[0][1], prompt)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.store.status(self.profiles)["jobs"][0]["prompt"], prompt)

    def test_schedule_snapshots_custom_prompt_and_edit_cancels_old_job(self):
        schedule = self.save_schedule({"profile_ids": [self.profiles[0]["id"]], "kind": "weekly", "timezone": "UTC", "time": "12:01", "prompt": "Reply hello once."})
        self.now += 60
        self.run_job()
        self.assertEqual(self.sent[0][1], "Reply hello once.")
        self.assertEqual(self.store.status(self.profiles)["jobs"][0]["prompt"], "Reply hello once.")
        updated = self.save_schedule(dict(schedule, prompt="Reply goodbye."))
        self.assertEqual(updated["prompt"], "Reply goodbye.")

    def test_invalid_prompt_never_queues_or_launches(self):
        settings = {"codex": {"model": "luna", "reasoning": "low"}}
        for prompt in ["", " ", "x" * 501, "bad\x00text", "/usage", " --resume", None, 42]:
            with self.subTest(prompt=repr(prompt)), self.assertRaises(WakeupError):
                self.store.enqueue_now([self.profiles[0]["id"]], "invalid" * 4, settings, prompt)
        self.run_job()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.store.status(self.profiles)["jobs"], [])

    def test_preexisting_job_keeps_legacy_prompt_after_migration(self):
        self.queue()
        with self.store._db() as db:
            db.execute("ALTER TABLE jobs DROP COLUMN prompt")
        self.run_job()
        self.assertEqual(self.sent[0][1], "say okay")

    def test_master_preference_survives_separate_process_for_both_states(self):
        module_dir = str(Path(__file__).parent)
        script = "import sys,json;sys.path.insert(0,sys.argv[1]);from wakeups import WakeupStore;print(json.dumps(WakeupStore(sys.argv[2]).status([])['enabled']))"
        for enabled in (True, False):
            self.store.set_enabled(enabled)
            result = subprocess.run([sys.executable, "-c", script, module_dir, self.temp.name], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout), enabled)
            self.assertEqual(self.store.status(self.profiles)["enabled"], enabled)

    def test_multi_provider_manual_run_has_one_durable_summary(self):
        self.profiles.extend([{"id":"antigravity-abcdef0123","provider":"antigravity","label":"Google"}, {"id":"claude-abcdef0123","provider":"claude","label":"Claude"}])
        def send(profile, prompt, attempt):
            self.sent.append((profile["id"], prompt, attempt))
            return {"state":"failed", "reason":"The selected model is unavailable."} if profile["provider"] == "claude" else {"state":"sent"}
        self.adapters = {provider:WakeupAdapter("luna","low",send,self.preflight,True,catalogue=self.adapter.catalogue) for provider in ("codex","antigravity","claude")}
        self.store.set_capabilities(self.adapters)
        settings = {provider:{"model":"luna","reasoning":"low"} for provider in self.adapters}
        ids = [profile["id"] for profile in self.profiles]
        self.store.enqueue_now(ids, "multi" * 5, settings, "private prompt must not be in notification")
        self.run_job()
        self.assertEqual(len(self.sent), 3)
        self.assertTrue(self.store.status(self.profiles)["enabled"])
        # Claim in a new process object, concurrently: at most one delivery claim.
        stores = [WakeupStore(self.temp.name, lambda:self.now, lambda:self.now) for _ in range(3)]
        with ThreadPoolExecutor(max_workers=3) as pool:
            batches = list(pool.map(lambda store:store.claim_notifications(), stores))
        summaries = [item for batch in batches for item in batch]
        self.assertEqual(len(summaries), 1)
        summary = summaries[0]
        self.assertEqual(summary["kind"], "run_summary")
        self.assertEqual(summary["source"], "manual")
        self.assertEqual({item["provider"] for item in summary["results"]}, {"codex","antigravity","claude"})
        self.assertEqual(sorted(item["state"] for item in summary["results"]), ["failed","sent","sent"])
        self.assertNotIn("private prompt", json.dumps(summary))
        self.store.finish_notification(summary["notification_id"], True)
        self.assertEqual(WakeupStore(self.temp.name).claim_notifications(), [])

    def test_schedule_summary_retains_label_and_due_time_after_deletion(self):
        schedule = self.save_schedule({"label":"Morning start", "kind":"once", "run_at":self.now+10, "profile_ids":[self.profiles[0]["id"]]})
        self.now += 11
        self.run_job()
        self.store.delete_schedule(schedule["id"])
        summary = self.store.claim_notifications()[0]
        self.assertEqual(summary["source"], "schedule:" + schedule["id"])
        self.assertEqual(summary["run_context"]["schedule_label"], "Morning start")
        self.assertEqual(summary["run_context"]["scheduled_for"], schedule["run_at"])
        self.assertEqual(summary["results"][0]["state"], "sent")

    def test_expired_processing_is_summarized_without_resend_after_restart(self):
        first = self.queue()
        with self.store._db() as db:
            db.execute("UPDATE jobs SET state='processing' WHERE id=?", (first["job_id"],))
        attempt = self.store._reserve(self.profiles[0], self.adapter, self.preflight(self.profiles[0]), first["job_id"])
        self.now += 181
        restarted = WakeupStore(self.temp.name, lambda:self.now, lambda:self.now)
        restarted.process_due(self.profiles, self.adapters)
        summary = restarted.claim_notifications()[0]
        self.assertEqual(summary["results"][0]["state"], "unknown")
        self.assertEqual(summary["results"][0]["attempt_id"], attempt)
        self.assertEqual(self.sent, [])
        self.assertTrue(restarted.status(self.profiles)["enabled"])
        restarted.process_due(self.profiles, self.adapters)
        self.assertEqual(restarted.claim_notifications(), [])

    def test_expired_queue_and_stopped_master_get_one_skipped_summary(self):
        self.queue()
        self.store.set_enabled(False)
        self.now += 181
        self.run_job()
        summary = self.store.claim_notifications()[0]
        self.assertEqual(summary["results"][0]["state"], "skipped")
        self.assertEqual(self.sent, [])
        self.assertFalse(self.store.status(self.profiles)["enabled"])
        self.run_job()
        self.assertEqual(self.store.claim_notifications(), [])

    def test_post_send_quota_check_confirms_reset_without_another_prompt(self):
        def postflight(profile):
            return dict(self.preflight(profile), window_state="active", window_reset_at=self.now+18000, window_reset_timezone="America/New_York")
        self.adapters["codex"]=WakeupAdapter("luna","low",self.send,self.preflight,True,catalogue=self.adapter.catalogue,postflight=postflight)
        self.queue();self.run_job()
        result=self.store.claim_notifications()[0]["results"][0]
        self.assertEqual(len(self.sent),1)
        self.assertFalse(result["reset_estimated"])
        self.assertEqual(result["reset_at"],self.now+18000)

    def test_rounded_full_window_keeps_cli_reported_reset(self):
        self.reading["window_state"] = "unknown"
        def after(profile):
            return dict(self.preflight(profile), window_reset_text="20:11", window_reset_timezone="America/New_York")
        self.adapters["codex"] = WakeupAdapter("luna", "low", self.send, self.preflight, True, catalogue=self.adapter.catalogue, postflight=after)
        self.queue(); self.run_job()
        result = self.store.claim_notifications()[0]["results"][0]
        self.assertEqual((result["state"], result["reset_text"], result["reset_source"]), ("sent", "20:11", "reported"))
        self.assertEqual(len(self.sent), 1)

    def test_sends_are_published_while_reset_reads_overlap(self):
        self.profiles.append({"id": "codex-abcdef0123", "provider": "codex", "label": "Work"})
        entered = [threading.Event(), threading.Event()]
        release = threading.Event()
        def before(profile):
            return dict(self.preflight(profile), account_identity=profile["id"] + "@example.invalid")
        def after(profile):
            entered[self.profiles.index(next(p for p in self.profiles if p["id"] == profile["id"]))].set()
            if not release.wait(5): raise TimeoutError()
            return dict(before(profile), window_state="active", window_reset_at=self.now+18000)
        self.adapters["codex"] = WakeupAdapter("luna", "low", self.send, before, True, catalogue=self.adapter.catalogue, postflight=after)
        self.queue(ids=[p["id"] for p in self.profiles])
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.run_job)
            try:
                self.assertTrue(all(event.wait(4) for event in entered), "Reset checks must overlap without blocking the next prompt")
                status = self.store.status(self.profiles)
                self.assertEqual(status["jobs"][0]["state"], "processing")
                self.assertEqual(len(status["jobs"][0]["profile_ids"]), 2)
                self.assertEqual([r["state"] for r in status["jobs"][0]["results"]], ["sent", "sent"])
                self.assertTrue(all(r["reset_status"] == "checking" for r in status["jobs"][0]["results"]))
                self.assertFalse(any(a["paused"] for a in status["attempts"]))
                self.assertEqual(self.store.claim_notifications(), [])
            finally:
                release.set()
            future.result(timeout=5)
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(len(self.store.claim_notifications()), 1)

    def test_live_reservation_is_sending_not_an_interrupted_pause(self):
        def sending(profile, prompt, attempt_id):
            status = self.store.status(self.profiles)
            self.assertTrue(status["attempts"][0]["in_progress"])
            self.assertFalse(status["attempts"][0]["paused"])
            return self.send(profile, prompt, attempt_id)
        self.adapters["codex"] = WakeupAdapter("luna", "low", sending, self.preflight, True, catalogue=self.adapter.catalogue)
        self.queue(); self.run_job()
        self.assertEqual(len(self.sent), 1)

    def test_reset_verification_failure_or_wrong_account_keeps_labelled_estimate(self):
        for index in range(4):
            def postflight(profile):
                if index==0:raise OSError("private transcript")
                if index==2:return dict(self.preflight(profile),quota_valid=False,window_state="unknown",window_reset_text="20:11")
                if index==3:return dict(self.preflight(profile),collected_at=self.now-121,window_state="unknown",window_reset_text="20:11")
                return dict(self.preflight(profile),account_identity="wrong@example.invalid",window_state="active",window_reset_at=self.now+100)
            self.adapters["codex"]=WakeupAdapter("luna","low",self.send,self.preflight,True,catalogue=self.adapter.catalogue,postflight=postflight)
            self.queue(str(index)*32);self.run_job()
            result=self.store.claim_notifications()[0]["results"][0]
            self.assertEqual(result["state"],"sent")
            self.assertTrue(result["reset_estimated"])
            self.assertNotIn("private transcript",json.dumps(result))
            self.now+=MIN_INTERVAL
        self.assertEqual(len(self.sent),4)

    def test_defaults_persist_and_merge_without_altering_pending_work(self):
        settings={"codex":{"model":"luna","reasoning":"low"}}
        self.store.save_defaults(settings)
        self.queue()
        schedule=self.save_schedule({"kind":"weekly","time":"12:01","timezone":"UTC","profile_ids":[self.profiles[0]["id"]]})
        self.store.save_defaults({"codex":{"model":"luna","reasoning":"medium"}})
        restarted=WakeupStore(self.temp.name,lambda:self.now,lambda:self.now)
        state=restarted.status(self.profiles)
        self.assertEqual(state["defaults"]["codex"]["reasoning"],"medium")
        self.assertEqual(state["jobs"][0]["provider_settings"],settings)
        self.assertEqual(state["schedules"][0]["provider_settings"],settings)
        self.assertTrue(state["enabled"])
        self.assertEqual(state["attempts"],[])
        restarted.clear_default("codex")
        self.assertEqual(restarted.status(self.profiles)["defaults"],{})
        self.assertEqual(restarted.status(self.profiles)["schedules"][0]["id"],schedule["id"])

    def test_defaults_validate_current_catalogue_without_silent_substitution(self):
        for settings in ({},None,{"unknown":{"model":"luna","reasoning":"low"}},{"codex":{"model":"missing","reasoning":"low"}},{"codex":{"model":"luna","reasoning":"max"}}):
            with self.subTest(settings=settings),self.assertRaises(WakeupError):self.store.save_defaults(settings)
        self.store.save_defaults({"codex":{"model":"luna","reasoning":"low"}})
        self.adapters["codex"]=WakeupAdapter("other","low",self.send,self.preflight,True,catalogue=[])
        self.store.set_capabilities(self.adapters)
        self.assertEqual(self.store.status(self.profiles)["defaults"]["codex"]["model"],"luna")
        with self.assertRaises(WakeupError):self.store.save_defaults({"codex":{"model":"luna","reasoning":"low"}})
        self.assertEqual(self.sent,[])

    def test_provider_default_updates_merge_atomically_and_require_csrf_action(self):
        self.adapters["claude"]=WakeupAdapter("haiku","low",self.send,self.preflight,True,catalogue=[{"id":"haiku","reasoning_levels":["low"]}])
        self.store.set_capabilities(self.adapters)
        choices=[{"codex":{"model":"luna","reasoning":"low"}},{"claude":{"model":"haiku","reasoning":"low"}}]
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(self.store.save_defaults,choices))
        self.assertEqual(set(self.store.status(self.profiles)["defaults"]),{"codex","claude"})
        result=self.store.apply_action({"action":"clear_default","provider":"claude"},self.profiles)
        self.assertEqual(set(result["defaults"]),{"codex"})
        with self.assertRaises(WakeupError):self.store.clear_default("invalid")

    def test_send_now_submits_once_despite_active_unknown_or_exhausted_window(self):
        for index, state in enumerate(("active","unknown")):
            self.reading.update(window_state=state, window_reset_at=self.now+18000, weekly_remaining_pct=0)
            self.queue(str(index)*32);self.run_job()
            self.assertEqual(len(self.sent),index+1)
            result=self.store.status(self.profiles)["jobs"][0]["results"][0]
            self.assertEqual(result["state"],"sent")
            self.assertFalse(result.get("reset_estimated",False))
            self.assertIn("not assumed",result["reason"])
            self.queue("duplicate"+str(index)*24);self.run_job()
            self.assertEqual(len(self.sent),index+1)
            self.now+=MIN_INTERVAL

    def test_quoted_codex_reset_clock_does_not_block_explicit_send_now(self):
        try:
            from .wakeup_cli import normalize_snapshot
        except ImportError:
            from wakeup_cli import normalize_snapshot
        sample={"status":"ok","account_name":"example@example.invalid","collected_at":self.now,"metrics":{"five_hour":{"remaining_pct":100,"reset":"20:11"},"weekly":{"remaining_pct":99}}}
        self.reading=normalize_snapshot(self.profiles[0],sample,now=self.now)
        self.assertEqual(self.reading["window_state"],"unknown")
        self.queue();self.run_job()
        self.assertEqual(len(self.sent),1)
        self.assertEqual(self.store.status(self.profiles)["jobs"][0]["results"][0]["state"],"sent")

    def test_duplicate_click_and_distinct_jobs_send_once(self):
        first = self.queue()
        self.assertEqual(first["job_id"], self.queue()["job_id"])
        self.queue("b" * 32)
        self.run_job()
        self.run_job()
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0][1], "say OK")
        self.assertIn("safety interval", self.store.status(self.profiles)["jobs"][1]["results"][0]["reason"])

    def test_duplicate_profiles_share_account_guard(self):
        self.profiles.append(dict(self.profiles[0], id="codex-abcdef0123"))
        self.queue(ids=[p["id"] for p in self.profiles])
        self.run_job()
        self.assertEqual(len(self.sent), 1)

    def test_simultaneous_workers_and_jobs_send_once(self):
        self.queue()
        self.queue("b" * 32)
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda _: self.run_job(), range(3)))
        self.assertEqual(len(self.sent), 1)

    def test_unknown_and_restart_never_retry(self):
        def unknown(*args):
            self.sent.append(args)
            raise TimeoutError("private details must not escape")
        self.adapters["codex"] = WakeupAdapter("luna", "low", unknown, self.preflight, True, catalogue=self.adapter.catalogue)
        self.queue(); self.run_job()
        self.now += MIN_INTERVAL + 1
        self.store = WakeupStore(self.temp.name, lambda: self.now, lambda: self.now)
        self.queue("b" * 32); self.run_job()
        self.assertEqual(len(self.sent), 1)
        status = self.store.status(self.profiles)
        self.assertTrue(status["attempts"][0]["paused"])
        self.assertNotIn("private details", json.dumps(status))
        self.store.resume_account(status["attempts"][0]["account_ref"])
        self.adapters["codex"] = self.adapter
        self.queue("c" * 32); self.run_job()
        self.assertEqual(len(self.sent), 2)

    def test_crashed_reservation_survives_without_job_result(self):
        queued = self.queue()
        with self.store._db() as db:
            db.execute("UPDATE jobs SET state='processing' WHERE id=?", (queued["job_id"],))
        self.store._reserve(self.profiles[0], self.adapter, self.preflight(self.profiles[0]), queued["job_id"])
        self.now += MIN_INTERVAL + 1
        self.queue("b" * 32); self.run_job()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.store.status(self.profiles)["attempts"][0]["state"], "unknown")

    def test_schedule_eligibility_and_manual_identity_freshness_checks(self):
        cases = [{"weekly_remaining_pct": 0}, {"weekly_remaining_pct": None}, {"weekly_remaining_pct": float("nan")},
                 {"identity_verified": False}, {"quota_valid": False}, {"quota_collected_at": self.now - 121}]
        for index, values in enumerate(cases):
            baseline = self.reading.copy(); self.reading.update(values)
            if "window_reset_at" in values:self.reading["window_reset_at"]=self.now+3600
            schedule=self.save_schedule({"kind":"once","run_at":self.now+10,"profile_ids":[self.profiles[0]["id"]]})
            self.now+=11;self.run_job();self.reading=baseline
        self.adapters["codex"] = WakeupAdapter("luna", "low", self.send, lambda _: dict(self.reading, collected_at=self.now - 121), True, catalogue=self.adapter.catalogue)
        self.queue("z" * 32); self.run_job()
        self.adapters["codex"] = WakeupAdapter("luna", "low", self.send, self.preflight, False, catalogue=self.adapter.catalogue)
        self.queue("y" * 32); self.run_job()
        self.assertEqual(self.sent, [])

    def test_schedules_attempt_once_for_active_or_unknown_windows_without_assuming_restart(self):
        for state in ("active", "unknown"):
            self.reading.update(window_state=state, window_reset_at=self.now+18000,
                                window_reset_text="17:00", window_reset_timezone="UTC")
            schedule = self.save_schedule({"kind":"once", "run_at":self.now+10,
                                           "profile_ids":[self.profiles[0]["id"]]})
            self.now += 11
            self.run_job()
            result = self.store.status(self.profiles)["jobs"][0]["results"][0]
            self.assertEqual(result["state"], "sent")
            self.assertIn("not assumed", result["reason"])
            self.assertFalse(result.get("reset_estimated", False))
            self.assertEqual(result["eligibility"]["window_state"], state)
            self.assertEqual(result["eligibility"]["weekly_remaining_pct"], 50)
            self.assertNotIn("account_identity", result["eligibility"])
            count = len(self.sent)
            # Another schedule and an explicit send share the same attempt guard.
            self.save_schedule({"kind":"once", "run_at":self.now+10,
                                "profile_ids":[self.profiles[0]["id"]]})
            self.now += 11
            self.queue(("a" if state == "active" else "b") * 32)
            self.run_job(); self.run_job(); self.run_job()
            self.assertEqual(len(self.sent), count)
            self.now += MIN_INTERVAL
        self.assertEqual(len(self.sent), 2)

    def test_scheduled_weekly_skip_retains_exhausted_window_reset_without_an_extra_read(self):
        self.reading.update(weekly_remaining_pct=0, window_state="unknown",
                            window_reset_text="12:01", window_reset_timezone="America/New_York",
                            quota_windows=[{"window":"weekly", "remaining_pct":0,
                                            "reset_text":"Nov 9, 8:50am"}])
        postflight = mock.Mock(side_effect=AssertionError("Skip must reuse its existing fresh panel"))
        self.adapters["codex"] = WakeupAdapter("luna", "low", self.send, self.preflight, True,
                                               catalogue=self.adapter.catalogue, postflight=postflight)
        self.save_schedule({"kind":"once", "run_at":self.now+10, "profile_ids":[self.profiles[0]["id"]]})
        self.now += 11; self.run_job()
        result = self.store.status(self.profiles)["jobs"][0]["results"][0]
        self.assertEqual(result["reason"], "Weekly quota is exhausted.")
        self.assertEqual(result["state"], "skipped")
        self.assertEqual(result["quota_limits"][0]["reset_text"], "Nov 9, 8:50am")
        self.assertEqual(result["reset_source"], "reported")
        self.assertEqual(self.sent, [])
        postflight.assert_not_called()

    def test_morning_seven_account_mix_sends_five_and_skips_two_exhausted_accounts(self):
        self.profiles = [{"id":provider+"-"+format(index,"010x"), "provider":provider}
                         for index,provider in enumerate(("antigravity","claude","codex","codex","codex","codex","codex"))]
        exhausted = {self.profiles[1]["id"], self.profiles[2]["id"]}
        def reading(profile):
            weekly = 0 if profile["id"] in exhausted else 40
            return dict(self.preflight(profile), account_identity=profile["id"]+"@example.invalid",
                        weekly_remaining_pct=weekly, five_hour_remaining_pct=100,
                        window_state="idle" if profile["provider"] == "antigravity" else "unknown",
                        quota_windows=[{"window":"weekly","remaining_pct":weekly,"reset_text":"Nov 9, 8am"}])
        self.adapters = {provider:WakeupAdapter("luna","low",self.send,reading,True,catalogue=self.adapter.catalogue)
                         for provider in ("codex","claude","antigravity")}
        settings = {provider:{"model":"luna","reasoning":"low"} for provider in self.adapters}
        self.save_schedule({"kind":"once","run_at":self.now+10,"profile_ids":[p["id"] for p in self.profiles],
                            "provider_settings":settings})
        self.now += 11; self.run_job()
        summary = self.store.claim_notifications()[0]
        self.assertEqual([r["state"] for r in summary["results"]].count("sent"), 5)
        self.assertEqual([r["state"] for r in summary["results"]].count("skipped"), 2)
        for result in summary["results"]:
            if result["profile_id"] in exhausted:
                self.assertEqual(result["quota_limits"][0]["window"], "weekly")
            elif result["provider"] == "codex":
                self.assertFalse(result.get("reset_estimated", False))
        self.store = WakeupStore(self.temp.name, lambda:self.now, lambda:self.now)
        self.run_job()
        self.assertEqual(len(self.sent), 5)
        self.assertEqual(len(self.store.status(self.profiles)["attempts"]), 5)

    def test_master_stop_during_preflight_prevents_send(self):
        def preflight(profile):
            self.store.set_enabled(False)
            return self.preflight(profile)
        self.adapters["codex"] = WakeupAdapter("luna", "low", self.send, preflight, True, catalogue=self.adapter.catalogue)
        self.queue(); self.run_job()
        self.assertEqual(self.sent, [])

    def test_pause_and_delete_schedule_during_preflight_prevent_send(self):
        for remove in (False, True):
            schedule = self.save_schedule({"kind": "once", "run_at": self.now + 10, "profile_ids": [self.profiles[0]["id"]]})
            def preflight(profile):
                if remove:
                    self.store.delete_schedule(schedule["id"])
                else:
                    self.store.toggle_schedule(schedule["id"], False)
                return self.preflight(profile)
            self.adapters["codex"] = WakeupAdapter("luna", "low", self.send, preflight, True, catalogue=self.adapter.catalogue)
            self.now += 11
            self.run_job()
        self.assertEqual(self.sent, [])

    def test_ledger_missing_or_corrupt_fails_closed(self):
        self.store.path.write_bytes(b"not a database")
        with self.assertRaises(WakeupError): self.queue()
        self.store.path.unlink()
        with self.assertRaises(WakeupError): self.queue()

    def test_schedule_edit_during_preflight_invalidates_old_selection(self):
        schedule = self.save_schedule({"kind": "once", "run_at": self.now + 10, "profile_ids": [self.profiles[0]["id"]]})
        def editing(profile):
            self.save_schedule(dict(schedule, run_at=self.now + 3600))
            return self.preflight(profile)
        self.adapters["codex"] = WakeupAdapter("luna", "low", self.send, editing, True, catalogue=self.adapter.catalogue)
        self.now += 11
        self.run_job()
        self.assertEqual(self.sent, [])

    def test_minimum_interval_daily_limit_and_no_catchup(self):
        for index in range(5):
            self.queue(str(index) * 32); self.run_job()
            if index != 4: self.now += MIN_INTERVAL
        self.assertEqual(len(self.sent), 5)
        # Daily guard independently enforced, even with malformed future timestamps.
        with self.store._db() as db:
            db.execute("UPDATE attempts SET created=?", (self.now - MIN_INTERVAL,))
        self.queue("x" * 32); self.run_job()
        self.assertEqual(len(self.sent), 5)
        self.save_schedule({"kind": "once", "run_at": self.now + 10, "profile_ids": [self.profiles[0]["id"]]})
        self.now += 300
        self.run_job()
        self.assertEqual(len(self.sent), 5)

    def test_schedule_edit_after_first_account_stops_remaining_accounts(self):
        self.profiles.append(dict(self.profiles[0], id="codex-abcdef0123"))
        schedule = self.save_schedule({"kind": "once", "run_at": self.now + 10, "profile_ids": [p["id"] for p in self.profiles]})
        def preflight(profile):
            if self.sent:
                self.save_schedule(dict(schedule, run_at=self.now + 3600))
            return dict(self.preflight(profile), account_identity=profile["id"] + "@example.invalid")
        self.adapters["codex"] = WakeupAdapter("luna", "low", self.send, preflight, True, catalogue=self.adapter.catalogue)
        self.now += 11; self.run_job()
        self.assertEqual(len(self.sent), 1)

    def test_expiry_after_slow_preflight_does_not_send(self):
        def slow(profile):
            self.now += 181
            return self.preflight(profile)
        self.adapters["codex"] = WakeupAdapter("luna", "low", self.send, slow, True, catalogue=self.adapter.catalogue)
        self.queue(); self.run_job()
        self.assertEqual(self.sent, [])

    def test_clock_anomaly_stops_system(self):
        self.store.monotonic = lambda: 100
        self.store._last_monotonic = 100
        self.queue()
        self.now += 3600
        self.run_job()
        self.assertTrue(self.store.status(self.profiles)["enabled"])
        self.assertTrue(self.store.status(self.profiles)["clock_error"])
        restarted = WakeupStore(self.temp.name, lambda: self.now, lambda: self.now)
        restarted.process_due(self.profiles, self.adapters)
        self.assertTrue(restarted.status(self.profiles)["clock_error"])
        self.assertEqual(self.sent, [])
        restarted.set_enabled(False)
        restarted.set_enabled(True)
        self.assertIsNone(restarted.status(self.profiles)["clock_error"])

    def test_weekly_dst_skips_missing_hour_and_uses_first_repeated_hour(self):
        schedule = {"kind": "weekly", "timezone": "America/New_York", "time": "02:30", "weekdays": [6]}
        before = dt.datetime(2027, 3, 14, tzinfo=dt.timezone.utc).timestamp()
        after = dt.datetime.fromtimestamp(next_occurrence(schedule, before), dt.timezone.utc)
        self.assertEqual(after.date(), dt.date(2027, 3, 21))
        schedule["time"] = "01:30"
        before = dt.datetime(2026, 11, 1, tzinfo=dt.timezone.utc).timestamp()
        first = next_occurrence(schedule, before)
        self.assertEqual(dt.datetime.fromtimestamp(first, dt.timezone.utc).hour, 5)
        self.assertGreater(next_occurrence(schedule, first), first + 6 * 86400)

    def test_once_local_timezone_and_input_validation(self):
        result = self.save_schedule({"kind": "once", "local_datetime": "2026-11-04T08:00", "timezone": "America/New_York", "profile_ids": [self.profiles[0]["id"]]})
        self.assertEqual(result["run_at"], "2026-11-04T13:00:00Z")
        for payload in ({"kind": "weekly", "time": "25:00"}, {"kind": "weekly", "time": "08:00", "weekdays": []}, {"kind": "weekly", "time": "08:00", "timezone": "invalid"}):
            with self.assertRaises(WakeupError): self.save_schedule(dict(payload, profile_ids=[self.profiles[0]["id"]]))

    def test_explicit_model_choices_validate_and_snapshot_into_job_and_attempt(self):
        choices = {"codex": {"model": "luna", "reasoning": "medium"}}
        bound = WakeupAdapter("luna", "medium", self.send, self.preflight, True, catalogue=self.adapter.catalogue)
        self.adapters["codex"] = WakeupAdapter("luna", "low", self.send, self.preflight, True,
                                              catalogue=self.adapter.catalogue, select=lambda model, reasoning: bound)
        self.store.set_capabilities(self.adapters)
        self.store.enqueue_now([self.profiles[0]["id"]], "a" * 32, choices)
        choices["codex"]["reasoning"] = "low"
        self.run_job()
        status = self.store.status(self.profiles)
        self.assertEqual(status["jobs"][0]["provider_settings"]["codex"]["reasoning"], "medium")
        self.assertEqual(status["attempts"][0]["reasoning"], "medium")
        for choices in ({}, {"codex": {"model": "missing", "reasoning": "low"}}, {"codex": {"model": "luna", "reasoning": "max"}}):
            with self.assertRaises(WakeupError): self.store.enqueue_now([self.profiles[0]["id"]], "b" * 32, choices)

    def test_idempotency_rejects_changed_model_selection(self):
        self.queue()
        with self.assertRaises(WakeupError): self.store.enqueue_now([self.profiles[0]["id"]], "a" * 32, {"codex": {"model": "luna", "reasoning": "medium"}})

    def test_failed_attempt_pauses_and_notifies_once_without_retry(self):
        def failed(*args):
            self.sent.append(args)
            return {"state": "failed", "reason": "Requested model is unavailable for this account."}
        self.adapters["codex"] = WakeupAdapter("luna", "low", failed, self.preflight, True, catalogue=self.adapter.catalogue)
        self.queue(); self.run_job()
        status = self.store.status(self.profiles)
        self.assertEqual(status["attempts"][0]["state"], "failed")
        self.assertTrue(status["attempts"][0]["paused"])
        self.assertEqual(len(self.sent), 1)
        notifications = self.store.claim_notifications()
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["results"][0]["model"], "luna")
        self.assertEqual(notifications[0]["results"][0]["reasoning"], "low")
        self.assertEqual(notifications[0]["results"][0]["provider"], "codex")
        self.assertEqual(self.store.claim_notifications(), [])
        self.store.finish_notification(notifications[0]["notification_id"], False)
        self.assertEqual(self.store.status(self.profiles)["notifications"][0]["delivery_state"], "delivery_failed")
        self.now += MIN_INTERVAL + 1
        self.queue("b" * 32); self.run_job()
        self.assertEqual(len(self.sent), 1)
        held = self.store.claim_notifications()[0]["results"][0]
        self.assertEqual(held["state"], "failed")
        self.assertIn("confirmed failure", held["reason"])

    def test_usage_rejection_and_later_guard_report_weekly_quota_without_resending(self):
        self.reading.update(quota_valid=True, quota_windows=[{"window":"weekly", "remaining_pct":0, "reset_text":"Nov 7, 11pm"}], window_reset_timezone="America/New_York", window_reset_text="9pm")
        def failed(*args):
            self.sent.append(args)
            return {"state":"failed", "reason":"Claude: The provider rejected the request because of a usage or rate limit. No prompt was resubmitted."}
        self.adapters["codex"] = WakeupAdapter("luna", "low", failed, self.preflight, True, catalogue=self.adapter.catalogue)
        for key in ("a"*32,"b"*32):
            self.queue(key); self.run_job()
            result = self.store.claim_notifications()[0]["results"][0]
            self.assertEqual(result["state"], "failed")
            self.assertEqual(result["failure_kind"], "usage_limit")
            self.assertEqual(result["quota_limits"][0]["window"], "weekly")
            self.assertEqual(result["quota_limits"][0]["reset_text"], "Nov 7, 11pm")
            self.assertNotIn("uncertain", result["reason"])
            self.assertEqual(result["reset_text"], "9pm")
        self.assertEqual(len(self.sent), 1)
        self.assertTrue(result["blocked_by_attempt_id"])
        self.assertEqual(len(self.store.status(self.profiles)["attempts"]), 1)

    def test_quota_failure_refreshes_missing_panel_and_other_accounts_continue(self):
        self.profiles.append({"id":"codex-abcdef0123", "provider":"codex", "label":"Work"})
        checked = []
        def before(profile): return dict(self.preflight(profile), account_identity=profile["id"]+"@example.invalid")
        def after(profile):
            checked.append(profile["id"])
            return dict(before(profile), quota_valid=True, quota_windows=[{"window":"five_hour", "remaining_pct":0, "reset_text":"9pm"}])
        def sending(profile, *args):
            self.sent.append(profile["id"])
            return {"state":"failed", "reason":"Provider usage or rate limit."} if profile["id"]==self.profiles[0]["id"] else {"state":"sent"}
        self.adapters["codex"] = WakeupAdapter("luna","low",sending,before,True,catalogue=self.adapter.catalogue,postflight=after)
        self.queue(ids=[p["id"] for p in self.profiles]); self.run_job()
        summary = self.store.claim_notifications()[0]
        self.assertEqual([r["state"] for r in summary["results"]], ["failed","sent"])
        self.assertEqual(summary["results"][0]["quota_limits"][0]["window"], "five_hour")
        self.assertEqual(len(self.sent), 2)
        self.assertIn(self.profiles[0]["id"], checked)
        self.assertEqual(self.store.claim_notifications(), [])

    def test_usage_failure_never_attributes_a_stale_wrong_or_healthy_quota(self):
        for index, changes in enumerate(({"quota_valid":False}, {"collected_at":self.now-121}, {"account_identity":"wrong@example.invalid"}, {"quota_windows":[{"window":"weekly","remaining_pct":40}]})):
            self.reading["quota_valid"] = False
            def after(profile):
                return dict(self.preflight(profile), **dict({"quota_valid":True, "quota_windows":[{"window":"weekly","remaining_pct":0}]}, **changes))
            def failed(*args): return {"state":"failed", "reason":"Provider usage or rate limit."}
            self.adapters["codex"] = WakeupAdapter("luna","low",failed,self.preflight,True,catalogue=self.adapter.catalogue,postflight=after)
            if index:
                self.now += MIN_INTERVAL
                self.store.resume_account(self.store.status(self.profiles)["attempts"][0]["account_ref"])
            self.queue(str(index)*32); self.run_job()
            result = self.store.claim_notifications()[0]["results"][0]
            self.assertEqual(result["state"], "failed")
            self.assertEqual(result["quota_limits"], [])
            self.assertEqual(result["quota_status"], "unavailable")

    def test_model_disappears_after_enqueue_fails_no_fallback_and_one_notification(self):
        self.queue()
        self.adapters["codex"] = WakeupAdapter("different", "low", self.send, self.preflight, True, catalogue=[])
        self.run_job()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.store.status(self.profiles)["jobs"][0]["results"][0]["state"], "failed")
        self.assertEqual(len(self.store.claim_notifications()), 1)
        self.run_job()
        self.assertEqual(self.store.claim_notifications(), [])

    def test_legacy_schedule_requires_explicit_choices(self):
        payload = {"label":"Legacy", "kind":"weekly", "time":"08:00", "weekdays":list(range(7)), "timezone":"UTC", "profile_ids":[self.profiles[0]["id"]]}
        with self.store._db() as db:
            db.execute("INSERT INTO schedules VALUES (?,?,?,?)", ("a"*32, json.dumps(payload), self.now+3600, 1))
        self.run_job()
        schedule = self.store.status(self.profiles)["schedules"][0]
        self.assertFalse(schedule["enabled"])
        self.assertIn("Choose models", schedule["settings_error"])
        with self.assertRaises(WakeupError): self.store.toggle_schedule(schedule["id"], True)

    def test_ordinary_quota_skip_is_in_one_summary(self):
        self.reading["weekly_remaining_pct"] = 0
        self.save_schedule({"kind":"once","run_at":self.now+10,"profile_ids":[self.profiles[0]["id"]]})
        self.now+=11;self.run_job()
        summary = self.store.claim_notifications()
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["results"][0]["state"], "skipped")
        self.assertEqual(self.store.claim_notifications(), [])

    def test_account_model_preflight_failure_notifies_and_other_accounts_continue(self):
        second = dict(self.profiles[0], id="codex-abcdef0123", label="Other account")
        self.profiles.append(second)
        def check(profile):
            if profile["id"] == self.profiles[0]["id"]:
                raise WakeupError("The selected model or reasoning is unavailable for this account.")
            return dict(self.preflight(profile), account_identity="other@example.invalid")
        self.adapters["codex"] = WakeupAdapter("luna", "low", self.send, check, True,
                                               catalogue=self.adapter.catalogue)
        self.queue(ids=[profile["id"] for profile in self.profiles])
        self.run_job()
        status = self.store.status(self.profiles)
        outcomes = {item["profile_id"]: item["state"] for item in status["jobs"][0]["results"]}
        self.assertEqual(outcomes, {self.profiles[0]["id"]: "failed", second["id"]: "sent"})
        self.assertEqual(len(self.sent), 1)
        notifications = self.store.claim_notifications()
        self.assertEqual(len(notifications), 1)
        self.assertIn("unavailable for this account", notifications[0]["results"][0]["reason"])

    def test_preflight_failure_pauses_recurring_source_after_full_batch(self):
        schedule = self.save_schedule({"kind":"weekly", "time":"12:01", "timezone":"UTC",
                                       "weekdays":list(range(7)), "profile_ids":[self.profiles[0]["id"]]})
        def check(profile):
            raise WakeupError("The chosen model is no longer available.")
        self.adapters["codex"] = WakeupAdapter("luna", "low", self.send, check, True,
                                               catalogue=self.adapter.catalogue)
        self.now += 60
        self.run_job()
        status = self.store.status(self.profiles)
        self.assertFalse(status["schedules"][0]["enabled"])
        self.assertIn("Review activity", status["schedules"][0]["last_error"])
        self.assertEqual(status["jobs"][0]["results"][0]["state"], "failed")
        self.assertEqual(self.sent, [])

    def test_three_account_slow_batch_keeps_each_account_eligible_for_processing(self):
        self.profiles.extend([dict(self.profiles[0], id="codex-abcdef0123"),
                              dict(self.profiles[0], id="codex-fedcba0123")])
        def check(profile):
            self.now += 70  # Confirming each quota panel can take time.
            return dict(self.preflight(profile), account_identity=profile["id"] + "@example.invalid")
        self.adapters["codex"] = WakeupAdapter("luna", "low", self.send, check, True,
                                               catalogue=self.adapter.catalogue)
        self.queue(ids=[profile["id"] for profile in self.profiles])
        self.run_job()
        self.assertEqual(len(self.sent), 3)
        self.assertEqual([item["state"] for item in self.store.status(self.profiles)["jobs"][0]["results"]],
                         ["sent", "sent", "sent"])

    def test_claims_one_batch_and_does_not_extend_a_missed_queued_job(self):
        self.queue()
        self.queue("b" * 32)
        self.run_job()
        status = self.store.status(self.profiles)
        self.assertEqual(sum(job["state"] == "queued" for job in status["jobs"]), 1)
        self.now += 121
        self.run_job()
        self.assertEqual(len(self.sent), 1)
        self.assertTrue(any(job["state"] == "expired" for job in self.store.status(self.profiles)["jobs"]))


if __name__ == "__main__":
    unittest.main()
