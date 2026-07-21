"""
Application Factory 示例入口。

Application Factory example entry point.

运行 / Run::

    .venv\\Scripts\\python.exe examples\\application_factory\\run.py
"""

from __future__ import annotations

from app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
