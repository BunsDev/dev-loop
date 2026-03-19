"""Tests for scripts/import-dashboards.py parsing functions."""

import importlib
import sys
from pathlib import Path

# Hyphenated filename requires importlib
_script = Path(__file__).parent.parent / "scripts" / "import-dashboards.py"
_spec = importlib.util.spec_from_file_location("import_dashboards", _script)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


class TestParseSelectAliases:
    def test_simple_columns(self):
        sql = "SELECT a, b FROM t"
        assert mod._parse_select_aliases(sql) == ["a", "b"]

    def test_aliased_aggregate(self):
        sql = "SELECT COUNT(*) as total FROM t"
        assert mod._parse_select_aliases(sql) == ["total"]

    def test_nested_parens(self):
        sql = "SELECT ROUND(AVG(x), 2) as avg_x FROM t"
        assert mod._parse_select_aliases(sql) == ["avg_x"]

    def test_date_trunc(self):
        sql = "SELECT DATE_TRUNC('day', TO_TIMESTAMP(_timestamp / 1000000)) as day, COUNT(*) as total FROM t"
        assert mod._parse_select_aliases(sql) == ["day", "total"]

    def test_no_from_clause(self):
        sql = "SELECT a, b"
        assert mod._parse_select_aliases(sql) == []

    def test_multiple_aggregates(self):
        sql = "SELECT SUM(a) as s, AVG(b) as a, MAX(c) as m FROM t"
        assert mod._parse_select_aliases(sql) == ["s", "a", "m"]

    def test_bare_column_with_table_prefix(self):
        sql = "SELECT t.column_name FROM t"
        assert mod._parse_select_aliases(sql) == ["column_name"]

    def test_case_expression(self):
        sql = "SELECT SUM(CASE WHEN x = 1 THEN 1 ELSE 0 END) as hits FROM t"
        assert mod._parse_select_aliases(sql) == ["hits"]


class TestMakeFields:
    def test_time_column_goes_to_x_axis(self):
        sql = "SELECT DATE_TRUNC('day', TO_TIMESTAMP(_timestamp / 1000000)) as day, COUNT(*) as total FROM t GROUP BY day"
        fields = mod._make_fields(sql, "bar")
        x_aliases = [f["alias"] for f in fields["x"]]
        y_aliases = [f["alias"] for f in fields["y"]]
        assert "day" in x_aliases
        assert "total" in y_aliases

    def test_aggregate_goes_to_y_axis(self):
        sql = "SELECT SUM(x) as total FROM t"
        fields = mod._make_fields(sql, "area")
        y_aliases = [f["alias"] for f in fields["y"]]
        assert "total" in y_aliases

    def test_fallback_timestamp_when_no_x(self):
        sql = "SELECT COUNT(*) as total FROM t"
        fields = mod._make_fields(sql, "bar")
        x_aliases = [f["alias"] for f in fields["x"]]
        assert "_timestamp" in x_aliases

    def test_empty_aliases_still_produce_fields(self):
        # No FROM clause → empty aliases
        sql = "SELECT a, b"
        fields = mod._make_fields(sql, "line")
        # Should have fallback x at minimum
        assert len(fields["x"]) >= 1

    def test_group_by_dimension_goes_to_x(self):
        sql = "SELECT persona, COUNT(*) as runs FROM t GROUP BY persona"
        fields = mod._make_fields(sql, "bar")
        x_aliases = [f["alias"] for f in fields["x"]]
        assert "persona" in x_aliases

    def test_colors_assigned_to_y(self):
        sql = "SELECT COUNT(*) as total FROM t"
        fields = mod._make_fields(sql, "bar")
        for y in fields["y"]:
            assert y["color"] is not None


class TestFixAggregateTimestamp:
    def test_pure_aggregate_gets_min_timestamp(self):
        sql = "SELECT COUNT(*) as total FROM t"
        fixed = mod._fix_aggregate_timestamp(sql)
        assert "MIN(_timestamp) as _timestamp" in fixed

    def test_group_by_left_unchanged(self):
        sql = "SELECT day, COUNT(*) as total FROM t GROUP BY day"
        fixed = mod._fix_aggregate_timestamp(sql)
        assert fixed == sql

    def test_already_has_min_timestamp(self):
        sql = "SELECT MIN(_timestamp) as _timestamp, COUNT(*) as total FROM t"
        fixed = mod._fix_aggregate_timestamp(sql)
        # Should not double up
        assert fixed.count("MIN(_timestamp)") == 1

    def test_no_aggregate_left_unchanged(self):
        sql = "SELECT a, b FROM t"
        fixed = mod._fix_aggregate_timestamp(sql)
        assert fixed == sql

    def test_round_avg_is_aggregate(self):
        sql = "SELECT ROUND(AVG(x), 2) as avg_x FROM t"
        fixed = mod._fix_aggregate_timestamp(sql)
        assert "MIN(_timestamp)" in fixed
