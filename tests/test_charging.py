"""Charging UI and suspend policy against synthetic power-supply lifecycles."""
import hashlib
import json
from pathlib import Path
import runpy
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "packages/charging"
DISPLAY = runpy.run_path(str(SOURCE / "libexec/tablet-charge-display"))


class ChargingDisplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.write("class/power_supply/qcom-battmgr-usb/online", 1)
        self.write("class/power_supply/qcom-battmgr-usb/usb_type", "[PD_PPS]")
        self.write("class/power_supply/qcom-battmgr-bat/voltage_now", 4_200_000)
        self.write("class/power_supply/qcom-battmgr-bat/current_now", 3_000_000)
        self.write("class/power_supply/qcom-battmgr-bat/temp", 310)

    def write(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(value))

    def snapshot(self):
        return DISPLAY["snapshot"](self.root, "erhai", False)

    def test_battery_power_is_net_and_separate_from_adapter_input(self):
        self.write("class/power_supply/qcom-battmgr-usb/voltage_now", 9_000_000)
        self.write("class/power_supply/qcom-battmgr-usb/current_now", 2_000_000)
        self.write("class/power_supply/qcom-battmgr-usb/charge_contract",
                   "protocol=pps state=charging request_mv=9000 request_ma=2000")
        sample = self.snapshot()
        self.assertAlmostEqual(sample["watts"], 12.6)
        self.assertEqual(sample["path"], "PPS")
        self.assertEqual((sample["request_v"], sample["request_a"]), (9, 2))

    def test_supervooc_does_not_reuse_inactive_pps_current(self):
        source = self.root / "class/power_supply/qcom-battmgr-usb"
        path, mv, ma = DISPLAY["path_details"](
            "erhai", source, {"protocol": "supervooc", "request_ma": "4000"}, "DCP")
        self.assertEqual((path, mv, ma), ("SUPERVOOC", None, None))

    def test_ufcs_and_fixed_pd_paths(self):
        source = self.root / "class/power_supply/qcom-battmgr-usb"
        for fields, expected in [
            ({"protocol": "ufcs", "state": "taper", "request_mv": "8800", "request_ma": "1500"},
             ("UFCS", 8800, 1500)),
            ({"fixed_pd_mv": "9000", "fixed_icl_ua": "2000000"}, ("PD 9 V", 9000, 2000)),
            ({"qc_mv": "9000"}, ("QC", None, None)),
        ]:
            with self.subTest(fields=fields):
                self.assertEqual(DISPLAY["path_details"]("erhai", source, fields, "DCP"), expected)

    def test_negative_current_reports_net_discharge(self):
        self.write("class/power_supply/qcom-battmgr-bat/current_now", -500_000)
        self.assertAlmostEqual(self.snapshot()["watts"], -2.1)

    def test_supervooc_input_uses_measured_pumps_when_buck_is_suspended(self):
        self.write("class/power_supply/qcom-battmgr-usb/current_now", 0)
        self.write("class/power_supply/qcom-battmgr-usb/charge_contract",
                   "protocol=supervooc state=deliver pump=1 serial_buck_suspended=1 "
                   "vbus_mv=9266 pump_ibus_ma=2483 request_ma=4000")
        sample = self.snapshot()
        self.assertEqual(sample["volts"], 9.266)
        self.assertEqual(sample["amps"], 2.483)
        self.assertAlmostEqual(sample["watts"], 12.6)

    def test_missing_pump_adc_is_unknown_instead_of_requested_current(self):
        self.write("class/power_supply/qcom-battmgr-usb/current_now", 0)
        self.write("class/power_supply/qcom-battmgr-usb/charge_contract",
                   "protocol=supervooc state=deliver pump=1 serial_buck_suspended=1 "
                   "vbus_mv=-1 pump_ibus_ma=-1 request_ma=4000")
        sample = self.snapshot()
        self.assertIsNone(sample["volts"])
        self.assertIsNone(sample["amps"])

    def test_missing_measurement_is_unknown_instead_of_zero(self):
        (self.root / "class/power_supply/qcom-battmgr-bat/current_now").unlink()
        self.assertIsNone(self.snapshot()["watts"])

    def test_unplug_hides_details_without_changing_policy(self):
        self.write("class/power_supply/qcom-battmgr-usb/online", 0)
        self.assertNotIn("watts", self.snapshot())
        sample = DISPLAY["snapshot"](self.root, "erhai", True)
        self.assertAlmostEqual(sample["watts"], 12.6)


class ChargeIdleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.wake = self.root / "wakeup0"
        self.wake.mkdir()
        (self.wake / "name").write_text("qcom-battmgr-charge")
        (self.wake / "active_time_ms").write_text("1000")
        gio = types.SimpleNamespace(DBusCallFlags=types.SimpleNamespace(NONE=0))
        glib = types.SimpleNamespace(
            SOURCE_CONTINUE=True, Variant=lambda signature, args: (signature, args), Error=RuntimeError)
        repository = types.SimpleNamespace(Gio=gio, GLib=glib)
        with patch.dict(sys.modules, {"gi": types.ModuleType("gi"), "gi.repository": repository,
                                      "pyudev": types.ModuleType("pyudev")}):
            self.idle = runpy.run_path(str(SOURCE / "libexec/tablet-charge-idle"))
        self.calls = []
        self.policy = object.__new__(self.idle["ChargeIdle"])
        self.policy.owner = ":1.42"
        self.policy.cookie = None
        self.policy.device = "erhai"
        self.policy.sysfs = self.root
        self.policy.bus = types.SimpleNamespace(call_sync=self.call)

    def call(self, *args):
        self.calls.append(args)
        return types.SimpleNamespace(unpack=lambda: (123,))

    def test_inhibit_only_suspend_and_release_when_unplugged(self):
        self.policy.update()
        self.assertEqual(self.policy.cookie, 123)
        self.assertEqual(self.calls[0][3], "Inhibit")
        # GNOME's 4 is suspend; 8 would also prevent display idle/blanking.
        self.assertEqual(self.calls[0][4][1][-1], 4)
        self.policy.update()
        self.assertEqual(len(self.calls), 1)
        (self.wake / "active_time_ms").write_text("0")
        self.policy.update()
        self.assertEqual(self.calls[1][3], "Uninhibit")
        self.assertIsNone(self.policy.cookie)

    def test_full_battery_retains_inhibitor_while_driver_wake_source_is_active(self):
        # The controller owns attachment policy; capacity/status do not gate it.
        self.policy.update()
        self.policy.update()
        self.assertEqual(self.policy.cookie, 123)
        self.assertEqual(len(self.calls), 1)

    def test_absent_or_unreadable_driver_does_not_block_sleep(self):
        (self.wake / "active_time_ms").write_text("unavailable")
        self.policy.update()
        self.assertEqual(self.calls, [])
        (self.wake / "active_time_ms").unlink()
        self.assertFalse(self.idle["charging_awake"](self.root, "erhai"))


class ImportedSourceTests(unittest.TestCase):
    def test_imported_files_match_recorded_sources(self):
        source = json.loads((SOURCE / "upstream-source.json").read_text())
        for entry in source["files"]:
            with self.subTest(file=entry["file"]):
                self.assertEqual(hashlib.sha256((SOURCE / entry["file"]).read_bytes()).hexdigest(),
                                 entry.get("local_sha256", entry["sha256"]))


class ChargeBehaviourTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.knob = root / "charge_behaviour"
        self.state = root / "state"
        self.knob.write_text("[auto] inhibit-charge\n")
        self.main = runpy.run_path(str(SOURCE / "libexec/tablet-charge-behaviour"))["main"]
        patcher = patch.dict(self.main.__globals__, {"KNOB": self.knob, "STATE": self.state})
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_mode(self, mode):
        with patch.object(sys, "argv", ["tablet-charge-behaviour", mode]):
            self.main()

    def test_persists_and_restores_supported_mode(self):
        self.run_mode("inhibit-charge")
        self.assertEqual((self.state / "behaviour").read_text(), "inhibit-charge\n")
        self.knob.write_text("[auto] inhibit-charge\n")
        self.run_mode("restore")
        self.assertEqual(self.knob.read_text(), "inhibit-charge\n")

    def test_rejected_write_preserves_previous_mode(self):
        self.run_mode("inhibit-charge")
        self.knob.write_text("[inhibit-charge]\n")
        with self.assertRaises(ValueError):
            self.run_mode("auto")
        self.assertEqual((self.state / "behaviour").read_text(), "inhibit-charge\n")
        self.assertEqual({file.name for file in self.state.iterdir()}, {"behaviour", "lock"})


if __name__ == "__main__":
    unittest.main()
