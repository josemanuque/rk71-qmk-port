"""Generate keyboard.json for royal_kludge/rk71_rgb from the matrix decoded out of stock firmware V1.12.
Each key: (row, col, label, x, w). y = row. Electrical matrix: rows D11,D10,D9,D8,D7; cols A8-A15,B0-B7.
"""
import json, sys

K = [
    # row 0
    (0,0,"Esc",0,1),(0,1,"1",1,1),(0,2,"2",2,1),(0,3,"3",3,1),(0,4,"4",4,1),(0,5,"5",5,1),(0,6,"6",6,1),
    (0,7,"7",7,1),(0,8,"8",8,1),(0,9,"9",9,1),(0,10,"0",10,1),(0,11,"-",11,1),(0,12,"=",12,1),
    (0,13,"Backspace",13,2),(0,14,"Ins",15,1),(0,15,"Home",16,1),
    # row 1
    (1,0,"Tab",0,1.5),(1,1,"Q",1.5,1),(1,2,"W",2.5,1),(1,3,"E",3.5,1),(1,4,"R",4.5,1),(1,5,"T",5.5,1),
    (1,6,"Y",6.5,1),(1,7,"U",7.5,1),(1,8,"I",8.5,1),(1,9,"O",9.5,1),(1,10,"P",10.5,1),(1,11,"[",11.5,1),
    (1,12,"]",12.5,1),(1,13,"\\",13.5,1.5),(1,14,"Del",15,1),(1,15,"End",16,1),
    # row 2
    (2,0,"Caps",0,1.75),(2,1,"A",1.75,1),(2,2,"S",2.75,1),(2,3,"D",3.75,1),(2,4,"F",4.75,1),(2,5,"G",5.75,1),
    (2,6,"H",6.75,1),(2,7,"J",7.75,1),(2,8,"K",8.75,1),(2,9,"L",9.75,1),(2,10,";",10.75,1),(2,11,"'",11.75,1),
    (2,13,"Enter",12.75,2.25),(2,14,"Pause",15,1),(2,15,"PgUp",16,1),
    # row 3
    (3,0,"LShift",0,2.25),(3,2,"Z",2.25,1),(3,3,"X",3.25,1),(3,4,"C",4.25,1),(3,5,"V",5.25,1),(3,6,"B",6.25,1),
    (3,7,"N",7.25,1),(3,8,"M",8.25,1),(3,9,",",9.25,1),(3,10,".",10.25,1),(3,11,"/",11.25,1),
    (3,13,"RShift",12.25,2.75),(3,14,"Up",15,1),(3,15,"PgDn",16,1),
    # row 4
    (4,0,"LCtrl",0,1.25),(4,1,"LWin",1.25,1.25),(4,2,"LAlt",2.5,1.25),(4,6,"Space",3.75,6.25),
    (4,10,"RAlt",10,1.25),(4,11,"Fn",11.25,1.25),(4,12,"RCtrl",12.5,1.25),
    (4,13,"Left",14,1),(4,14,"Down",15,1),(4,15,"Right",16,1),
]
assert len(K) == 71, len(K)
assert len({(r, c) for r, c, *_ in K}) == 71

MODS = {"Esc","Backspace","Ins","Home","Tab","\\","Del","End","Caps","Enter","Pause","PgUp","LShift",
        "RShift","Up","PgDn","LCtrl","LWin","LAlt","RAlt","Fn","RCtrl","Left","Down","Right"}
MAXX, MAXY = 16, 4

layout, leds = [], []
for r, c, lab, x, w in K:
    k = {"label": lab, "matrix": [r, c], "x": x, "y": r}
    if w != 1: k["w"] = w
    layout.append(k)
    cx = x + w / 2 - 0.5
    leds.append({"matrix": [r, c], "x": round(cx * 224 / MAXX), "y": round(r * 64 / MAXY),
                 "flags": 1 if lab in MODS else 4})

