from typing import Any, Dict

import pytest

import background_tasks.summarizer as summarizer


def test_extract_readable_text_strips_scripts_and_styles() -> None:
    html = (
        "<html><head><style>.x{color:red}</style><script>var a=1;</script></head>"
        "<body><h1>Title &amp; Intro</h1><p>Hello <b>world</b>!</p>"
        "<noscript>no js</noscript><div>More text</div></body></html>"
    )

    text = summarizer._extract_readable_text(html)  # type: ignore[attr-defined]

    assert "var a=1" not in text
    assert ".x{color:red}" not in text
    assert "no js" not in text
    assert "Title & Intro" in text
    assert "Hello world" in text
    assert "More text" in text


def test_summarize_with_gemma3_calls_ollama_with_cleaned_text(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: Dict[str, Any] = {}

    def fake_generate(*, model: str, prompt: str, options: Dict[str, Any]) -> Dict[str, str]:  # type: ignore[override]
        captured["model"] = model
        captured["prompt"] = prompt
        assert "<script>" not in prompt
        assert "var a=1" not in prompt
        assert "Title & Intro" in prompt
        return {"response": "Title & Intro is discussed. Content is summarized in prose, not bullets."}

    monkeypatch.setattr(summarizer.ollama, "generate", fake_generate)  # type: ignore[arg-type]

    # Provide sufficient readable words to avoid early "Insufficient" return
    long_body = " ".join(["content"] * 40)
    html = f"<h1>Title &amp; Intro</h1><script>var a=1</script><p>{long_body}</p>"
    out = summarizer.summarize_with_gemma3(html, max_chars=1000, model="gemma3:1b")

    assert out.endswith(".")
    assert captured.get("model") == "gemma3:1b"
    assert "Task: Write a clear multi-paragraph summary" in captured["prompt"]


def test_summarize_with_gemma3_empty_input_raises() -> None:
    with pytest.raises(summarizer.SummarizationError):
        summarizer.summarize_with_gemma3("")


def test_finalize_summary_snaps_to_sentence_end() -> None:
    text = "This is a complete sentence. This is another incomplete sent"
    finalized = summarizer._finalize_summary_text(text, max_words=None)  # type: ignore[attr-defined]
    assert finalized.endswith(".")
    assert finalized == "This is a complete sentence."


def test_finalize_summary_respects_word_cap() -> None:
    words = ["word"] * 2000
    long_text = " ".join(words) + "."
    finalized = summarizer._finalize_summary_text(long_text, max_words=1500)  # type: ignore[attr-defined]
    assert len(finalized.split()) <= 1500


