import pytest
import os
import sys

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    # Create reports directory if it doesn't exist
    if not os.path.exists("reports"):
        os.makedirs("reports")

    # Configure html report path if not provided
    if not getattr(config.option, 'htmlpath', None):
        import datetime

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        config.option.htmlpath = f"reports/test_report_{timestamp}.html"
        config.option.self_contained_html = True
