"""Session state helpers for nutrient filter controls."""

from typing import Dict, List

from models import NutrientSpec
from optimize import SliderBounds


class NutrientStateManager:
    """
    Manage Streamlit session-state for nutrient controls.

    Args:
        streamlit_module: Streamlit module or a fake module in tests.
        logger: Logger used for app-level UI events.
    """

    def __init__(self, streamlit_module: object, logger: object) -> None:
        """
        Store the external dependencies used by helper methods.

        Args:
            streamlit_module: Streamlit module-like object.
            logger: Logger for state events.
        """
        self._st = streamlit_module
        self._log = logger

    def any_key(self, spec: NutrientSpec) -> str:
        """
        Return the session-state key for the Any toggle.

        Args:
            spec: Nutrient specification.

        Returns:
            Session-state key.
        """
        self._log.debug(
            "Building Any toggle key",
            extra={"event": "ui.key.any", "nutrient": spec.key},
        )
        return f"{spec.key}_any"

    def slider_key(self, spec: NutrientSpec) -> str:
        """
        Return the session-state key for the range slider.

        Args:
            spec: Nutrient specification.

        Returns:
            Session-state key.
        """
        self._log.debug(
            "Building slider key",
            extra={"event": "ui.key.slider", "nutrient": spec.key},
        )
        return f"{spec.key}_slider"

    def min_key(self, spec: NutrientSpec) -> str:
        """
        Return the session-state key for the min input.

        Args:
            spec: Nutrient specification.

        Returns:
            Session-state key.
        """
        self._log.debug(
            "Building min input key",
            extra={"event": "ui.key.min", "nutrient": spec.key},
        )
        return f"{spec.key}_min"

    def max_key(self, spec: NutrientSpec) -> str:
        """
        Return the session-state key for the max input.

        Args:
            spec: Nutrient specification.

        Returns:
            Session-state key.
        """
        self._log.debug(
            "Building max input key",
            extra={"event": "ui.key.max", "nutrient": spec.key},
        )
        return f"{spec.key}_max"

    def coerce_float(self, value: object, fallback: float) -> float:
        """
        Convert a value to float with a fallback.

        Args:
            value: Raw value from session state.
            fallback: Value returned when conversion fails.

        Returns:
            Float value.
        """
        self._log.debug("Coercing numeric value", extra={"event": "ui.value.coerce"})
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    def clamp(self, value: float, lower: float, upper: float) -> float:
        """
        Clamp a value into an inclusive range.

        Args:
            value: Value to clamp.
            lower: Inclusive lower bound.
            upper: Inclusive upper bound.

        Returns:
            Clamped value.
        """
        self._log.debug("Clamping numeric value", extra={"event": "ui.value.clamp"})
        return max(lower, min(value, upper))

    def initialize_nutrient_state(self, spec: NutrientSpec) -> None:
        """
        Seed session state keys for a nutrient filter.

        Args:
            spec: Nutrient specification.
        """
        self._log.debug(
            "Initializing nutrient session state",
            extra={"event": "ui.nutrient.initialize", "nutrient": spec.key},
        )
        any_key = self.any_key(spec)
        slider_key = self.slider_key(spec)
        min_key = self.min_key(spec)
        max_key = self.max_key(spec)

        if any_key not in self._st.session_state:
            self._st.session_state[any_key] = True

        if slider_key not in self._st.session_state:
            self._st.session_state[slider_key] = spec.defaults

        if min_key not in self._st.session_state:
            self._st.session_state[min_key] = spec.defaults[0]

        if max_key not in self._st.session_state:
            self._st.session_state[max_key] = spec.defaults[1]

    def set_all_any_toggles(
        self,
        specs: List[NutrientSpec],
        enabled: bool,
    ) -> None:
        """
        Set the Any toggle state for every nutrient filter.

        Args:
            specs: Nutrient specifications to update.
            enabled: Desired Any toggle state.
        """
        self._log.info(
            "Updating all Any toggles",
            extra={
                "event": "ui.nutrient.any.bulk_update",
                "enabled": enabled,
                "nutrient_count": len(specs),
            },
        )
        for spec in specs:
            self._st.session_state[self.any_key(spec)] = enabled

    def sync_inputs_from_slider(self, spec: NutrientSpec) -> None:
        """
        Keep min and max inputs aligned with the slider selection.

        Args:
            spec: Nutrient specification.
        """
        self._log.debug(
            "Syncing numeric inputs from slider",
            extra={"event": "ui.sync.from_slider", "nutrient": spec.key},
        )
        slider_value = self._st.session_state[self.slider_key(spec)]
        slider_min, slider_max = tuple(slider_value)
        self._st.session_state[self.min_key(spec)] = float(slider_min)
        self._st.session_state[self.max_key(spec)] = float(slider_max)

    def sync_slider_from_inputs(self, spec: NutrientSpec) -> None:
        """
        Keep slider aligned with manual min and max inputs.

        Args:
            spec: Nutrient specification.
        """
        self._log.debug(
            "Syncing slider from numeric inputs",
            extra={"event": "ui.sync.from_inputs", "nutrient": spec.key},
        )
        lower, upper = spec.bounds
        raw_min = self.coerce_float(
            self._st.session_state.get(self.min_key(spec)),
            spec.defaults[0],
        )
        raw_max = self.coerce_float(
            self._st.session_state.get(self.max_key(spec)),
            spec.defaults[1],
        )
        bounded_min = self.clamp(raw_min, lower, upper)
        bounded_max = self.clamp(raw_max, lower, upper)
        self._st.session_state[self.min_key(spec)] = bounded_min
        self._st.session_state[self.max_key(spec)] = bounded_max

        if bounded_min < bounded_max:
            self._st.session_state[self.slider_key(spec)] = (bounded_min, bounded_max)

    def is_invalid_range(self, spec: NutrientSpec) -> bool:
        """
        Return True when active manual bounds are invalid.

        Args:
            spec: Nutrient specification.

        Returns:
            Whether the current min/max pair is invalid.
        """
        self._log.debug(
            "Validating nutrient range",
            extra={"event": "ui.validate.range", "nutrient": spec.key},
        )
        if not self._st.session_state.get(self.any_key(spec), False):
            return False
        min_value = self.coerce_float(
            self._st.session_state.get(self.min_key(spec)),
            spec.defaults[0],
        )
        max_value = self.coerce_float(
            self._st.session_state.get(self.max_key(spec)),
            spec.defaults[1],
        )
        return min_value >= max_value

    def build_slider_bounds(self, specs: List[NutrientSpec]) -> SliderBounds:
        """
        Build optimization bounds from current nutrient slider controls.

        Args:
            specs: Nutrient specifications.

        Returns:
            Dataclass containing per-nutrient min and max limits.
        """
        self._log.info(
            "Building optimization bounds", extra={"event": "optimizer.bounds.build"}
        )
        minimums: Dict[str, float | None] = {}
        maximums: Dict[str, float | None] = {}

        for spec in specs:
            column_name = spec.db_column
            if not self._st.session_state.get(self.any_key(spec), False):
                minimums[column_name] = None
                maximums[column_name] = None
                continue
            min_value = self.coerce_float(
                self._st.session_state.get(self.min_key(spec)),
                spec.defaults[0],
            )
            max_value = self.coerce_float(
                self._st.session_state.get(self.max_key(spec)),
                spec.defaults[1],
            )
            minimums[column_name] = min_value
            maximums[column_name] = max_value

        return SliderBounds(minimums=minimums, maximums=maximums)
