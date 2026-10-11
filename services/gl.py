"""GL-code suggestions: keyword rules, not a model.

Small businesses post invoices to the same handful of general-ledger
accounts every month. A deterministic keyword table beats a black box here:
every suggestion carries the rule that fired, so the controller can see
*why* and can edit the table. Returns up to 2 suggestions with confidence.
"""

from __future__ import annotations

from dataclasses import dataclass

# (gl_code, gl_name, keywords)
GL_TABLE: list[tuple[str, str, tuple[str, ...]]] = [
    # Seeded chart of accounts for the walkthrough retailer. The corpus is
    # gift/houseware merchandise, so the dominant account is merchandise for
    # resale; the rest is the standard SME overhead set.
    ("5000", "Merchandise for Resale (COGS)",
     ("holder", "lantern", "mug", "candle", "decoration", "gift", "ribbon",
      "ornament", "t-light", "tlight", "hanger", "coathanger", "light",
      "bottle", "warmer", "sticker", "tag", "card", "wrap", "bag", "box",
      "plate", "stand", "bank", "cracker", "chain kit", "trinket", "chandelier",
      "sleigh", "stocking", "angel", "star", "heart", "lantern", "basket",
      "frame", "mirror", "clock", "vase", "cushion", "throw", "apron",
      "teatowel", "napkin", "cutlery", "doormat", "gardener", "kneeling",
      "watering", "plant", "seed", "tool")),
    ("6000", "Office Supplies",
     ("office", "paper", "toner", "stationery", "pen", "ink", "desk",
      "notebook", "printer", "supplies")),
    ("6100", "Software & SaaS",
     ("software", "saas", "subscription", "license", "cloud", "hosting",
      "api", "seat", "renewal", "plan")),
    ("6200", "Utilities",
     ("electric", "water", "gas", "internet", "phone", "utility", "hydro",
      "telecom", "broadband")),
    ("6300", "Rent & Facilities",
     ("rent", "lease", "facility", "cleaning", "maintenance", "repair",
      "hvac", "plumbing")),
    ("6400", "Marketing & Advertising",
     ("marketing", "advertising", "ads", "seo", "campaign", "sponsor",
      "printing", "signage", "design")),
    ("6500", "Professional Services",
     ("consulting", "legal", "accounting", "audit", "attorney", "advisor",
      "service fee", "professional")),
    ("6600", "Travel & Meals",
     ("travel", "flight", "hotel", "taxi", "uber", "meal", "dinner",
      "lunch", "airfare", "lodging", "mileage")),
    ("6700", "IT Equipment",
     ("laptop", "monitor", "keyboard", "server", "hardware", "computer",
      "equipment", "cable", "router")),
    ("6800", "Insurance",
     ("insurance", "premium", "policy", "coverage", "liability")),
    ("6900", "Shipping & Freight",
     ("shipping", "freight", "courier", "delivery", "postage", "ups",
      "fedex", "dhl")),
]


@dataclass(frozen=True)
class GLSuggestion:
    gl_code: str
    gl_name: str
    confidence: float   # 0..1, share of lines matching the rule
    matched_keywords: tuple[str, ...]
    reason: str


def suggest(lines: list[tuple[str, float]]) -> list[GLSuggestion]:
    """Suggest GL codes from (description, amount) line items.

    Confidence = share of invoice spend (by amount) covered by the rule's
    keywords. Ties broken by table order.
    """
    total = sum(max(a, 0.0) for _, a in lines)
    if total <= 0:
        return []
    scored: list[GLSuggestion] = []
    for code, name, keywords in GL_TABLE:
        hits: set[str] = set()
        covered = 0.0
        for desc, amt in lines:
            low = desc.lower()
            found = [k for k in keywords if k in low]
            if found:
                hits.update(found)
                covered += max(amt, 0.0)
        if hits:
            conf = covered / total
            scored.append(GLSuggestion(
                code, name, round(conf, 3), tuple(sorted(hits)),
                f"{conf:.0%} of invoice spend mentions {', '.join(sorted(hits))}."))
    scored.sort(key=lambda s: (-s.confidence, s.gl_code))
    return scored[:2]
