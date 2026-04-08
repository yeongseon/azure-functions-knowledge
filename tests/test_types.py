from __future__ import annotations

from azure_functions_knowledge.types import Document


class TestDocument:
    def test_create_with_required_fields(self) -> None:
        doc = Document(
            document_id="page-1",
            content="Hello world",
            title="Test Page",
            url="https://notion.so/test",
            source="notion",
        )
        assert doc.document_id == "page-1"
        assert doc.content == "Hello world"
        assert doc.title == "Test Page"
        assert doc.url == "https://notion.so/test"
        assert doc.source == "notion"
        assert doc.metadata == {}
        assert doc.score is None

    def test_create_with_all_fields(self) -> None:
        doc = Document(
            document_id="page-2",
            content="Content",
            title="Title",
            url="https://example.com",
            source="confluence",
            metadata={"blocks": [{"type": "paragraph"}]},
            score=0.95,
        )
        assert doc.metadata == {"blocks": [{"type": "paragraph"}]}
        assert doc.score == 0.95

    def test_keyword_only(self) -> None:
        try:
            Document("page-1", "content", "title", "url", "source")  # type: ignore[misc]
            msg = "Should have raised TypeError"
            raise AssertionError(msg)
        except TypeError:
            pass

    def test_equality(self) -> None:
        doc1 = Document(
            document_id="a",
            content="c",
            title="t",
            url="u",
            source="s",
        )
        doc2 = Document(
            document_id="a",
            content="c",
            title="t",
            url="u",
            source="s",
        )
        assert doc1 == doc2

    def test_metadata_default_is_independent(self) -> None:
        doc1 = Document(document_id="a", content="", title="", url="", source="")
        doc2 = Document(document_id="b", content="", title="", url="", source="")
        doc1.metadata["key"] = "value"
        assert "key" not in doc2.metadata
