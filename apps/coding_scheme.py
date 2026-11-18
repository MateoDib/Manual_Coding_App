"""Reviewed, nonidentifying coding grammar shared with the optional assistant.

Adapted from the shared narrative grammar, without Carbon_Tax phase rules. Interview examples
are deliberately excluded. Update this version when the research rules change.
"""

SCHEME_VERSION = "climate-anxiety-2026-11-17.v3"
SCHEME = {
    "version": SCHEME_VERSION,
    "principle": "Represent the participant's reasoning, including incorrect beliefs, without correcting it using outside knowledge. Topics use stable lowercase English snake_case codes; display labels are separate.",
    "operators": {
        "-->": "Positive causal or logical consequence A leads to B. Encode increases, decreases, deterioration etc in the topic itself; never use negative arrows.",
        "=": "Participant's definition, framing or equivalence, not a causal effect.",
        "&": "Coexistence without additive combination. Not a Boolean AND gate or a necessary joint condition.",
        "+": "Additive combination or policy bundle.",
        "<": "A < B means B takes priority over A.",
        ">": "A > B means A takes priority over B.",
        ";": "Separate distinct narrative paths within the same question-response pair.",
        "()": "Aggregate subtopics under the preceding topic. Not independent causal nodes.",
        "[]": "Actor, group, scope or viewpoint qualifying the preceding topic. Not independent causal nodes. Nested qualifications such as company(agriculture, sme) remain in the scope string.",
        "|": "Information source attached to a topic, relation or narrative path. Never a causal node.",
        "none": "A response that adds no substantive information, including an explicit non-substantive continuation. This is a document status, never a topic.",
    },
    "study": "Climate Anxiety — one continuous interview, without phases.",
    "interpretation_rule": "Represent only expressed reasoning about climate experiences, concerns, emotions, responses and consequences. Do not require a carbon-tax root, policy-acceptability endpoint, anxiety endpoint or any predetermined chain. An emotion is represented only when supported by the participant.",
    "cumulative_rule": "For a follow-up, reuse the relevant earlier backbone from the same interview and refine it. Do not change earlier documents or carry unrelated earlier branches forward.",
    "sources": [
        "newspaper",
        "television",
        "social_media",
        "professional_experience",
        "personal_experience",
        "family",
        "friends",
        "public_authority",
        "scientific_report",
        "ipcc_reports",
    ],
    "scopes": [
        "self",
        "future_self",
        "others",
        "households",
        "firms",
        "low_income_households",
        "rural_households",
        "urban_households",
        "car_dependent_people",
        "public_authorities",
    ],
    "consistency": "Prefer established concept codes when their meaning matches exactly; preserve substantive distinctions and directional labels. Do not silently merge historical variants. Braces have no defined meaning in this scheme. A change in layout does not change coding agreement.",
}
