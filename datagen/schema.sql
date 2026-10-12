PRAGMA foreign_keys = ON;

CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE devices (
  sku TEXT PRIMARY KEY, name TEXT NOT NULL, manufacturer TEXT NOT NULL, tier TEXT NOT NULL,
  storage_gb INTEGER, msrp_cents INTEGER NOT NULL, release_date TEXT NOT NULL,
  status TEXT NOT NULL, protection_tier INTEGER NOT NULL, sold_until TEXT,
  data_source TEXT NOT NULL DEFAULT 'stub'
);
CREATE TABLE plans (
  sku TEXT PRIMARY KEY, name TEXT NOT NULL, family TEXT NOT NULL, variant TEXT NOT NULL, tier TEXT NOT NULL,
  line_prices TEXT NOT NULL, extra_line_cents INTEGER NOT NULL, min_lines INTEGER NOT NULL, max_lines INTEGER,
  data_cap_gb INTEGER, hotspot_high_speed_gb INTEGER NOT NULL, hotspot_unlimited INTEGER NOT NULL,
  canada_mexico_gb INTEGER, intl_data_gb INTEGER, video_quality TEXT, price_guarantee_years INTEGER,
  priority_network INTEGER NOT NULL, prices_include_autopay INTEGER NOT NULL, device_connection_cents INTEGER,
  eligibility TEXT, perks TEXT NOT NULL, upgrade_note TEXT, status TEXT NOT NULL,
  data_source TEXT NOT NULL DEFAULT 'stub'
);
CREATE TABLE addons (
  sku TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
  monthly_cents INTEGER NOT NULL, one_time_cents INTEGER NOT NULL, per TEXT NOT NULL, description TEXT,
  eligible_families TEXT, protection_tier INTEGER, compatible_device_skus TEXT,
  deductible_screen_cents INTEGER, deductible_damage_cents INTEGER, deductible_loss_theft_cents INTEGER,
  data_source TEXT NOT NULL DEFAULT 'stub'
);
CREATE TABLE promotions (
  sku TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, value_cents INTEGER NOT NULL, source TEXT NOT NULL,
  payout_months INTEGER, per TEXT NOT NULL, max_units INTEGER, requires_new_line INTEGER NOT NULL,
  requires_port_in INTEGER NOT NULL, requires_tradein INTEGER NOT NULL, new_line_or_tradein INTEGER NOT NULL,
  requires_device INTEGER NOT NULL, requires_byod INTEGER NOT NULL, device_skus TEXT, plan_families TEXT,
  plan_variants TEXT, min_plan_cents INTEGER, discount_plan_only INTEGER NOT NULL, discount_groups TEXT,
  credit_tiers TEXT, min_lines INTEGER NOT NULL, min_tenure_months INTEGER, min_device_age_months INTEGER,
  min_support_contacts_90d INTEGER, requires_addon_kind TEXT, min_accessories INTEGER, percent_off INTEGER,
  description TEXT, data_source TEXT NOT NULL DEFAULT 'stub'
);
CREATE TABLE tradein_curves (
  device_sku TEXT NOT NULL REFERENCES devices(sku), age_months INTEGER NOT NULL,
  value_cents INTEGER NOT NULL, PRIMARY KEY (device_sku, age_months)
);

CREATE TABLE accounts (
  account_id TEXT PRIMARY KEY, segment TEXT NOT NULL, tenure_months INTEGER NOT NULL,
  language TEXT NOT NULL, contact_preference TEXT NOT NULL, credit_tier TEXT NOT NULL,
  autopay INTEGER NOT NULL, discount_group TEXT, persona_note TEXT
);
CREATE TABLE lines (
  line_id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(account_id),
  member_label TEXT NOT NULL, member_role TEXT NOT NULL,
  plan_sku TEXT NOT NULL REFERENCES plans(sku), device_sku TEXT REFERENCES devices(sku),
  byod INTEGER NOT NULL, device_purchase_date TEXT,
  financing_balance_cents INTEGER NOT NULL, financing_months_remaining INTEGER NOT NULL,
  monthly_installment_cents INTEGER NOT NULL, tradein_eligible INTEGER NOT NULL
);
CREATE TABLE line_addons (
  line_id TEXT NOT NULL REFERENCES lines(line_id), addon_sku TEXT NOT NULL REFERENCES addons(sku),
  PRIMARY KEY (line_id, addon_sku)
);
CREATE TABLE account_addons (
  account_id TEXT NOT NULL REFERENCES accounts(account_id), addon_sku TEXT NOT NULL REFERENCES addons(sku),
  PRIMARY KEY (account_id, addon_sku)
);
CREATE TABLE usage_monthly (
  line_id TEXT NOT NULL REFERENCES lines(line_id), month TEXT NOT NULL,
  data_gb REAL NOT NULL, voice_minutes INTEGER NOT NULL, streaming_hours REAL NOT NULL,
  hotspot_gb REAL NOT NULL, PRIMARY KEY (line_id, month)
);
CREATE TABLE billing_history (
  account_id TEXT NOT NULL REFERENCES accounts(account_id), month TEXT NOT NULL,
  total_cents INTEGER NOT NULL, change_cents INTEGER NOT NULL, change_reason TEXT NOT NULL,
  PRIMARY KEY (account_id, month)
);
CREATE TABLE support_interactions (
  interaction_id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(account_id),
  interaction_date TEXT NOT NULL, channel TEXT NOT NULL, topic TEXT NOT NULL,
  sentiment REAL NOT NULL, resolved INTEGER NOT NULL
);
CREATE TABLE account_signals (
  account_id TEXT PRIMARY KEY REFERENCES accounts(account_id),
  competitor_research_score REAL NOT NULL, port_out_inquiry INTEGER NOT NULL,
  app_sessions_30d INTEGER NOT NULL
);

CREATE TABLE personas (
  persona_id TEXT PRIMARY KEY, account_id TEXT REFERENCES accounts(account_id), kind TEXT NOT NULL,
  title TEXT NOT NULL, primary_theme TEXT NOT NULL, secondary_themes TEXT, scenario TEXT NOT NULL,
  stated_lines INTEGER, stated_budget_cents INTEGER, stated_usage TEXT, stated_notes TEXT, starting_cart TEXT,
  related_account_id TEXT REFERENCES accounts(account_id)
);

CREATE INDEX idx_lines_account ON lines(account_id);
CREATE INDEX idx_support_account ON support_interactions(account_id, interaction_date);
