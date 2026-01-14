import sys
import unittest
from db_tech.tech_data_tool import (
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
        # Should be a number
        self.assertNotIn("No results found", result)
        self.assertIn("MAX(speed)", result)

    def test_condition_operators(self):
        # Test > operator
        query = TechDataQuery(
            table="moves",
            columns=["name", "power"],
            conditions=[QueryCondition(column="power", operator=">", value=150)],
            limit=5,
        )
        result = execute_query(query)
        self.assertNotIn("No results found", result)
        # e.g. explosion, self-destruct

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
        # Not a real join test, but testing the string field 'weak_against_1'
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
        # Test SUM and AVG
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
        # Test OR logic (Fire type OR water type)
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
        # It's possible the list only contains fire if we limit to 5, so explicit check might be tricky without ordering
        # But we mostly want to ensure it executes without error.

    def test_in_operator(self):
        # Test IN operator
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
