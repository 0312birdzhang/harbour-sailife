import QtQuick 2.0
import QtQuick.Window 2.0

// CarPlay-style shell: left dock (clock, home, recent apps, settings) +
// content area. The home grid lives in the content area; a launched app
// window covers it (the compositor places chromeless app windows at
// x=140..1920), the dock always stays visible on top of the left strip.
Window {
    id: root
    visible: true
    width: 1920
    height: 720
    color: "#000000"
    title: "CarLife UI"

    property bool settingsOpen: false
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

        // home button: back to the grid
        Rectangle {
            id: homeButton
            anchors.top: clock.bottom
            anchors.topMargin: 30
            anchors.horizontalCenter: parent.horizontalCenter
            width: 96
            height: 84
            radius: 20
            color: homeMA.pressed ? "#2e6bff" : "#1c2333"
            Text {
                anchors.centerIn: parent
                font.pixelSize: 44
                text: "⌂"
            }
            MouseArea {
                id: homeMA
                anchors.fill: parent
                onClicked: carController.homeClicked()
            }
        }

        // recently used apps (most recent first, dock shows the first 5)
        Repeater {
            model: {
                var x = carController.dockApps
                return x.length > 5 ? x.slice(0, 5) : x
            }
            Rectangle {
                x: 22
                y: 220 + index * 96
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

        // settings entry, pinned to the bottom of the dock
        Rectangle {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 22
            anchors.horizontalCenter: parent.horizontalCenter
            width: 96
            height: 84
            radius: 20
            color: gearMA.pressed ? "#2e6bff" : "#1c2333"
            Text {
                anchors.centerIn: parent
                font.pixelSize: 42
                text: "⚙"
            }
            MouseArea {
                id: gearMA
                anchors.fill: parent
                onClicked: {
                    carController.openSettings()
                    root.settingsOpen = true
                }
            }
        }
    }

    // ---------- content area: home grid ----------
    // hidden while an app is on screen: the app surface may not fill its
    // item exactly, and the grid must never show through behind it
    Grid {
        id: grid
        visible: carController.currentApp === ""
        x: 140
        width: parent.width - 140
        anchors.verticalCenter: parent.verticalCenter
        columns: 5
        spacing: 20

        Repeater {
            model: carController.tiles
            Rectangle {
                width: 300
                height: 260
                radius: 24
                color: tileMA.pressed ? "#1e2c47" : "#131a29"
                Image {
                    anchors.top: parent.top
                    anchors.topMargin: 36
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 96
                    height: 96
                    fillMode: Image.PreserveAspectFit
                    source: modelData.icon !== "" ? "file://" + modelData.icon : ""
                    visible: modelData.icon !== ""
                }
                Text {
                    anchors.top: parent.top
                    anchors.topMargin: 40
                    anchors.horizontalCenter: parent.horizontalCenter
                    font.pixelSize: 84
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

    // ---------- settings page ----------
    Rectangle {
        id: settingsPage
        visible: settingsOpen
        anchors.fill: parent
        color: "#11131a"

        Rectangle {
            id: settingsHeader
            anchors.top: parent.top
            width: parent.width
            height: 64
            color: "#1a2233"
            Rectangle {
                id: backButton
                anchors.left: parent.left
                anchors.leftMargin: 24
                anchors.verticalCenter: parent.verticalCenter
                width: 150
                height: 44
                radius: 10
                color: backButtonMA.pressed ? "#2e6bff" : "#2a3550"
                Text {
                    anchors.centerIn: parent
                    color: "#ffffff"
                    font.pixelSize: 24
                    text: "← 返回"
                }
                MouseArea {
                    id: backButtonMA
                    anchors.fill: parent
                    onClicked: settingsOpen = false
                }
            }
            Text {
                anchors.centerIn: parent
                color: "#e8eaf0"
                font.pixelSize: 30
                font.bold: true
                text: "设置 — 分类与应用"
            }
            Rectangle {
                id: saveButton
                anchors.right: parent.right
                anchors.rightMargin: 24
                anchors.verticalCenter: parent.verticalCenter
                width: 150
                height: 44
                radius: 10
                color: "#2e6bff"
                Text {
                    anchors.centerIn: parent
                    color: "#ffffff"
                    font.pixelSize: 24
                    font.bold: true
                    text: "保存"
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        if (carController.saveConfig())
                            settingsOpen = false
                    }
                }
            }
        }

        // left: current mappings
        Text {
            id: mapLabel
            anchors.top: settingsHeader.bottom
            anchors.left: parent.left
            anchors.leftMargin: 30
            anchors.topMargin: 16
            color: "#8fa3c2"
            font.pixelSize: 24
            text: "分类映射 (点击 ✕ 删除)"
        }
        ListView {
            id: mapList
            anchors.top: mapLabel.bottom
            anchors.topMargin: 10
            anchors.left: parent.left
            anchors.leftMargin: 30
            width: 760
            height: parent.height - settingsHeader.height - 46
            spacing: 10
            clip: true
            model: carController.rows
            delegate: Rectangle {
                width: 740
                height: 64
                radius: 12
                color: "#223049"
                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 20
                    anchors.verticalCenter: parent.verticalCenter
                    width: 180
                    elide: Text.ElideRight
                    color: "#7fd0ff"
                    font.pixelSize: 26
                    font.bold: true
                    text: modelData.category
                }
                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 210
                    anchors.verticalCenter: parent.verticalCenter
                    width: 420
                    elide: Text.ElideRight
                    color: "#ffffff"
                    font.pixelSize: 26
                    text: modelData.appName
                }
                Rectangle {
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    width: 56
                    height: 44
                    radius: 8
                    color: delMA.pressed ? "#ff5a5a" : "#33415e"
                    Text {
                        anchors.centerIn: parent
                        color: "#ffffff"
                        font.pixelSize: 26
                        text: "✕"
                    }
                    MouseArea {
                        id: delMA
                        anchors.fill: parent
                        onClicked: carController.removeMapping(index)
                    }
                }
            }
        }

        // right: add-mapping flow
        Text {
            id: pickCatLabel
            anchors.top: settingsHeader.bottom
            anchors.left: parent.left
            anchors.leftMargin: 850
            anchors.topMargin: 16
            color: "#8fa3c2"
            font.pixelSize: 24
            text: "1. 选择分类"
        }
        Flow {
            id: catFlow
            anchors.top: pickCatLabel.bottom
            anchors.topMargin: 10
            anchors.left: parent.left
            anchors.leftMargin: 850
            width: 1020
            spacing: 12
            Repeater {
                model: {
                    var x = carController.rows   // re-evaluate on rowsChanged
                    return root.categoryChoices()
                }
                Rectangle {
                    width: catText.width + 40
                    height: 52
                    radius: 12
                    color: root.selectedCategory === modelData
                           ? "#2e6bff" : catMA.pressed ? "#2a3a55" : "#223049"
                    Text {
                        id: catText
                        anchors.centerIn: parent
                        color: "#ffffff"
                        font.pixelSize: 24
                        text: modelData
                    }
                    MouseArea {
                        id: catMA
                        anchors.fill: parent
                        onClicked: root.selectedCategory = modelData
                    }
                }
            }
        }

        Text {
            id: pickAppLabel
            anchors.top: catFlow.bottom
            anchors.topMargin: 18
            anchors.left: parent.left
            anchors.leftMargin: 850
            color: "#8fa3c2"
            font.pixelSize: 24
            text: root.selectedCategory === ""
                  ? "2. 先选一个分类" : "2. 选择应用 (含 Flatpak / 安卓)"
        }
        ListView {
            id: appList
            anchors.top: pickAppLabel.bottom
            anchors.topMargin: 10
            anchors.left: parent.left
            anchors.leftMargin: 850
            width: 1020
            height: parent.height - pickAppLabel.y - 46
            spacing: 8
            clip: true
            model: {
                var x = carController.rows   // re-evaluate on rowsChanged
                return root.availableChoices()
            }
            delegate: Rectangle {
                width: 1000
                height: 58
                radius: 10
                color: appMA.pressed ? "#2a3a55" : "#1a2233"
                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 20
                    anchors.verticalCenter: parent.verticalCenter
                    width: 500
                    elide: Text.ElideRight
                    color: "#ffffff"
                    font.pixelSize: 26
                    text: modelData.name
                }
                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: 20
                    anchors.verticalCenter: parent.verticalCenter
                    elide: Text.ElideMiddle
                    color: "#5f718f"
                    font.pixelSize: 20
                    text: modelData.id
                }
                MouseArea {
                    id: appMA
                    anchors.fill: parent
                    onClicked: {
                        if (root.selectedCategory !== "")
                            carController.addMapping(root.selectedCategory,
                                                     modelData.id)
                    }
                }
            }
        }
    }

    property var selectedCategory: ""

    property var presetCategories: [
        "音乐", "电话", "信息", "导航", "视频",
        "天气", "工具", "社交", "阅读", "其他"
    ]

    function categoryChoices() {
        var out = presetCategories.slice()
        var rows = carController.rows
        for (var i = 0; i < rows.length; i++) {
            var c = rows[i].category
            if (out.indexOf(c) < 0)
                out.push(c)
        }
        return out
    }

    function availableChoices() {
        var all = carController.availableApps()
        var rows = carController.rows
        var used = {}
        for (var i = 0; i < rows.length; i++)
            used[rows[i].appId] = true
        var out = []
        for (var j = 0; j < all.length; j++)
            if (!used[all[j].id])
                out.push(all[j])
        return out
    }
}
