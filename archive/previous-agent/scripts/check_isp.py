import hid, sys
for d in hid.enumerate():
    if d['vendor_id'] == 0x0C45:
        path = d['path']
        if isinstance(path, bytes): path = path.decode()
        print(path)
        sys.exit(0)
sys.exit(1)
