import json

from typer.testing import CliRunner

from app import __version__
from app.main import app

runner = CliRunner()

STDIN_TB = '''Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
    boom()
KeyError: 'user_id'
'''


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_stdin_json_output():
    result = runner.invoke(app, ["--json"], input=STDIN_TB)
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["exception"]["type"] == "KeyError"
    assert payload["frames_count"] == 1
    assert payload["suspects"][0]["function"] == "<module>"


def test_no_frames_errors():
    result = runner.invoke(app, ["--json"], input="there are no frames in here")
    assert result.exit_code == 1


def test_file_input_with_git_repo(repo):
    p = repo.write("pkg/views.py", "def get_user():\n    return users['id']\n")
    repo.commit("add get_user", days_ago=1, author="Alice")

    tb = (
        "Traceback (most recent call last):\n"
        f'  File "{p}", line 2, in get_user\n'
        "    return users['id']\n"
        "KeyError: 'id'\n"
    )
    log = repo.path / "tb.txt"
    log.write_text(tb, encoding="utf-8")

    result = runner.invoke(app, [str(log), "--no-color"])
    assert result.exit_code == 0
    assert "Alice" in result.stdout
    assert "Top suspect" in result.stdout
