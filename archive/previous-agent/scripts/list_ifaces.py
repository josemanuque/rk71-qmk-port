import hid
devs = hid.enumerate(0x05AC, 0x024F)
for d in devs:
    print(f"iface={d['interface_number']} usage={d['usage']:04X} usagepage={d['usage_page']:04X} path={d['path']}")
