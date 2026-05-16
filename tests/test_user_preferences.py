from services.follow_the_shade.preference_query import enrich_query_with_preferences


def test_enrich_query_adds_shade_and_area_and_time() -> None:
    enriched = enrich_query_with_preferences(
        "find me a cafe",
        {
            "exposure_preference": "shade",
            "favorite_areas": ["Riva"],
            "default_time_preset": "afternoon",
            "avoid_busy": False,
        },
    )
    assert "shade" in enriched.lower()
    assert "riva" in enriched.lower()
    assert "afternoon" in enriched.lower()


def test_enrich_query_keeps_explicit_request() -> None:
    query = "I want sun around Bacvice tomorrow morning."
    enriched = enrich_query_with_preferences(
        query,
        {
            "exposure_preference": "shade",
            "favorite_areas": ["Riva"],
            "default_time_preset": "afternoon",
        },
    )
    assert enriched == query
