# Data dictionary

All tables live in `data/sandbox.db` (SQLite). Money is in **cents**. Dates are ISO-8601 (`YYYY-MM-DD`; months are
`YYYY-MM`). The dataset is "as of" **2026-10-01**. Every catalog row carries `data_source = 'stub'`: the data is
synthetic and nothing here is an offer.

Current schema version: **9** (history at the bottom). `tests/test_data_dictionary.py` fails if this file falls out
of step with the schema or the data, so update it in the same change as any schema change.

## Metadata
- `metadata(key, value)`: facts about the build; read it with `SELECT key, value FROM metadata`
  - `data_source`: always `stub`
  - `seed`: the generator seed; the same seed produces the same data
  - `as_of`: the date the data is "as of" (device ages, tenure and support windows are measured from it)
  - `brand`: a reminder that the data is not official
  - `schema_version`: see the version line above
  - `content_sha256`: checksum of every data row (not the file bytes), to verify your copy

## Catalog
Sources: names, plans, add-ons and offers follow t-mobile.com as of 2026-10-08. Prices and values are stub numbers.
Anything the site does not publish is NULL (unknown), never zero.

- `devices(sku, name, manufacturer, tier, storage_gb, msrp_cents, release_date, status, protection_tier, sold_until, data_source)`
  - `sku`: `TMO-STUB-DEV-####`; `name`: marketing name; `manufacturer`: Apple, Google, Motorola, Samsung, T-Mobile, TCL
  - `tier`: `flagship`, `mid` or `value`, derived from price: flagship >= $799, mid $400-$798, value < $400
  - `msrp_cents`: starting full retail price. `storage_gb` is NULL: the site does not show storage
  - `sold_until`: last day the phone was on sale (NULL for `current` phones, which are still sold). For `legacy` phones it is approximately two years after release. A customer's `device_purchase_date` always falls between `release_date` and `sold_until`
  - `release_date`: approximate. `status`: `current` (45 phones for sale) or `legacy` (17 older phones customers may own; cannot be bought)
  - `protection_tier` (1-6): which device-protection tier the device needs; derived from price, because the site does not publish the mapping
  - `data_source`: always `stub`
- `plans(sku, name, family, variant, tier, line_prices, extra_line_cents, min_lines, max_lines, data_cap_gb, hotspot_high_speed_gb, hotspot_unlimited, canada_mexico_gb, intl_data_gb, video_quality, price_guarantee_years, priority_network, prices_include_autopay, device_connection_cents, eligibility, perks, upgrade_note, status, data_source)`: 11 plans
  - `sku`: `TMO-STUB-PLAN-...`; `name`: for example "Experience Beyond 2.0"
  - `family`: `essentials`, `experience_more` or `experience_beyond`
  - `variant`: `standard`, `saver`, `four_line_offer`, `partner`, `community` or `senior_55`
  - `tier`: `basic` (Saver), `standard` (Essentials family) or `premium` (More and Beyond)
  - `line_prices`: comma-separated **marginal** price of line 1, 2, 3, 4, 5 in cents; `extra_line_cents` prices every line beyond that. A household pays the sum, e.g. Beyond for 3 lines = 10500 + 7500 + 5000
  - `min_lines` / `max_lines`: line limits (55+ and Saver: max 2, NULL = no limit; the 4 Line Offer: min 4)
  - `data_cap_gb`: premium data cap (NULL = unlimited premium data); `hotspot_high_speed_gb`: high-speed hotspot data; `hotspot_unlimited`: 1 if hotspot continues at reduced speed after that
  - `canada_mexico_gb`, `intl_data_gb` (215+ countries), `video_quality`, `price_guarantee_years`, `upgrade_note`: NULL = not published for this plan
  - `priority_network`: 1 on the Community plans; `prices_include_autopay`: 1 = listed prices assume AutoPay
  - `device_connection_cents`: one-time per-line connection charge (NULL = not shown)
  - `eligibility`: NULL (anyone), `partner`, `community` or `55_plus`; compare with `accounts.discount_group`
  - `perks`: comma-separated included perks (`streaming-video-ads`, `streaming-video-bundle`, `satellite-connectivity`, `streaming-video-offer-3usd`)
  - `status`: `current` or `limited_time`; `data_source`: always `stub`
  - Assumptions: a variant shares its base plan's benefits; lines beyond the published table cost the last published line price
