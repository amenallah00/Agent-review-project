from app.llm.base import parse_review_json


def test_parses_valid_json_response():
    raw = '''{
        "summary": "Une vulnérabilité détectée",
        "issues": [
            {"filename": "app/db.py", "line": 42, "severity": "critical",
             "message": "Injection SQL", "suggestion": "Utiliser des requêtes préparées"}
        ]
    }'''
    result = parse_review_json(raw)
    assert result.summary == "Une vulnérabilité détectée"
    assert len(result.issues) == 1
    assert result.issues[0].severity == "critical"
    assert result.issues[0].line == 42


def test_handles_malformed_json_gracefully():
    result = parse_review_json("ceci n'est pas du JSON")
    assert result.issues == []
    assert result.raw_response == "ceci n'est pas du JSON"


def test_handles_empty_issues_list():
    raw = '{"summary": "Aucun problème détecté", "issues": []}'
    result = parse_review_json(raw)
    assert result.issues == []
    assert result.summary == "Aucun problème détecté"


def test_ignores_non_dict_items_in_issues():
    raw = '{"summary": "test", "issues": ["texte inattendu", {"filename": "a.py", "line": 1, "severity": "info", "message": "ok"}]}'
    result = parse_review_json(raw)
    assert len(result.issues) == 1
