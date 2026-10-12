from datagen import catalog


def test_every_catalog_item_is_stub_marked():
    for item in (*catalog.DEVICES, *catalog.PLANS, *catalog.ADDONS, *catalog.PROMOTIONS):
        assert "STUB" in item.sku or item.sku.startswith("PROMO-STUB")


def test_skus_are_unique():
    skus = [i.sku for i in (*catalog.DEVICES, *catalog.PLANS, *catalog.ADDONS)]
    assert len(skus) == len(set(skus))


def test_catalog_has_expected_breadth():
    assert len(catalog.DEVICES) >= 12
    assert len(catalog.PLANS) >= 4
    kinds = {a.kind for a in catalog.ADDONS}
    assert {"protection", "streaming", "home_internet", "accessory", "connected_line"} <= kinds


def test_tradein_value_never_exceeds_msrp_and_decays():
    device = catalog.DEVICES[0]
    values = [catalog.tradein_value_cents(device, age) for age in range(0, 61)]
    assert values[0] <= device.msrp_cents
    assert all(a >= b for a, b in zip(values, values[1:], strict=False))
    assert values[-1] > 0


def test_tradein_curve_covers_zero_to_sixty_months():
    curve = catalog.tradein_curve(catalog.DEVICES[0])
    assert [age for age, _ in curve] == list(range(0, 61))


def plan(sku_suffix: str):
    return next(p for p in catalog.PLANS if p.sku == f"TMO-STUB-PLAN-{sku_suffix}")


def test_plan_lineup_mirrors_the_live_site():
    assert len(catalog.PLANS) == 11
    assert {p.family for p in catalog.PLANS} == {"essentials", "experience_more", "experience_beyond"}
    assert {p.variant for p in catalog.PLANS} == {
        "standard", "saver", "four_line_offer", "community", "partner", "senior_55"
    }
    assert plan("BEYOND").name == "Experience Beyond 2.0"


def test_plan_totals_follow_the_published_per_line_prices():
    assert [catalog.plan_total_cents(plan("BEYOND"), n) for n in range(1, 6)] == [10500, 18000, 23000, 28000, 33000]
    assert [catalog.plan_total_cents(plan("MORE"), n) for n in range(1, 6)] == [9000, 15000, 18500, 22000, 25500]
    essentials = [catalog.plan_total_cents(plan("ESSENTIALS"), n) for n in range(1, 7)]
    assert essentials == [6500, 10000, 12000, 14000, 16000, 18000]
    assert [catalog.plan_total_cents(plan("ESSENTIALS-SAVER"), n) for n in (1, 2)] == [5500, 9000]
    assert catalog.plan_total_cents(plan("MORE-COMMUNITY"), 3) == 13500
    assert catalog.plan_total_cents(plan("BEYOND-PARTNER"), 5) == 26000


def test_line_price_is_the_marginal_cost_of_that_position():
    beyond = plan("BEYOND")
    assert [catalog.plan_price_cents(beyond, i) for i in range(6)] == [10500, 7500, 5000, 5000, 5000, 5000]
    assert catalog.plan_price_cents(plan("ESSENTIALS"), 5) == 2000  # published 6th-line price


def test_four_line_offer_requires_four_lines():
    offer = plan("ESSENTIALS-4LINE")
    assert offer.min_lines == 4 and offer.status == "limited_time"
    assert catalog.plan_total_cents(offer, 4) == 12000 and catalog.plan_total_cents(offer, 5) == 15000


def test_eligibility_groups_and_line_limits():
    for suffix in ("MORE-55", "BEYOND-55"):
        assert plan(suffix).eligibility == "55_plus" and plan(suffix).max_lines == 2
    assert plan("ESSENTIALS-SAVER").max_lines == 2
    assert plan("MORE-COMMUNITY").priority_network and plan("BEYOND-COMMUNITY").priority_network
    assert not plan("MORE-PARTNER").priority_network and plan("MORE-PARTNER").eligibility == "partner"
    assert plan("MORE").eligibility is None and plan("MORE").max_lines is None


def test_plan_benefit_nuances():
    more, beyond, ess = plan("MORE"), plan("BEYOND"), plan("ESSENTIALS")
    assert ess.data_cap_gb == 50 and more.data_cap_gb is None and beyond.data_cap_gb is None
    assert (ess.hotspot_high_speed_gb, more.hotspot_high_speed_gb, beyond.hotspot_high_speed_gb) == (0, 60, 250)
    assert (more.canada_mexico_gb, beyond.canada_mexico_gb) == (15, 30)
    assert ess.canada_mexico_gb is None  # not published on the page
    assert more.price_guarantee_years == beyond.price_guarantee_years == 5 and ess.price_guarantee_years is None
    assert "streaming-video-bundle" in beyond.perks and "streaming-video-bundle" not in more.perks
    assert "streaming-video-ads" in more.perks
    assert ess.perks == ()
    assert plan("BEYOND-COMMUNITY").hotspot_high_speed_gb == 250  # variants share the base plan's benefits


