import os, struct, time, sys, select, threading, fcntl, ctypes, socket

def first_existing(paths):
    for path in paths:
        if os.path.exists(path):
            return path
    return paths[0]

def find_usb_gadget():
    override = os.environ.get('SAILIFE_GADGET')
    if override and os.path.isdir(override):
        return override
    root = first_existing(('/config/usb_gadget',
                           '/sys/kernel/config/usb_gadget'))
    try:
        gadgets = [os.path.join(root, name) for name in sorted(os.listdir(root))
                   if os.path.isdir(os.path.join(root, name))]
    except OSError:
        gadgets = []
    for gadget in gadgets:
        try:
            with open(gadget + '/UDC') as f:
                if f.read().strip():
                    return gadget
        except OSError:
            pass
    for gadget in gadgets:
        try:
            if any('accessory' in name.lower()
                   for name in os.listdir(gadget + '/functions')):
                return gadget
        except OSError:
            pass
    preferred = os.path.join(root, 'g1')
    return preferred if os.path.isdir(preferred) else (gadgets[0] if gadgets else preferred)

def find_udc(gadget):
    override = os.environ.get('SAILIFE_UDC')
    if override:
        return override
    try:
        with open(gadget + '/UDC') as f:
            bound = f.read().strip()
            if bound:
                return bound
    except OSError:
        pass
    try:
        return sorted(os.listdir('/sys/class/udc'))[0]
    except (OSError, IndexError):
        return 'a600000.dwc3'

DEV = first_existing(('/dev/usb/usb_accessory', '/dev/usb_accessory'))
FIFO = '/tmp/cast.h264'
AUDIO_FIFO = '/tmp/sailife-audio.pcm'

# USB gadget (AOA) control. When the head unit drops the session after a
# timeout (e.g. heavy app slows the video), the accessory misc device is
# often left dead: writes fail with ENODEV ("No such device") and only a
# fresh USB enumeration clears the stale state. We therefore recover by
# re-binding the UDC, worst case redoing the whole AOA handshake.
GADGET = find_usb_gadget()
UDC_NAME = find_udc(GADGET)
PID_DEFAULT = '0x4ee1'      # pre-AOA PID; the HU sends 0x51/0x52/0x53 to this
PID_ACCESSORY = '0x2d00'    # AOA data mode
VID_ACCESSORY = '0x18d1'    # Google VID required for Android Open Accessory

# head unit video size
HU_W = 1920
HU_H = 720
CMD = 1
VIDEO = 2
MEDIA = 3
TOUCH = 6

MSG_CMD_HU_PROTOCOL_VERSION = 0x00018001
MSG_CMD_HU_INFO = 0x00018003
MSG_CMD_VIDEO_ENCODER_INIT = 0x00018007
MSG_CMD_VIDEO_ENCODER_START = 0x00018009
MSG_CMD_STATISTIC_INFO = 0x00018027
MSG_CMD_PROTOCOL_VERSION_MATCH_STATUS = 0x00010002
MSG_CMD_MD_INFO = 0x00010004
MSG_CMD_VIDEO_ENCODER_INIT_DONE = 0x00010008
MSG_CMD_MD_AUTHEN_RESULT = 0x0001004B
MSG_CMD_FOREGROUND = 0x0001001B
MSG_MEDIA_INIT = 0x00030001
MSG_MEDIA_DATA = 0x00030006
MSG_VIDEO_DATA = 0x00020001
MSG_TOUCH_ACTION = 0x00068001

