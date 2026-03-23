"""SQL query construction for frontend food retrieval."""

from typing import List

from models import QUERY_LIMIT, NutrientSpec


class FoodQueryBuilder:
    """
    Build SQL query text for nutrient candidate retrieval.

    Args:
        logger: Logger used for query-build events.
    """

    def __init__(self, logger: object) -> None:
        """
        Initialize the query builder.

        Args:
            logger: Logger instance for query logging.
        """
        self._query_log = logger

    def build_where_clauses(self, specs: List[NutrientSpec]) -> List[str]:
        """
        Build SQL filter clauses.

        Args:
            specs: Nutrient specifications.

        Returns:
            SQL predicate fragments.
        """
        self._query_log.info(
            "Building nutrient SQL predicates",
            extra={"event": "query.sql.where_build"},
        )
        _ = specs
        return ["1=1"]

    def build_food_query(self, specs: List[NutrientSpec]) -> str:
        """
        Build the SQL query for the food table.

        Args:
            specs: Nutrient specifications.

        Returns:
            SQL query string.
        """
        self._query_log.info(
            "Constructing food SQL query",
            extra={"event": "query.sql.build"},
        )
        where_sql = "\n        AND ".join(self.build_where_clauses(specs))
        cte_sql = self._build_nutrient_view_cte()
        select_sql = self._build_select_projection()
        return (
            f"\n        WITH nutrient_view AS (\n{cte_sql}\n        )\n"
            f"{select_sql}\n        FROM nutrient_view\n        "
            f"WHERE {where_sql}\n        ORDER BY protein DESC\n"
            f"        LIMIT {QUERY_LIMIT}\n    "
        )

    def _build_nutrient_view_cte(self) -> str:
        """
        Build the nutrient_view CTE body.

        Returns:
            SQL for the CTE select statement.
        """
        self._query_log.info(
            "Building nutrient view CTE",
            extra={"event": "query.sql.cte"},
        )
        return """
            SELECT
                fdc_id,
                "Value" AS value,
                food_name,
                serving_size,
                "Energy [id:1008]" AS kilocalories,
                "Total lipid (fat)" AS fat,
                "Fatty acids, total saturated" AS saturated_fat,
                COALESCE("Sugars, Total", "Total Sugars") AS sugar,
                "Sodium, Na" AS sodium,
                "Cholesterol" AS cholesterol,
                "Protein" AS protein,
                COALESCE(
                    "Carbohydrate, by difference",
                    "Carbohydrate, by summation"
                ) AS carbs,
                "Iron, Fe" AS iron,
                "Calcium, Ca" AS calcium,
                "Potassium, K" AS potassium,
                "Fiber, total dietary" AS fiber,
                "Vitamin A, RAE" AS vitamin_a,
                "Thiamin" AS vitamin_b,
                "Vitamin C, total ascorbic acid" AS vitamin_c,
                "Vitamin D (D2 + D3)" AS vitamin_d,
                "Vitamin E (alpha-tocopherol)" AS vitamin_e,
                "Vitamin K (phylloquinone)" AS vitamin_k
            FROM food_nutrients
        """

    def _build_select_projection(self) -> str:
        """
        Build the final SELECT projection.

        Returns:
            SQL projection clause for nutrient_view.
        """
        self._query_log.info(
            "Building final SQL projection",
            extra={"event": "query.sql.projection"},
        )
        return """
        SELECT
            fdc_id,
            value,
            food_name,
            serving_size,
            kilocalories,
            fat,
            saturated_fat,
            sugar,
            sodium,
            cholesterol,
            protein,
            carbs,
            iron,
            calcium,
            potassium,
            fiber,
            vitamin_a,
            vitamin_b,
            vitamin_c,
            vitamin_d,
            vitamin_e,
            vitamin_k
        """
