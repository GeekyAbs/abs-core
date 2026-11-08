from pathlib import Path

from scripts.ingest import ROOT, load_docs, resolve_paths


def test_resolve_paths_is_relative_to_backend_root():
    paths = resolve_paths("docs/knowledge.md.example")

    assert paths == [ROOT / "docs/knowledge.md.example"]


def test_resolve_paths_supports_globs(tmp_path):
    (tmp_path / "a.md").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.md").write_text("beta", encoding="utf-8")

    paths = resolve_paths(str(tmp_path / "*.md"))

    assert [p.name for p in paths] == ["a.md", "b.md"]


def test_resolve_paths_skips_missing_files(tmp_path):
    existing = tmp_path / "a.md"
    existing.write_text("alpha", encoding="utf-8")

    paths = resolve_paths(f"{existing},{tmp_path / 'missing.md'}")

    assert paths == [existing]


def test_load_docs_skips_blank_files(tmp_path):
    blank = tmp_path / "blank.md"
    blank.write_text("   \n", encoding="utf-8")
    good = tmp_path / "good.md"
    good.write_text("Abesh builds agents.", encoding="utf-8")

    docs = load_docs([blank, good])

    assert len(docs) == 1
    assert docs[0][0] == str(good)
    assert docs[0][2] == "Abesh builds agents."


def test_load_docs_is_utf8_safe(tmp_path):
    path: Path = tmp_path / "unicode.md"
    path.write_text("Abesh is based in Kolkata — naïve résumé.", encoding="utf-8")

    docs = load_docs([path])

    assert "Kolkata" in docs[0][2]
