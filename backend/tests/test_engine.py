"""Engine, executor and sandbox tests. Run from the project root:

    python -m unittest discover -s backend/tests -t .
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest

_TMP = tempfile.mkdtemp(prefix="nexflow-test-")
os.environ["NEXFLOW_DB"] = os.path.join(_TMP, "test.db")
os.environ["NEXFLOW_FILES_DIR"] = os.path.join(_TMP, "files")

from backend.engine import analyze_graph, run_workflow  # noqa: E402
from backend.executors import ExecutionContext, NodeError, exec_database, exec_file, exec_loop  # noqa: E402
from backend.safe_eval import EvalError, safe_eval  # noqa: E402


def node(node_id, ntype, **data):
    return {"id": node_id, "type": ntype, "position": {"x": 0, "y": 0}, "data": data}


def edge(source, target, source_handle=None, target_handle=None):
    return {"id": f"{source}-{target}", "source": source, "target": target,
            "sourceHandle": source_handle, "targetHandle": target_handle}


def run(nodes, edges, user="u1"):
    async def collect():
        return [e async for e in run_workflow(nodes, edges, user)]
    return asyncio.run(collect())


def final(events):
    return next(e["data"] for e in events if e["event"] == "done")


class SafeEvalTests(unittest.TestCase):
    def test_basics(self):
        self.assertEqual(safe_eval("input * 2", {"input": 21}), 42)
        self.assertEqual(safe_eval("[x * 2 for x in input if x > 1]", {"input": [1, 2, 3]}), [4, 6])
        self.assertEqual(safe_eval("return input.upper()", {"input": "ab"}), "AB")
        self.assertEqual(safe_eval('f"{input}!"', {"input": "hi"}), "hi!")

    def test_escapes_are_blocked(self):
        for expr in ["().__class__", "__import__('os')", "input.__class__", "'{0.__class__}'.format(1)",
                     "open('/etc/passwd')", "9**9**9", "'x' * 10**9", "[].append(1)", "lambda: 1"]:
            with self.assertRaises(EvalError, msg=expr):
                safe_eval(expr, {"input": 1})


class EngineTests(unittest.TestCase):
    def test_branching_skips_untaken_path(self):
        nodes = [node("i", "customInput", inputType="Number", inputValue="7"),
                 node("c", "condition", operator="greater-than", compareValue="5"),
                 node("big", "code", code="input * 2"), node("small", "text", text="small {{input}}"),
                 node("o1", "customOutput", outputName="big"), node("o2", "customOutput", outputName="small")]
        edges = [edge("i", "c", "value", "value"), edge("c", "big", "true", "input"),
                 edge("c", "small", "false", "input"), edge("big", "o1", None, "value"),
                 edge("small", "o2", None, "value")]
        events = run(nodes, edges)
        done = final(events)
        self.assertEqual(done["status"], "success")
        self.assertEqual(done["outputs"], {"big": 14})
        skipped = {e["data"]["node_id"] for e in events if e["event"] == "node_skipped"}
        self.assertEqual(skipped, {"small", "o2"})

    def test_failure_stops_run_and_reports_node(self):
        nodes = [node("i", "customInput", inputType="Number", inputValue="abc")]
        done = final(run(nodes, []))
        self.assertEqual(done["status"], "failed")
        self.assertIn("must be a number", done["error"])

    def test_cycle_and_unknown_type_rejected(self):
        a, b = node("a", "text", text="x"), node("b", "text", text="y")
        self.assertIn("Workflow contains a cycle", analyze_graph([a, b], [edge("a", "b"), edge("b", "a")])["errors"])
        events = run([node("z", "nope")], [])
        self.assertEqual(events[0]["event"], "error")

    def test_text_template_handles_special_characters(self):
        nodes = [node("i", "customInput", inputValue="C:\\path\\1 and \\g<0>"),
                 node("t", "text", text="v={{input}} missing={{other}}")]
        done = final(run(nodes, [edge("i", "t", "value", "input")]))
        self.assertEqual(done["status"], "success")
        events = run(nodes, [edge("i", "t", "value", "input")])
        out = next(e["data"]["output"] for e in events if e["event"] == "node_complete" and e["data"]["node_id"] == "t")
        self.assertEqual(out, "v=C:\\path\\1 and \\g<0> missing={{other}}")

    def test_transform_get_path_and_loop(self):
        nodes = [node("i", "customInput", inputType="JSON", inputValue='{"a": {"items": ["x", "y"]}}'),
                 node("t", "transform", operation="get_path", path="a.items"),
                 node("l", "loop", mode="template", template="<{{item}}:{{index}}>")]
        events = run(nodes, [edge("i", "t", "value", "input"), edge("t", "l", None, "items")])
        out = next(e["data"]["output"] for e in events if e["event"] == "node_complete" and e["data"]["node_id"] == "l")
        self.assertEqual(out, ["<x:0>", "<y:1>"])

    def test_delay_is_async_and_passes_value(self):
        nodes = [node("i", "customInput", inputValue="v"), node("d", "delay", delay=10)]
        events = run(nodes, [edge("i", "d", "value", "input")])
        out = next(e["data"]["output"] for e in events if e["event"] == "node_complete" and e["data"]["node_id"] == "d")
        self.assertEqual(out, "v")


class SandboxTests(unittest.TestCase):
    def test_database_reads_and_blocks_dangerous_sql(self):
        ctx = ExecutionContext("u1")
        try:
            result = exec_database(ctx, {"query": "SELECT name FROM users WHERE plan='pro' ORDER BY id"}, {})
            self.assertEqual([r["name"] for r in result["rows"]], ["Alice", "Carol"])
            for bad in ["ATTACH DATABASE '/tmp/x.db' AS x", "PRAGMA table_info(users)", "DROP TABLE users",
                        "SELECT 1; SELECT 2", "SELECT load_extension('x')"]:
                with self.assertRaises(NodeError, msg=bad):
                    exec_database(ctx, {"query": bad}, {})
            dml = exec_database(ctx, {"query": "UPDATE users SET plan='pro' WHERE id=2"}, {})
            self.assertEqual(dml["affected_rows"], 1)
        finally:
            ctx.close()

    def test_file_node_is_confined_to_workspace(self):
        ctx = ExecutionContext("user-a")
        exec_file(ctx, {"action": "write", "path": "notes/a.txt"}, {"content": "hello"})
        self.assertEqual(exec_file(ctx, {"action": "read", "path": "notes/a.txt"}, {}), "hello")
        exec_file(ctx, {"action": "append", "path": "notes/a.txt"}, {"content": "!"})
        self.assertEqual(exec_file(ctx, {"action": "read", "path": "notes/a.txt"}, {}), "hello!")
        for bad in ["../escape.txt", "/etc/passwd", "notes/../../x", "", "\\windows"]:
            with self.assertRaises(NodeError, msg=bad):
                exec_file(ctx, {"action": "read", "path": bad}, {})
        other = ExecutionContext("user-b")
        with self.assertRaises(NodeError):
            exec_file(other, {"action": "read", "path": "notes/a.txt"}, {})

    def test_loop_limits_and_modes(self):
        self.assertEqual(exec_loop(None, {"mode": "expression", "expression": "item * 2"}, {"items": [1, 2]}), [2, 4])
        with self.assertRaises(NodeError):
            exec_loop(None, {"mode": "expression", "expression": "nope"}, {"items": [1]})


if __name__ == "__main__":
    unittest.main()
