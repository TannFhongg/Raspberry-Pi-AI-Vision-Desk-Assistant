from __future__ import annotations

from system.ui_presenters import build_result_detail_view


def test_build_result_detail_view_prioritizes_ai_answer_highlights(tmp_path) -> None:
    latest_result_path = tmp_path / "latest_result.txt"
    latest_result_path.write_text(
        "\n".join(
            [
                "Status: Answer Ready",
                "Model: demo-vision-model",
                "Duration Seconds: 1.23",
                "Camera Backend: opencv",
                "Camera Resolution: 1920 x 1080",
            ]
        ),
        encoding="utf-8",
    )
    answer_text = "\n".join(
        [
            "A small indoor room with two young men visible.",
            "",
            "What's visible",
            "• Center: shirtless young man wearing a necklace, seated and looking at the camera.",
            "• Left: another young man wearing white headphones and glasses, partly turned away.",
            "• Room features: a loft bed with a ladder on the right and a bright window.",
        ]
    )

    detail_view = build_result_detail_view(
        selected_mode="analyze_image",
        answer_text=answer_text,
        result_state="RESULT_READY",
        detail_text="",
        error_text="",
        latest_result_path=latest_result_path,
    )

    detail_html = str(detail_view["body_html"])
    assert detail_view["has_content"] is True
    assert "Scene Highlights" in detail_html
    assert "Center: shirtless young man wearing a necklace" in detail_html
    assert "Left: another young man wearing white headphones and glasses" in detail_html
    assert "Processing Metadata" in detail_html
    assert "Camera backend: opencv" in detail_html


def test_build_result_detail_view_falls_back_to_processing_detail(tmp_path) -> None:
    detail_view = build_result_detail_view(
        selected_mode="read_text",
        answer_text="",
        result_state="RESULT_READY",
        detail_text="Final cleanup is still in progress.",
        error_text="",
        latest_result_path=tmp_path / "missing-result.txt",
    )

    detail_html = str(detail_view["body_html"])
    assert detail_view["has_content"] is True
    assert "Final cleanup is still in progress." in detail_html
