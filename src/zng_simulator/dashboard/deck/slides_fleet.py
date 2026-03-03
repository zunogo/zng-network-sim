"""Slide data for the Fleet & OEM partner pitch deck (9 slides)."""

from __future__ import annotations

from .renderers import C
from .slides_investor import Slide

FLEET_SLIDES: list[Slide] = [
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
            "tagline": "Fleet Operators & OEMs \u2014 Partner Deck",
            "tagline_style": "highlight",
            "subtitle": "Swap energy. Maximize uptime. Scale reliably.",
        },
    ),
    # ------------------------------------------------------------------
    # 2. Fleet Pain
    # ------------------------------------------------------------------
    Slide(
        id=2,
        title="Fleets need uptime",
        layout="two_col",
        data={
            "heading": "Fleets need uptime",
            "subheading": (
                "Charging downtime directly reduces utilization and revenue."
            ),
            "left": {
                "title": "Traditional Charging",
                "title_color": C["red_400"],
                "bg": C["red_bg"],
                "items": [
                    "30\u201360 minute sessions",
                    "Queueing + charger availability risk",
                    "Depots become bottlenecks",
                    "Downtime = lost orders",
                ],
            },
            "right": {
                "title": "Fleet Reality",
                "title_color": C["blue_400"],
                "bg": C["blue_bg"],
                "items": [
                    {"text": "Every minute matters", "highlight": True},
                    "Routes and peaks shift daily",
                    "99.9% availability expectations",
                    "Rapid expansion needs modular infra",
                ],
            },
            "footer": "Swapping makes energy a fast, predictable pit stop.",
        },
    ),
    # ------------------------------------------------------------------
    # 3. Business Model
    # ------------------------------------------------------------------
    Slide(
        id=3,
        title="Network-owned model",
        layout="two_col",
        data={
            "heading": "Network-owned model",
            "subheading": (
                "Zunogo owns and operates the batteries and swap "
                "infrastructure \u2014 fleets consume energy as a service."
            ),
            "left": {
                "title": "Zunogo owns & operates",
                "title_color": C["yellow_300"],
                "bg": C["gray_800"],
                "items": [
                    "Battery inventory",
                    "Charger docks / stations",
                    "Deployment, upkeep, maintenance",
                    "Monitoring, uptime, and asset health",
                ],
            },
            "right": {
                "title": "Fleets pay for service",
                "title_color": C["blue_300"],
                "bg": C["gray_800"],
                "items": [
                    {"text": "Energy + availability", "highlight": True},
                    "No battery ownership headaches",
                    "No station capex / upkeep burden",
                    "Reliability comes built-in via SLA + operations",
                ],
            },
            "footer": "Zunogo turns energy into a managed network service.",
        },
    ),
    # ------------------------------------------------------------------
    # 4. Fleet Value
    # ------------------------------------------------------------------
    Slide(
        id=4,
        title="Why fleets choose Zunogo",
        layout="fleet_value",
        data={
            "heading": "Why fleets choose Zunogo",
            "subheading": (
                "When energy is faster, cheaper, and reliable \u2014 fleets win."
            ),
            "cards": [
                {
                    "title": "More revenue days",
                    "accent": C["yellow_300"],
                    "description": (
                        "Seconds-per-swap energy keeps vehicles "
                        "running across shifts."
                    ),
                },
                {
                    "title": "Lower total cost",
                    "accent": C["green_300"],
                    "description": (
                        "Designed to be more affordable than competitors, "
                        "while scaling rapidly."
                    ),
                },
                {
                    "title": "Reliability by design",
                    "accent": C["blue_300"],
                    "description": (
                        "Zunogo owns upkeep and uptime \u2014 fleets "
                        "operate, we maintain."
                    ),
                },
            ],
            "sla": {
                "title": "SLA-backed service targets",
                "metrics": [
                    {"label": "Uptime SLA", "value": "99.5%"},
                    {"label": "Battery availability", "value": "< 5 min wait"},
                    {"label": "Swap time", "value": "Typical < 1 min"},
                ],
                "note": (
                    "Targets are defined in the SLA with clear measurement "
                    "boundaries (to avoid user-behavior edge cases)."
                ),
            },
            "responsibility": {
                "title": "What the fleet does vs. what Zunogo does",
                "sides": [
                    {
                        "title": "Fleet operator",
                        "items": [
                            "Buys/leases vehicles",
                            "Runs routes & riders",
                            "Registers fleet to Zunogo",
                        ],
                    },
                    {
                        "title": "Zunogo network",
                        "items": [
                            "Deploys stations where you need them",
                            "Owns packs + stations",
                            "Upkeep, monitoring, and SLA uptime",
                        ],
                    },
                ],
            },
        },
    ),
    # ------------------------------------------------------------------
    # 5. OEM Model
    # ------------------------------------------------------------------
    Slide(
        id=5,
        title='OEMs: "Powered by Zunogo"',
        layout="oem_model",
        data={
            "heading": 'OEMs: "Powered by Zunogo"',
            "subheading": (
                "OEMs sell vehicles to fleets without batteries. "
                "Fleet registration enables vehicles to use the "
                "Zunogo swap network."
            ),
            "sections": [
                [
                    {
                        "title": "What the OEM gets",
                        "accent": C["blue_300"],
                        "items": [
                            "Sell more vehicles (adoption unlocked by energy network)",
                            'Optional "powered by Zunogo" co-marketing',
                            {"text": "Referral fee per activated vehicle", "highlight": True},
                            "Integration support + QC + certification",
                            "Lower customer friction: no battery purchase needed",
                        ],
                    },
                    {
                        "title": "Activation flow",
                        "accent": C["yellow_300"],
                        "ordered": True,
                        "items": [
                            "OEM sells vehicle to fleet (no battery)",
                            "Fleet registers with Zunogo",
                            "Vehicle gets activated on the Zunogo network",
                            "Riders can swap immediately at stations",
                        ],
                        "note": (
                            "Activation is primarily vehicle \u2194 fleet mapping. "
                            "No rider details required."
                        ),
                    },
                ],
                [
                    {
                        "title": "Integration boundary",
                        "accent": C["blue_300"],
                        "items": [
                            "OEM complies with mechanical interface",
                            "OEM integrates Zunogo-supplied electronics into the vehicle",
                            "Zunogo performs QC and certification",
                        ],
                    },
                    {
                        "title": "Responsibility split",
                        "accent": C["yellow_300"],
                        "items": [
                            "Zunogo is responsible for issues with components provided by Zunogo",
                            "OEM remains responsible for the rest of the vehicle",
                        ],
                    },
                ],
            ],
        },
    ),
    # ------------------------------------------------------------------
    # 6. Product & Network
    # ------------------------------------------------------------------
    Slide(
        id=6,
        title="What gets deployed",
        layout="image_grid",
        data={
            "heading": "What gets deployed",
            "subheading": (
                "Standardized packs + modular docks + software = "
                "a swap network that scales."
            ),
            "rows": [
                [
                    {
                        "image": "zunogoBatteryPack.png",
                        "title": "Zunogo Battery Pack",
                        "title_color": C["yellow_400"],
                        "description": (
                            "Safe, network-managed energy modules "
                            "owned by the Zunogo network."
                        ),
                    },
                    {
                        "image": "zunogoChargerDock.png",
                        "title": "Zunogo Dock Charger",
                        "title_color": C["blue_400"],
                        "description": (
                            "Modular, stackable docks for rapid "
                            "deployments and reliable uptime."
                        ),
                    },
                ],
                [
                    {
                        "image": "batteryMesh.png",
                        "title": "",
                        "description": (
                            "Fleet/OEM visibility via monitoring, "
                            "diagnostics, and asset management."
                        ),
                    },
                    {
                        "image": "stationMaking.png",
                        "title": "",
                        "description": (
                            "Modular docks \u2192 rapid capacity changes "
                            "as demand shifts."
                        ),
                    },
                ],
            ],
        },
    ),
    # ------------------------------------------------------------------
    # 7. Commercials
    # ------------------------------------------------------------------
    Slide(
        id=7,
        title="Commercial model",
        layout="cards_3col",
        data={
            "heading": "Commercial model",
            "subheading": (
                "Affordable at scale, reliable in uptime \u2014 designed to "
                "be lucrative for fleets and simple for OEMs."
            ),
            "cards": [
                {
                    "title": "Zunogo-owned assets",
                    "accent": C["yellow_300"],
                    "description": (
                        "Fleets avoid battery ownership and "
                        "station capex/upkeep."
                    ),
                },
                {
                    "title": "Better fleet economics",
                    "accent": C["green_300"],
                    "description": (
                        "Lower total cost + higher utilization "
                        "\u2192 more revenue per vehicle."
                    ),
                },
                {
                    "title": "OEM sales unlock",
                    "accent": C["blue_300"],
                    "description": (
                        'OEMs can sell "powered by Zunogo" vehicles '
                        "to fleets without bundling batteries."
                    ),
                },
            ],
            "footer": (
                "Next: finalize pricing, SLAs, and onboarding "
                "timeline for your pilot."
            ),
        },
    ),
    # ------------------------------------------------------------------
    # 8. Next Steps
    # ------------------------------------------------------------------
    Slide(
        id=8,
        title="Partner with Zunogo",
        layout="cta",
        data={
            "heading": "Partner with Zunogo",
            "body": (
                "Pilot with a fleet, or integrate as an OEM \u2014 "
                "we'll tailor the rollout to your routes and volumes."
            ),
            "contact_heading": "Contact",
            "contact_body": "Ready to deploy swap at scale?",
            "email": "hello@zunogo.com",
            "footer": (
                "Pilot scope \u2022 Integration requirements "
                "\u2022 Commercial terms"
            ),
        },
    ),
    # ------------------------------------------------------------------
    # 9. Team
    # ------------------------------------------------------------------
    Slide(
        id=9,
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
                        "\u2022 Built and operated large-scale connected device deployments",
                        "\u2022 Security + device identity for fleet/OEM integrations",
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
                        "\u2022 Builds scalable firmware stacks for connected platforms",
                        "\u2022 Ships FOTA and hardened embedded platforms for EV charging",
                        "\u2022 Reliability engineering for commercial uptime and safety",
                        "\u2022 Deep hands-on experience across battery + charger platforms",
                    ],
                },
            ],
        },
    ),
]
