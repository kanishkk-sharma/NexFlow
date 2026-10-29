"""A small, dependency-free expression evaluator for the Code and Loop nodes.

It evaluates a single Python *expression* by walking the AST and only allowing
an explicit whitelist of constructs. There is no ``eval``/``exec`` involved, so
attribute traversal tricks (``().__class__``...) are impossible by design.
"""

from __future__ import annotations

import ast
import json
import math
import operator
from typing import Any

MAX_EXPR_CHARS = 5000
MAX_STEPS = 200_000
MAX_SEQUENCE = 100_000


class EvalError(Exception):
    """Raised for any invalid or disallowed expression."""


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Not: operator.not_}
_CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


def _safe_range(*args: int) -> list[int]:
    result = range(*args)
    if len(result) > MAX_SEQUENCE:
        raise EvalError("range() is too large")
    return list(result)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_loads(value: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError) as exc:
        raise EvalError(f"json_loads failed: {exc}") from exc


FUNCTIONS: dict[str, Any] = {
    "len": len, "str": str, "int": int, "float": float, "bool": bool,
    "sum": sum, "min": min, "max": max, "abs": abs, "round": round,
    "sorted": sorted, "list": list, "any": any, "all": all,
    "enumerate": lambda seq: list(enumerate(seq)),
    "zip": lambda *seqs: list(zip(*seqs)),
    "range": _safe_range,
    "sqrt": math.sqrt, "floor": math.floor, "ceil": math.ceil,
    "json_dumps": _json_dumps, "json_loads": _json_loads,
}

CONSTANTS: dict[str, Any] = {"True": True, "False": False, "None": None, "pi": math.pi}

_STR_METHODS = {
    "upper", "lower", "strip", "lstrip", "rstrip", "split", "splitlines", "join",
    "replace", "startswith", "endswith", "title", "capitalize", "find", "count",
    "zfill", "isdigit", "isalpha", "isalnum", "isupper", "islower",
}
_LIST_METHODS = {"index", "count"}
_DICT_METHODS = {"get", "keys", "values", "items"}


