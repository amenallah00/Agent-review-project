from app.diff_chunker import chunk_files
from app.diff_parser import FileChange, Hunk


def _file(filename, content, new_start=1):
    hunk = Hunk(header=f"@@ -1,1 +{new_start},1 @@", new_start=new_start, content=content)
    return FileChange(filename=filename, hunks=[hunk], lines_added=content.count("+"))


def test_small_files_fit_in_one_chunk():
    files = [_file("a.py", "+x = 1"), _file("b.py", "+y = 2")]
    chunks = chunk_files(files, max_tokens_per_chunk=1000)
    assert len(chunks) == 1
    assert len(chunks[0].files) == 2
    assert chunks[0].truncated_files == []


def test_large_file_gets_truncated_not_dropped():
    huge_content = "\n".join(f"+line_{i} = {i}" for i in range(3000))
    files = [_file("huge.py", huge_content)]
    chunks = chunk_files(files, max_tokens_per_chunk=200)

    assert len(chunks) == 1
    assert chunks[0].files[0].filename == "huge.py"
    assert "huge.py" in chunks[0].truncated_files
    # Le fichier tronqué doit être bien plus petit que l'original
    truncated_size = len(chunks[0].files[0].hunks[0].content)
    assert truncated_size < len(huge_content)


def test_files_split_across_multiple_chunks_when_budget_exceeded():
    files = [_file(f"file_{i}.py", "+" + ("x" * 400)) for i in range(5)]
    chunks = chunk_files(files, max_tokens_per_chunk=150)
    assert len(chunks) > 1
    # Tous les fichiers doivent apparaître au total, répartis entre les chunks
    all_filenames = [f.filename for c in chunks for f in c.files]
    assert len(all_filenames) == 5
