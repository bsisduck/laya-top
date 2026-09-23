"""Column priorities for a table's available terminal cells (including padding)."""


def table_columns(width: int, groups: bool, padding: int = 1) -> tuple[tuple[str, str, int], ...]:
    if groups:
        columns = [
            ("category", "CATEGORY / SUBCATEGORY", 24),
            ("count", "PROCESSES", 9),
            ("cpu", "CPU %", 6),
            ("memory", "RSS TOTAL", 10),
        ]
        flexible = "category"
        if width >= sum(c[2] + 2 * padding for c in columns) + 14 + 2 * padding:
            columns.append(("name", "TOP CONSUMER", 14))
            flexible = "name"
        remove_order = ("memory", "count", "cpu")
    else:
        columns = [
            ("pid", "PID", 7),
            ("name", "PROCESS", 24),
            ("category", "CATEGORY / SUBCATEGORY", 24),
            ("cpu", "CPU %", 6),
            ("memory", "MEMORY", 10),
        ]
        flexible = "name"
        for column in (("user", "USER", 12), ("state", "STATE", 9), ("source", "SOURCE", 7)):
            if sum(c[2] + 2 * padding for c in columns) + column[2] + 2 * padding <= width:
                columns.append(column)
            else:
                break
        remove_order = ("category", "pid", "memory", "cpu")

    def remaining() -> int:
        return width - sum(c[2] for c in columns if c[0] != flexible) - 2 * padding * len(columns)

    # Keep the process/category name readable even in very small windows.
    for key in remove_order:
        if remaining() >= 8:
            break
        columns = [c for c in columns if c[0] != key]
    return tuple(
        (key, label, max(1, remaining()) if key == flexible else size)
        for key, label, size in columns
    )
