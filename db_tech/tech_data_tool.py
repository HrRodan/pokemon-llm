import sqlite3
from typing import List, Optional, Any, Literal, Union
from pydantic import BaseModel, Field

DB_PATH = "db_tech/tech.db"

# Explicit column definitions for better agent awareness
PokemonColumn = Literal[
    "id",
    "name",
    "hit_points",
    "attack",
    "defense",
    "special_attack",
    "special_defense",
    "speed",
    "type_1",
    "type_2",
    "ability_1",
    "ability_2",
    "ability_hidden",
    "height_m",
    "weight_kg",
    "base_experience",
    "base_happiness",
    "capture_rate",
    "hatch_counter",
    "is_legendary",
    "is_mythical",
    "generation",
    "weak_against_1",
    "weak_against_2",
    "strong_against_1",
    "strong_against_2",
]

MoveColumn = Literal[
    "id",
    "name",
    "type",
    "power",
    "accuracy",
    "power_points",
    "damage_class",
    "priority",
    "generation",
]

ItemColumn = Literal[
    "id",
    "name",
    "cost",
    "category",
    "generation",
    "effect",
]

# Combined column type for queries that might target any table (though 'table' field restricts context)
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


def execute_query(query: TechDataQuery) -> str:
    """
    Executes a structured query against the technical database and returns a markdown table.

    Args:
        query: The structured TechDataQuery object.

    Returns:
        A Markdown formatted string containing the query results or an error message.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Construct SELECT
        select_parts : List[str] = []
        for col in query.columns:
            if isinstance(col, str):
                select_parts.append(col)
            elif isinstance(col, Aggregation):
                select_parts.append(f"{col.func}({col.column})")
            else:
                # Pydantic handles the Union, but static analysis might complain or if passed directly
                # In runtime with correct model, this is covered.
                pass

        select_clause = ", ".join(select_parts)

        sql = f"SELECT {select_clause} FROM {query.table}"
        params : List[Any] = []

        # Construct WHERE
        if query.conditions:
            where_parts : List[str] = []
            for cond in query.conditions:
                if cond.operator == "IN":
                    if isinstance(cond.value, list):
                        placeholders = ", ".join(["?"] * len(cond.value))
                        where_parts.append(f"{cond.column} IN ({placeholders})")
                        params.extend(cond.value)
                    else:
                        where_parts.append(f"{cond.column} IN (?)")
                        params.append(cond.value)
                else:
                    where_parts.append(f"{cond.column} {cond.operator} ?")
                    params.append(cond.value)

            logic = f" {query.condition_logic} "
            sql += f" WHERE {logic.join(where_parts)}"

        # GROUP BY
        if query.group_by:
            sql += f" GROUP BY {', '.join(query.group_by)}"

        # ORDER BY
        if query.order_by:
            sql += f" ORDER BY {query.order_by} {query.order_direction}"

        # LIMIT
        if query.limit:
            sql += f" LIMIT {query.limit}"

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]

        # Format as Markdown
        if not rows:
            return "No results found."

        header = "| " + " | ".join(columns) + " |"
        separator = "| " + " | ".join(["---"] * len(columns)) + " |"

        lines = [header, separator]
        for row in rows:
            lines.append("| " + " | ".join(map(str, row)) + " |")

        return "\n".join(lines)

    except Exception as e:
        return f"Error executing query: {e}"
    finally:
        conn.close()


if __name__ == "__main__":
    # Simple test
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
