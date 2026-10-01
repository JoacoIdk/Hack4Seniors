"""
Storage abstraction layer.

The interface is modelled after a relational database: data lives in *tables*,
rows are dicts, and queries are expressed with filter dicts that compile
directly to parameterized SQL. PostgreSQL is the primary backend; the flatfile
backend emulates the same semantics with JSON files so the app can run without
a database (local development, tests, demos).

Filters
-------
A ``where`` dict maps ``column`` or ``column__op`` to a value. All conditions are
ANDed together::

    {"name": "alice"}                  # name = 'alice'
    {"age__gte": 65, "city": "Stgo"}   # age >= 65 AND city = 'Stgo'
    {"id__in": [1, 2, 3]}              # id = ANY([1, 2, 3])
    {"email__is_null": True}           # email IS NULL
    {"name__ilike": "%ali%"}           # case-insensitive LIKE

Supported ops: eq, ne, lt, lte, gt, gte, in, not_in, like, ilike, is_null.

Ordering
--------
``order_by`` accepts a column name or a list of them; prefix with ``-`` for
descending order, e.g. ``order_by=["-created_at", "id"]``.

Configuration (environment)
---------------------------
STORAGE        "postgres" | "flatfile"   (default: "flatfile")
DATABASE_URL   PostgreSQL DSN, required for "postgres"
STORAGE_PATH   Directory for flatfile data (default: "./data")
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import re
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Iterable, Mapping, Sequence

logger = logging.getLogger(__name__)

Row = dict[str, Any]
Where = Mapping[str, Any]
OrderBy = str | Sequence[str] | None

OPERATORS = ("eq", "ne", "lt", "lte", "gt", "gte", "in", "not_in", "like", "ilike", "is_null")

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class StorageError(Exception):
    """Base error raised by the storage layer."""


class UnsupportedOperation(StorageError):
    """Raised when a backend cannot perform the requested operation."""


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #

def _validate_identifier(name: str) -> str:
    if not _IDENTIFIER.match(name):
        raise StorageError(f"Invalid identifier: {name!r}")
    return name


def _parse_condition(key: str) -> tuple[str, str]:
    column, _, op = key.partition("__")
    op = op or "eq"
    if op not in OPERATORS:
        raise StorageError(f"Unknown filter operator {op!r} in {key!r}")
    return _validate_identifier(column), op


def _parse_order(order_by: OrderBy) -> list[tuple[str, bool]]:
    """Return a list of (column, descending) tuples."""
    if order_by is None:
        return []
    if isinstance(order_by, str):
        order_by = [order_by]
    parsed = []
    for item in order_by:
        descending = item.startswith("-")
        parsed.append((_validate_identifier(item.lstrip("-")), descending))
    return parsed


# --------------------------------------------------------------------------- #
# Interface
# --------------------------------------------------------------------------- #

class Storage(ABC):
    """Backend-agnostic, table-oriented storage interface."""

    # Lifecycle ----------------------------------------------------------------

    @abstractmethod
    async def connect(self) -> None:
        """Open connections / prepare the backend. Call once at startup."""

    @abstractmethod
    async def close(self) -> None:
        """Release resources. Call once at shutdown."""

    # Schema -------------------------------------------------------------------

    @abstractmethod
    async def create_table(self, table: str, columns: Mapping[str, str]) -> None:
        """
        Create ``table`` if it does not exist.

        ``columns`` maps column names to SQL type definitions, e.g.
        ``{"id": "SERIAL PRIMARY KEY", "name": "TEXT NOT NULL"}``.
        The flatfile backend ignores the types but creates the table file.
        """

    @abstractmethod
    async def drop_table(self, table: str) -> None:
        """Drop ``table`` if it exists."""

    # CRUD ---------------------------------------------------------------------

    @abstractmethod
    async def insert(self, table: str, values: Mapping[str, Any]) -> Row:
        """Insert a row and return it as stored (including generated ``id``)."""

    async def insert_many(self, table: str, rows: Iterable[Mapping[str, Any]]) -> list[Row]:
        """Insert several rows atomically."""
        async with self.transaction() as tx:
            return [await tx.insert(table, row) for row in rows]

    @abstractmethod
    async def find(
        self,
        table: str,
        where: Where | None = None,
        *,
        columns: Sequence[str] | None = None,
        order_by: OrderBy = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Row]:
        """Return rows matching ``where``."""

    async def find_one(self, table: str, where: Where | None = None, **kwargs: Any) -> Row | None:
        rows = await self.find(table, where, limit=1, **kwargs)
        return rows[0] if rows else None

    async def get(self, table: str, id: Any) -> Row | None:
        """Fetch a row by its ``id`` column."""
        return await self.find_one(table, {"id": id})

    @abstractmethod
    async def update(self, table: str, where: Where, values: Mapping[str, Any]) -> list[Row]:
        """Update rows matching ``where`` and return the updated rows."""

    @abstractmethod
    async def delete(self, table: str, where: Where) -> int:
        """Delete rows matching ``where`` and return how many were removed."""

    @abstractmethod
    async def count(self, table: str, where: Where | None = None) -> int:
        """Count rows matching ``where``."""

    async def exists(self, table: str, where: Where | None = None) -> bool:
        return await self.find_one(table, where) is not None

    # Transactions -------------------------------------------------------------

    @abstractmethod
    def transaction(self) -> "AsyncTransaction":
        """
        Async context manager yielding a ``Storage`` bound to a transaction.

        Everything done through the yielded object is committed on normal exit
        and rolled back if an exception escapes::

            async with storage.transaction() as tx:
                user = await tx.insert("users", {...})
                await tx.insert("profiles", {"user_id": user["id"]})
        """

    # Raw SQL ------------------------------------------------------------------

    async def execute(self, sql: str, *args: Any) -> str:
        """Run a raw SQL statement. SQL backends only."""
        raise UnsupportedOperation(f"{type(self).__name__} does not support raw SQL")

    async def fetch(self, sql: str, *args: Any) -> list[Row]:
        """Run a raw SQL query and return rows. SQL backends only."""
        raise UnsupportedOperation(f"{type(self).__name__} does not support raw SQL")


AsyncTransaction = Any  # an async context manager yielding Storage


# --------------------------------------------------------------------------- #
# PostgreSQL backend
# --------------------------------------------------------------------------- #

class _SQLBuilder:
    """Builds PostgreSQL statements with ``$n`` positional parameters."""

    def __init__(self) -> None:
        self.params: list[Any] = []

    def param(self, value: Any) -> str:
        self.params.append(value)
        return f"${len(self.params)}"

    @staticmethod
    def ident(name: str) -> str:
        return f'"{_validate_identifier(name)}"'

    def where(self, where: Where | None) -> str:
        if not where:
            return ""
        clauses = [self._condition(key, value) for key, value in where.items()]
        return " WHERE " + " AND ".join(clauses)

    def _condition(self, key: str, value: Any) -> str:
        column, op = _parse_condition(key)
        col = self.ident(column)
        if op == "eq":
            return f"{col} IS NULL" if value is None else f"{col} = {self.param(value)}"
        if op == "ne":
            return f"{col} IS NOT NULL" if value is None else f"{col} IS DISTINCT FROM {self.param(value)}"
        if op == "is_null":
            return f"{col} IS NULL" if value else f"{col} IS NOT NULL"
        if op == "in":
            return f"{col} = ANY({self.param(list(value))})"
        if op == "not_in":
            return f"NOT ({col} = ANY({self.param(list(value))}))"
        sql_op = {"lt": "<", "lte": "<=", "gt": ">", "gte": ">=", "like": "LIKE", "ilike": "ILIKE"}[op]
        return f"{col} {sql_op} {self.param(value)}"

    def order(self, order_by: OrderBy) -> str:
        parts = [f"{self.ident(c)} {'DESC' if d else 'ASC'}" for c, d in _parse_order(order_by)]
        return " ORDER BY " + ", ".join(parts) if parts else ""

    def paging(self, limit: int | None, offset: int | None) -> str:
        sql = ""
        if limit is not None:
            sql += f" LIMIT {self.param(int(limit))}"
        if offset is not None:
            sql += f" OFFSET {self.param(int(offset))}"
        return sql


class PostgresStorage(Storage):
    """PostgreSQL backend using an ``asyncpg`` connection pool."""

    def __init__(self, dsn: str, *, min_size: int = 1, max_size: int = 10, _conn: Any = None, _pool: Any = None):
        self.dsn = dsn
        self.min_size = min_size
        self.max_size = max_size
        self._pool = _pool
        self._conn = _conn  # set when bound to a transaction

    async def connect(self) -> None:
        if self._pool is not None:
            return
        try:
            import asyncpg
        except ImportError as e:
            raise StorageError("PostgreSQL storage requires 'asyncpg' (pip install asyncpg)") from e
        self._pool = await asyncpg.create_pool(self.dsn, min_size=self.min_size, max_size=self.max_size)
        logger.info("Connected to PostgreSQL.")

    async def close(self) -> None:
        if self._pool is not None and self._conn is None:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL pool closed.")

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[Any]:
        if self._conn is not None:
            yield self._conn
            return
        if self._pool is None:
            raise StorageError("PostgresStorage is not connected; call connect() first")
        async with self._pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator["PostgresStorage"]:
        # Nested transactions become savepoints automatically in asyncpg.
        async with self._connection() as conn:
            async with conn.transaction():
                yield PostgresStorage(self.dsn, _conn=conn, _pool=self._pool)

    # Raw SQL ------------------------------------------------------------------

    async def execute(self, sql: str, *args: Any) -> str:
        async with self._connection() as conn:
            return await conn.execute(sql, *args)

    async def fetch(self, sql: str, *args: Any) -> list[Row]:
        async with self._connection() as conn:
            return [dict(r) for r in await conn.fetch(sql, *args)]

    # Schema -------------------------------------------------------------------

    async def create_table(self, table: str, columns: Mapping[str, str]) -> None:
        q = _SQLBuilder()
        cols = ", ".join(f"{q.ident(name)} {definition}" for name, definition in columns.items())
        await self.execute(f"CREATE TABLE IF NOT EXISTS {q.ident(table)} ({cols})")

    async def drop_table(self, table: str) -> None:
        await self.execute(f"DROP TABLE IF EXISTS {_SQLBuilder.ident(table)}")

    # CRUD ---------------------------------------------------------------------

    async def insert(self, table: str, values: Mapping[str, Any]) -> Row:
        q = _SQLBuilder()
        if values:
            cols = ", ".join(q.ident(c) for c in values)
            params = ", ".join(q.param(v) for v in values.values())
            sql = f"INSERT INTO {q.ident(table)} ({cols}) VALUES ({params}) RETURNING *"
        else:
            sql = f"INSERT INTO {q.ident(table)} DEFAULT VALUES RETURNING *"
        rows = await self.fetch(sql, *q.params)
        return rows[0]

    async def find(
        self,
        table: str,
        where: Where | None = None,
        *,
        columns: Sequence[str] | None = None,
        order_by: OrderBy = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Row]:
        q = _SQLBuilder()
        cols = ", ".join(q.ident(c) for c in columns) if columns else "*"
        sql = (
            f"SELECT {cols} FROM {q.ident(table)}"
            f"{q.where(where)}{q.order(order_by)}{q.paging(limit, offset)}"
        )
        return await self.fetch(sql, *q.params)

    async def update(self, table: str, where: Where, values: Mapping[str, Any]) -> list[Row]:
        if not values:
            return await self.find(table, where)
        q = _SQLBuilder()
        assignments = ", ".join(f"{q.ident(c)} = {q.param(v)}" for c, v in values.items())
        sql = f"UPDATE {q.ident(table)} SET {assignments}{q.where(where)} RETURNING *"
        return await self.fetch(sql, *q.params)

    async def delete(self, table: str, where: Where) -> int:
        q = _SQLBuilder()
        status = await self.execute(f"DELETE FROM {q.ident(table)}{q.where(where)}", *q.params)
        return int(status.split()[-1])  # asyncpg returns e.g. "DELETE 3"

    async def count(self, table: str, where: Where | None = None) -> int:
        q = _SQLBuilder()
        rows = await self.fetch(f"SELECT COUNT(*) AS n FROM {q.ident(table)}{q.where(where)}", *q.params)
        return rows[0]["n"]


# --------------------------------------------------------------------------- #
# Flatfile backend
# --------------------------------------------------------------------------- #

def _like_to_regex(pattern: str, flags: int = 0) -> re.Pattern[str]:
    out = []
    for ch in pattern:
        out.append(".*" if ch == "%" else "." if ch == "_" else re.escape(ch))
    return re.compile("^" + "".join(out) + "$", flags | re.DOTALL)


def _matches(row: Row, where: Where | None) -> bool:
    if not where:
        return True
    for key, expected in where.items():
        column, op = _parse_condition(key)
        actual = row.get(column)
        if op == "eq":
            ok = actual == expected
        elif op == "ne":
            ok = actual != expected
        elif op == "is_null":
            ok = (actual is None) == bool(expected)
        elif op == "in":
            ok = actual in list(expected)
        elif op == "not_in":
            ok = actual not in list(expected)
        elif actual is None:
            ok = False  # SQL semantics: comparisons with NULL are never true
        elif op == "like":
            ok = bool(_like_to_regex(expected).match(str(actual)))
        elif op == "ilike":
            ok = bool(_like_to_regex(expected, re.IGNORECASE).match(str(actual)))
        else:
            ok = {"lt": actual < expected, "lte": actual <= expected,
                  "gt": actual > expected, "gte": actual >= expected}[op]
        if not ok:
            return False
    return True


def _sort_rows(rows: list[Row], order_by: OrderBy) -> list[Row]:
    # Apply sorts from least to most significant (stable sort); NULLs last like PostgreSQL ASC.
    for column, descending in reversed(_parse_order(order_by)):
        rows.sort(key=lambda r: (r.get(column) is None, r.get(column) if r.get(column) is not None else 0),
                  reverse=descending)
    return rows


class _FlatFileState:
    """State shared between a FlatFileStorage and its transaction views."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = asyncio.Lock()
        self.tables: dict[str, list[Row]] = {}
        self.dirty: set[str] = set()


