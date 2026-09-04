# Offline simulation of acquire_link escalation (no hardware needed).
# Fakes sysfs/configfs, the accessory device, netlink uevents and the clock,
# then drives the recovery state machine through its scenarios.
import sys, types, io, os, time, builtins

SRC = open(r'D:\code\sfos-carlife\harbour-sailife\carlife-proto\carlife_proto.py', encoding='utf-8').read()
SRC = SRC[:SRC.index("vis_w, vis_h = 1920, 720")]   # functions only, no main loop

class Sysfs:
    def __init__(self):
        self.udc = 'configured'
        self.pid = '0x2d00'
        self.events = []
sysfs = Sysfs()

class PidWriter:
    def write(self, v):
        sysfs.pid = v.strip()
        sysfs.events.append('pid=' + sysfs.pid)
    def __enter__(self): return self
    def __exit__(self, *a): return False

class UdcWriter:
    def __init__(self): pass
    def write(self, v):
        v = v.strip()
        if v == '':
            sysfs.udc = 'not attached'; sysfs.events.append('unbind')
        elif v.startswith('a600000'):
            sysfs.udc = 'configured'; sysfs.events.append('bind')
        else:
            raise OSError('bad udc value %r' % v)
    def __enter__(self): return self
    def __exit__(self, *a): return False

real_open = open
def fake_open(path, mode='r', *a, **kw):
    p = str(path)
    if p.startswith('/sys/'):
        if 'udc' in p and p.endswith('state'):
            return io.StringIO(sysfs.udc)
        if p.endswith('idProduct'):
            if 'w' in mode:
                return PidWriter()
            return io.StringIO(sysfs.pid)
        if p.endswith('/UDC'):
            assert 'w' in mode
            return UdcWriter()
        raise OSError('unknown sys path ' + p)
    if p == '/dev/uinput':
        return io.BytesIO()
    return real_open(path, mode, *a, **kw)
builtins.open = fake_open

real_os_open = os.open
def fake_os_open(path, flags):
    if str(path) == '/dev/usb/usb_accessory':
        if sysfs.udc == 'configured':
            return 42
        raise OSError(6, 'No such device')
    return real_os_open(path, flags)
os.open = fake_os_open
os.close = lambda fd: None
os.write = lambda fd, b: len(b)
os.read = lambda fd, n: b''

sys.modules['fcntl'] = types.ModuleType('fcntl')          # not on Windows
sys.modules['fcntl'].ioctl = lambda *a, **k: None

class Clock: t = 1000.0
time.sleep = lambda s: setattr(Clock, 't', Clock.t + s)
time.time = lambda: Clock.t

no_ready = types.ModuleType('select')
no_ready.select = lambda r, w, x, t=0: ([], [], [])

g = {'__name__': 'carlife_sim'}
exec(compile(SRC, 'carlife_proto.py', 'exec'), g)
acquire = g['acquire_link']

# A: fresh start, USB already configured -> level 0, plain open
fd = acquire()
assert fd == 42 and g['g_recover_level'] == 0 and not sysfs.events, (fd, sysfs.events)
print('A ok: fresh open, level 0, no rebind')

# B: session dies 5s after open -> escalate to rebind (level 1)
Clock.t += 5; sysfs.events.clear()
fd = acquire()
assert g['g_recover_level'] == 1 and 'unbind' in sysfs.events and 'bind' in sysfs.events and fd == 42, \
    (g['g_recover_level'], sysfs.events, fd)
print('B ok: quick death -> UDC rebind, reopened')

# C: dies again quickly -> full AOA (level 2); HU silent (no uevent), PID restored
Clock.t += 5; sysfs.events.clear()
g['_netlink_uevent_socket'] = lambda: None
fd = acquire()
assert g['g_recover_level'] == 2 and sysfs.pid == '0x2d00' and fd == 42, (g['g_recover_level'], sysfs.pid, fd)
assert sysfs.events.count('unbind') == 2 and 'pid=0x4ee1' in sysfs.events, sysfs.events
print('C ok: level 2 attempted, no START -> PID restored to 0x2d00, reopened')

# D: still level 2, this time the HU answers with ACCESSORY=START
class FakeSock:
    def recv(self, n): return b'change@/kernel/devices\x00ACCESSORY=START\x00'
    def close(self): pass
ready = [True]
sel = types.ModuleType('select')
def fake_select(r, w, x, t=0):
    if r and ready[0]:
        ready[0] = False
        return (list(r), [], [])
    return ([], [], [])
sel.select = fake_select
g['select'] = sel
g['_netlink_uevent_socket'] = lambda: FakeSock()
Clock.t += 2; sysfs.events.clear()
fd = acquire()
assert g['g_recover_level'] == 2 and sysfs.pid == '0x2d00' and fd == 42, (g['g_recover_level'], sysfs.pid, fd)
print('D ok: ACCESSORY=START received -> PID switched to 0x2d00, reopened')

# E: stable (>30s) session then death -> back to the cheap level 0
Clock.t += 100; sysfs.events.clear()
fd = acquire()
assert g['g_recover_level'] == 0 and not sysfs.events and fd == 42, (g['g_recover_level'], sysfs.events)
print('E ok: stable session death -> reset to level 0')

# F: HU absent (UDC never configured) -> acquire returns None, no crash
Clock.t += 100
sysfs.udc = 'not attached'
def stuck_select(r, w, x, t=0): return ([], [], [])
sel.select = stuck_select
fd = acquire()
assert fd is None, fd
print('F ok: no car attached -> acquire returns None cleanly')

# G: fresh boot at default PID -> L0 runs the AOA dance itself,
#    no START (no car) -> times out and restores the accessory PID
g['_netlink_uevent_socket'] = lambda: None
sysfs.pid = '0x4ee1'
Clock.t += 100; sysfs.events.clear()
fd = acquire()
assert sysfs.pid == '0x2d00' and 'pid=0x2d00' in sysfs.events, (sysfs.pid, sysfs.events)
assert g['g_recover_level'] == 0, g['g_recover_level']
print('G ok: fresh boot at default PID -> L0 ran AOA dance, PID restored')

# H: fresh boot at default PID, HU answers with ACCESSORY=START
ready[0] = True
sel.select = fake_select
sysfs.pid = '0x4ee1'
Clock.t += 100; sysfs.events.clear()
fd = acquire()
assert sysfs.pid == '0x2d00' and fd == 42, (sysfs.pid, fd)
assert sysfs.events.count('unbind') == 1, sysfs.events   # single flip, no restore
print('H ok: L0 AOA with START -> switched to 0x2d00, opened')

# I: no-session nudge — force_level=1 triggers a rebind even though the
#    last attempt is old enough that normal escalation would pick level 0
Clock.t += 100; sysfs.events.clear()
fd = acquire(force_level=1)
assert g['g_recover_level'] == 1 and 'unbind' in sysfs.events and fd == 42, \
    (g['g_recover_level'], sysfs.events, fd)
print('I ok: nudge (force_level=1) -> UDC rebind, reopened')

print('ALL SCENARIOS PASS')
