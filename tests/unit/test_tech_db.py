"""
Unit tests for tools.tech_data_tools.

execute_query now receives a validated TechDataQuery instance (via @tool dispatcher).
Direct calls pass the model instance; validation error testing goes through handle_tool_call.
"""

import json
import unittest
from tools.tech_data_tools import (
    execute_query,
    TechDataQuery,
    FilterCondition,
    FilterGroup,
    Aggregation,
)
from ai_tools.utils import handle_tool_call


class TestTechDataTool(unittest.TestCase):
    def test_simple_select(self):
        query = TechDataQuery(
            table="pokemons",
            columns=["name", "hit_points"],
            where=FilterGroup(
                filters=[FilterCondition(column="name", operator="=", value="bulbasaur")]
            ),
            limit=1,
        )
        result = execute_query(query)
        self.assertIn("bulbasaur", result)
        self.assertIn("45", result)  # HP of bulbasaur

    def test_aggregation_max(self):
        query = TechDataQuery(
            table="pokemons",
            columns=[Aggregation(func="MAX", column="speed")],
            where=None,
        )
        result = execute_query(query)
        self.assertNotIn("No results found", result)
        self.assertIn("MAX(speed)", result)

    def test_condition_operators(self):
        query = TechDataQuery(
            table="moves",
            columns=["name", "power"],
            where=FilterGroup(
                filters=[FilterCondition(column="power", operator=">", value=150)]
            ),
            limit=5,
        )
        result = execute_query(query)
        self.assertNotIn("No results found", result)

    def test_group_by(self):
        query = TechDataQuery(
            table="items",
            columns=["category", Aggregation(func="COUNT", column="id")],
            where=None,
            group_by=["category"],
            order_by="category",
            limit=5,
        )
        result = execute_query(query)
        self.assertNotIn("No results found", result)
        self.assertIn("COUNT(id)", result)

    def test_joins_implicit_via_weakness(self):
        query = TechDataQuery(
            table="pokemons",
            columns=["name", "weak_against_1"],
            where=FilterGroup(
                filters=[FilterCondition(column="name", operator="=", value="charizard")]
            ),
            limit=1,
        )
        result = execute_query(query)
        self.assertIn("charizard", result)
        self.assertIn("rock", result)

    def test_aggregation_sum_avg(self):
        query = TechDataQuery(
            table="pokemons",
            columns=[
                Aggregation(func="AVG", column="attack"),
                Aggregation(func="SUM", column="base_experience"),
            ],
            where=FilterGroup(
                filters=[FilterCondition(column="type_1", operator="=", value="fire")]
            ),
        )
        result = execute_query(query)
        self.assertNotIn("No results found", result)
        self.assertIn("AVG(attack)", result)
        self.assertIn("SUM(base_experience)", result)

    def test_complex_logic_or(self):
        query = TechDataQuery(
            table="pokemons",
            columns=["name", "type_1"],
            where=FilterGroup(
                logic="OR",
                filters=[
                    FilterCondition(column="type_1", operator="=", value="fire"),
                    FilterCondition(column="type_1", operator="=", value="water"),
                ],
            ),
            limit=5,
        )
        result = execute_query(query)
        self.assertIn("fire", result)

    def test_in_operator(self):
        query = TechDataQuery(
            table="items",
            columns=["name", "cost"],
            where=FilterGroup(
                filters=[
                    FilterCondition(
                        column="name", operator="IN", value=["potion", "antidote"]
                    )
                ]
            ),
        )
        result = execute_query(query)
        self.assertIn("potion", result)
        self.assertIn("antidote", result)

    def test_validation_error_returns_error_via_dispatcher(self):
        """Bad args dispatched through handle_tool_call return a readable error string."""
        bad_call = {
            "id": "c1",
            "function": {
                "name": "execute_query",
                # 'table' is invalid (not "pokemons"/"moves"/"items"), triggering ValidationError
                "arguments": json.dumps(
                    {"table": "invalid_table", "columns": ["name"]}
                ),
            },
        }
        results = handle_tool_call([bad_call], [execute_query])
        self.assertIn("Error", results[0]["output"])


if __name__ == "__main__":
    unittest.main()