def addon(suffix: str):
    return next(a for a in catalog.ADDONS if a.sku == f"TMO-STUB-ADD-{suffix}")


def test_add_on_lineup_covers_every_category():
    by_kind: dict[str, int] = {}
    for a in catalog.ADDONS:
        by_kind[a.kind] = by_kind.get(a.kind, 0) + 1
    assert by_kind == {"protection": 6, "streaming": 1, "connected_line": 3, "home_internet": 3, "accessory": 18}


def test_no_proprietary_or_carrier_names_in_add_ons_and_perks():
    banned = ("360", "p360", "rely", "amplified", "all-in", "apple tv", "watch plan", "syncup", "jump", "mcafee",
              "zagg", "mophie", "uag", "magsafe", "netflix", "hulu", "t-mobile", "satellite", "scam shield")
    text = " ".join(a.name.lower() + " " + (a.description or "").lower() for a in catalog.ADDONS)
    text += " ".join(perk for p in catalog.PLANS for perk in p.perks)
    assert [word for word in banned if word in text.replace("satellite-connectivity", "")] == []


def test_protection_price_rises_with_device_tier():
    prices = [addon(f"PROT-T{n}").monthly_cents for n in range(1, 7)]
    assert prices == [700, 900, 1300, 1600, 1900, 2600]
    assert all(addon(f"PROT-T{n}").protection_tier == n for n in range(1, 7))
    assert addon("PROT-T3").per == "device"


def test_every_device_has_a_protection_tier_and_price_orders_the_tiers():
    assert {d.protection_tier for d in catalog.DEVICES} == {1, 2, 3, 4, 5, 6}
    assert catalog.device_by_name("moto g - 2026").protection_tier == 1
    assert catalog.device_by_name("Galaxy Z Fold8 Ultra").protection_tier == 6
    ordered = sorted(catalog.DEVICES, key=lambda d: d.msrp_cents)
    assert [d.protection_tier for d in ordered] == sorted(d.protection_tier for d in ordered)


def test_home_internet_tiers_and_connection_charge():
    prices = [addon(f"HINT-{t}").monthly_cents for t in ("BASIC", "PLUS", "PREMIUM")]
    assert prices == [5000, 6000, 7000] and addon("HINT-BASIC").one_time_cents == 3500
    assert addon("HINT-BASIC").per == "account"


def test_connected_lines_and_streaming_eligibility():
    lines = ("LINE-WATCH", "LINE-WATCH-PLUS", "LINE-CONNECTED-BEYOND")
    assert [addon(s).monthly_cents for s in lines] == [1000, 1500, 500]
    assert addon("LINE-CONNECTED-BEYOND").eligible_families == ("experience_beyond",)
    assert addon("STREAM-VIDEO").monthly_cents == 300
    assert addon("STREAM-VIDEO").eligible_families == ("experience_more", "experience_beyond")
    assert addon("HINT-BASIC").eligible_families is None


def test_accessories_are_device_specific_where_published():
    case = addon("ACC-CASE-SILICONE-18PRO")
    assert case.one_time_cents == 4999 and case.monthly_cents == 0
    assert case.compatible_devices == (catalog.device_by_name("iPhone 18 Pro").sku,)
    assert addon("ACC-LENS-PROTECTOR").compatible_devices is None  # compatibility not published
    assert addon("ACC-BUNDLE-3IN1-18PRO").one_time_cents == 9999


def test_protection_deductibles_rise_with_the_tier_and_with_claim_severity():
    tiers = [addon(f"PROT-T{n}") for n in range(1, 7)]
    for claim in ("deductible_screen_cents", "deductible_damage_cents", "deductible_loss_theft_cents"):
        values = [getattr(a, claim) for a in tiers]
        assert values == sorted(values) and len(set(values)) > 3, claim
    for a in tiers:
        assert a.deductible_screen_cents < a.deductible_damage_cents < a.deductible_loss_theft_cents


def test_only_protection_has_deductibles():
    others = [a for a in catalog.ADDONS if a.kind != "protection"]
    assert all(a.deductible_screen_cents is None and a.deductible_loss_theft_cents is None for a in others)


def test_higher_tiers_cost_more_per_month_and_per_claim():
    cheap, dear = addon("PROT-T1"), addon("PROT-T6")
    assert dear.monthly_cents > cheap.monthly_cents
    assert dear.deductible_loss_theft_cents > cheap.deductible_loss_theft_cents


def test_legacy_devices_have_a_sale_window_and_current_ones_are_still_sold():
    for d in catalog.DEVICES:
        if d.status == "current":
            assert d.sold_until is None
        else:
            assert d.sold_until == d.release_date.replace(year=d.release_date.year + 2)
            assert d.sold_until < catalog.AS_OF.replace(month=12)
