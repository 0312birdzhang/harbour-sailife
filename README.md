# harbour-sailife — SailfishOS → CarLife 投屏

将 SailfishOS 平板的**车机 UI**（CarPlay/AA 风格）通过百度 CarLife 协议投屏到车机，
并支持车机触摸反向控制 UI。

## 架构

```
车机 (CarLife host, USB AOA)
  ↑ USB AOA (PID 0x2D00)
平板 (SailfishOS, Xiaomi Pad 5)
  ├─ imira-comp (虚拟 1920x720 compositor) —— carlife_proto 启动时拉起
  │    └─ carui (Qt Quick 车机 UI，跑在虚拟屏幕)
  ├─ carlife-capture (lipstick-recorder shm 采集 → x264 编码 → FIFO)
  ├─ carlife_proto.py (AOA 握手 + CarLife 协议 + 视频/触摸转发)
  └─ touchd (已废弃，触摸改由 carui 内部处理)
```

## 模块

| 目录 | 内容 |
|------|------|
| `carlife-proto/` | AOA manager + CarLife 协议处理（8 字节帧头、CMD 握手、视频切帧） |
| `carui/` | 车机 UI（Qt Quick QML，1920x720，CarPlay 风格 tile 网格） |
| `capture/` | 采集编码：lipstick-recorder（imira 组件）+ x264 软编码 |
| `device/` | uinput 触摸注入（备用） |
| `imira-patches/` | imira-comp 修改（carui 全屏支持） |
| `scripts/` | 启动脚本 |

## 关键技术点

- **AOA**：内核 `f_accessory` 驱动 + `ACCESSORY=START` uevent → 切 PID 0x2D00
- **CarLife 视频**：`stream-format=byte-stream`（Annex-B），1920x720@30
- **切帧 bug 修复**：`extract_au` 需解析 slice 头 `first_mb_in_slice`（=0 为新 AU），
  否则 IDR 帧内多 slice 被误切导致车机解码下半绿屏
- **虚拟屏幕**：imira-comp（Qt5Compositor）1920x720，carui 全屏（无窗口 chrome/dock）
- **触摸**：carlife_proto 转发 TOUCH → `/tmp/carui-touch` → carui 读坐标命中 tile

## 真机

平板 Xiaomi Pad 5 (nabu) SailfishOS，车机支持 CarLife USB 连接。