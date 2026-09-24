import re
import shlex
from collections import defaultdict
from collections.abc import Callable
from functools import lru_cache

from .models import Process
from .tagging import Tag, application


@lru_cache(maxsize=128)
def compile_query(query: str) -> Callable[[Process, Tag], bool]:
    if not query.strip():
        return lambda process, tag: True
    try:
        terms = shlex.split(query.casefold())
    except ValueError:
        terms = query.casefold().split()

    def match(process: Process, tag: Tag) -> bool:
        app = application(process)
        haystack = f"{process.name} {app} {tag.label} {process.user}".casefold()
        for term in terms:
            negate = term.startswith("-")
            token = term[1:] if negate else term
            if ":" in token:
                key, value = token.split(":", 1)
                fields = {
                    "tag": tag.label,
                    "sub": tag.subcategory,
                    "user": process.user,
                    "pid": str(process.pid),
                    "app": app,
                    "state": process.status,
                    "source": tag.source,
                }
                found = value in fields[key].casefold() if key in fields else token in haystack
                if key == "pid":
                    found = value == str(process.pid)
            elif comparison := re.fullmatch(r"(cpu|mem)([<>])([\d.]+)", token):
                key, operator, number = comparison.groups()
                try:
                    limit = float(number)
                except ValueError:
                    return False
                current = process.cpu if key == "cpu" else process.rss / 1024**2
                found = current > limit if operator == ">" else current < limit
            else:
                found = token in haystack
            if found == negate:
                return False
        return True

    return match


def matches(process: Process, tag: Tag, query: str) -> bool:
    return compile_query(query)(process, tag)


def order(processes: list[Process], sort: str, reverse: bool = False) -> list[Process]:
    keys = {
        "cpu": lambda p: (-p.cpu, p.pid),
        "memory": lambda p: (-p.rss, p.pid),
        "pid": lambda p: (p.pid,),
        "name": lambda p: (p.name.casefold(), p.pid),
        "age": lambda p: (p.identity.created, p.pid),
    }
    return sorted(processes, key=keys[sort], reverse=reverse)


def tree_order(processes: list[Process]) -> list[tuple[Process, int]]:
    """Filtered-out parents become roots; cycles cannot recurse forever."""
    pids = {p.pid for p in processes}
    children: dict[int, list[Process]] = defaultdict(list)
    for process in processes:
        children[process.ppid].append(process)
    result, seen = [], set()

    def visit(root: Process, depth: int):
        stack = [(root, depth)]
        while stack:
            process, level = stack.pop()
            if process.pid in seen:
                continue
            seen.add(process.pid)
            result.append((process, min(level, 8)))
            stack.extend((p, level + 1) for p in reversed(children[process.pid]))

    for process in processes:
        if process.ppid not in pids:
            visit(process, 0)
    for process in processes:
        visit(process, 0)
    return result
