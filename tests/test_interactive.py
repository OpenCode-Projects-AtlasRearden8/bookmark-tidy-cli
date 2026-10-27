from bookmark_tidy.interactive import Reviewer, fmt_add_date, trunc


def refuser():
    def boom(_message):
        raise AssertionError("input should never be called")

    return boom


def test_disabled_reviewer_never_prompts():
    reviewer = Reviewer(interactive=False, input_fn=refuser())
    assert reviewer.prompt("Choose?", default="d") == "d"
    assert not reviewer.quitting


def test_eof_falls_back_and_stops_asking():
    messages = []

    def raise_eof(message):
        messages.append(message)
        raise EOFError

    reviewer = Reviewer(interactive=True, input_fn=raise_eof)
    assert reviewer.prompt("Choose?", default="d") == "d"
    assert reviewer.quitting
    assert reviewer.prompt("More?", default="d2") == "d2"
    assert len(messages) == 1


def test_quit_returns_defaults_for_everything_after():
    calls = []

    def fake_input(_message):
        calls.append(_message)
        return "q"

    reviewer = Reviewer(interactive=True, input_fn=fake_input)
    assert reviewer.prompt("First?", default="d") == "d"
    assert reviewer.quitting
    assert reviewer.prompt("Second?", default="d2") == "d2"
    assert len(calls) == 1


def test_normal_reply_flows_through():
    replies = iter(["yes", ""]
                   )
    reviewer = Reviewer(interactive=True, input_fn=lambda _m: next(replies))
    assert reviewer.prompt("First?", default="d") == "yes"
    assert reviewer.prompt("Second?", default="d") == ""


def test_fmt_add_date():
    assert fmt_add_date(1672531200) == "2023-01-01"
    assert fmt_add_date(None) == ""
    assert fmt_add_date("x") == ""


def test_trunc():
    assert trunc("abc") == "abc"
    assert trunc("https://example.com/" + "a" * 100, 20).endswith("\u2026")
