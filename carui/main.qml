import QtQuick 2.0
import QtQuick.Window 2.0

// CarPlay-style shell: left dock (clock, recent apps, home) +
// content area. The home grid lives in the content area; a launched app
// window covers it (the compositor places chromeless app windows at
// x=140..1920), the dock always stays visible on top of the left strip.
Window {
    id: root
    visible: true
    width: 1920
    height: 720
    color: "#000000"
    title: "Sailife UI"

    property string clockText: Qt.formatDateTime(new Date(), "hh:mm")
    Timer {
        interval: 15000
        running: true
        repeat: true
        onTriggered: root.clockText = Qt.formatDateTime(new Date(), "hh:mm")
    }

    function categoryIcon(cat) {
        var map = {
            "音乐": "🎵", "电话": "📞", "信息": "💬", "导航": "🧭",
            "视频": "🎬", "天气": "☁️", "工具": "🧰", "其他": "🧩",
            "游戏": "🎮", "社交": "🗨️", "阅读": "📖", "拍照": "📷"
        }
        return map[cat] !== undefined ? map[cat] : "🧩"
    }

    // ---------- left dock ----------
    Rectangle {
        id: dock
        x: 0
        width: 140
        height: parent.height
        color: "#05070c"

        Text {
            id: clock
            anchors.top: parent.top
            anchors.topMargin: 26
            anchors.horizontalCenter: parent.horizontalCenter
            color: "#e8eaf0"
            font.pixelSize: 40
            font.bold: true
            text: root.clockText
        }

        // recently used apps (most recent first; 4 fit between the home
        // button and the gear without overlapping)
        Repeater {
            model: {
                var x = carController.dockApps
                return x.length > 4 ? x.slice(0, 4) : x
            }
            Rectangle {
                x: 22
                y: 118 + index * 92
                width: 96
                height: 84
                radius: 20
                color: dockMA.pressed ? "#2e6bff" : "#141b2b"
                Image {
                    anchors.centerIn: parent
                    width: 56
                    height: 56
                    fillMode: Image.PreserveAspectFit
                    source: modelData.icon !== "" ? "file://" + modelData.icon : ""
                    visible: modelData.icon !== ""
                }
                Text {
                    anchors.centerIn: parent
                    visible: modelData.icon === ""
                    color: "#e8eaf0"
                    font.pixelSize: 34
                    font.bold: true
                    text: modelData.name.charAt(0)
                }
                MouseArea {
                    id: dockMA
                    anchors.fill: parent
                    onClicked: carController.dockClicked(modelData.appId)
                }
            }
        }

        // home entry, pinned to the bottom-left
        Rectangle {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 22
            anchors.horizontalCenter: parent.horizontalCenter
            width: 96
            height: 84
            radius: 20
            color: homeMA.pressed ? "#2e6bff" : "#1c2333"
            Text {
                anchors.centerIn: parent
                font.pixelSize: 42
                text: "⌂"
            }
            MouseArea {
                id: homeMA
                anchors.fill: parent
                onClicked: carController.homeClicked()
            }
        }
    }

    // ---------- content area: home grid ----------
    // hidden while an app is on screen: the app surface may not fill its
    // item exactly, and the grid must never show through behind it.
    // Tiles are fixed-size; extra rows scroll vertically.
    Flickable {
        id: gridFlick
        visible: carController.currentApp === ""
        x: 160
        width: parent.width - x - 20
        height: parent.height
        contentWidth: width
        contentHeight: grid.height + 40
        flickableDirection: Flickable.VerticalFlick
        boundsBehavior: Flickable.StopAtBounds
        clip: true

        Grid {
            id: grid
            x: 0
            y: 20
            width: parent.width
            columns: 5
            spacing: 20
            property real tileHeight: 260
            property real tileWidth: (width - (columns - 1) * spacing) / columns

            Repeater {
                model: carController.tiles
                Rectangle {
                    width: grid.tileWidth
                    height: grid.tileHeight
                    radius: 24
                    color: tileMA.pressed ? "#1e2c47" : "#131a29"
                    Image {
                        anchors.top: parent.top
                        anchors.topMargin: Math.max(14, parent.height * 0.13)
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: Math.min(96, parent.height * 0.42)
                        height: width
                        fillMode: Image.PreserveAspectFit
                        source: modelData.icon !== "" ? "file://" + modelData.icon : ""
                        visible: modelData.icon !== ""
                    }
                    Text {
                        anchors.top: parent.top
                        anchors.topMargin: Math.max(14, parent.height * 0.14)
                        anchors.horizontalCenter: parent.horizontalCenter
                        font.pixelSize: Math.min(84, parent.height * 0.38)
                        visible: modelData.icon === ""
                        text: root.categoryIcon(modelData.category)
                    }
                    Text {
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 22
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: parent.width - 24
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideRight
                        color: "#ffffff"
                        font.pixelSize: 28
                        font.bold: true
                        text: modelData.name
                    }
                    MouseArea {
                        id: tileMA
                        anchors.fill: parent
                        onClicked: carController.tileClicked(index)
                    }
                }
            }
        }
    }

}
