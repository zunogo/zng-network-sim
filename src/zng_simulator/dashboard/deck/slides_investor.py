"""Slide data for the Investor pitch deck (13 slides)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .renderers import C


@dataclass
class Slide:
    id: int
    title: str
    layout: str
    data: dict[str, Any] = field(default_factory=dict)


INVESTOR_SLIDES: list[Slide] = [
    # ------------------------------------------------------------------
    # 1. Title
    # ------------------------------------------------------------------
    Slide(
        id=1,
        title="zunogo",
        layout="title",
        data={
            "logo": "zunogo.png",
            "heading": "zunogo",
            "heading_color": C["yellow_300"],
            "tagline": "Energy for Endless Journeys",
            "tagline_style": "highlight",
        },
    ),
    # ------------------------------------------------------------------
    # 2. The Opportunity
    # ------------------------------------------------------------------
    Slide(
        id=2,
        title="The Opportunity",
        layout="two_col",
        data={
            "heading": "The Opportunity",
            "subheading": "Charging slows fleets. Swapping keeps them moving.",
            "intro": (
                "Current EV charging infrastructure creates unacceptable "
                "downtime for commercial 2-wheeler fleet operations"
            ),
            "left": {
                "title": "Traditional Charging",
                "title_color": C["red_400"],
                "bg": C["red_bg"],
                "items": [
                    "30-60 minute charging times",
                    "Expensive infrastructure",
                    "Limited availability",
                    "Vehicle downtime = lost revenue",
                ],
            },
            "right": {
                "title": "2-Wheeler Fleet Reality",
                "title_color": C["blue_400"],
                "bg": C["blue_bg"],
                "items": [
                    {"text": "Every minute costs revenue", "highlight": True},
                    "Range anxiety prevents EV 2-wheeler adoption",
                    "Delivery routes need 99.9% uptime",
                    "Rapid fleet scaling requirements",
                ],
            },
        },
    ),
    # ------------------------------------------------------------------
    # 3. Market Validation
    # ------------------------------------------------------------------
    Slide(
        id=3,
        title="Market Validation",
        layout="stats_grid",
        data={
            "heading": "Battery Swapping is Proven & Validated",
            "subheading": "From pilots to scale \u2014 the model works.",
            "highlight": "The market is real",
            "rows": [
                [
                    {
                        "value": "38M+",
                        "label": "Battery Swaps Completed",
                        "detail": "SunMobility (IndoFast)",
                        "color": C["green_400"],
                        "bg": C["green_bg"],
                    },
                    {
                        "value": "1.5B+",
                        "label": "Green Kilometers Traveled",
                        "detail": "Yuma Energy",
                        "color": C["blue_400"],
                        "bg": C["blue_bg"],
                    },
                    {
                        "value": "1,037",
                        "label": "Active Swap Stations",
                        "detail": "SunMobility Network",
                        "color": C["purple_400"],
                        "bg": C["purple_bg"],
                    },
                ],
                [
                    {
                        "value": "106K+",
                        "label": "Total Vehicles & Drivers Active",
                        "detail": "Across all platforms",
                        "color": C["yellow_400"],
                        "bg": C["yellow_bg"],
                    },
                    {
                        "value": "17",
                        "label": "Cities Currently Active",
                        "detail": "Rapid geographic expansion",
                        "color": C["red_400"],
                        "bg": C["red_bg"],
                    },
                ],
            ],
        },
    ),
    # ------------------------------------------------------------------
    # 4. Current Market Landscape
    # ------------------------------------------------------------------
    Slide(
        id=4,
        title="Current Market Landscape",
        layout="image_grid",
        data={
            "heading": "",
            "subheading": (
                "Existing players have validated the market "
                "but left critical gaps..."
            ),
            "rows": [
                [
                    {
                        "image": "sunMobility.png",
                        "title": "SunMobility",
                        "title_color": C["blue_400"],
                        "subtitle": "1,037 stations",
                    },
                    {
                        "image": "honda.jpg",
                        "title": "Honda e:Swap",
                        "title_color": C["green_400"],
                        "subtitle": "3 major cities",
                    },
                    {
                        "image": "gogoro.jpeg",
                        "title": "Gogoro",
                        "title_color": C["purple_400"],
                        "subtitle": "Global technology",
                    },
                    {
                        "image": "raceEnergy.png",
                        "title": "RACEnergy",
                        "title_color": C["orange_400"],
                        "subtitle": "Swaps for 3 Wheelers",
                    },
                ],
                [
                    {
                        "image": "batterySmart.png",
                        "title": "Battery Smart",
                        "title_color": C["yellow_400"],
                        "subtitle": "Pan-India expansion",
                    },
                    {
                        "image": "yuma.png",
                        "title": "Yuma Energy",
                        "title_color": C["cyan_400"],
                        "subtitle": "17 cities, 50K+ drivers",
                    },
                    {
                        "image": "ril.jpeg",
                        "title": "Reliance",
                        "title_color": C["red_400"],
                        "subtitle": "Pilots underway",
                    },
                ],
            ],
        },
    ),
    # ------------------------------------------------------------------
    # 5. Current Market Economics
    # ------------------------------------------------------------------
    Slide(
        id=5,
        title="Current Market Economics",
        layout="table",
        data={
            "heading": "Current Player Cost Analysis (16-Dock Station)",
            "headers": [
                {"label": "Category"},
                {"label": "Gogoro"},
                {"label": "SunMobility"},
                {"label": "Battery Smart"},
                {"label": "Yulu"},
                {"label": "Reliance"},
                {"label": "Honda"},
            ],
            "header_colors": [
                C["yellow_300"],
                C["purple_300"],
                C["blue_300"],
                C["yellow_300"],
                C["cyan_300"],
                C["red_300"],
                C["green_300"],
            ],
            "rows": [
                {
                    "cells": ["CAPEX", "", "", "", "", "", ""],
                    "bold": True,
                },
                {
                    "cells": [
                        "16 Dock Cost",
                        "~$20,000",
                        "~$7,000",
                        "~$2,000",
                        "~$6,000",
                        "~$9,000",
                        "~$15,000",
                    ],
                },
                {
                    "cells": [
                        "Shelter/Covering",
                        "NA",
                        "NA",
                        "~$2,500",
                        "NA",
                        "NA",
                        "NA",
                    ],
                },
                {
                    "cells": [
                        "Supporting Equipment",
                        "~$3,500",
                        "~$3,500",
                        "~$3,500",
                        "~$3,500",
                        "~$3,500",
                        "~$3,500",
                    ],
                },
                {
                    "cells": [
                        "Total CAPEX",
                        "$23,500",
                        "$10,500",
                        "$8,000",
                        "$9,500",
                        "$12,500",
                        "$18,500",
                    ],
                    "bold": True,
                    "bg": "rgba(30,58,138,0.1)",
                },
                {
                    "cells": [
                        "6-Year OPEX",
                        "$39,600",
                        "$46,800",
                        "$64,800",
                        "$64,800",
                        "$46,800",
                        "$39,600",
                    ],
                    "bold": True,
                },
                {
                    "cells": [
                        "Total Cost (6 Years)",
                        "$63,100",
                        "$57,300",
                        "$72,800",
                        "$74,300",
                        "$59,300",
                        "$58,100",
                    ],
                    "bold": True,
                    "large": True,
                    "bg": "rgba(113,63,18,0.1)",
                },
            ],
            "summary": (
                "Current solutions range from $57K - $74K "
                "per station over 6 years"
            ),
        },
    ),
    # ------------------------------------------------------------------
    # 6. Zunogo's Opportunity
    # ------------------------------------------------------------------
    Slide(
        id=6,
        title="Zunogo's Opportunity",
        layout="two_col_quad",
        data={
            "heading": "Zunogo's opportunity",
            "subtitle": "Market Reality Check",
            "rows": [
                [
                    {
                        "title": "Affordability Crisis",
                        "body": "Solutions are either CapEx heavy or OpEx heavy",
                        "detail": "Fleet operators struggle with economics",
                        "accent": C["red_400"],
                        "bg": C["red_bg"],
                    },
                    {
                        "title": "Scalability Bottleneck",
                        "body": "The pace of scaling speed is slow",
                        "detail": "Market demand outpaces infrastructure growth",
                        "accent": C["orange_400"],
                        "bg": C["orange_bg"],
                    },
                ],
                [
                    {
                        "title": "Deployment Inflexibility",
                        "body": "Once a station is deployed, it's close to unmovable",
                        "detail": "Cannot adapt to changing demand patterns",
                        "accent": C["blue_400"],
                        "bg": C["blue_bg"],
                    },
                    {
                        "title": "Legacy Thinking",
                        "body": "Outdated technology approaches",
                        "detail": "Missing next-generation innovations",
                        "accent": C["purple_400"],
                        "bg": C["purple_bg"],
                    },
                ],
            ],
            "footer": "The market is ready for <strong>true disruption</strong>",
        },
    ),
    # ------------------------------------------------------------------
    # 7. Battery Swapping Service Architecture (animated)
    # ------------------------------------------------------------------
    Slide(
        id=7,
        title="Battery Swapping Service Architecture",
        layout="animated_html",
        data={},
    ),
    # ------------------------------------------------------------------
    # 8. The Product
    # ------------------------------------------------------------------
    Slide(
        id=8,
        title="The Product",
        layout="image_grid",
        data={
            "heading": "The Product",
            "subheading": "From architecture to hardware \u2014 what we actually ship.",
            "rows": [
                [
                    {
                        "image": "zunogoBatteryPack.png",
                        "title": "Zunogo Battery Pack",
                        "title_color": C["yellow_400"],
                        "bullets": [
                            "Best-in-class safety with swappable energy storage",
                            "Self-healing mesh network capability",
                            "Built-in tracking via Google's Find Hub Network",
                            "50% fewer manufacturing processes",
                        ],
                    },
                    {
                        "image": "zunogoChargerDock.png",
                        "title": "Zunogo Dock Charger",
                        "title_color": C["blue_400"],
                        "bullets": [
                            "3-phase input for ultra-fast deployments",
                            "High MTBF (Mean Time Between Failures)",
                            "Stackable like LEGO for flexible stations yet super secure",
                            "Simple design: charger + battery storage box",
                        ],
                    },
                ],
            ],
        },
    ),
    # ------------------------------------------------------------------
    # 9. Where is the Station then?
    # ------------------------------------------------------------------
    Slide(
        id=9,
        title="Where is the Station then?",
        layout="image_grid",
        data={
            "heading": "Where is the Station then?",
            "rows": [
                [
                    {
                        "image": "batteryMesh.png",
                        "title": "Battery Mesh Network",
                        "title_color": C["yellow_400"],
                        "description": (
                            "Self-healing network of interconnected battery "
                            "packs forms the brain of the station"
                        ),
                    },
                    {
                        "image": "stationMaking.png",
                        "title": "Flexible Station Assembly",
                        "title_color": C["blue_400"],
                        "description": (
                            "LEGO-like modular construction forms the physical "
                            "structure of the Station, while being super secure."
                        ),
                    },
                ],
            ],
        },
    ),
    # ------------------------------------------------------------------
    # 10. Competitive Advantages
    # ------------------------------------------------------------------
    Slide(
        id=10,
        title="Competitive Advantages",
        layout="cards_3col",
        data={
            "heading": "Competitive Advantages",
            "cards": [
                {
                    "title": "Affordability (Cost Asymmetry)",
                    "accent": C["yellow_300"],
                    "bullets": [
                        "Collapsing an entire product layer reduces system cost dramatically",
                        "True disruption: structural cost advantage vs. status quo",
                        "Passes savings to fleets; improves unit economics immediately",
                    ],
                },
                {
                    "title": "Scalability (Modular Mass Production)",
                    "accent": C["green_300"],
                    "bullets": [
                        "Stations built from a single, repeatable charger module",
                        "Manufacturing akin to appliances, not automobiles",
                        "1,000 cars/year is hard; 10,000 appliances/month is trivial",
                        "Zunogo can deploy at unprecedented speed and volume",
                        "Leaves competitors no path to match the scale curve",
                    ],
                },
                {
                    "title": "Flexibility (On-Demand Capacity)",
                    "accent": C["blue_300"],
                    "bullets": [
                        "Add or remove docks in minutes to match demand",
                        "Rapid redeployment; sites are never lock-in investments",
                        "Example: reconfigure a 50-dock site in a few quick trips",
                        "Optimizes utilization; reduces stranded asset risk",
                    ],
                },
            ],
            "footer": (
                "The architecture grants Zunogo three superpowers \u2014 "
                "Affordability, Scalability, and Flexibility \u2014 making it the "
                "most compelling choice for commercial 2-wheeler energy."
            ),
        },
    ),
    # ------------------------------------------------------------------
    # 11. Cost Comparison (Zunogo vs competitors)
    # ------------------------------------------------------------------
    Slide(
        id=11,
        title="Cost Comparison",
        layout="table",
        data={
            "heading": "Cost Comparison \u2014 Crushing Cost Asymmetry",
            "subheading": (
                "Zunogo's architecture collapses an entire cost layer, "
                "creating structural cost asymmetry vs incumbents."
            ),
            "headers": [
                {"label": "Category"},
                {"label": "Gogoro"},
                {"label": "Sun Mobility"},
                {"label": "Battery Smart"},
                {"label": "Yulu"},
                {"label": "Reliance"},
                {"label": "Honda"},
                {"label": "Zunogo"},
            ],
            "header_colors": [
                C["yellow_300"],
                C["purple_300"],
                C["blue_300"],
                C["yellow_300"],
                C["cyan_300"],
                C["red_300"],
                C["green_300"],
                C["white"],
            ],
            "highlight_col": 7,
            "rows": [
                {
                    "cells": ["CAPEX", "", "", "", "", "", "", ""],
                    "bold": True,
                },
                {
                    "cells": [
                        "16 Dock Cost",
                        "~20,000 USD",
                        "~7,000 USD",
                        "~2,000 USD",
                        "~6,000 USD",
                        "~9,000 USD",
                        "~15,000 USD",
                        "~2,000 USD",
                    ],
                },
                {
                    "cells": [
                        "Shelter/Covering",
                        "NA",
                        "NA",
                        "~2,500 USD",
                        "NA",
                        "NA",
                        "NA",
                        "NA",
                    ],
                },
                {
                    "cells": [
                        "Supporting Equipment & Connection",
                        "~3,500 USD",
                        "~3,500 USD",
                        "~3,500 USD",
                        "~3,500 USD",
                        "~3,500 USD",
                        "~3,500 USD",
                        "~3,500 USD",
                    ],
                },
                {
                    "cells": [
                        "Total CAPEX",
                        "23,500 USD",
                        "10,500 USD",
                        "8,000 USD",
                        "9,500 USD",
                        "12,500 USD",
                        "18,500 USD",
                        "5,500 USD",
                    ],
                    "bold": True,
                    "bg": "rgba(30,58,138,0.1)",
                },
                {
                    "cells": [
                        "6-Year OPEX Expense",
                        "39,600 USD",
                        "46,800 USD",
                        "64,800 USD",
                        "64,800 USD",
                        "46,800 USD",
                        "39,600 USD",
                        "36,000 USD",
                    ],
                    "bold": True,
                },
                {
                    "cells": [
                        "Total Expense (CAPEX + 6-Year OPEX)",
                        "63,100 USD",
                        "57,300 USD",
                        "72,800 USD",
                        "74,300 USD",
                        "59,300 USD",
                        "58,100 USD",
                        "41,500 USD",
                    ],
                    "bold": True,
                    "large": True,
                    "bg": "rgba(113,63,18,0.1)",
                },
                {
                    "cells": [
                        "Percent Difference from Zunogo",
                        "52.05%",
                        "38.07%",
                        "75.42%",
                        "79.04%",
                        "42.89%",
                        "40.00%",
                        "0%",
                    ],
                    "bold": True,
                },
            ],
            "summary": (
                "Zunogo's architecture creates overwhelming cost "
                "asymmetry vs incumbents."
            ),
            "summary_sub": (
                "Lower CAPEX + Lower OPEX \u2192 Faster payback, superior "
                "unit economics, and unbeatable scalability."
            ),
            "expander_title": "Show full monthly OPEX breakdown",
            "expander_table": {
                "headers": [
                    {"label": "Category"},
                    {"label": "Gogoro"},
                    {"label": "Sun Mobility"},
                    {"label": "Battery Smart"},
                    {"label": "Yulu"},
                    {"label": "Reliance"},
                    {"label": "Honda"},
                    {"label": "Zunogo"},
                ],
                "header_colors": [
                    C["yellow_300"],
                    C["purple_300"],
                    C["blue_300"],
                    C["yellow_300"],
                    C["cyan_300"],
                    C["red_300"],
                    C["green_300"],
                    C["white"],
                ],
                "highlight_col": 7,
                "rows": [
                    {
                        "cells": [
                            "Electricity (per month)",
                            "350 USD",
                            "350 USD",
                            "350 USD",
                            "350 USD",
                            "350 USD",
                            "350 USD",
                            "350 USD",
                        ],
                    },
                    {
                        "cells": [
                            "Real Estate (per month)",
                            "100 USD",
                            "100 USD",
                            "250 USD",
                            "250 USD",
                            "100 USD",
                            "100 USD",
                            "100 USD",
                        ],
                    },
                    {
                        "cells": [
                            "Station Keeping (per month)",
                            "100 USD",
                            "200 USD",
                            "300 USD",
                            "300 USD",
                            "200 USD",
                            "100 USD",
                            "50 USD",
                        ],
                    },
                ],
            },
        },
    ),
    # ------------------------------------------------------------------
    # 12. Team
    # ------------------------------------------------------------------
    Slide(
        id=12,
        title="Team",
        layout="team",
        data={
            "heading": "The Team",
            "subheading": "Founders engineered to win the category.",
            "members": [
                {
                    "name": "Abhilash Betanamudi",
                    "photo": "abhilash.png",
                    "color": C["purple_400"],
                    "bullets": [
                        "\u2022 Architected swap stations for RACE Energy and Reliance",
                        "\u2022 Led India's first AIS-156 Phase II certified swappable battery",
                        "\u2022 Built fleet-grade telematics at $0.3/vehicle/month at scale",
                        "\u2022 Patented conductive sensing for robust safety/diagnostics",
                        "\u2022 End-to-end product + systems architecture (battery \u2192 station \u2192 ops)",
                    ],
                },
                {
                    "name": "Ankit Mishra",
                    "photo": "ankit.jpeg",
                    "color": C["green_400"],
                    "bullets": [
                        "\u2022 Power electronics specialist (high-reliability energy systems)",
                        "\u2022 Leads battery manufacturing + BMS engineering",
                        "\u2022 Designs defence-grade chargers built for uptime and MTBF",
                        "\u2022 Production-minded engineering: quality, testability, and scale",
                        "\u2022 Deep expertise across pack, charger, and station power stack",
                    ],
                },
                {
                    "name": "Sreejit Sreedharan",
                    "photo": "sreejit.jpeg",
                    "color": C["blue_400"],
                    "bullets": [
                        "\u2022 10+ years shipping embedded + IoT systems",
                        "\u2022 10,000+ node mesh deployments (real-world reliability)",
                        "\u2022 Secure wireless + device identity for fleet/OEM integrations",
                        "\u2022 Ultra-low-power design (multi-month/years battery life)",
                        "\u2022 Co-inventor on sensing technology (robust sensing at scale)",
                    ],
                },
                {
                    "name": "Vinod Boga",
                    "photo": "vinod.jpeg",
                    "color": C["yellow_400"],
                    "bullets": [
                        "\u2022 Lead engineer in Battery Management Systems (BMS)",
                        "\u2022 Builds scalable firmware stacks + secure wireless protocols",
                        "\u2022 Ships FOTA and hardened embedded platforms for EV charging",
                        "\u2022 Reliability engineering for commercial uptime and safety",
                        "\u2022 Deep hands-on experience across battery + charger platforms",
                    ],
                },
            ],
        },
    ),
    # ------------------------------------------------------------------
    # 13. Next Steps
    # ------------------------------------------------------------------
    Slide(
        id=13,
        title="Next Steps",
        layout="cta",
        data={
            "heading": "Let's Build the Future",
            "body": (
                "We're actively seeking strategic investors and partners "
                "to accelerate our market expansion"
            ),
            "contact_heading": "Contact Us",
            "contact_body": "Ready to power the electric future?",
            "email": "hello@zunogo.com",
            "footer": (
                "Investment opportunities \u2022 Partnership structures "
                "\u2022 Growth roadmap"
            ),
        },
    ),
]
