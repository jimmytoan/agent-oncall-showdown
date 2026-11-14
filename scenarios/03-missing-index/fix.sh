#!/usr/bin/env bash
# Reference fix (what a careful human would do). Used to self-test the scenario.
source "$(dirname "$0")/../_lib.sh"
psql_q "CREATE INDEX CONCURRENTLY products_category_price_idx ON products (category, price)" >/dev/null
