import os, struct, time, sys, select, threading, subprocess

DEV = '/dev/usb/usb_accessory'
FIFO = '/tmp/cast.h264'
TOUCHD = '/opt/carlife/touchd'

# tablet screen (px)
TAB_W = 1600
TAB_H = 2560
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

touch_proc = None

def start_touchd():
    global touch_proc
    if touch_proc and touch_proc.poll() is None:
        return
    try:
        touch_proc = subprocess.Popen([TOUCHD], stdin=subprocess.PIPE)
        print('touchd started', flush=True)
    except OSError as e:
        print('touchd start fail: %s' % e, flush=True)
touch_proc = None
carui_touch_fd = None

def translate(cx, cy):
    px = int(cx * TAB_W / HU_W)
    py = int(cy * TAB_H / HU_H)
    px = max(0, min(TAB_W - 1, px))
    py = max(0, min(TAB_H - 1, py))
    return px, py

def handle_touch(fd, body):
    """Parse CarLife TOUCH CMD message and inject via uinput."""
    global touch_proc
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
    while i < len(payload):
        key = payload[i]
        i += 1
        field = key >> 3
        wire = key & 7
        if wire == 0:
            val = 0
            shift = 0
            while True:
                b = payload[i]
                i += 1
                val |= (b & 0x7f) << shift
                if not (b & 0x80):
                    break
                shift += 7
            fields[field] = val
        elif wire == 2:
            ln = payload[i]
            i += 1
            i += ln
        else:
            break
    action = fields.get(1, 0)
    cx = fields.get(2, 0)
    cy = fields.get(3, 0)
    print('[%s] TOUCH action=%d HU(%d,%d)' % (time.strftime('%H:%M:%S'), action, cx, cy), flush=True)
    # forward to the car-UI (carui) so the head-unit touch drives the UI,
    # not the tablet screen
    global carui_touch_fd
    if carui_touch_fd is None:
        try:
            carui_touch_fd = open('/tmp/carui-touch', 'w')
            print('carui-touch opened', flush=True)
        except Exception as e:
            print('carui-touch open fail: %s' % e, flush=True)
    if carui_touch_fd:
        try:
            carui_touch_fd.write('%d %d %d\n' % (action, cx, cy))
            carui_touch_fd.flush()
        except Exception as e:
            print('carui touch write fail: %s' % e, flush=True)

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

def send_frame(fd, msg_type, msg):
    head = bytes(3) + bytes([msg_type]) + int2b(len(msg))
    try:
        n1 = os.write(fd, head)
        n2 = os.write(fd, msg)
        print('  [TX type=%d len=%d wrote=%d+%d]' % (msg_type, len(msg), n1, n2), flush=True)
    except OSError as e:
        print('  [TX FAIL %s]' % e, flush=True)

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

def open_dev():
    while True:
        try:
            return os.open(DEV, os.O_RDWR)
        except OSError as e:
            print('open fail (%s), retry in 2s' % e, flush=True)
            time.sleep(2)

def find_sc(b, s):
    i = b.find(b'\x00\x00\x00\x01', s)
    if i != -1:
        return i, 4
    i = b.find(b'\x00\x00\x01', s)
    if i != -1:
        return i, 3
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

def video_loop_fifo(stop):
    global g_fd
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
            send_frame(g_fd, VIDEO, export_video(MSG_VIDEO_DATA, frames[i % len(frames)]))
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
    while not stop.is_set():
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
            send_frame(g_fd, VIDEO, export_video(MSG_VIDEO_DATA, au))
    fifo.close()

vis_w, vis_h = 1920, 720
video_thread = None
video_stop = threading.Event()
print('carlife_proto started, waiting...', flush=True)
g_fd = open_dev()
sr = StreamReader(g_fd)
print('connected', flush=True)

while True:
    try:
        frame = sr.read_frame()
    except (OSError, EOFError):
        print('[%s] lost connection, reopening...' % time.strftime('%H:%M:%S'), flush=True)
        try:
            os.close(g_fd)
        except OSError:
            pass
        time.sleep(1)
        g_fd = open_dev()
        sr = StreamReader(g_fd)
        print('reconnected', flush=True)
        continue
    if frame is None:
        continue
    msg_type, body = frame
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