class FlatFileStorage(Storage):
    """
    JSON-file backend: one ``<table>.json`` file per table inside ``path``.

    Tables are cached in memory and written atomically after each mutation
    (or once at commit inside a transaction). Rows get an auto-incrementing
    integer ``id`` when none is supplied. Intended for development and small
    single-process deployments — it is not safe across multiple processes.
    """

    def __init__(self, path: str | os.PathLike[str] = "data", *, _state: _FlatFileState | None = None):
        self._state = _state or _FlatFileState(Path(path))
        self._in_tx = _state is not None

    # Lifecycle ----------------------------------------------------------------

    async def connect(self) -> None:
        self._state.path.mkdir(parents=True, exist_ok=True)
        logger.info("Using flatfile storage at %s", self._state.path.resolve())

    async def close(self) -> None:
        async with self._guard():
            self._flush()

    # Internals ----------------------------------------------------------------

    @asynccontextmanager
    async def _guard(self) -> AsyncIterator[None]:
        # Transactions already hold the lock for their whole duration.
        if self._in_tx:
            yield
            return
        async with self._state.lock:
            yield
            self._flush()

    def _file(self, table: str) -> Path:
        return self._state.path / f"{_validate_identifier(table)}.json"

    def _table(self, table: str) -> list[Row]:
        tables = self._state.tables
        if table not in tables:
            file = self._file(table)
            if not file.exists():
                raise StorageError(f"Table {table!r} does not exist")
            tables[table] = json.loads(file.read_text(encoding="utf-8") or "[]")
        return tables[table]

    def _flush(self) -> None:
        for table in self._state.dirty:
            file = self._file(table)
            if table not in self._state.tables:  # dropped
                file.unlink(missing_ok=True)
                continue
            tmp = file.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self._state.tables[table], default=str, indent=2), encoding="utf-8")
            os.replace(tmp, file)
        self._state.dirty.clear()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator["FlatFileStorage"]:
        state = self._state
        if self._in_tx:
            # Nested transaction: behave like a savepoint.
            snapshot = copy.deepcopy(state.tables), set(state.dirty)
            try:
                yield self
            except BaseException:
                state.tables, state.dirty = snapshot
                raise
            return
        async with state.lock:
            snapshot = copy.deepcopy(state.tables)
            try:
                yield FlatFileStorage(_state=state)
            except BaseException:
                state.tables = snapshot
                state.dirty.clear()
                raise
            self._flush()

    # Schema -------------------------------------------------------------------

    async def create_table(self, table: str, columns: Mapping[str, str]) -> None:
        async with self._guard():
            try:
                self._table(table)
            except StorageError:
                self._state.tables[table] = []
                self._state.dirty.add(table)

    async def drop_table(self, table: str) -> None:
        async with self._guard():
            self._state.tables.pop(table, None)
            if self._file(table).exists():
                self._state.dirty.add(table)

    # CRUD ---------------------------------------------------------------------

    async def insert(self, table: str, values: Mapping[str, Any]) -> Row:
        async with self._guard():
            rows = self._table(table)
            row = copy.deepcopy(dict(values))
            if row.get("id") is None:
                ids = [r["id"] for r in rows if isinstance(r.get("id"), int)]
                row["id"] = max(ids, default=0) + 1
            elif any(r.get("id") == row["id"] for r in rows):
                raise StorageError(f"Duplicate id {row['id']!r} in table {table!r}")
            rows.append(row)
            self._state.dirty.add(table)
            return copy.deepcopy(row)

    async def find(
        self,
        table: str,
        where: Where | None = None,
        *,
        columns: Sequence[str] | None = None,
        order_by: OrderBy = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Row]:
        async with self._guard():
            rows = _sort_rows([r for r in self._table(table) if _matches(r, where)], order_by)
            start = offset or 0
            rows = rows[start:start + limit] if limit is not None else rows[start:]
            if columns:
                rows = [{c: r.get(c) for c in columns} for r in rows]
            return copy.deepcopy(rows)

    async def update(self, table: str, where: Where, values: Mapping[str, Any]) -> list[Row]:
        async with self._guard():
            updated = []
            for row in self._table(table):
                if _matches(row, where):
                    row.update(copy.deepcopy(dict(values)))
                    updated.append(copy.deepcopy(row))
            if updated:
                self._state.dirty.add(table)
            return updated

    async def delete(self, table: str, where: Where) -> int:
        async with self._guard():
            rows = self._table(table)
            kept = [r for r in rows if not _matches(r, where)]
            removed = len(rows) - len(kept)
            if removed:
                rows[:] = kept
                self._state.dirty.add(table)
            return removed

    async def count(self, table: str, where: Where | None = None) -> int:
        async with self._guard():
            return sum(1 for r in self._table(table) if _matches(r, where))


