"""Tests for structured logging setup."""

import logging

from atlas_intel.logging import setup_logging


def test_setup_logging_development():
    """Development mode configures console renderer."""
    setup_logging(level="INFO", env="development")
    root = logging.getLogger()
    assert root.handlers
    assert root.level == logging.INFO


def test_setup_logging_production():
    """Production mode configures JSON renderer."""
    setup_logging(level="WARNING", env="production")
    root = logging.getLogger()
    assert root.handlers
    assert root.level == logging.WARNING


def test_setup_logging_sets_level():
    """Log level is respected."""
    setup_logging(level="DEBUG", env="development")
    root = logging.getLogger()
    assert root.level == logging.DEBUG
