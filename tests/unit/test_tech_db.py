"""
Unit tests for tools.tech_data_tools.
"""

import unittest
from tools.tech_data_tools import (
    execute_query,
    TechDataQuery,
    QueryCondition,
    Aggregation,
)


class TestTechDataTool(unittest.TestCase):
    def test_simple_select(self):
        query = TechDataQuery(
            table="pokemons",
            columns=["name", "hit_points"],
            conditions=[QueryCondition(column="name", operator="=", value="bulbasaur")],
            limit=1,
        )
        result = execute_query(query)
        self.assertIn("bulbasaur", result)
        self.assertIn("45", result)  # HP of bulbasaur

    def test_aggregation_max(self):
        query = TechDataQuery(
            table="pokemons",
            columns=[Aggregation(func="MAX", column="speed")],
            conditions=[],
        )
        result = execute_query(query)
        self.assertNotIn("No results found", result)
        self.assertIn("MAX(speed)", result)

    def test_condition_operators(self):
        query = TechDataQuery(
            table="moves",
            columns=["name", "power"],
            conditions=[QueryCondition(column="power", operator=">", value=150)],
            limit=5,
        )
        result = execute_query(query)
        self.assertNotIn("No results found", result)

    def test_group_by(self):
        query = TechDataQuery(
            table="items",
            columns=["category", Aggregation(func="COUNT", column="id")],
            conditions=[],
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
            conditions=[QueryCondition(column="name", operator="=", value="charizard")],
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
            conditions=[QueryCondition(column="type_1", operator="=", value="fire")],
        )
        result = execute_query(query)
        self.assertNotIn("No results found", result)
        self.assertIn("AVG(attack)", result)
        self.assertIn("SUM(base_experience)", result)

    def test_complex_logic_or(self):
        query = TechDataQuery(
            table="pokemons",
            columns=["name", "type_1"],
            conditions=[
                QueryCondition(column="type_1", operator="=", value="fire"),
                QueryCondition(column="type_1", operator="=", value="water"),
            ],
            condition_logic="OR",
            limit=5,
        )
        result = execute_query(query)
        self.assertIn("fire", result)

    def test_in_operator(self):
        query = TechDataQuery(
            table="items",
            columns=["name", "cost"],
            conditions=[
                QueryCondition(
                    column="name", operator="IN", value=["potion", "antidote"]
                )
            ],
        )
        result = execute_query(query)
        self.assertIn("potion", result)
        self.assertIn("antidote", result)


if __name__ == "__main__":
    unittest.main()
