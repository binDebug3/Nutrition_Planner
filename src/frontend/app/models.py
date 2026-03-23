"""Domain models and constants for the Streamlit nutrient frontend."""

from dataclasses import dataclass
from typing import List, Tuple


QUERY_LIMIT = 2000


DIETARY_TOGGLE_LABELS: List[Tuple[str, str]] = [
    ("gluten_free", "Gluten Free"),
    ("vegan", "Vegan"),
    ("vegetarian", "Vegetarian"),
    ("dairy_free", "Dairy Free"),
    ("nut_free", "Nut-Free"),
]


@dataclass(frozen=True)
class NutrientSpec:
    """
    UI and SQL metadata for a nutrient filter.

    Args:
        key: Stable session-state key prefix.
        label: Display name in the UI.
        db_column: Column name in the food_nutrients table.
        bounds: Inclusive min and max allowed values.
        defaults: Default min and max values.
    """

    key: str
    label: str
    db_column: str
    bounds: Tuple[float, float]
    defaults: Tuple[float, float]


NUTRIENT_SPECS: List[NutrientSpec] = [
    NutrientSpec(
        "kilocalories",
        "Kilocalories",
        "kilocalories",
        (0.0, 4000.0),
        (1800.0, 2200.0),
    ),
    NutrientSpec("fat", "Fat", "fat", (0.0, 100.0), (0.0, 20.0)),
    NutrientSpec(
        "saturated_fat",
        "Saturated Fat",
        "saturated_fat",
        (0.0, 50.0),
        (0.0, 5.0),
    ),
    NutrientSpec(
        "sugar",
        "Sugar",
        "sugar",
        (0.0, 120.0),
        (0.0, 40.0),
    ),
    NutrientSpec("sodium", "Sodium", "sodium", (0.0, 5000.0), (50.0, 1500.0)),
    NutrientSpec(
        "cholesterol",
        "Cholesterol",
        "Cholesterol",
        (0.0, 300.0),
        (0.0, 75.0),
    ),
    NutrientSpec("protein", "Protein", "Protein", (0.0, 100.0), (10.0, 60.0)),
    NutrientSpec(
        "carbs",
        "Carbs",
        "Carbohydrate, by summation",
        (0.0, 150.0),
        (10.0, 80.0),
    ),
    NutrientSpec("iron", "Iron", "iron", (0.0, 45.0), (2.0, 18.0)),
    NutrientSpec("calcium", "Calcium", "calcium", (0.0, 1500.0), (100.0, 900.0)),
    NutrientSpec(
        "potassium",
        "Potassium",
        "potassium",
        (0.0, 5000.0),
        (200.0, 3500.0),
    ),
    NutrientSpec("fiber", "Fiber", "fiber", (0.0, 80.0), (5.0, 35.0)),
    NutrientSpec("vitamin_a", "Vitamin A", "vitamin_a", (0.0, 3000.0), (100.0, 900.0)),
    NutrientSpec(
        "vitamin_b",
        "Vitamin B",
        "vitamin_b",
        (0.0, 10.0),
        (0.1, 2.0),
    ),
    NutrientSpec(
        "vitamin_c",
        "Vitamin C",
        "vitamin_c",
        (0.0, 2000.0),
        (10.0, 250.0),
    ),
    NutrientSpec(
        "vitamin_d",
        "Vitamin D",
        "vitamin_d",
        (0.0, 200.0),
        (2.0, 50.0),
    ),
    NutrientSpec(
        "vitamin_e",
        "Vitamin E",
        "vitamin_e",
        (0.0, 100.0),
        (1.0, 20.0),
    ),
    NutrientSpec(
        "vitamin_k",
        "Vitamin K",
        "vitamin_k",
        (0.0, 500.0),
        (5.0, 150.0),
    ),
]
