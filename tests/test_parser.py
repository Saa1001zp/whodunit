from app.parser import parse_traceback

BASIC = '''Traceback (most recent call last):
  File "app/views.py", line 88, in get_user
    return users[user_id]
  File "app/api.py", line 12, in handle
    return get_user(uid)
KeyError: 'user_id'
'''

SYNTAX = '''  File "bad.py", line 1
    x ===
      ^
SyntaxError: invalid syntax
'''

PSEUDO = '''Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "<frozen importlib._bootstrap>", line 1007, in _find_and_load
KeyError: 'x'
'''

CHAINED = '''Traceback (most recent call last):
  File "a.py", line 1, in <module>
    1 / 0
ZeroDivisionError: division by zero

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "a.py", line 3, in <module>
    raise RuntimeError("boom")
RuntimeError: boom
'''

CARET = '''Traceback (most recent call last):
  File "m.py", line 2, in <module>
    print(x["y"])
          ~^^^^^
KeyError: 'y'
'''


def test_basic_frames():
    info = parse_traceback(BASIC)
    assert len(info.frames) == 2
    first = info.frames[0]
    assert first.file == "app/views.py"
    assert first.line == 88
    assert first.func == "get_user"
    assert first.source == "return users[user_id]"
    assert info.exc_type == "KeyError"
    assert info.exc_message == "'user_id'"


def test_depth_last_is_exception_point():
    info = parse_traceback(BASIC)
    assert info.frames[0].depth == 0.0
    assert info.frames[-1].depth == 1.0


def test_syntax_error_without_func():
    info = parse_traceback(SYNTAX)
    assert len(info.frames) == 1
    frame = info.frames[0]
    assert frame.file == "bad.py"
    assert frame.func == ""
    assert frame.source == "x ==="
    assert info.exc_type == "SyntaxError"


def test_pseudo_frames_flagged():
    info = parse_traceback(PSEUDO)
    assert info.frames[0].pseudo is True
    assert info.frames[0].not_a_file is True
    assert info.frames[1].pseudo is True


def test_chained_exception_takes_last():
    info = parse_traceback(CHAINED)
    assert len(info.frames) == 2
    assert info.exc_type == "RuntimeError"
    assert info.exc_message == "boom"


def test_caret_line_not_treated_as_source():
    info = parse_traceback(CARET)
    assert info.frames[0].source == 'print(x["y"])'


def test_empty_text():
    info = parse_traceback("")
    assert info.frames == []