class _Evaluator:
    def __init__(self) -> None:
        self.steps = 0

    def eval(self, node: ast.AST, scope: dict[str, Any]) -> Any:
        self.steps += 1
        if self.steps > MAX_STEPS:
            raise EvalError("Expression is too expensive to evaluate")
        method = getattr(self, f"_eval_{type(node).__name__}", None)
        if method is None:
            raise EvalError(f"Unsupported syntax: {type(node).__name__}")
        return method(node, scope)

    # ---- literals & names -------------------------------------------------
    def _eval_Constant(self, node: ast.Constant, scope: dict[str, Any]) -> Any:
        return node.value

    def _eval_Name(self, node: ast.Name, scope: dict[str, Any]) -> Any:
        if node.id in scope:
            return scope[node.id]
        if node.id in CONSTANTS:
            return CONSTANTS[node.id]
        raise EvalError(f"Unknown name '{node.id}'")

    def _eval_List(self, node: ast.List, scope: dict[str, Any]) -> list:
        return [self.eval(e, scope) for e in node.elts]

    def _eval_Tuple(self, node: ast.Tuple, scope: dict[str, Any]) -> tuple:
        return tuple(self.eval(e, scope) for e in node.elts)

    def _eval_Dict(self, node: ast.Dict, scope: dict[str, Any]) -> dict:
        if any(k is None for k in node.keys):
            raise EvalError("Dict unpacking is not supported")
        return {self.eval(k, scope): self.eval(v, scope) for k, v in zip(node.keys, node.values)}

    def _eval_JoinedStr(self, node: ast.JoinedStr, scope: dict[str, Any]) -> str:
        return "".join(str(self.eval(v, scope)) for v in node.values)

    def _eval_FormattedValue(self, node: ast.FormattedValue, scope: dict[str, Any]) -> str:
        value = self.eval(node.value, scope)
        if node.conversion == ord("r"):
            value = repr(value)
        elif node.conversion == ord("s"):
            value = str(value)
        spec = self.eval(node.format_spec, scope) if node.format_spec else ""
        try:
            return format(value, spec)
        except (TypeError, ValueError) as exc:
            raise EvalError(f"Invalid format spec: {exc}") from exc

    # ---- operators --------------------------------------------------------
    def _eval_BinOp(self, node: ast.BinOp, scope: dict[str, Any]) -> Any:
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise EvalError(f"Unsupported operator: {type(node.op).__name__}")
        left, right = self.eval(node.left, scope), self.eval(node.right, scope)
        if isinstance(node.op, ast.Pow) and (
            not isinstance(right, (int, float)) or abs(right) > 1000
        ):
            raise EvalError("Exponent is too large")
        if isinstance(node.op, ast.Mult):
            for seq, count in ((left, right), (right, left)):
                if isinstance(seq, (str, list, tuple)) and isinstance(count, int):
                    if len(seq) * max(count, 0) > MAX_SEQUENCE:
                        raise EvalError("Result is too large")
        try:
            return op(left, right)
        except (TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
            raise EvalError(str(exc)) from exc

    def _eval_UnaryOp(self, node: ast.UnaryOp, scope: dict[str, Any]) -> Any:
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise EvalError(f"Unsupported operator: {type(node.op).__name__}")
        try:
            return op(self.eval(node.operand, scope))
        except TypeError as exc:
            raise EvalError(str(exc)) from exc

    def _eval_BoolOp(self, node: ast.BoolOp, scope: dict[str, Any]) -> Any:
        is_and = isinstance(node.op, ast.And)
        value: Any = None
        for operand in node.values:
            value = self.eval(operand, scope)
            if is_and and not value:
                return value
            if not is_and and value:
                return value
        return value

    def _eval_Compare(self, node: ast.Compare, scope: dict[str, Any]) -> bool:
        left = self.eval(node.left, scope)
        for op_node, comparator in zip(node.ops, node.comparators):
            op = _CMP_OPS.get(type(op_node))
            if op is None:
                raise EvalError(f"Unsupported comparison: {type(op_node).__name__}")
            right = self.eval(comparator, scope)
            try:
                if not op(left, right):
                    return False
            except TypeError as exc:
                raise EvalError(str(exc)) from exc
            left = right
        return True

    def _eval_IfExp(self, node: ast.IfExp, scope: dict[str, Any]) -> Any:
        branch = node.body if self.eval(node.test, scope) else node.orelse
        return self.eval(branch, scope)

    # ---- access -----------------------------------------------------------
    def _eval_Subscript(self, node: ast.Subscript, scope: dict[str, Any]) -> Any:
        target = self.eval(node.value, scope)
        key = self.eval(node.slice, scope)
        try:
            return target[key]
        except (KeyError, IndexError, TypeError) as exc:
            raise EvalError(f"Cannot index value: {exc}") from exc

    def _eval_Slice(self, node: ast.Slice, scope: dict[str, Any]) -> slice:
        def part(expr: ast.AST | None) -> Any:
            return self.eval(expr, scope) if expr is not None else None

        return slice(part(node.lower), part(node.upper), part(node.step))

    def _eval_Call(self, node: ast.Call, scope: dict[str, Any]) -> Any:
        if node.keywords:
            raise EvalError("Keyword arguments are not supported")
        args = [self.eval(a, scope) for a in node.args]
        func = node.func
        try:
            if isinstance(func, ast.Name):
                fn = FUNCTIONS.get(func.id)
                if fn is None:
                    raise EvalError(f"Function '{func.id}' is not allowed")
                return fn(*args)
            if isinstance(func, ast.Attribute):
                obj = self.eval(func.value, scope)
                allowed = (
                    _STR_METHODS if isinstance(obj, str)
                    else _LIST_METHODS if isinstance(obj, (list, tuple))
                    else _DICT_METHODS if isinstance(obj, dict)
                    else set()
                )
                if func.attr not in allowed:
                    raise EvalError(f"Method '{func.attr}' is not allowed")
                return getattr(obj, func.attr)(*args)
        except EvalError:
            raise
        except (TypeError, ValueError, OverflowError, ZeroDivisionError) as exc:
            raise EvalError(str(exc)) from exc
        raise EvalError("Unsupported call target")

    # ---- comprehensions ---------------------------------------------------
    def _comprehension(self, generators: list[ast.comprehension], scope: dict[str, Any], emit) -> list:
        results: list[Any] = []

        def walk(index: int, local: dict[str, Any]) -> None:
            if index == len(generators):
                results.append(emit(local))
                if len(results) > MAX_SEQUENCE:
                    raise EvalError("Result is too large")
                return
            gen = generators[index]
            if gen.is_async:
                raise EvalError("Async comprehensions are not supported")
            iterable = self.eval(gen.iter, local)
            try:
                iterator = iter(iterable)
            except TypeError as exc:
                raise EvalError("Value is not iterable") from exc
            for item in iterator:
                inner = dict(local)
                self._assign(gen.target, item, inner)
                if all(self.eval(cond, inner) for cond in gen.ifs):
                    walk(index + 1, inner)

        walk(0, dict(scope))
        return results

    def _assign(self, target: ast.AST, value: Any, scope: dict[str, Any]) -> None:
        if isinstance(target, ast.Name):
            scope[target.id] = value
        elif isinstance(target, ast.Tuple):
            try:
                values = list(value)
            except TypeError as exc:
                raise EvalError("Cannot unpack value") from exc
            if len(values) != len(target.elts):
                raise EvalError("Unpack length mismatch")
            for sub, item in zip(target.elts, values):
                self._assign(sub, item, scope)
        else:
            raise EvalError("Unsupported assignment target")

    def _eval_ListComp(self, node: ast.ListComp, scope: dict[str, Any]) -> list:
        return self._comprehension(node.generators, scope, lambda s: self.eval(node.elt, s))

    def _eval_GeneratorExp(self, node: ast.GeneratorExp, scope: dict[str, Any]) -> list:
        return self._comprehension(node.generators, scope, lambda s: self.eval(node.elt, s))


def safe_eval(expression: str, variables: dict[str, Any] | None = None) -> Any:
    """Evaluate ``expression`` with ``variables`` in scope, or raise EvalError."""
    source = (expression or "").strip()
    if source.startswith("return "):
        source = source[len("return "):].strip()
    if source.startswith("result ="):
        source = source[len("result ="):].strip()
    if not source:
        raise EvalError("Expression is empty")
    if len(source) > MAX_EXPR_CHARS:
        raise EvalError(f"Expression is longer than {MAX_EXPR_CHARS} characters")
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as exc:
        raise EvalError(f"Syntax error: {exc.msg}") from exc
    try:
        return _Evaluator().eval(tree.body, dict(variables or {}))
    except RecursionError as exc:
        raise EvalError("Expression is nested too deeply") from exc
