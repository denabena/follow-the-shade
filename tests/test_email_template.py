from services.notifications.templates import render_digest_email


def test_render_digest_email_includes_subject_html_and_text() -> None:
    subject, html, text = render_digest_email(
        {
            "analysis_id": "shade_123",
            "request": {"preference": "shade", "location_label": "Riva, Split"},
            "results": [
                {
                    "name": "Figa",
                    "exposure": {
                        "summary": "Mostly shaded from 14:00 to 18:00.",
                        "match_score": 0.9,
                        "samples": [
                            {
                                "time": "2026-05-16T14:00:00+02:00",
                                "state": "shade",
                            }
                        ],
                    },
                }
            ],
        },
        {
            "area": "Riva",
            "time_window_preset": "afternoon",
            "exposure_preference": "shade",
        },
        app_public_url="https://followtheshade.test",
    )

    assert subject == "Your Riva shade picks for afternoon"
    assert "<strong>Figa</strong>" in html
    assert "Mostly shaded from 14:00 to 18:00." in text
    assert "https://followtheshade.test/?analysis_id=shade_123" in text
