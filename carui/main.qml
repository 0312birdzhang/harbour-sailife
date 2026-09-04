import QtQuick 2.0
import QtQuick.Window 2.0

Window {
    id: root
    visible: true
    width: 1920
    height: 720
    color: "#11131a"
    title: "CarLife UI"

    // Head-unit taps arrive as a real mouse (uinput) routed by the
    // compositor; hit-test the tiles ourselves and launch via the C++
    // controller.
    MouseArea {
        anchors.fill: parent
        onClicked: {
            for (var i = 0; i < tileRepeater.count; i++) {
                var item = tileRepeater.itemAt(i)
                if (!item) continue
                var pos = item.mapToItem(root.contentItem, 0, 0)
                if (mouse.x >= pos.x && mouse.x < pos.x + item.width &&
                    mouse.y >= pos.y && mouse.y < pos.y + item.height) {
                    carController.tileClicked(i)
                    return
                }
            }
        }
    }

    property var tileModel: [
        { icon: "🧭", name: "导航", color: "#2e6bff" },
        { icon: "🎵", name: "音乐", color: "#b23bff" },
        { icon: "📞", name: "电话", color: "#00b871" },
        { icon: "💬", name: "信息", color: "#ff8a00" },
        { icon: "🎮", name: "应用", color: "#ff3b6b" },
        { icon: "☁️", name: "天气", color: "#00b0d0" },
        { icon: "⚙️", name: "设置", color: "#6a7a94" },
        { icon: "🧩", name: "更多", color: "#8a6dff" }
    ]

    function handleTap(x, y) {
        for (var i = 0; i < tileRepeater.count; i++) {
            var item = tileRepeater.itemAt(i)
            if (!item) continue
            var pos = item.mapToItem(root.contentItem, 0, 0)
            if (x >= pos.x && x < pos.x + item.width && y >= pos.y && y < pos.y + item.height) {
                console.log("tile clicked: " + item.tileName)
                return
            }
        }
        console.log("tap at " + x + "," + y + " (no tile)")
    }

    // ---------- top status bar ----------
    Rectangle {
        id: topBar
        anchors.top: parent.top
        width: parent.width
        height: 56
        color: "#1a2233"
        Text {
            id: clock
            anchors.left: parent.left
            anchors.leftMargin: 28
            anchors.verticalCenter: parent.verticalCenter
            color: "#e8eaf0"
            font.pixelSize: 26
            font.family: "sans-serif"
            text: "12:30"
        }
        Row {
            anchors.right: parent.right
            anchors.rightMargin: 24
            anchors.verticalCenter: parent.verticalCenter
            spacing: 18
            Text { color: "#9fb3d0"; font.pixelSize: 20; text: "WiFi" }
            Text { color: "#9fb3d0"; font.pixelSize: 20; text: "BT" }
            Text { color: "#9fb3d0"; font.pixelSize: 20; text: "GPS" }
        }
    }

    // ---------- app grid ----------
    Grid {
        id: grid
        anchors.top: topBar.bottom
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: 20
        anchors.bottomMargin: 10
        columns: 4
        spacing: 48

        Repeater {
            id: tileRepeater
            model: root.tileModel
            Item {
                property string tileName: modelData.name
                objectName: "tile_" + index
                scale: 1.0
                width: 300
                height: 210
                Rectangle {
                    anchors.fill: parent
                    radius: 22
                    color: modelData.color
                    opacity: 0.9
                }
                Text {
                    anchors.top: parent.top
                    anchors.topMargin: 18
                    anchors.horizontalCenter: parent.horizontalCenter
                    font.pixelSize: 72
                    text: modelData.icon
                }
                Text {
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 14
                    anchors.horizontalCenter: parent.horizontalCenter
                    color: "#ffffff"
                    font.pixelSize: 24
                    font.bold: true
                    text: (carAppNames && carAppNames[index] !== undefined && carAppNames[index] !== "") ? carAppNames[index] : modelData.name
                }
            }
        }
    }
}