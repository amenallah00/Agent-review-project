from app.pattern_detector import detect_patterns


def test_detects_eval_usage():
    added = {10: "    result = eval(user_input)"}
    matches = detect_patterns("app/utils.py", added)
    names = [m.pattern_name for m in matches]
    assert "eval_usage" in names
    assert matches[0].severity == "critical"


def test_detects_hardcoded_secret():
    added = {5: 'api_key = "sk-abcdef1234567890"'}
    matches = detect_patterns("app/config.py", added)
    assert any(m.pattern_name == "hardcoded_secret" for m in matches)


def test_detects_sql_string_concat():
    added = {20: 'query = "SELECT * FROM users WHERE id = " + user_id'}
    matches = detect_patterns("app/db.py", added)
    assert any(m.pattern_name == "sql_string_concat" for m in matches)


def test_bare_except_only_flagged_for_python_files():
    added = {8: "except:"}
    py_matches = detect_patterns("app/main.py", added)
    js_matches = detect_patterns("app/main.js", added)
    assert any(m.pattern_name == "bare_except" for m in py_matches)
    assert not any(m.pattern_name == "bare_except" for m in js_matches)


def test_loose_equality_only_flagged_for_js_files():
    added = {12: "if (x == null) { return; }"}
    js_matches = detect_patterns("app/index.js", added)
    py_matches = detect_patterns("app/index.py", added)
    assert any(m.pattern_name == "loose_equality_js" for m in js_matches)
    assert not any(m.pattern_name == "loose_equality_js" for m in py_matches)


def test_clean_code_produces_no_matches():
    added = {1: "def add(a, b):", 2: "    return a + b"}
    matches = detect_patterns("app/math_utils.py", added)
    assert matches == []
