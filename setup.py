"""Setup script for Congress Tracker."""

from setuptools import setup, find_packages

setup(
    name="congress_tracker",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "httpx>=0.27.0",
        "tenacity>=8.2.3",
        "sqlalchemy>=2.0.25",
        "anthropic>=0.42.0",
        "atproto>=0.0.55",
        "python-dateutil>=2.8.2",
        "python-dotenv>=1.0.0",
        "click>=8.1.7",
        "pydantic>=2.5.3",
        "structlog>=24.1.0",
    ],
    entry_points={
        "console_scripts": [
            "congress-tracker=congress_tracker.cli:cli",
        ],
    },
    python_requires=">=3.10",
)
