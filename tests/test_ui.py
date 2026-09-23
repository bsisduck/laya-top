from dataclasses import replace

from textual.widgets import Button, DataTable, Input

from laya_top.actions import ActionResult
from laya_top.app import LayaTop
from laya_top.collector import DemoCollector
from laya_top.screens import ConfirmScreen, DetailScreen


async def test_search_group_drilldown_and_small_terminal():
    app = LayaTop(demo=True, interval=30)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause(0.3)
        assert app.query_one(DataTable).row_count == 12
        await pilot.press("slash")
        app.query_one(Input).value = "tag:AI"
        await pilot.pause()
        assert app.query_one(DataTable).row_count == 1
        await pilot.press("enter", "escape", "g")
        await pilot.pause()
        assert app.mode == "groups"
        await pilot.press("enter")
        await pilot.pause()
        assert app.mode == "processes"
        assert app.query_one(Input).value.startswith("tag:")
        await pilot.resize_terminal(80, 24)
        await pilot.pause()
        assert app.has_class("compact")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, DetailScreen)
        await pilot.press("escape")
        assert len(app.screen_stack) == 1


async def test_selection_survives_sort_and_disappearance_does_not_retarget():
    app = LayaTop(demo=True, interval=30)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause(0.3)
        selected = app.selected
        app.action_sort_by("memory")
        await pilot.pause()
        assert app.selected == selected
        app.snapshot = replace(
            app.snapshot,
            processes=tuple(p for p in app.snapshot.processes if p.identity.key != selected),
        )
        app.render_table()
        await pilot.pause()
        assert app.selected is None
        app.render_table()
        await pilot.pause()
        assert app.selected is None
        await pilot.press("down")
        await pilot.pause()
        assert app.selected is not None


async def test_force_kill_confirmation_requires_pid_and_cancels():
    process = DemoCollector().sample().processes[0]
    app = LayaTop(demo=True, interval=30)
    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.3)
        app.push_screen(ConfirmScreen(process, "kill"))
        await pilot.pause()
        assert app.screen.query_one("#confirm", Button).disabled
        app.screen.query_one(Input).value = str(process.pid)
        await pilot.pause()
        assert not app.screen.query_one("#confirm", Button).disabled
        # A sampling tick while a modal is open must not crash or change its target.
        await app.collect_sample()
        assert app.screen.target == process
        await pilot.press("escape")
        assert len(app.screen_stack) == 1


async def test_empty_results_and_demo_controls():
    app = LayaTop(demo=True, interval=30)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.3)
        app.action_control("terminate")
        assert len(app.screen_stack) == 1
        app.query_one(Input).value = "no-such-process"
        await pilot.pause()
        assert app.query_one(DataTable).row_count == 0
        app.action_control("kill")
        assert len(app.screen_stack) == 1


async def test_confirmation_captures_original_target_and_blocks_other_shortcuts():
    class FakeController:
        calls = []

        def protection(self, target):
            return None

        def execute(self, target, action):
            self.calls.append((target.identity, action))
            return ActionResult(True, "Test signal requested.")

    controller = FakeController()
    app = LayaTop(demo=True, interval=30, controller=controller)
    async with app.run_test(size=(120, 38)) as pilot:
        await pilot.pause(0.3)
        target = app.selected_process()
        await pilot.press("k")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.press("k", "g", "t")
        assert len(app.screen_stack) == 2
        assert app.mode == "processes"
        app.selected = next(key for key in app.visible_processes if key != target.identity.key)
        await pilot.click("#confirm")
        await pilot.pause()
        assert controller.calls == [(target.identity, "terminate")]


async def test_label_pin_tree_and_freeze():
    app = LayaTop(demo=True, interval=30)
    async with app.run_test(size=(120, 38)) as pilot:
        await pilot.pause(0.3)
        target = app.selected
        await pilot.press("f", "t", "space")
        await pilot.pause()
        assert target in app.pins
        assert app.mode == "tree"
        assert app.frozen
        await pilot.press("l")
        await pilot.pause()
        await pilot.click("#save")
        await pilot.pause()
        assert app.tags[target].source == "You"