# --------------------------------------------------------------------------- #
# Factory & FastAPI integration
# --------------------------------------------------------------------------- #

def create_storage(kind: str | None = None) -> Storage:
    """Build a storage backend from arguments or environment variables."""
    kind = (kind or os.getenv("STORAGE") or "flatfile").strip().lower()
    if kind in ("postgres", "postgresql", "pg", "sql"):
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            raise StorageError("DATABASE_URL must be set to use PostgreSQL storage")
        return PostgresStorage(dsn)
    if kind in ("flatfile", "file", "json"):
        return FlatFileStorage(os.getenv("STORAGE_PATH", "data"))
    raise StorageError(f"Unknown storage backend: {kind!r}")


_storage: Storage | None = None


async def init_storage(kind: str | None = None) -> Storage:
    """Create and connect the global storage. Call from the app lifespan."""
    global _storage
    if _storage is None:
        _storage = create_storage(kind)
        await _storage.connect()
    return _storage


async def close_storage() -> None:
    global _storage
    if _storage is not None:
        await _storage.close()
        _storage = None


def get_storage() -> Storage:
    """FastAPI dependency: ``storage: Storage = Depends(get_storage)``."""
    if _storage is None:
        raise StorageError("Storage not initialized; call init_storage() at startup")
    return _storage