# --- uinput synthetic mouse ------------------------------------------------
# The compositor (imira-comp, harbour-imira original) drives its windows from
# a REAL input device (/dev/input/eventX). Its InputHandler consumes
# EV_REL+EV_KEY and routes each click through the Qt Quick scene (hit-test),
# which is exactly why multi-window switching works there but Qt 5.6's
# synthetic sendMouse* (with its stale mouse-focus bug) does not. So the
# head-unit touch is re-injected as a real relative mouse: EV_REL move +
# EV_KEY BTN_LEFT click.
UI_SET_EVBIT = 0x40045564  # _IOW('U', 100, int)
UI_SET_RELBIT = 0x40045566  # _IOW('U', 102, int)
UI_SET_KEYBIT = 0x40045565  # _IOW('U', 101, int)
UI_DEV_SETUP  = 0x405C5503  # _IOW('U', 3, struct uinput_setup) size 92
UI_DEV_CREATE = 0x5501      # _IO('U', 1)

EV_SYN, EV_KEY, EV_REL = 0, 1, 2
REL_X, REL_Y = 0, 1
BTN_LEFT = 0x110

_uinput_fd = None
# imira-comp's InputHandler starts the cursor at the output centre.
_mx, _my = HU_W // 2, HU_H // 2

class _UinputSetup(ctypes.Structure):
    # struct uinput_setup: input_id + name[80] + ff_effects_max (no max_effects
    # on modern kernels; the extra field makes ioctl fail with EINVAL).
    _fields_ = [("id", ctypes.c_uint16 * 4),
                ("name", ctypes.c_char * 80),
                ("ff_effects_max", ctypes.c_uint32)]

def uinput_init():
    global _uinput_fd
    if _uinput_fd is not None:
        return
    fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
    for ev in (EV_REL, EV_KEY, EV_SYN):
        fcntl.ioctl(fd, UI_SET_EVBIT, ev)
    for rel in (REL_X, REL_Y):
        fcntl.ioctl(fd, UI_SET_RELBIT, rel)
    fcntl.ioctl(fd, UI_SET_KEYBIT, BTN_LEFT)
    ds = _UinputSetup()
    ds.name = b'carlife-mouse'
    ds.id[0] = 3                 # BUS_USB
    ds.id[1] = 1
    fcntl.ioctl(fd, UI_DEV_SETUP, ds)
    fcntl.ioctl(fd, UI_DEV_CREATE)
    _uinput_fd = fd
    print('uinput mouse created', flush=True)

def uinput_ev(t, c, v):
    # struct input_event: timeval (2x long) + __u16 type + __u16 code +
    # __s32 value — value must be SIGNED (relative deltas can be negative).
    os.write(_uinput_fd, struct.pack('llHHi', 0, 0, t, c, v))

def uinput_move(x, y):
    global _mx, _my
    dx = int(x) - _mx
    dy = int(y) - _my
    if dx:
        uinput_ev(EV_REL, REL_X, dx)
    if dy:
        uinput_ev(EV_REL, REL_Y, dy)
    uinput_ev(EV_SYN, 0, 0)
    _mx, _my = int(x), int(y)

def uinput_click(down):
    uinput_ev(EV_KEY, BTN_LEFT, 1 if down else 0)
    uinput_ev(EV_SYN, 0, 0)

def handle_touch(fd, body):
    """Parse CarLife TOUCH CMD message and inject via uinput."""
    if len(body) < 8:
        return
    carmsg_len = struct.unpack('>H', body[0:2])[0]
    service = struct.unpack('>I', body[4:8])[0]
    payload = body[8:8 + carmsg_len] if carmsg_len > 0 else b''
    if service != MSG_TOUCH_ACTION:
        return
    if len(payload) < 3:
        return
    fields = {}
    i = 0

    def read_varint_at(pos):
        val = 0
        shift = 0
        while pos < len(payload) and shift < 64:
            b = payload[pos]
            pos += 1
            val |= (b & 0x7f) << shift
            if not (b & 0x80):
                return val, pos
            shift += 7
        return None, pos

    while i < len(payload):
        key = payload[i]
        i += 1
        field = key >> 3
        wire = key & 7
        if wire == 0:
            val, i = read_varint_at(i)
            if val is None:
                return
            fields[field] = val
        elif wire == 2:
            ln, i = read_varint_at(i)
            if ln is None or i + ln > len(payload):
                return
            i += ln
        else:
            return
    action = fields.get(1, 0)
    cx = fields.get(2, 0)
    cy = fields.get(3, 0)
    print('[%s] TOUCH action=%d HU(%d,%d)' % (time.strftime('%H:%M:%S'), action, cx, cy), flush=True)
    # Inject as a real relative mouse so the compositor's InputHandler
    # (harbour-imira original) routes it through the Qt Quick scene.
    try:
        uinput_init()
        uinput_move(cx, cy)
        if action == 0:
            uinput_click(True)
        elif action == 1:
            uinput_click(False)
    except OSError as e:
        print('uinput inject fail: %s' % e, flush=True)
    except struct.error as e:
        print('uinput struct fail: %s' % e, flush=True)