kb = {
    "keyboard_name": "RK71 RGB",
    "manufacturer": "Royal Kludge",
    "url": "http://en.rkgaming.com",
    "maintainer": "josemanuque",
    "usb": {"vid": "0x0C45", "pid": "0x8071", "device_version": "1.0.0"},
    "development_board": "sn32f240b_shared_matrix",
    "diode_direction": "COL2ROW",
    "debounce": 10,
    "matrix_pins": {
        "cols": ["A8","A9","A10","A11","A12","A13","A14","A15","B0","B1","B2","B3","B4","B5","B6","B7"],
        "rows": ["D11","D10","D9","D8","D7"],
    },
    "features": {"bootmagic": True, "extrakey": True, "nkro": True, "rgb_matrix": True,
                 "mousekey": False, "console": False, "command": False, "audio": False, "backlight": False},
    "bootmagic": {"matrix": [0, 0]},
    "dynamic_keymap": {"layer_count": 5},
    "rgb_matrix": {
        "driver": "sn32f2xx",
        "max_brightness": 200,
        "animations": {k: True for k in ["band_val","breathing","cycle_all","cycle_left_right","cycle_up_down",
                       "cycle_pinwheel","cycle_spiral","digital_rain","gradient_left_right","gradient_up_down",
                       "rainbow_moving_chevron","raindrops","jellybean_raindrops","solid_reactive_simple",
                       "solid_reactive_multiwide","splash","multisplash","typing_heatmap","pixel_rain"]},
        "layout": leds,
    },
    "layouts": {"LAYOUT": {"layout": layout}},
}
json.dump(kb, open(sys.argv[1], "w"), indent=4)
print("wrote", sys.argv[1], "keys:", len(layout))

# ---- VIA definition (v3) -------------------------------------------------
if len(sys.argv) > 2:
    rows = []
    for r in range(5):
        keys = sorted([k for k in K if k[0] == r], key=lambda k: k[3])
        row, cur = [], 0.0
        for rr, c, lab, x, w in keys:
            props = {}
            if abs(x - cur) > 1e-6: props["x"] = round(x - cur, 2)
            if w != 1: props["w"] = w
            if props: row.append(props)
            row.append(f"{rr},{c}")
            cur = x + w
        rows.append(row)
    via = {"name": "RK71 RGB (QMK)", "vendorId": "0x0C45", "productId": "0x8071",
           "matrix": {"rows": 5, "cols": 16}, "keycodes": ["qmk_lighting"],
           "menus": ["qmk_rgb_matrix", {
               # keyboard/rk71_rgb/rk71_rgb.c via_custom_value_command_kb(): channel 0, values 1..3
               "label": "Side lights",
               "content": [{"label": "Side lights", "content": [
                   {"label": "Colour", "type": "dropdown", "options": ["Follow keyboard", "Fixed colour", "Off"],
                    "content": ["id_side_mode", 0, 1]},
                   {"showIf": "{id_side_mode} == 1", "label": "Fixed colour", "type": "dropdown",
                    "options": ["White", "Red", "Yellow", "Green", "Cyan", "Blue", "Magenta"],
                    "content": ["id_side_colour", 0, 2]},
                   {"label": "Brightness", "type": "range", "options": [0, 31],
                    "content": ["id_side_bright", 0, 8]},
                   {"label": "Red", "type": "range", "options": [0, 31], "content": ["id_side_red", 0, 5]},
                   {"label": "Green", "type": "range", "options": [0, 31], "content": ["id_side_green", 0, 6]},
                   {"label": "Blue", "type": "range", "options": [0, 31], "content": ["id_side_blue", 0, 7]},
                   {"label": "Show status (pairing, mode, battery)", "type": "toggle",
                    "content": ["id_side_status", 0, 3]}]}]}],
           "customKeycodes": [  # QK_KB_0… in keyboard/rk71_rgb/rk71_rgb.h, same order
               {"name": f"BT {n}", "title": f"Bluetooth device {n} (hold 3 s: pair)", "shortName": f"BT{n}"}
               for n in range(1, 6)] + [
               {"name": "BT/USB", "title": "Switch wired / Bluetooth (hold 3 s: pair current slot)", "shortName": "BT/USB"},
               {"name": "BT Clear", "title": "Hold 3 s: forget all Bluetooth devices", "shortName": "BTclr"},
               {"name": "Battery", "title": "Show the battery level on the side lights", "shortName": "Batt"}],
           "layouts": {"keymap": rows}}
    json.dump(via, open(sys.argv[2], "w"), indent=2)
    print("wrote", sys.argv[2])
