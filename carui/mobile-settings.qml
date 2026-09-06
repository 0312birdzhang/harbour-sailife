import QtQuick 2.0
import Sailfish.Silica 1.0

ApplicationWindow {
    id: app
    readonly property bool useChinese: Qt.locale().name.indexOf("zh") === 0
    function textFor(english, chinese) { return useChinese ? chinese : english }
    allowedOrientations: Orientation.All
    cover: Component {
        CoverBackground {
            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - 2 * Theme.paddingLarge
                spacing: Theme.paddingMedium
                Image {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: Math.min(parent.width, parent.height) * 0.62
                    height: width
                    fillMode: Image.PreserveAspectFit
                    source: "file:///opt/carlife/carui/harbour-sailife.png"
                }
                Label {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: carController.serviceRunning ? app.textFor("Sailife · Running", "Sailife · 运行中") : app.textFor("Sailife · Stopped", "Sailife · 已停止")
                    color: Theme.highlightColor
                    font.pixelSize: Theme.fontSizeSmall
                }
            }
            CoverActionList {
                CoverAction {
                    iconSource: carController.serviceRunning
                              ? "image://theme/icon-cover-cancel"
                              : "image://theme/icon-cover-play"
                    onTriggered: carController.setServiceRunning(
                                     !carController.serviceRunning)
                }
            }
        }
    }
    initialPage: Component {
        Page {
            id: page
            allowedOrientations: Orientation.All
            function toggle(appId) {
                if (!carController.toggleApp(appId))
                    saveNotice.text = app.textFor("Save failed", "保存失败")
                else
                    saveNotice.text = app.textFor("Saved automatically", "已自动保存")
            }

            SilicaFlickable {
                anchors.fill: parent
                contentHeight: content.height
                Column {
                    id: content
                    width: page.width
                    PageHeader { title: "Sailife" }
                    SectionHeader { text: app.textFor("Projection service", "投屏服务") }
                    TextSwitch {
                        width: parent.width
                        text: carController.serviceRunning ? app.textFor("Sailife service is running", "Sailife 服务运行中") : app.textFor("Sailife service is stopped", "Sailife 服务已停止")
                        description: app.textFor("Enable only while connected to the car display. Turning it off avoids background encoding and compositor power use.", "仅在连接车机投屏时开启，关闭可避免后台编码与合成耗电。")
                        automaticCheck: false
                        checked: carController.serviceRunning
                        onClicked: carController.setServiceRunning(!checked)
                    }
                    SectionHeader { text: app.textFor("Car display home apps", "车机主页应用") }
                    Label {
                        id: saveNotice
                        x: Theme.horizontalPageMargin
                        width: parent.width - 2 * Theme.horizontalPageMargin
                        horizontalAlignment: Text.AlignHCenter
                        color: Theme.highlightColor
                    }
                    Label {
                        x: Theme.horizontalPageMargin
                        width: parent.width - 2 * Theme.horizontalPageMargin
                        wrapMode: Text.WordWrap
                        color: Theme.secondaryColor
                        font.pixelSize: Theme.fontSizeSmall
                        text: app.textFor("Select the apps to show on the car display home screen. Changes are saved and applied immediately.", "直接勾选需要显示在车机主页的应用，修改会立即保存并自动更新。")
                    }
                    Repeater {
                        model: carController.availableApps()
                        delegate: ListItem {
                            width: page.width
                            contentHeight: Theme.itemSizeSmall
                            onClicked: page.toggle(modelData.id)
                            Image {
                                id: appIcon
                                x: Theme.horizontalPageMargin
                                anchors.verticalCenter: parent.verticalCenter
                                width: Theme.iconSizeMedium
                                height: width
                                fillMode: Image.PreserveAspectFit
                                source: modelData.icon !== ""
                                      ? "file://" + modelData.icon : ""
                            }
                            Label {
                                anchors.left: appIcon.right
                                anchors.leftMargin: Theme.paddingLarge
                                anchors.right: appSwitch.left
                                anchors.rightMargin: Theme.paddingMedium
                                anchors.verticalCenter: parent.verticalCenter
                                truncationMode: TruncationMode.Fade
                                text: modelData.name
                            }
                            Switch {
                                id: appSwitch
                                anchors.right: parent.right
                                anchors.rightMargin: Theme.horizontalPageMargin
                                anchors.verticalCenter: parent.verticalCenter
                                automaticCheck: false
                                checked: carController.selectedApps.indexOf(
                                             modelData.id) >= 0
                                onClicked: page.toggle(modelData.id)
                            }
                        }
                    }
                    Item { width: 1; height: Theme.paddingLarge }
                }
                VerticalScrollDecorator { }
            }
        }
    }
}