def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)

def pb_key(field, wire):
    return varint((field << 3) | wire)

def pb_varint_field(field, value):
    return pb_key(field, 0) + varint(value)

def pb_str_field(field, s):
    b = s.encode('utf-8')
    return pb_key(field, 2) + varint(len(b)) + b

def pb_bool_field(field, v):
    return pb_key(field, 0) + varint(1 if v else 0)

def msg_match_status():
    return pb_varint_field(1, 1)

def msg_device_info():
    m = b''
    m += pb_str_field(1, 'Android')
    m += pb_str_field(2, 'kona')
    m += pb_str_field(12, 'QKQ1.190828.002')
    m += pb_str_field(11, 'c4-miui-ota-bd47.bj')
    m += pb_str_field(19, '10')
    m += pb_str_field(20, '29')
    m += pb_varint_field(21, 29)
    m += pb_str_field(16, '5df9412c')
    m += pb_str_field(14, '21051182G')
    return m

def msg_authen_result():
    return pb_bool_field(1, True)

def msg_video_encoder_info(width, height, framerate):
    m = b''
    m += pb_varint_field(1, width)
    m += pb_varint_field(2, height)
    m += pb_varint_field(3, framerate)
    return m

def msg_music_init():
    m = b''
    m += pb_varint_field(1, 48000)
    m += pb_varint_field(2, 2)
    m += pb_varint_field(3, 16)
    return m

def int2b(v):
    return struct.pack('>I', v & 0xFFFFFFFF)

def short2b(v):
    return struct.pack('>H', v & 0xFFFF)

def export_cmd(service, payload):
    # CarLife CMD message: [2B len][2B 0][4B service][payload]  (8-byte head)
    if payload is None:
        return short2b(0) + short2b(0) + int2b(service)
    return short2b(len(payload)) + short2b(0) + int2b(service) + payload

def export_video(service, payload):
    ts = int(time.time() * 1000) & 0xFFFFFFFF
    return int2b(len(payload)) + int2b(ts) + int2b(service) + payload

_tx_lock = threading.Lock()

def _write_all(fd, data):
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        if n <= 0:
            raise OSError('USB write returned %d' % n)
        view = view[n:]

def send_frame(fd, msg_type, msg):
    head = bytes(3) + bytes([msg_type]) + int2b(len(msg))
    try:
        # CMD and VIDEO are produced by different threads. Keep header and
        # payload atomic relative to other protocol frames and handle short
        # writes from the accessory character device.
        with _tx_lock:
            if msg_type == VIDEO and (not g_connected or not g_stream_on):
                return False
            _write_all(fd, head)
            _write_all(fd, msg)
        if msg_type not in (VIDEO, MEDIA):
            print('  [TX type=%d len=%d]' % (msg_type, len(msg)), flush=True)
        return True
    except OSError as e:
        print('  [TX FAIL type=%d %s]' % (msg_type, e), flush=True)
        return False

