from app.cost_guard import apply_chunk_budget
from app.diff_chunker import DiffChunk
from app.diff_parser import FileChange, Hunk


def _chunk(*filenames):
    files = [FileChange(filename=f, hunks=[Hunk(header="@@", new_start=1, content="+x")]) for f in filenames]
    return DiffChunk(files=files)


def test_no_budget_applied_when_under_limit():
    chunks = [_chunk("a.py"), _chunk("b.py")]
    result = apply_chunk_budget(chunks, max_chunks=5)
    assert len(result.chunks_to_process) == 2
    assert result.skipped_chunk_count == 0
    assert result.skipped_file_names == []


def test_budget_truncates_chunks_beyond_limit():
    chunks = [_chunk("a.py"), _chunk("b.py"), _chunk("c.py"), _chunk("d.py")]
    result = apply_chunk_budget(chunks, max_chunks=2)
    assert len(result.chunks_to_process) == 2
    assert result.skipped_chunk_count == 2


def test_skipped_file_names_lists_all_files_in_dropped_chunks():
    chunks = [_chunk("a.py"), _chunk("b.py", "c.py")]
    result = apply_chunk_budget(chunks, max_chunks=1)
    assert result.skipped_file_names == ["b.py", "c.py"]


def test_exact_limit_is_not_truncated():
    chunks = [_chunk("a.py"), _chunk("b.py")]
    result = apply_chunk_budget(chunks, max_chunks=2)
    assert result.skipped_chunk_count == 0
