"""Offline regression tests. HA services are mocked; no running HA is required.

Run: python3 -m unittest discover -s tests -v
"""

import asyncio
import datetime as dt
import importlib.util
from pathlib import Path
import sys
import re
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "_mwa_test"
package = ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = package
# API requests are mocked so credentials, a network and requests are unnecessary.
requests_stub = ModuleType("requests")
requests_stub.RequestException = type("RequestException", (Exception,), {})
requests_stub.HTTPError = type("HTTPError", (requests_stub.RequestException,), {})
requests_stub.Session = object
with patch.dict(sys.modules, {"requests": requests_stub}):
    spec = importlib.util.spec_from_file_location(f"{PACKAGE}.api", ROOT / "api.py")
    api = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = api
    spec.loader.exec_module(api)
from _mwa_test.recorder import HourlyStatistics, _bucket_start, _hourly_buckets, _statistics_from_ledger

UTC = dt.timezone.utc
CENTRAL = ZoneInfo("America/Chicago")
NOW = dt.datetime(2026, 10, 14, 18, 30, tzinfo=UTC)
EARLIEST = NOW - dt.timedelta(days=7)


def row(hour, cons, **extra):
    return {"dateTime": f"2026-10-14T{hour:02}:00:00", "cons": cons, **extra}


def normalize(rows, **options):
    return _hourly_buckets(rows, now=NOW, earliest=EARLIEST, **options)


class BucketTests(unittest.TestCase):
    def test_hour_ending_utc(self):
        self.assertEqual(_bucket_start(row(12, 1)), dt.datetime(2026, 10, 14, 11, tzinfo=UTC))

    def test_local_summer_and_winter(self):
        for date, expected in [("2026-01-15T12:00:00", 17), ("2026-07-15T12:00:00", 16)]:
            self.assertEqual(_bucket_start({"dateTime": date}, "local", CENTRAL).hour, expected)

    def test_explicit_offset_preserved(self):
        self.assertEqual(_bucket_start({"dateTime": "2026-10-14T12:00:00+02:00"}, "local", CENTRAL).hour, 9)

    def test_ambiguous_local_time_requires_offset(self):
        with self.assertRaisesRegex(ValueError, "explicit offset"):
            _bucket_start({"dateTime": "2026-11-01T01:00:00"}, "local", CENTRAL)

    def test_future_and_estimated_excluded(self):
        result = normalize([row(19, 100), row(12, 4, estimationType=1), row(13, 3, estimationType="0")])
        self.assertEqual(list(result.values()), [3])

    def test_duplicates_replace_instead_of_add(self):
        result = normalize([row(12, 5), row(12, 5), row(12, 7)])
        self.assertEqual(list(result.values()), [7])

    def test_invalid_numeric_and_timestamp_values(self):
        values = [row(12, value) for value in (None, "NaN", "Infinity", "bad")]
        values += [{"cons": 1}, {"dateTime": "bad", "cons": 1}, {"dateTime": "2026-10-14T12:30:00", "cons": 1}]
        self.assertEqual(normalize(values), {})

    def test_outlier_and_negative_options(self):
        self.assertEqual(list(normalize([row(12, 2001), row(13, -5)]).values()), [0, 0])
        self.assertEqual(list(normalize([row(12, 2001), row(13, -5)], max_reasonable=0, skip_negative=False).values()), [2001, -5])

    def test_portal_batch_separates_into_original_hours(self):
        values = [65.4, 332.8, 15, 3.4, 16.1]
        buckets = normalize([row(hour, value) for hour, value in zip(range(3, 8), values)])
        stats = _statistics_from_ledger(buckets)
        self.assertEqual([r["start"].hour for r in stats], list(range(1, 7)))
        self.assertEqual(stats[0]["sum"], 0)
        self.assertAlmostEqual(stats[-1]["sum"], 432.7)
        self.assertEqual([round(stats[i]["sum"] - stats[i-1]["sum"], 1) for i in range(1, len(stats))], values)

    def test_missing_hours_can_be_filled_later(self):
        buckets = normalize([row(3, 10), row(5, 20)])
        self.assertEqual([r["sum"] for r in _statistics_from_ledger(buckets)], [0, 10, 10, 30])
        buckets.update(normalize([row(4, 5)]))
        self.assertEqual([r["sum"] for r in _statistics_from_ledger(buckets)], [0, 10, 15, 35])


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = object.__new__(api.MyWaterAdvisorApi)
        self.client._meter_id = 42

    def test_hourly_endpoint_dates(self):
        calls = []
        def request(method, url, **kwargs):
            calls.append(url)
            return [row(12, 5)]
        self.client._request_json = request
        result = self.client.fetch_hourly_data(NOW - dt.timedelta(days=7), NOW, CENTRAL)
        self.assertEqual(len(result), 1)
        self.assertTrue(calls[0].endswith('/consumption/hourly/42/2026-10-06/2026-10-15'))

    def test_unexpected_payload_is_an_error(self):
        self.client._request_json = lambda *a, **kw: {"error": "bad"}
        with self.assertRaises(api.InvalidConsumptionData):
            self.client.fetch_hourly_data(EARLIEST, NOW)


class ImportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.saved = {}
        self.database = {}
        self.imports = []
        saved, database, imports = self.saved, self.database, self.imports
        class Store:
            def __init__(self, hass, version, key): self.key = key
            async def async_load(self): return saved.get(self.key)
            async def async_save(self, data): saved[self.key] = data
        def add(hass, metadata, rows):
            # Mirror HA's external-statistics ID validation at the service boundary.
            if not re.fullmatch(r'(?!.*__)(?!_)[0-9a-z_]+(?<!_):(?!_)[0-9a-z_]+(?<!_)', metadata['statistic_id']):
                raise ValueError('Invalid statistic_id')
            imports.append((metadata, rows))
            for record in rows:
                database[(metadata['statistic_id'], record['start'])] = record
        modules = {}
        for name in ('homeassistant', 'homeassistant.helpers', 'homeassistant.helpers.storage', 'homeassistant.components', 'homeassistant.components.recorder', 'homeassistant.components.recorder.models', 'homeassistant.components.recorder.statistics', 'homeassistant.util', 'homeassistant.util.unit_conversion', 'homeassistant.exceptions', 'homeassistant.helpers.update_coordinator'):
            modules[name] = ModuleType(name)
        modules['homeassistant.helpers.storage'].Store = Store
        model = modules['homeassistant.components.recorder.models']
        model.StatisticData = dict
        model.StatisticMetaData = dict
        model.StatisticMeanType = SimpleNamespace(NONE=0)
        modules['homeassistant.components.recorder.statistics'].async_add_external_statistics = add
        modules['homeassistant.util.unit_conversion'].VolumeConverter = SimpleNamespace(UNIT_CLASS='volume')
        class CoordinatorBase:
            def __init__(self, hass, *args, **kwargs): self.hass = hass
        modules['homeassistant.exceptions'].ConfigEntryAuthFailed = type('ConfigEntryAuthFailed', (Exception,), {})
        modules['homeassistant.helpers.update_coordinator'].DataUpdateCoordinator = CoordinatorBase
        modules['homeassistant.helpers.update_coordinator'].UpdateFailed = type('UpdateFailed', (Exception,), {})
        modules['requests'] = requests_stub
        self.patcher = patch.dict(sys.modules, modules)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.hass = SimpleNamespace()
        self.statistic_id = 'mywateradvisor:test_hourly_utc'
        self.ledger = HourlyStatistics(self.hass, self.statistic_id)
        await self.ledger.async_load()

    async def update(self, rows):
        await self.ledger.async_update(normalize(rows), NOW, EARLIEST)

    async def test_repeat_import_and_restart_are_idempotent(self):
        await self.update([row(3, 10), row(4, 20)])
        original = dict(self.database)
        await self.update([row(3, 10), row(4, 20)])
        self.assertEqual(original, self.database)
        self.ledger = HourlyStatistics(self.hass, self.statistic_id)
        await self.ledger.async_load()
        await self.update([row(3, 10), row(4, 20)])
        self.assertEqual(original, self.database)
        self.assertEqual(self.ledger.total, 30)
        self.assertEqual(self.imports[-1][0]['source'], 'mywateradvisor')

    async def test_correction_rebuilds_all_later_sums(self):
        await self.update([row(3, 10), row(4, 20), row(5, 30)])
        await self.update([row(3, 5)])
        self.assertEqual(self.ledger.total, 55)
        sums = [r['sum'] for _, r in sorted(self.database.items(), key=lambda item: item[0][1])]
        self.assertEqual(sums, [0, 5, 25, 55])

    async def test_new_late_bucket_and_zero_replacement(self):
        await self.update([row(3, 10), row(5, 20)])
        await self.update([row(4, 5), row(5, 0)])
        self.assertEqual(self.ledger.total, 15)
        self.assertEqual(self.imports[-1][1][-1]['sum'], 15)

    async def test_rejected_replacement_removes_previous_spike(self):
        await self.update([row(3, 1500), row(4, 20)])
        await self.update([row(3, 3000)])
        self.assertEqual(self.ledger.total, 20)

    async def test_estimate_does_not_overwrite_real_bucket(self):
        await self.update([row(3, 10)])
        await self.update([row(3, 50, estimationType=1)])
        self.assertEqual(self.ledger.total, 10)

    async def test_queued_import_replayed_after_restart(self):
        await self.update([row(3, 10)])
        self.database.clear()  # Simulate HA stopping before recorder committed.
        self.ledger = HourlyStatistics(self.hass, self.statistic_id)
        await self.ledger.async_load()
        await self.update([row(3, 10)])
        self.assertEqual(len(self.database), 2)
        self.assertEqual(min(r['sum'] for r in self.database.values()), 0)


    async def test_coordinator_fetches_normalizes_and_imports(self):
        from _mwa_test.coordinator import MyWaterAdvisorDataUpdateCoordinator
        class Clock(dt.datetime):
            @classmethod
            def now(cls, tz=None): return NOW
        async def executor(function): return function()
        self.hass.config = SimpleNamespace(time_zone='America/Chicago')
        self.hass.async_add_executor_job = executor
        entry = SimpleNamespace(entry_id='01K7J7R3QAP5JZ4E9WRQ6GM2FA', options={}, data={'username':'test','password':'test'})
        coordinator = MyWaterAdvisorDataUpdateCoordinator(self.hass, entry)
        calls = []
        def fetch(start, end):
            calls.append(start)
            return [row(3, 65.4), row(4, 332.8), row(5, 15), row(6, 3.4), row(7, 16.1)]
        coordinator._fetch = fetch
        module = sys.modules[MyWaterAdvisorDataUpdateCoordinator.__module__]
        with patch.object(module, 'dt', SimpleNamespace(datetime=Clock, timedelta=dt.timedelta, timezone=dt.timezone)):
            first = await coordinator._async_update_data()
            second = await coordinator._async_update_data()
        self.assertEqual(first['total'], 432.7)
        self.assertEqual(first['total'], second['total'])
        self.assertEqual(first['fetched_buckets'], 5)
        self.assertTrue(first['statistic_id'].startswith('mywateradvisor:01k7j7r3qap5jz4e9wrq6gm2fa_'))
        self.assertEqual(first['statistic_id'], first['statistic_id'].lower())
        coordinator.statistics.last_success = NOW - dt.timedelta(days=20)
        with patch.object(module, 'dt', SimpleNamespace(datetime=Clock, timedelta=dt.timedelta, timezone=dt.timezone)):
            await coordinator._async_update_data()
        self.assertEqual(calls[-1], NOW - dt.timedelta(days=21))

    async def test_time_mode_change_uses_separate_statistics(self):
        from _mwa_test.coordinator import MyWaterAdvisorDataUpdateCoordinator
        self.hass.config = SimpleNamespace(time_zone='America/Chicago')
        entry = SimpleNamespace(entry_id='test', options={}, data={})
        utc = MyWaterAdvisorDataUpdateCoordinator(self.hass, entry)
        entry.options = {'time_raw_mode':'local'}
        local = MyWaterAdvisorDataUpdateCoordinator(self.hass, entry)
        self.assertNotEqual(utc.statistic_id, local.statistic_id)
        self.assertEqual(str(local.time_zone), 'America/Chicago')


if __name__ == '__main__':
    unittest.main()
