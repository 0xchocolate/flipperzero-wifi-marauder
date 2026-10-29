import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
START = (ROOT / "scenes/wifi_marauder_scene_start.c").read_text()
CONSOLE = (ROOT / "scenes/wifi_marauder_scene_console_output.c").read_text()
TEXT_INPUT = (ROOT / "scenes/wifi_marauder_scene_text_input.c").read_text()
EXECUTOR = (ROOT / "script/wifi_marauder_script_executor.c").read_text()
STAGE_ADD = (ROOT / "scenes/wifi_marauder_scene_script_stage_add.c").read_text()
APP_I = (ROOT / "wifi_marauder_app_i.h").read_text()
APP_H = (ROOT / "wifi_marauder_app.h").read_text()
FAM = (ROOT / "application.fam").read_text()


def menu_item_labels():
    marker = "const WifiMarauderItem items[NUM_MENU_ITEMS] = {"
    start = START.index(marker) + len(marker)
    labels = []
    depth = 1
    in_string = False
    escaped = False
    item_start = None
    for index in range(start, len(START)):
        char = START[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
            if depth == 2:
                item_start = index
        elif char == "}":
            if depth == 2 and item_start is not None:
                item = START[item_start:index]
                match = re.search(r'\{\s*"([^"]+)"', item)
                if match:
                    labels.append(match.group(1))
                item_start = None
            depth -= 1
            if depth == 0:
                break
    return labels


def function_body(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[brace + 1:index]
    raise AssertionError(f"unterminated function: {signature}")


class CliParityTests(unittest.TestCase):
    def test_menu_count_and_trailing_entries(self):
        labels = menu_item_labels()
        declared = int(re.search(r"#define NUM_MENU_ITEMS \((\d+)\)", APP_I).group(1))
        self.assertEqual(declared, len(labels))
        self.assertEqual(labels[-2:], ["Scripts", "Save to flipper sdcard"])

    def test_required_v120_commands_are_first_class(self):
        required = {
            "csimotion start", "csimotion status", "csimotion recalibrate",
            "geofence list", "geofence set", "geofence clear",
            "save -a", "save -s", "load -a", "load -s",
            "add -a -b", "add -c -b", "select -a -f",
            "gps -n native", "gps -n all", "gps -n gps", "gps -n glonass",
            "gps -n galileo", "gps -n navic", "gps -n qzss",
            "gps -n beidou", "gps -n beidou -b",
        }
        for command in required:
            self.assertIn(f'"{command}"', START)
        for setting in ("ForcePMKID", "ForceProbe", "SavePCAP", "EnableLED", "EPDeauth", "Censor"):
            self.assertIn(f'"settings -s {setting} enable"', START)
            self.assertIn(f'"settings -s {setting} disable"', START)
        self.assertNotIn("<index>", START)
        self.assertNotIn("<password>", START)

    def test_removed_commands_are_not_emitted_or_newly_selectable(self):
        self.assertNotIn('"scanap\\n"', EXECUTOR)
        self.assertNotIn('"scansta\\n"', EXECUTOR)
        self.assertIn('"scanall\\n"', EXECUTOR)
        self.assertNotIn('"[+] Sniff Esp"', STAGE_ADD)
        self.assertNotIn('"sniffesp"', EXECUTOR)
        parser = (ROOT / "script/wifi_marauder_script.c").read_text()
        load_stages = function_body(parser, "void _wifi_marauder_script_load_stages")
        self.assertNotIn("WifiMarauderScriptStageTypeSniffEsp", load_stages)
        self.assertNotIn("btwardrive", CONSOLE)

    def test_manual_deauth_and_compact_script_selection(self):
        self.assertIn('"attack -t deauth -s %s -d %s"', TEXT_INPUT)
        self.assertNotIn("%18s", TEXT_INPUT)
        self.assertIn('i == 0 ? "" : ","', EXECUTOR)
        self.assertNotIn('"%d, "', EXECUTOR)
        self.assertIn("(size_t)written >= sizeof(command) - command_length", EXECUTOR)
        self.assertIn("if(command_length + 1 >= sizeof(command)) return", EXECUTOR)
        self.assertIn("if(stage->type != WifiMarauderScriptSelectTypeAp) return", EXECUTOR)
        select_menu = (ROOT / "script/menu/wifi_marauder_script_stage_menu_select.c").read_text()
        self.assertIn("AP only", select_menu)
        self.assertIn("app->user_input_string_reference = NULL", select_menu)

    def test_version_metadata_is_consistent(self):
        self.assertIn('#define WIFI_MARAUDER_APP_VERSION "v0.8.0"', APP_H)
        self.assertRegex(FAM, r"fap_version=\(7, 12\)")

    def test_script_edit_buffers_match_input_capacity(self):
        user_input = (ROOT / "scenes/wifi_marauder_scene_user_input.c").read_text()
        parser = (ROOT / "script/wifi_marauder_script.c").read_text()
        select_menu = (ROOT / "script/menu/wifi_marauder_script_stage_menu_select.c").read_text()
        exec_menu = (ROOT / "script/menu/wifi_marauder_script_stage_menu_exec.c").read_text()
        self.assertIn("realloc(*app->user_input_string_reference, input_length + 1)", user_input)
        self.assertIn("sizeof(app->text_input_store)", user_input)
        self.assertIn("wifi_marauder_script_duplicate_editable_string", parser)
        for source in (select_menu, exec_menu):
            self.assertIn("WIFI_MARAUDER_TEXT_INPUT_STORE_SIZE + 1", source)

    def test_stop_on_exit_classification_and_guard(self):
        body = function_body(START, "static bool wifi_marauder_command_stops_on_exit")
        long_running = (
            "scanall", "pingscan", "arpscan", "recon wifi", "recon ble",
            "remoteid scan", "remoteid track", "attack ", "blespam ", "spoofat ", "wardrive",
            "evilportal -c start", "karma ", "sniff", "mactrack", "packetcount",
            "foxhunt ", "portscan ", "gps -t", "gpsdata", "nmea",
            "csimotion start",
        )
        for command in long_running:
            self.assertIn(f'"{command}"', body)
        for command in (
            "recon status", "csimotion status", "csimotion recalibrate",
            "geofence list", "settings", "help", "info",
        ):
            self.assertNotIn(f'"{command}"', body)
        self.assertIn("if(app->stop_on_exit || ran_script)", CONSOLE)
        self.assertIn("const bool ran_script = app->script != NULL", CONSOLE)
        self.assertNotIn("if(app->is_command) {\n        wifi_marauder_uart_tx", CONSOLE)
        self.assertIn("app->show_stopscan_tip = app->stop_on_exit", START)

    def test_conditional_keyboard_prompts(self):
        self.assertIn(r'const char quoted_prefix[] = "select -a -f \""', TEXT_INPUT)
        self.assertIn("max_filter_length", TEXT_INPUT)
        self.assertIn('strcmp(app->selected_tx_string, "csimotion start")', START)
        self.assertIn('strcmp(app->selected_tx_string, "csimotion status")', START)
        self.assertIn('strcmp(app->selected_tx_string, "geofence list")', START)
        for prompt in (
            "Enter AP index", "slot lat lon radius name", "Enter geofence slot (1-5)",
            "MAC [-ch channel] [-e SSID]", "MAC -ap AP_index",
        ):
            self.assertIn(prompt, TEXT_INPUT)


if __name__ == "__main__":
    unittest.main()
