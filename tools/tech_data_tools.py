from enum import StrEnum
from typing import List, Optional, Any, Literal, Union, Type
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select, func, desc, asc, and_, or_, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ai_tools.tool_definition import tool
from data.models import Pokemon, Move, Item, Base
from utils.config import settings

# ---------------------------------------------------------------------------
# Lazy singleton — the engine is created on first use, not at import time.
# ---------------------------------------------------------------------------

_engine: "Engine | None" = None


def _get_engine() -> "Engine":
    """Return (and lazily create) the shared SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(f"sqlite:///{settings.TECH_DB_PATH}")
    return _engine


def create_column_enum(model_class: Type[Base], enum_name: str) -> Any:
    """
    Dynamically creates a StrEnum from a SQLAlchemy model's columns.
    Using StrEnum allows Pydantic to serialize values as strings and
    enables direct comparison with column names.
    """
    columns = {c.name.upper(): c.name for c in inspect(model_class).columns}
    return StrEnum(enum_name, columns)


# Explicit column definitions for better agent awareness
PokemonColumn = create_column_enum(Pokemon, "PokemonColumn")
MoveColumn = create_column_enum(Move, "MoveColumn")
ItemColumn = create_column_enum(Item, "ItemColumn")

AnyColumn = Union[PokemonColumn, MoveColumn, ItemColumn]


class FilterCondition(BaseModel):
    """
    A single filter condition applying a comparison operator to a column.
    """

    column: AnyColumn = Field(
        ..., description="The name of the database column to filter on."
    )
    operator: Literal["=", ">", "<", ">=", "<=", "!=", "LIKE", "IN"] = Field(
        ...,
        description="The comparison operator (e.g., '=', '>', 'LIKE', 'IN'). Use 'LIKE' with '%' for pattern matching. Use 'IN' for a list of values.",
    )
    value: Any = Field(
        ...,
        description="The value to compare against. Provide a list of values if using the 'IN' operator.",
    )


class FilterGroup(BaseModel):
    """
    A group of filter conditions or nested groups combined by a logical operator.
    Allows for complex, nested Boolean logic (e.g., (A AND B) OR C).
    """

    logic: Literal["AND", "OR"] = Field(
        "AND",
        description="The logical operator used to combine filters in this group. Note: In SQL, AND has higher precedence than OR.",
    )
    filters: List[Union["FilterGroup", FilterCondition]] = Field(
        ...,
        description="A list of conditions or nested filter groups to be combined.",
    )


# Rebuild to support recursive definition
FilterGroup.model_rebuild()


class Aggregation(BaseModel):
    """
    Represents a SQL aggregation function (like COUNT, AVG) performed on a column.
    """

    func: Literal["MIN", "MAX", "AVG", "SUM", "COUNT"] = Field(
        ..., description="The SQL aggregation function to apply."
    )
    column: AnyColumn = Field(..., description="The column to aggregate.")


class TechDataQuery(BaseModel):
    """
    Structured representation of a technical data query for the Pokemon database.
    This model defines the SELECT, WHERE, GROUP BY, and ORDER BY clauses.
    """

    table: Literal["pokemons", "moves", "items"] = Field(
        ..., description="The database table to query."
    )
    columns: List[Union[AnyColumn, Aggregation]] = Field(
        ...,
        description="List of columns to retrieve. Can include specific column names or aggregation functions (e.g., MIN(attack)).",
    )
    where: Optional[FilterGroup] = Field(
        None,
        description="Optional filter criteria for the query. Supports nested AND/OR logic. Example: {'logic': 'OR', 'filters': [{'column': 'type_1', 'operator': '=', 'value': 'fire'}, {'logic': 'AND', 'filters': [...]}]}",
    )
    group_by: Optional[List[AnyColumn]] = Field(
        None,
        description="Optional list of columns to group the results by. Required when using aggregations.",
    )
    order_by: Optional[AnyColumn] = Field(
        None, description="Optional column name to sort the results by."
    )
    order_direction: Literal["ASC", "DESC"] = Field(
        "ASC", description="The sort direction: ASC (ascending) or DESC (descending)."
    )
    limit: Optional[int] = Field(
        None, description="The maximum number of rows to return (default is all matches)."
    )


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


def _build_clauses(model: Type[Base], filter_node: Union[FilterGroup, FilterCondition]) -> Any:
    """Recursively builds SQLAlchemy Boolean clauses from FilterGroup/FilterCondition."""
    if isinstance(filter_node, FilterCondition):
        col_attr = getattr(model, filter_node.column)
        val = filter_node.value

        if filter_node.operator == "=":
            return col_attr == val
        elif filter_node.operator == "!=":
            return col_attr != val
        elif filter_node.operator == ">":
            return col_attr > val
        elif filter_node.operator == "<":
            return col_attr < val
        elif filter_node.operator == ">=":
            return col_attr >= val
        elif filter_node.operator == "<=":
            return col_attr <= val
        elif filter_node.operator == "LIKE":
            return col_attr.like(val)
        elif filter_node.operator == "IN":
            if not isinstance(val, list):
                val = [val]
            return col_attr.in_(val)
        else:
            raise ValueError(f"Unsupported operator: {filter_node.operator}")

    elif isinstance(filter_node, FilterGroup):
        clauses = [_build_clauses(model, f) for f in filter_node.filters]
        if not clauses:
            return None
        if filter_node.logic == "AND":
            return and_(*clauses)
        else:
            return or_(*clauses)
    return None


def _execute_query(query: TechDataQuery) -> str:
    """
    Executes a structured query against the technical database and returns a markdown table.
    """
    try:
        model = get_model_class(query.table)

        # --- Build SELECT columns ---
        stmt_columns = []
        header_names = []

        for col in query.columns:
            if isinstance(col, (str, PokemonColumn, MoveColumn, ItemColumn)):
                stmt_columns.append(getattr(model, col))
                header_names.append(str(col))
            elif isinstance(col, Aggregation):
                model_col = getattr(model, col.column)
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

        # --- Build WHERE clauses ---
        if query.where:
            clause = _build_clauses(model, query.where)
            if clause is not None:
                stmt = stmt.where(clause)

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
        with Session(_get_engine()) as session:
            result = session.execute(stmt)
            rows = result.all()

        if not rows:
            return "No results found."

        # Create Markdown Table
        header = "| " + " | ".join(header_names) + " |"
        separator = "| " + " | ".join(["---"] * len(header_names)) + " |"

        lines = [header, separator]
        for row in rows:
            lines.append("| " + " | ".join(map(str, row)) + " |")

        return "\n".join(lines)

    except Exception as e:
        return f"Error executing query: {e}"


@tool(schema=TechDataQuery)
def execute_query(query: TechDataQuery) -> str:
    """
    Executes a structured technical query against the Pokemon database (pokemons, moves, items).
    Supports filtering with nested AND/OR logic, aggregations, grouping, and sorting.
    Returns the result as a Markdown table.

    Examples for the Agent:

    1. Simple Filter: "Get names of Fire pokemon with attack > 100"
       {
         "table": "pokemons",
         "columns": ["name", "attack"],
         "where": {
           "logic": "AND",
           "filters": [
             {"column": "type_1", "operator": "=", "value": "fire"},
             {"column": "attack", "operator": ">", "value": 100},
             {"column": "is_default", "operator": "=", "value": true}
           ]
         }
       }

    2. Aggregation & Grouping: "Count pokemon per primary type"
       {
         "table": "pokemons",
         "columns": ["type_1", {"func": "COUNT", "column": "id"}],
         "group_by": ["type_1"],
         "order_by": "type_1"
       }

    3. Complex Nested Logic: "(Type is Fire AND Attack > 100) OR (Type is Water AND Speed > 100)"
       {
         "table": "pokemons",
         "columns": ["name", "type_1", "attack", "speed"],
         "where": {
           "logic": "OR",
           "filters": [
             {
               "logic": "AND",
               "filters": [
                 {"column": "type_1", "operator": "=", "value": "fire"},
                 {"column": "attack", "operator": ">", "value": 100}
               ]
             },
             {
               "logic": "AND",
               "filters": [
                 {"column": "type_1", "operator": "=", "value": "water"},
                 {"column": "speed", "operator": ">", "value": 100}
               ]
             }
           ]
         }
       }
    """
    return _execute_query(query)


TOOL_FUNCTIONS = [execute_query]


if __name__ == "__main__":
    # Test complex nesting: (type_1 = fire AND attack > 100) OR type_1 = water
    q = TechDataQuery(
        table="pokemons",
        columns=["name", "type_1", "attack"],
        where=FilterGroup(
            logic="OR",
            filters=[
                FilterGroup(
                    logic="AND",
                    filters=[
                        FilterCondition(column="type_1", operator="=", value="fire"),
                        FilterCondition(column="attack", operator=">", value=100),
                    ]
                ),
                FilterCondition(column="type_1", operator="=", value="water"),
            ]
        ),
        order_by="attack",
        order_direction="DESC",
        limit=10,
    )
    print("Executing query...")
    print(execute_query(q))