class StreamReader:
    def __init__(self, fd):
        self.fd = fd
        self.buf = b''
    def _fill(self):
        r, _, _ = select.select([self.fd], [], [], 3)
        if not r:
            return False
        try:
            d = os.read(self.fd, 65536)
        except OSError:
            raise
        if not d:
            raise EOFError
        self.buf += d
        return True
    def read_exact(self, n):
        while len(self.buf) < n:
            if not self._fill():
                return None
        out = self.buf[:n]
        self.buf = self.buf[n:]
        return out
    def read_frame(self):
        hdr = self.read_exact(8)
        if hdr is None:
            return None
        msg_type = hdr[3]
        length = struct.unpack('>I', hdr[4:8])[0]
        if length > 0:
            body = self.read_exact(length)
            if body is None:
                return None
        else:
            body = b''
        return msg_type, body

def parse_cmd(body):
    if len(body) < 8:
        return 0, None, b''
    carmsg_len = struct.unpack('>H', body[0:2])[0]
    service = struct.unpack('>I', body[4:8])[0]
    payload = body[8:8 + carmsg_len] if carmsg_len > 0 else b''
    return service, payload

def ts():
    return time.strftime('%H:%M:%S')

def udc_state():
    try:
        with open('/sys/class/udc/%s/state' % UDC_NAME) as f:
            return f.read().strip()
    except OSError:
        return 'unknown'

def gadget_pid():
    try:
        with open(GADGET + '/idProduct') as f:
            return f.read().strip()
    except OSError:
        return 'unknown'

def gadget_vid():
    try:
        with open(GADGET + '/idVendor') as f:
            return f.read().strip()
    except OSError:
        return 'unknown'

def write_sys(path, val):
    try:
        with open(path, 'w') as f:
            f.write(val)
        return True
    except OSError as e:
        print('write %s fail: %s' % (path, e), flush=True)
        return False

def set_pid_and_bind(pid):
    """configfs attributes only accept writes while the UDC is unbound."""
    write_sys(GADGET + '/UDC', '\n')
    time.sleep(0.2)
    write_sys(GADGET + '/idVendor', VID_ACCESSORY)
    write_sys(GADGET + '/idProduct', pid)
    time.sleep(0.2)
    write_sys(GADGET + '/UDC', UDC_NAME + '\n')
    time.sleep(0.5)

def rebind_udc():
    """Unbind + rebind the UDC: forces a clean re-enumeration. The gadget
    keeps its accessory PID, so a head unit that already knows the device
    re-claims it without the full AOA dance."""
    print('[%s] UDC rebind (forced re-enumeration)' % ts(), flush=True)
    write_sys(GADGET + '/UDC', '\n')
    time.sleep(0.5)
    write_sys(GADGET + '/UDC', UDC_NAME + '\n')
    time.sleep(1.0)

def _netlink_uevent_socket():
    try:
        s = socket.socket(socket.AF_NETLINK, socket.SOCK_DGRAM, 15)  # KOBJECT_UEVENT
        s.bind((0, 1))
        return s
    except OSError as e:
        print('netlink bind fail: %s' % e, flush=True)
        return None

def enter_accessory_mode():
    """Full AOA dance: default PID, wait for the HU to send the accessory
    start requests (kernel then broadcasts ACCESSORY=START), switch to the
    accessory PID — same sequence as aoa_manager.py. Bind the uevent socket
    BEFORE switching PID so the START event cannot slip through."""
    print('[%s] AOA handshake: VID:PID -> %s:%s, waiting for ACCESSORY=START' % (ts(), VID_ACCESSORY, PID_DEFAULT), flush=True)
    s = _netlink_uevent_socket()
    if gadget_vid() != VID_ACCESSORY or gadget_pid() != PID_DEFAULT:
        set_pid_and_bind(PID_DEFAULT)
    ok = False
    deadline = time.time() + 30
    while s and time.time() < deadline:
        r, _, _ = select.select([s], [], [], 1)
        if r and b'ACCESSORY=START' in s.recv(65536):
            ok = True
            break
    if s:
        s.close()
    if not ok:
        print('[%s] AOA handshake: no START within 30s' % ts(), flush=True)
        if gadget_pid() != PID_ACCESSORY:
            set_pid_and_bind(PID_ACCESSORY)   # restore for the next attempt
        return False
    print('[%s] AOA handshake: START received, PID -> %s' % (ts(), PID_ACCESSORY), flush=True)
    set_pid_and_bind(PID_ACCESSORY)
    return True

