import contextlib
import json
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
try:
    from . import wakeup_catalog as catalog
    from . import wakeup_cli
except ImportError:
    import wakeup_catalog as catalog
    import wakeup_cli
class CatalogTests(unittest.TestCase):
    def setUp(self):catalog._cache.clear()
    def test_claude_resolves_alias_and_uses_actual_supported_efforts(self):
        data={"response":{"response":{"models":[{"value":"haiku","resolvedModel":"claude-new-haiku","displayName":"Haiku","supportedEffortLevels":["low","high"]},{"value":"default"}]}}}
        self.assertEqual(catalog.parse_models("claude",json.dumps(data)),[{"id":"claude-new-haiku","label":"Haiku","reasoning_levels":["low","high"]}])
    def test_codex_filters_hidden_and_invalid_models(self):
        data={"models":[{"slug":"luna-current","display_name":"Luna","supported_reasoning_levels":[{"effort":"low"},{"effort":"max"}]},{"slug":"hidden","visibility":"hide"},{"slug":"bad;command"}]}
        self.assertEqual(catalog.parse_models("codex",json.dumps(data)),[{"id":"luna-current","label":"Luna","reasoning_levels":["low","max"]}])
    def test_any_visible_generation_and_codex_only_models_are_preserved(self):
        models = [{"slug": "gpt-6.1-sol", "supported_in_api": False, "supported_reasoning_levels": [{"effort": "low"}]},
                  {"slug": "future-luna", "supported_reasoning_levels": [{"effort": "minimal"}]}]
        self.assertEqual([item["id"] for item in catalog.parse_models("codex", json.dumps({"models": models}))], ["gpt-6.1-sol", "future-luna"])

    def test_antigravity_model_listing_and_fixed_models(self):
        self.assertEqual(catalog.parse_models("antigravity","gemini-new-low\tFlash Low\nclaude-new\tClaude\n")[1]["reasoning_levels"],["fixed"])
    def test_cache_only_runs_metadata_command_and_missing_pair_rejected(self):
        collector=SimpleNamespace(cli_executable=lambda _:"codex",profile_lock=lambda _:contextlib.nullcontext(),profile_environment=lambda p:{},profile_workdir=lambda p:Path("."))
        profile={"id":"codex-0123456789","provider":"codex"}
        output=json.dumps({"models":[{"slug":"luna","supported_reasoning_levels":[{"effort":"low"}]}]})
        with patch.object(wakeup_cli,"run_once",return_value=subprocess.CompletedProcess([],0,output,"")) as run:
            catalog.profile_models(collector,profile);catalog.require_model(collector,profile,"luna","low")
            with self.assertRaises(ValueError):catalog.require_model(collector,profile,"retired","low")
        run.assert_called_once();self.assertEqual(run.call_args.args[0],["codex","debug","models"])
    def test_separate_metadata_binary_preserves_quota_binary(self):
        collector=SimpleNamespace(cli_executable=lambda _:"quota-codex", wakeup_cli_executable=lambda _:"current-codex", profile_lock=lambda _:contextlib.nullcontext(),profile_environment=lambda p:{},profile_workdir=lambda p:Path("."))
        output=json.dumps({"models":[{"slug":"current","supported_reasoning_levels":[{"effort":"low"}]}]})
        with patch.object(wakeup_cli,"run_once",return_value=subprocess.CompletedProcess([],0,output,"")) as run:
            catalog.profile_models(collector,{"id":"codex-0123456789","provider":"codex"})
        self.assertEqual(run.call_args.args[0],["current-codex","debug","models"])
        self.assertEqual(collector.cli_executable("codex"),"quota-codex")

    def test_antigravity_effort_metadata_overrides_name_suffix_without_model_turn(self):
        collector=SimpleNamespace(cli_executable=lambda _:"agy",profile_lock=lambda _:contextlib.nullcontext(),profile_environment=lambda p:{},profile_workdir=lambda p:Path("."))
        results=[subprocess.CompletedProcess([],0,"flash-low\tFlash\n",""),subprocess.CompletedProcess([],0,json.dumps({"command":{"data":{"adjustable":True,"available":["low","medium","high"]}},"num_turns":0}),"")]
        with patch.object(wakeup_cli,"run_once",side_effect=results) as run:
            models=catalog.profile_models(collector,{"id":"antigravity-0123456789","provider":"antigravity"})
        self.assertEqual(models[0]["reasoning_levels"],["low","medium","high"])
        self.assertEqual(run.call_args_list[1].args[0][1:3],["-p","/effort"])
