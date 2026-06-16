from creator_agent.agent.story_recap import analyze_story_recap


def test_story_recap_analysis_extracts_conflict_beyond_opening_scene():
    transcript = """
    At the Davenport family engagement banquet, everyone was busy praising Luke Acres like he was the final limited edition male lead.
    I stood in the corner of the banquet hall wearing a black waiter uniform that was half a size too small.
    Hidden truth, professional fraud, serial cheater, emotional manipulator, and long-term parasite currently attempting to marry into the Davenport family for financial control.
    She wore a deep blue evening gown, simple but devastating, and her eyes were cold enough to make Central Heating feel insecure.
    I stared at Luke's gentle expression, then listened to my system.
    """

    analysis = analyze_story_recap(
        "After HEARING My Thoughts, The Ice QUEEN Billionaire REFUSED to Let Me Leave - Manhwa Recap",
        transcript,
    )

    assert analysis.protagonist.startswith("I stood in the corner")
    assert "professional fraud" in analysis.central_conflict
    assert "hearing hidden thoughts" in analysis.packaging_notes[0]
