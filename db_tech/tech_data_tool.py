from enum import StrEnum
from typing import List, Optional, Any, Literal, Union, Type
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select, func, desc, asc, and_, or_, inspect
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select
from db_tech.models import Pokemon, Move, Item, Base

DB_PATH = "db_tech/tech.db"
engine = create_engine(f"sqlite:///{DB_PATH}")


def create_column_enum(model_class: Type[Base], enum_name: str) -> Any:
    """
    Dynamically creates a StrEnum from a SQLAlchemy model's columns.

    Using StrEnum is critical here because:
    1. It allows Pydantic to serialize/validate these values directly as strings in the JSON schema.
    2. It enables direct comparison with string column names without accessing `.value`.
    """
    # Keys become the Enum member names (uppercase constants, e.g. PokemonColumn.NAME)
    # Values become the actual string values used by Pydantic/Database (e.g. "name")
    columns = {c.name.upper(): c.name for c in inspect(model_class).columns}
    return StrEnum(enum_name, columns)


# Explicit column definitions for better agent awareness
PokemonColumn = create_column_enum(Pokemon, "PokemonColumn")
MoveColumn = create_column_enum(Move, "MoveColumn")
ItemColumn = create_column_enum(Item, "ItemColumn")

AnyColumn = Union[PokemonColumn, MoveColumn, ItemColumn]


class QueryCondition(BaseModel):
    """
    Represents a single SQL WHERE condition.
    """

    column: AnyColumn
    operator: Literal["=", ">", "<", ">=", "<=", "!=", "LIKE", "IN"]
    value: Any


class Aggregation(BaseModel):
    """
    Represents a SQL aggregation function on a column.
    """

    func: Literal["MIN", "MAX", "AVG", "SUM", "COUNT"]
    column: AnyColumn


class TechDataQuery(BaseModel):
    """
    Structured representation of a technical data query for the Pokemon database.
    Transformed into a SQL query by the tool.
    """

    table: Literal["pokemons", "moves", "items"]
    # Allow columns to be specific names or aggregations
    columns: List[Union[AnyColumn, Aggregation]]
    conditions: List[QueryCondition] = Field(default_factory=list)
    condition_logic: Literal["AND", "OR"] = "AND"
    group_by: Optional[List[str]] = None
    order_by: Optional[str] = None
    order_direction: Literal["ASC", "DESC"] = "ASC"
    limit: Optional[int] = None


def get_model_class(table_name: str) -> Type[Base]:
    """Factory to retrieve the SQLAlchemy model class based on table name."""
    if table_name == "pokemons":
        return Pokemon
    elif table_name == "moves":
        return Move
    elif table_name == "items":
        return Item
    else:
        raise ValueError(f"Unknown table: {table_name}")


def execute_query(query: TechDataQuery) -> str:
    """
    Executes a structured query against the technical database and returns a markdown table.

    Uses SQLAlchemy ORM to safely construct queries, preventing injection and ensuring
    proper type handling.

    Args:
        query: The structured TechDataQuery object.

    Returns:
        A Markdown formatted string containing the query results or an error message.
    """
    try:
        model = get_model_class(query.table)

        # --- Build SELECT columns ---
        # Dynamically retrieve column attributes from the model class using getattr().
        # This allows mapping string column names from the query object to actual ORM columns.
        stmt_columns = []
        header_names = []

        for col in query.columns:
            if isinstance(col, str):
                stmt_columns.append(getattr(model, col))
                header_names.append(col)
            elif isinstance(col, Aggregation):
                model_col = getattr(model, col.column)
                # Map aggregation functions to SQLAlchemy func calls
                if col.func == "MIN":
                    stmt_columns.append(func.min(model_col))
                elif col.func == "MAX":
                    stmt_columns.append(func.max(model_col))
                elif col.func == "AVG":
                    stmt_columns.append(func.avg(model_col))
                elif col.func == "SUM":
                    stmt_columns.append(func.sum(model_col))
                elif col.func == "COUNT":
                    stmt_columns.append(func.count(model_col))
                header_names.append(f"{col.func}({col.column})")

        stmt = select(*stmt_columns)

        # --- Build WHERE conditions ---
        clauses = []
        for cond in query.conditions:
            col_attr = getattr(model, cond.column)
            val = cond.value

            if cond.operator == "=":
                clauses.append(col_attr == val)
            elif cond.operator == "!=":
                clauses.append(col_attr != val)
            elif cond.operator == ">":
                clauses.append(col_attr > val)
            elif cond.operator == "<":
                clauses.append(col_attr < val)
            elif cond.operator == ">=":
                clauses.append(col_attr >= val)
            elif cond.operator == "<=":
                clauses.append(col_attr <= val)
            elif cond.operator == "LIKE":
                clauses.append(col_attr.like(val))
            elif cond.operator == "IN":
                # Ensure value is a list for IN operator
                if not isinstance(val, list):
                    val = [val]
                clauses.append(col_attr.in_(val))

        # Apply conditions with specified logic (AND/OR)
        if clauses:
            if query.condition_logic == "AND":
                stmt = stmt.where(and_(*clauses))
            else:
                stmt = stmt.where(or_(*clauses))

        # --- Apply GROUP BY ---
        if query.group_by:
            group_cols = [getattr(model, c) for c in query.group_by]
            stmt = stmt.group_by(*group_cols)

        # --- Apply ORDER BY ---
        if query.order_by:
            order_col = getattr(model, query.order_by)
            if query.order_direction == "DESC":
                stmt = stmt.order_by(desc(order_col))
            else:
                stmt = stmt.order_by(asc(order_col))

        # --- Apply LIMIT ---
        if query.limit:
            stmt = stmt.limit(query.limit)

        # --- Execute and Format ---
        with Session(engine) as session:
            result = session.execute(stmt)
            rows = result.all()

        if not rows:
            return "No results found."

        # Create Markdown Table
        header = "| " + " | ".join(header_names) + " |"
        separator = "| " + " | ".join(["---"] * len(header_names)) + " |"

        lines = [header, separator]
        for row in rows:
            # row is a Row object, can be iterated like a tuple
            lines.append("| " + " | ".join(map(str, row)) + " |")

        return "\n".join(lines)

    except Exception as e:
        return f"Error executing query: {e}"


if __name__ == "__main__":
    # Test case to verify functionality
    q = TechDataQuery(
        table="pokemons",
        columns=["name", "type_1", "attack"],
        conditions=[
            QueryCondition(column="type_1", operator="=", value="fire"),
            QueryCondition(column="attack", operator=">", value=100),
        ],
        order_by="attack",
        order_direction="DESC",
        limit=5,
    )
    print(execute_query(q))
