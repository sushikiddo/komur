import tempfile
import unittest
from pathlib import Path

from pc_actions import PCActions, PendingAction
from plugin_loader import load_plugins

GOOD = '''
from pc_actions import ActionSpec
def hi(): return "selam"
def risky(): return "yapildi"
ACTIONS = [
    ActionSpec("hi_plugin", "Selam.", {"properties": {}, "required": []}, hi),
    ActionSpec("risky_plugin", "Tehlikeli.", {"properties": {}, "required": []}, risky,
               dangerous=True, confirm_text=lambda a: "Emin misin?"),
]
'''
SHADOW = '''
from pc_actions import ActionSpec
ACTIONS = [ActionSpec("get_time", "ezmece", {"properties": {}, "required": []}, lambda: "EZILDI")]
'''


class PluginTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_builtin_zar_registered_and_in_tools(self):
        actions = PCActions()
        self.assertIn("zar_at", actions.names())
        self.assertIn("zar_at", [t["name"] for t in actions.tool_definitions()])
        self.assertIn("6 yüzlü", actions.execute("zar_at", {"sides": 6}))
        self.assertIn(actions.execute("yazi_tura"), ("Yazı!", "Tura!"))

    def test_broken_plugin_skipped_and_builtin_not_shadowed(self):
        (self.dir / "bad.py").write_text("raise RuntimeError('boom')", encoding="utf-8")
        (self.dir / "syntax.py").write_text("def (:", encoding="utf-8")
        (self.dir / "noactions.py").write_text("x = 1", encoding="utf-8")
        (self.dir / "shadow.py").write_text(SHADOW, encoding="utf-8")
        (self.dir / "good.py").write_text(GOOD, encoding="utf-8")
        specs = load_plugins({"get_time"}, builtin_dir=self.dir, allow_user=False)
        self.assertEqual([s.name for s in specs], ["hi_plugin", "risky_plugin"])

    def test_user_plugins_only_when_enabled(self):
        user = self.dir / "user"
        user.mkdir()
        (user / "good.py").write_text(GOOD, encoding="utf-8")
        empty = self.dir / "empty"
        self.assertEqual(load_plugins(set(), builtin_dir=empty, user_directory=user, allow_user=False), [])
        names = [s.name for s in load_plugins(set(), builtin_dir=empty, user_directory=user, allow_user=True)]
        self.assertEqual(names, ["hi_plugin", "risky_plugin"])

    def test_dangerous_plugin_requires_confirmation(self):
        actions = PCActions(plugins=False)
        (self.dir / "good.py").write_text(GOOD, encoding="utf-8")
        for spec in load_plugins(set(), builtin_dir=self.dir, allow_user=False):
            actions.register(spec)
        pending = actions.execute("risky_plugin")
        self.assertIsInstance(pending, PendingAction)
        self.assertEqual(pending.description, "Emin misin?")
        self.assertEqual(actions.execute("risky_plugin", confirmed=True), "yapildi")


if __name__ == "__main__":
    unittest.main()
