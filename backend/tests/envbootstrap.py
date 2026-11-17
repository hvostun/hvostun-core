"""Must be imported before app.core.config so Settings bind to hvostun_test."""

import os

os.environ["FASTAPI_ENV"] = "test"
