from app.diff_parser import filter_irrelevant_files, parse_diff, total_lines_changed

SAMPLE_DIFF = """diff --git a/app/main.py b/app/main.py
index 1111111..2222222 100644
--- a/app/main.py
+++ b/app/main.py
@@ -10,6 +10,8 @@ def foo():
     x = 1
     y = 2
+    z = 3
+    print(z)
     return x + y
diff --git a/package-lock.json b/package-lock.json
index 3333333..4444444 100644
--- a/package-lock.json
+++ b/package-lock.json
@@ -1,3 +1,3 @@
-{"lockfileVersion": 1}
+{"lockfileVersion": 2}
"""


def test_parse_diff_extracts_files_and_hunks():
    files = parse_diff(SAMPLE_DIFF)
    assert len(files) == 2
    assert files[0].filename == "app/main.py"
    assert files[1].filename == "package-lock.json"
    assert len(files[0].hunks) == 1


def test_added_line_numbers_matches_new_file_lines():
    files = parse_diff(SAMPLE_DIFF)
    main_py = files[0]
    # Hunk "@@ -10,6 +10,8 @@" : 2 lignes de contexte (10, 11) puis les 2 lignes ajoutées.
    added = main_py.added_line_numbers()
    assert 12 in added  # z = 3
    assert 13 in added  # print(z)


def test_filter_irrelevant_files_removes_lockfile():
    files = parse_diff(SAMPLE_DIFF)
    filtered = filter_irrelevant_files(files)
    assert len(filtered) == 1
    assert filtered[0].filename == "app/main.py"


def test_total_lines_changed():
    files = parse_diff(SAMPLE_DIFF)
    filtered = filter_irrelevant_files(files)
    assert total_lines_changed(filtered) == 2
