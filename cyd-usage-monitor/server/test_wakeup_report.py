import datetime as dt
import io
import unittest
from PIL import Image
try:
    from .wakeup_report import render_summary, reset_label, image_reset_parts, quota_limit_lines
except ImportError:
    from wakeup_report import render_summary, reset_label, image_reset_parts, quota_limit_lines


class WakeupReportTests(unittest.TestCase):
    def test_failed_quota_windows_and_resets_are_in_image_layout_and_text(self):
        result = {"provider":"claude", "label":"Claude account", "state":"failed", "failure_kind":"usage_limit", "reason":"Not sent: prior usage rejection; account held for review.", "quota_limits":[{"window":"weekly","reset_text":"Nov 7, 11pm (America/New_York)","reset_timezone":"America/New_York"},{"window":"five_hour","reset_at":1793800800}]}
        lines = quota_limit_lines(result,"America/New_York")
        self.assertIn("Weekly quota exhausted",lines[0])
        self.assertIn("Nov 7, 11pm",lines[0])
        self.assertNotIn("America/", " ".join(lines))
        self.assertIn("Five-hour quota exhausted",lines[1])
        with Image.open(io.BytesIO(render_summary({"results":[result]},"America/New_York"))) as image:
            self.assertGreater(image.height,500)
        self.assertIn("not confirmed",quota_limit_lines({"failure_kind":"usage_limit"},"UTC")[0])

    def test_rounded_quota_reset_is_labelled_cli_reported(self):
        result = {"state":"sent", "reset_text":"20:11", "reset_timezone":"America/New_York", "reset_source":"reported"}
        self.assertEqual(image_reset_parts(result, "America/New_York"), ("8:11 PM", "CLI reported"))

    def event(self, count=3):
        providers = ["codex", "antigravity", "claude"]
        return {"kind":"run_summary", "source":"manual", "created_at":"2026-11-04T13:00:00Z", "results":[
            {"provider":providers[index%3], "label":"Example account " + str(index), "model":"current-model", "reasoning":"low", "state":["sent","failed","skipped"][index%3], "reason":"The model is unavailable for this account.", "reset_at":1793800800, "reset_estimated":True} for index in range(count)]}

    def test_real_jpeg_contains_branded_sections_and_bounded_size(self):
        for count in (0, 3, 50):
            report = render_summary(self.event(count), "America/New_York")
            with Image.open(io.BytesIO(report)) as image:
                self.assertEqual(image.format,"JPEG")
                self.assertEqual(image.width,1000)
                self.assertLessEqual(image.height,16000)
                self.assertGreater(image.height,400)
            self.assertLess(len(report),5_000_000)

    def test_long_labels_and_reasons_wrap_without_unbounded_allocation(self):
        event=self.event(50)
        for account in event["results"]:
            account.update(label="Very long account name "*20, model="model-"*30, reason="An extended failure reason "*50)
        with Image.open(io.BytesIO(render_summary(event,"America/New_York"))) as image:
            self.assertLessEqual(image.height,16000)
        event["results"].append({})
        with self.assertRaises(ValueError):render_summary(event)

    def test_seven_codex_one_antigravity_one_claude_with_mixed_outcomes(self):
        event=self.event(9)
        providers=["codex"]*7+["antigravity","claude"]
        names=["Personal Pro", "Work – engineering", "Research and development account with a longer name", "Production", "Planning", "Account with 0 remaining weekly quota", "NameWithNoSpaces"*6, "Google personal", "Claude Pro"]
        for index,account in enumerate(event["results"]):
            account.update(provider=providers[index],label=names[index],state=["sent","failed","skipped","unknown"][index%4], reset_at=1793800800+index*270,reset_estimated=index%2==0)
        for source in ("manual","schedule:example"):
            event.update(source=source,run_context={"schedule_label":"Weekday mornings"})
            with Image.open(io.BytesIO(render_summary(event,"America/New_York"))) as image:
                self.assertEqual(image.width,1000)
                self.assertGreater(image.height,1800)
                self.assertLess(image.height,4000)

    def test_reset_uses_user_timezone_and_marks_estimates(self):
        winter=dt.datetime(2026,11,4,18,0,tzinfo=dt.timezone.utc).timestamp()
        summer=dt.datetime(2026,7,4,18,0,tzinfo=dt.timezone.utc).timestamp()
        self.assertIn("01:00 PM EST",reset_label({"reset_at":winter},"America/New_York"))
        self.assertIn("02:00 PM EDT",reset_label({"reset_at":summer},"America/New_York"))
        self.assertTrue(reset_label({"reset_at":winter,"reset_estimated":True},"America/New_York").startswith("Estimated:"))
        self.assertEqual(reset_label({"state":"unknown"},"America/New_York"),"Not confirmed")

    def test_cli_time_without_epoch_is_not_silently_reinterpreted(self):
        result={"reset_text":"4:20pm (America/New_York)","reset_timezone":"America/New_York"}
        self.assertIn("4:20pm",reset_label(result,"America/New_York"))
        self.assertEqual(reset_label(result,"Europe/London"),"Not reported")


class ImageResetDisplayTests(unittest.TestCase):
    def test_local_time_column_has_no_repeated_timezone(self):
        stamp=dt.datetime(2026,11,4,18,20,tzinfo=dt.timezone.utc).timestamp()
        primary,note=image_reset_parts({"reset_at":stamp},"America/New_York","2026-11-04T13:00:00Z")
        self.assertEqual(primary,"1:20 PM");self.assertEqual(note,"Today")
        for value in (primary,note):
            self.assertNotIn("EST",value);self.assertNotIn("America/",value)
        primary,note=image_reset_parts({"reset_at":stamp,"reset_estimated":True},"America/New_York")
        self.assertIn("Estimated",note)
        primary,note=image_reset_parts({"reset_text":"4:20pm (America/New_York)","reset_timezone":"America/New_York"},"America/New_York")
        self.assertEqual(primary,"4:20 PM");self.assertEqual(note,"Confirmed")
        self.assertEqual(image_reset_parts({"state":"failed"},"America/New_York"),("N/A","Not reported"))
