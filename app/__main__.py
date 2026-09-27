"""
makes `python -m app` work
"""
from app.render import enable_utf8

# force utf-8 before typer renders --help, otherwise a cp1251 console mangles the text
enable_utf8()

from app.main import app  # noqa: E402

if __name__ == "__main__":
    app()
