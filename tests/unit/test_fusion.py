"""Unit tests for fusion signal computations."""

from atlas_intel.schemas.fusion import SignalComponent
from atlas_intel.services.fusion_service import _weighted_composite


class TestWeightedComposite:
    def test_all_components_available(self):
        components = [
            SignalComponent(name="a", score=0.8, has_data=True),
            SignalComponent(name="b", score=0.4, has_data=True),
            SignalComponent(name="c", score=-0.2, has_data=True),
        ]
        weights = {"a": 0.5, "b": 0.3, "c": 0.2}
        score, confidence = _weighted_composite(components, weights)
        assert confidence == 1.0
        assert score is not None
        expected = 0.5 * 0.8 + 0.3 * 0.4 + 0.2 * (-0.2)
        assert abs(score - expected) < 0.001

    def test_missing_component_renormalized(self):
        components = [
            SignalComponent(name="a", score=0.6, has_data=True),
            SignalComponent(name="b", score=None, has_data=False),
            SignalComponent(name="c", score=0.4, has_data=True),
        ]
        weights = {"a": 0.5, "b": 0.3, "c": 0.2}
        score, confidence = _weighted_composite(components, weights)
        # confidence: 2/3 components
        assert abs(confidence - 2 / 3) < 0.001
        # renormalized weights: a=0.5/0.7, c=0.2/0.7
        expected = 0.6 * (0.5 / 0.7) + 0.4 * (0.2 / 0.7)
        assert score is not None
        assert abs(score - expected) < 0.001

    def test_no_data_returns_none(self):
        components = [
            SignalComponent(name="a", score=None, has_data=False),
            SignalComponent(name="b", score=None, has_data=False),
        ]
        weights = {"a": 0.5, "b": 0.5}
        score, confidence = _weighted_composite(components, weights)
        assert score is None
        assert confidence == 0.0

    def test_single_component(self):
        components = [
            SignalComponent(name="a", score=0.5, has_data=True),
        ]
        weights = {"a": 1.0}
        score, confidence = _weighted_composite(components, weights)
        assert score == 0.5
        assert confidence == 1.0

    def test_weights_updated_on_components(self):
        components = [
            SignalComponent(name="a", score=0.6, has_data=True),
            SignalComponent(name="b", score=None, has_data=False),
        ]
        weights = {"a": 0.6, "b": 0.4}
        _weighted_composite(components, weights)
        assert components[0].weight == 1.0  # renormalized (0.6/0.6)
        assert components[1].weight == 0.0