def wait_configured(timeout):
    """Wait for the UDC to be configured — and to STAY configured: the
    state flaps while the head unit is still settling the enumeration, and
    opening during the flap costs one extra drop."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if udc_state() == 'configured':
            time.sleep(1)
            if udc_state() == 'configured':
                return True
            continue
        time.sleep(0.5)
    return udc_state() == 'configured'

g_need_idr = False
g_stream_on = False     # HU handshake finished (VIDEO_ENCODER_START seen)
g_connected = False     # accessory fd open and believed alive
g_last_attempt = 0.0    # when acquire_link last ran
g_last_open = 0.0       # when the currently-used fd was opened
g_recover_level = 0     # 0 plain reopen, 1 rebind UDC, 2 full AOA handshake
g_hu_seen = False       # the HU sent something since the fd opened
g_link_open_ts = 0.0    # for the no-session nudge timer
g_nudged = False        # already rebind-nudged during this silent stretch
g_nudge_ts = 0.0        # when the watchdog last rebind-nudged

def acquire_link(force_level=None):
    """Open the accessory device, recovering the USB link as needed.

    Escalation: a session that dies (or fails to come up) within 30s means
    the USB state is stale — go from plain reopen to UDC rebind to the full
    AOA handshake, and stay escalated until a stable (>30s) session.
    force_level raises the level for one call (the no-session nudge).
    Returns an open fd or None."""
    global g_connected, g_stream_on, g_last_attempt, g_last_open, g_recover_level
    global g_hu_seen, g_link_open_ts
    g_connected = False
    g_stream_on = False
    if force_level is not None:
        g_recover_level = max(g_recover_level, force_level)
    elif g_last_attempt and time.time() - g_last_attempt < 30:
        if time.time() - g_nudge_ts > 5:
            # the watchdog's nudge rebind already re-enumerated; recovering
            # from it needs only a reopen, a second rebind just adds churn
            g_recover_level = min(g_recover_level + 1, 2)
    elif g_last_open and time.time() - g_last_open > 30:
        g_recover_level = 0   # last session was stable, try the cheap path
    g_last_attempt = time.time()
    print('[%s] acquire_link level=%d (UDC %s, PID %s)' % (ts(), g_recover_level, udc_state(), gadget_pid()), flush=True)
    if g_recover_level == 2:
        enter_accessory_mode()
    elif g_recover_level == 1:
        rebind_udc()
    elif gadget_vid() != VID_ACCESSORY or gadget_pid() != PID_ACCESSORY:
        # Fresh boot (or first plug): nobody has switched us into accessory
        # mode yet. Run the AOA dance ourselves — the chain is otherwise
        # self-contained, there is no external aoa_manager service.
        enter_accessory_mode()
    if not wait_configured(20):
        print('[%s] UDC not configured, retrying later' % ts(), flush=True)
        return None
    try:
        fd = os.open(DEV, os.O_RDWR)
    except OSError as e:
        print('[%s] open fail: %s' % (ts(), e), flush=True)
        time.sleep(1)
        return None
    g_last_open = time.time()
    g_link_open_ts = g_last_open
    g_hu_seen = False
    g_connected = True
    print('[%s] accessory fd=%d open' % (ts(), fd), flush=True)
    return fd

def find_sc(b, s):
    """Return the earliest start code (3- or 4-byte) at/after s.

    The encoder uses a 3-byte start code (00 00 01) whenever the previous
    NAL does not end in 0x00, e.g. the IDR slice after the SPS/PPS. A naive
    'find 4-byte first' skips those and wrongly lands on the next 4-byte
    frame boundary, so the head unit never sees an IDR (black screen)."""
    i4 = b.find(b'\x00\x00\x00\x01', s)
    i3 = b.find(b'\x00\x00\x01', s)
    if i4 != -1 and (i3 == -1 or i4 <= i3):
        return i4, 4
    if i3 != -1:
        return i3, 3
    return -1, 0

def is_new_frame_start(nal_head):
    """True if this VCL slice begins a new access unit (first_mb_in_slice==0).
    nal_head: first bytes of a NAL unit (after start code)."""
    if len(nal_head) < 2:
        return False
    t = nal_head[0] & 0x1f
    if t not in (1, 5):
        return False
    data = nal_head[1:]
    bits = []
    for byte in data:
        bits.extend((byte >> (7 - i)) & 1 for i in range(8))
    i = 0
    leading = 0
    while i < len(bits) and bits[i] == 0:
        leading += 1
        i += 1
        if leading > 16:
            return False
    if i >= len(bits):
        return False
    i += 1
    val = 0
    for j in range(leading):
        if i < len(bits):
            val = (val << 1) | bits[i]
            i += 1
    val += (1 << leading) - 1
    return val == 0

def extract_au(buf):
    """Return one Annex-B access unit and the remaining buffer."""
    pos, sl = find_sc(buf, 0)
    if pos == -1:
        return None, buf
    positions = []
    start = pos
    while True:
        p, slen = find_sc(buf, start)
        if p == -1:
            break
        if slen == 3 and p > 0 and buf[p - 1] == 0:
            start = p + 3
            continue
        positions.append((p, slen))
        start = p + slen
    if len(positions) < 2:
        return None, buf
    frame_end = None
    first_vcl_done = False
    for p, slen in positions:
        ns = p + slen
        if ns >= len(buf):
            break
        head = buf[ns:ns + 24]
        if is_new_frame_start(head):
            if not first_vcl_done:
                first_vcl_done = True
                continue
            frame_end = p
            break
    if frame_end is None:
        return None, buf
    au = buf[positions[0][0]:frame_end]
    return au, buf[frame_end:]

def frame_has_idr(au):
    """True if this access unit begins with an IDR slice (type 5)."""
    pos = 0
    while True:
        i4 = au.find(b'\x00\x00\x00\x01', pos)
        i3 = au.find(b'\x00\x00\x01', pos)
        if i4 != -1 and (i3 == -1 or i4 <= i3):
            i, sc = i4, 4
        elif i3 != -1:
            i, sc = i3, 3
        else:
            break
        if i + sc < len(au):
            t = au[i + sc] & 0x1f
            if t in (1, 5):
                return t == 5
        pos = i + sc
    return False

def video_loop_fifo(stop):
    global g_fd, g_need_idr
    src = os.environ.get('CARLIFE_VIDEO_FILE', '')
    if src:
        try:
            with open(src, 'rb') as f:
                raw = f.read()
        except OSError as e:
            print('video file error: %s' % e, flush=True)
            return
        print('video TEST FILE source: %s (%d bytes)' % (src, len(raw)), flush=True)
        frames = []
        buf = raw
        while True:
            au, buf = extract_au(buf)
            if au is None:
                break
            frames.append(au)
        if not frames:
            print('no frames parsed', flush=True)
            return
        print('test file: %d frames' % len(frames), flush=True)
        i = 0
        while not stop.is_set():
            if not g_stream_on or not g_connected:
                time.sleep(0.05)
                continue
            if not send_frame(g_fd, VIDEO,
                              export_video(MSG_VIDEO_DATA, frames[i % len(frames)])):
                time.sleep(0.05)
                continue
            i += 1
            time.sleep(0.033)
        return
    try:
        fifo = open(FIFO, 'rb', buffering=0)
    except OSError as e:
        print('fifo open error: %s' % e, flush=True)
        return
    print('video FIFO source: %s' % FIFO, flush=True)
    buf = b''
    waiting_idr = True
    while not stop.is_set():
        if g_need_idr:
            waiting_idr = True
            g_need_idr = False
        if not g_stream_on or not g_connected:
            # Link down or the HU handshake has not finished yet: drain the
            # FIFO so we never queue up stale frames, and send nothing.
            try:
                fifo.read(65536)
            except OSError:
                time.sleep(0.2)
            buf = b''
            time.sleep(0.05)
            continue
        try:
            d = fifo.read(65536)
        except OSError:
            time.sleep(0.2)
            continue
        if not d:
            time.sleep(0.03)
            continue
        buf += d
        if len(buf) > 4 * 1024 * 1024:
            # Truncate to the last start code so we never split a frame:
            # cutting mid-NAL makes the head unit lose sync (black screen).
            i = buf.rfind(b'\x00\x00\x00\x01')
            if i == -1:
                i = buf.rfind(b'\x00\x00\x01')
            buf = buf[i:] if i != -1 else b''
        while True:
            au, buf = extract_au(buf)
            if au is None:
                break
            # The head unit only starts decoding at an IDR (type 5). Drop
            # everything until we see one; the encoder emits one every ~0.5s.
            if waiting_idr and not frame_has_idr(au):
                continue
            waiting_idr = False
            if not send_frame(g_fd, VIDEO, export_video(MSG_VIDEO_DATA, au)):
                waiting_idr = True
                break
    fifo.close()

def audio_loop_fifo(stop):
    """Forward 48 kHz stereo S16LE in the 2560-byte chunks used by the
    reference mobile implementation. Drain while disconnected so stale
    audio is never replayed after a reconnect."""
    try:
        fifo = open(AUDIO_FIFO, 'rb', buffering=0)
    except OSError as e:
        print('audio fifo error: %s' % e, flush=True)
        return
    print('audio FIFO source: %s' % AUDIO_FIFO, flush=True)
    buf = b''
    while not stop.is_set():
        try:
            data = fifo.read(4096)
        except OSError:
            time.sleep(0.05)
            continue
        if not data:
            time.sleep(0.01)
            continue
        if not g_stream_on or not g_connected:
            buf = b''
            continue
        buf += data
        while len(buf) >= 2560:
            pcm, buf = buf[:2560], buf[2560:]
            if not send_frame(g_fd, MEDIA,
                              export_video(MSG_MEDIA_DATA, pcm)):
                buf = b''
                break
    fifo.close()

vis_w, vis_h = 1920, 720
video_thread = None
video_stop = threading.Event()
audio_stop = threading.Event()
threading.Thread(target=audio_loop_fifo, args=(audio_stop,), daemon=True).start()
print('carlife_proto started, waiting...', flush=True)
try:
    uinput_init()   # create the synthetic mouse before imira-comp scans /dev/input
except OSError as e:
    print('uinput init fail: %s' % e, flush=True)
g_fd = acquire_link()
while g_fd is None:
    time.sleep(2)
    g_fd = acquire_link()
sr = StreamReader(g_fd)
print('connected', flush=True)

def nudge_watchdog(stop):
    """If the HU never opens its session after we open the device (e.g. the
    old daemon was killed mid-stream and the HU does not retry on an
    already-enumerated device), one UDC rebind forces re-enumeration, which
    the HU answers immediately. Only nudges; the main loop owns the fd."""
    global g_nudged, g_nudge_ts
    while not stop.is_set():
        time.sleep(1)
        if g_connected and not g_hu_seen and not g_nudged \
                and time.time() - g_link_open_ts > 20:
            g_nudged = True
            g_nudge_ts = time.time()
            print('[%s] no HU session for 20s, nudging with UDC rebind' % ts(), flush=True)
            rebind_udc()
            # the open fd dies with the unbind; the main loop's read fails
            # and runs its normal recovery path

nudge_stop = threading.Event()
threading.Thread(target=nudge_watchdog, args=(nudge_stop,), daemon=True).start()

while True:
    try:
        frame = sr.read_frame()
    except (OSError, EOFError) as e:
        print('[%s] link lost (%s), recovering...' % (ts(), e), flush=True)
        g_connected = False   # stop the video thread before the fd dies
        try:
            os.close(g_fd)
        except OSError:
            pass
        g_fd = acquire_link()
        while g_fd is None:
            time.sleep(2)
            g_fd = acquire_link()
        sr = StreamReader(g_fd)
        print('[%s] link back, waiting for HU handshake' % ts(), flush=True)
        continue
    if frame is None:
        continue
    msg_type, body = frame
    g_hu_seen = True
    g_nudged = False
    if msg_type == CMD:
        service, payload = parse_cmd(body)
        print('[%s] CMD 0x%08X len=%d raw=%s' % (time.strftime('%H:%M:%S'), service, len(payload), body[:32].hex()), flush=True)
        if service == MSG_CMD_HU_PROTOCOL_VERSION:
            # try to honour the version carried by the head unit
            v = None
            if len(payload) >= 4:
                v = struct.unpack('>i', payload[0:4])[0]
            print('  HU protocol version value=%s' % v, flush=True)
            send_frame(g_fd, CMD, export_cmd(MSG_CMD_PROTOCOL_VERSION_MATCH_STATUS, msg_match_status()))
            print('  -> PROTOCOL_VERSION_MATCH_STATUS', flush=True)
        elif service == MSG_CMD_HU_INFO:
            send_frame(g_fd, CMD, export_cmd(MSG_CMD_MD_INFO, msg_device_info()))
            print('  -> MD_INFO', flush=True)
        elif service == MSG_CMD_VIDEO_ENCODER_INIT:
            try:
                if len(payload) >= 12:
                    w = int.from_bytes(payload[0:4], 'big')
                    h = int.from_bytes(payload[4:8], 'big')
                    fr = int.from_bytes(payload[8:12], 'big')
                    if 0 < w < 4000 and 0 < h < 4000:
                        vis_w, vis_h = w, h
                    print('  HU wants %dx%d@%d' % (w, h, fr), flush=True)
            except Exception:
                pass
            enc = msg_video_encoder_info(vis_w, vis_h, 30)
            send_frame(g_fd, CMD, export_cmd(MSG_CMD_VIDEO_ENCODER_INIT_DONE, enc))
            send_frame(g_fd, CMD, export_cmd(MSG_CMD_FOREGROUND, None))
            print('  -> VIDEO_ENCODER_INIT_DONE + FOREGROUND (%dx%d)' % (vis_w, vis_h), flush=True)
        elif service == MSG_CMD_STATISTIC_INFO:
            send_frame(g_fd, CMD, export_cmd(MSG_CMD_MD_AUTHEN_RESULT, msg_authen_result()))
            print('  -> MD_AUTHEN_RESULT', flush=True)
        elif service == MSG_CMD_VIDEO_ENCODER_START:
            send_frame(g_fd, MEDIA, export_video(MSG_MEDIA_INIT, msg_music_init()))
            print('  -> MEDIA_INIT', flush=True)
            g_need_idr = True
            g_stream_on = True
            if not video_thread or not video_thread.is_alive():
                video_stop.clear()
                video_thread = threading.Thread(target=video_loop_fifo, args=(video_stop,), daemon=True)
                video_thread.start()
                print('  video thread started', flush=True)
        else:
            print('  (unhandled CMD)', flush=True)
    elif msg_type == MEDIA:
        print('[%s] MEDIA len=%d' % (time.strftime('%H:%M:%S'), len(body)), flush=True)
    elif msg_type == TOUCH:
        handle_touch(g_fd, body)
    elif msg_type == VIDEO:
        print('[%s] VIDEO len=%d' % (time.strftime('%H:%M:%S'), len(body)), flush=True)
    else:
        print('[%s] UNKNOWN type=%d len=%d' % (time.strftime('%H:%M:%S'), msg_type, len(body)), flush=True)