- `addons(sku, name, kind, monthly_cents, one_time_cents, per, description, eligible_families, protection_tier, compatible_device_skus, deductible_screen_cents, deductible_damage_cents, deductible_loss_theft_cents, data_source)`: 31 add-ons; names are generic. 18 are accessories: 6 modeled on the site's examples for the newest iPhones and 12 **invented** (a case and a screen protector for each of Apple, Samsung, Google and Motorola phones, plus four universal items) so every phone has accessories to suggest
  - `kind`: `protection`, `streaming`, `connected_line`, `home_internet` or `accessory`
  - `per`: what one unit covers: `device`, `line`, `account` or `item`
  - `monthly_cents` and `one_time_cents` (for example a $35 connection charge, or an accessory's price)
  - `protection_tier` (1-6, protection only): must match the `protection_tier` of the phone it covers. The cart enforces this and checks that every protection add-on covers exactly one phone: the one on a named line (or the new phone being put on that line), or an uncovered phone in the cart. Tier prices ($7, $9, $13, $16, $19, $26) come from a search snippet; the page itself states a $7-$26 range
  - `deductible_screen_cents`, `deductible_damage_cents`, `deductible_loss_theft_cents` (protection only): per-claim fee by tier. **Invented stub values** (the site publishes no amounts); they rise with the tier
  - `eligible_families`: comma-separated plan families that may buy it (NULL = any); `compatible_device_skus`: devices an accessory fits (NULL = not published)
  - `description`: free text; `data_source`: always `stub`
- `promotions(sku, name, kind, value_cents, source, payout_months, per, max_units, requires_new_line, requires_port_in, requires_tradein, new_line_or_tradein, requires_device, requires_byod, device_skus, plan_families, plan_variants, min_plan_cents, discount_plan_only, discount_groups, credit_tiers, min_lines, min_tenure_months, min_device_age_months, min_support_contacts_90d, requires_addon_kind, min_accessories, percent_off, description, data_source)`: 21 offers
  - `source`: `site` (18, modeled on published offers) or `stub` (3 **invented** retention offers)
  - `kind`: `device_credit`, `prepaid_card`, `line_credit`, `bill_credit` or `accessory_discount`
  - `value_cents`: the total for credits and cards, the **monthly** amount for `bill_credit`; `payout_months`: months it is spread over (NULL on a bill credit = ongoing); `percent_off`: for `accessory_discount`
  - `per`: what one unit attaches to: `cart`, `device` or `line`; `max_units` caps the units
  - Conditions (NULL / 0 = none): `requires_new_line`, `requires_port_in` (the new line brings a number from another carrier), `requires_tradein`, `new_line_or_tradein` (either route works), `requires_device`, `requires_byod` (new line with the customer's own phone), `device_skus`, `plan_families`, `plan_variants`, `min_plan_cents` (first-line price of the plan), `discount_plan_only`, `discount_groups`, `credit_tiers`, `min_lines`, `min_tenure_months`, `min_device_age_months`, `min_support_contacts_90d`, `requires_addon_kind`, `min_accessories`
  - `description`: free text; `data_source`: always `stub`
- `tradein_curves(device_sku, age_months, value_cents)`: estimated trade-in value of a device in good condition by age, `age_months` 0-60

## Customers
- `accounts(account_id, segment, tenure_months, language, contact_preference, credit_tier, autopay, discount_group, persona_note)`: one account is one household
  - `account_id`: `ACC-#####`; the 42 persona accounts are `ACC-PERSONA-01` to `ACC-PERSONA-42` and carry a `persona_note` (NULL on all others)
  - `segment`: `student`, `single`, `couple`, `family`, `smb` or `senior`
  - `language`: `en`, `es` or `other`; `contact_preference`: `app`, `sms`, `email` or `call`
  - `credit_tier`: `prime`, `near_prime` or `subprime`; `autopay`: 1 if on AutoPay
  - `discount_group`: NULL, `student`, `partner`, `community` or `55_plus`; decides which discount plans and promotions the household may use
- `lines(line_id, account_id, member_label, member_role, plan_sku, device_sku, byod, device_purchase_date, financing_balance_cents, financing_months_remaining, monthly_installment_cents, tradein_eligible)`
  - `member_label`: display name (e.g. "Teen A"); `member_role`: `primary`, `partner`, `adult`, `teen`, `child`, `student`, `employee` or `senior`
  - `plan_sku`, `device_sku`: foreign keys to `plans` and `devices`. **All lines of an account share one plan** (chosen for the household's heaviest user, so lighter users can overpay); `byod` = 1 means the customer's own phone (no `device_sku`, no financing)
  - Financing is a 24-month installment plan: `financing_balance_cents` and `financing_months_remaining` are 0 once paid off; `monthly_installment_cents` is the current payment
  - `tradein_eligible`: 1 if the line has a device that can be traded in
- `line_addons(line_id, addon_sku)`, `account_addons(account_id, addon_sku)`: protection is per line; streaming, home internet and connected lines are per account

## Personas
- `personas(persona_id, account_id, kind, title, primary_theme, secondary_themes, scenario, stated_lines, stated_budget_cents, stated_usage, stated_notes, starting_cart, related_account_id)`: 50 ready-made people to demo and test against, ten per hackathon theme
  - `kind`: `customer` (42, each with an account `ACC-PERSONA-01` to `ACC-PERSONA-42`; `persona_id` equals `account_id`) or `prospect` (8, `PROSPECT-01` to `PROSPECT-08`, not customers yet, so `account_id` is NULL)
  - `primary_theme`: `cart_whisperer`, `matchmaker`, `next_best_moment`, `timekeeper` or `household_optimizer`; `secondary_themes`: comma-separated other themes the persona also suits
  - `title`, `scenario`: the situation in plain language. They describe the story and never state the right answer
  - `stated_lines`, `stated_budget_cents` (per month), `stated_usage` (`light`, `moderate` or `heavy`), `stated_notes`: what a prospect says they need (NULL for customers)
  - `starting_cart`: JSON list of items ready to send to `POST /v1/cart/{id}/items` (NULL when the persona has no cart)
  - `related_account_id`: another account belonging to the same family (two personas are linked so consolidation can be explored)

## Signals
- `usage_monthly(line_id, month, data_gb, voice_minutes, streaming_hours, hotspot_gb)`: up to 12 months per line (fewer for accounts newer than 12 months)
- `billing_history(account_id, month, total_cents, change_cents, change_reason)`: up to 12 months per account; `change_cents` is the change from the previous month and `change_reason` says why: `stable` (normal wobble), `device_installment` (a new phone's payment started), `installment_ended` (a phone's payments finished and the bill fell) or `promo_expired` (a discount ended and the bill rose to list price). When several apply in one month the order is `device_installment`, `installment_ended`, `promo_expired`. A promo only expires on accounts with at least 3 months of history. A bill is plans + protection + add-ons + device installments, minus the Home Internet bundle credit ($15) for accounts that have both Home Internet and a phone line. An installment only appears from the month the phone was bought
- `support_interactions(interaction_id, account_id, interaction_date, channel, topic, sentiment, resolved)`: contacts in the last 270 days. The personas have **pinned** counts so each tells one clear story (for example the at-risk couple has 5 recent contacts, the loyal family none)
  - `channel`: `phone`, `chat`, `app` or `store`; `topic`: `billing`, `network`, `device`, `plan_change` or `cancellation_inquiry`
  - `sentiment`: -1 (angry) to 1 (happy); `resolved`: 1 if resolved
- `account_signals(account_id, competitor_research_score, port_out_inquiry, app_sessions_30d)`: proxy signals; `competitor_research_score` is 0 to 1; `port_out_inquiry` is 1 if the account asked about porting its number away; `app_sessions_30d` counts recent app visits

## Things worth discovering
The data has real structure to find, such as which accounts are drifting, which households are paying for the wrong
plans, and which phones are worth trading in now. It is not uniformly random. Held-out outcomes (for example who
actually churned) are **not** in this database.

## Schema version history
- **9**: `personas` table (50 personas, ten per theme, with scenarios, prospects' stated needs and starting carts); `billing_history.change_reason`; invented accessories for every phone family
- **8**: `devices.sold_until` (customers only own phones that were on sale when bought); one plan per account; personas' support histories pinned; Home Internet bundle credit applied to bills
- **7**: promotions rebuilt around published offers and customer context (many condition columns, `source`, `per`); students get a `discount_group`
- **6**: protection add-ons gain per-claim deductibles (stub values)
- **5**: add-ons rebuilt from the site (generic names): `per`, `description`, `eligible_families`, `protection_tier`, `compatible_device_skus`; devices gain `protection_tier`
- **4**: plans rebuilt from the site: per-line price tables, line limits, eligibility, benefits; accounts gain `discount_group`
- **3**: devices rebuilt from the site (45 current plus 17 legacy): `status`, nullable `storage_gb`
- **2**: promotions gain `segment` and `requires_addon_kind` (replaced in version 7)
- **1**: first release
