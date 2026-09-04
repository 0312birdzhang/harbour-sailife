#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QUrl>
#include <QQuickWindow>
#include <QQuickItem>
#include <QTimer>
#include <QObject>
#include <QProcess>
#include <QFile>
#include <QDir>
#include <QVariantList>
#include <QStringList>
#include <functional>
#include <cstdio>
#include <fcntl.h>
#include <unistd.h>

static const char *kAppConfig = "/opt/carlife/carui-apps.conf";

struct AppInfo {
    QString category;
    QString name;
    QString exec;
};

static bool parseDesktop(const QString &id, QString *name, QString *exec)
{
    QFile f(QStringLiteral("/usr/share/applications/") + id + QStringLiteral(".desktop"));
    if (!f.open(QIODevice::ReadOnly | QIODevice::Text))
        return false;
    *name = id;
    *exec = QString();
    while (!f.atEnd()) {
        QString line = QString::fromUtf8(f.readLine()).trimmed();
        if (line.startsWith(QStringLiteral("Name=")))
            *name = line.mid(5);
        else if (line.startsWith(QStringLiteral("Exec=")) && exec->isEmpty())
            *exec = line.mid(5);
    }
    if (exec->isEmpty())
        return false;
    // Exec comes as "app %u", "sailjail -p x /usr/bin/app" or
    // "invoker --type=y /usr/bin/app". We need the plain binary: the
    // sandbox/booster would wire the app to lipstick, not to our
    // virtual display imira-comp-0.
    QStringList parts = exec->split(QLatin1Char(' '), QString::SkipEmptyParts);
    QString binary = parts.value(0);
    for (int i = parts.count() - 1; i > 0; --i) {
        if (parts.at(i).startsWith(QLatin1Char('/'))) {
            binary = parts.at(i);
            break;
        }
    }
    *exec = binary;
    return !binary.isEmpty();
}

static QVector<AppInfo> readApps()
{
    QVector<AppInfo> apps;
    QFile f(QString::fromLatin1(kAppConfig));
    if (!f.open(QIODevice::ReadOnly | QIODevice::Text))
        return apps;
    while (!f.atEnd()) {
        QString line = QString::fromUtf8(f.readLine()).trimmed();
        if (line.isEmpty() || line.startsWith(QLatin1Char('#')))
            continue;
        QStringList parts = line.split(QLatin1Char(':'));
        if (parts.size() < 2)
            continue;
        QString category = parts[0].trimmed();
        QString appId = parts[1].trimmed();
        QString name, exec;
        if (!parseDesktop(appId, &name, &exec))
            continue;
        if (exec.isEmpty())
            continue;
        AppInfo a;
        a.category = category;
        a.name = name;
        a.exec = exec;
        apps.append(a);
    }
    return apps;
}

static QHash<QString, qint64> s_appPids;   // exec -> last launched pid

static qint64 launchApp(const QString &exec)
{
    QString cmd = QStringLiteral(
        "QT_QPA_PLATFORM=wayland WAYLAND_DISPLAY=imira-comp-0 "
        "QT_IM_MODULE=none "
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/100000/dbus/user_bus_socket ");
    cmd += QStringLiteral("exec ") + exec;
    qint64 pid = 0;
    QProcess::startDetached(QStringLiteral("/bin/sh"),
                            QStringList() << QStringLiteral("-c") << cmd,
                            QString(), &pid);
    return pid;
}

// A hidden app window (imira-comp "home" minimizes instead of destroying;
// see imira-comp.cpp hideWindow) is reused so the same surface keeps its
// input focus — re-launching would hit Qt 5.6's stale-focus bug.
static bool isPidHidden(qint64 pid)
{
    QFile f(QStringLiteral("/tmp/imira-hidden"));
    if (!f.open(QIODevice::ReadOnly | QIODevice::Text))
        return false;
    return f.readAll().contains(QByteArray::number(pid));
}

static void showAppWindow(qint64 pid)
{
    FILE *tf = fopen("/tmp/imira-touch", "a");
    if (tf) {
        fprintf(tf, "S %lld\n", pid);
        fclose(tf);
    }
    fprintf(stderr, "carui: show app pid=%lld\n", pid);
}

static bool imiraHasApp()
{
    QFile f(QStringLiteral("/tmp/imira-app-running"));
    if (!f.open(QIODevice::ReadOnly | QIODevice::Text))
        return false;
    return f.readAll().trimmed() == QStringLiteral("1");
}

static QVector<AppInfo> g_apps;

// The compositor is the unmodified harbour-imira one: head-unit taps arrive
// as a REAL input-device mouse (uinput) and hit the Qt Quick scene, so
// carui must handle its own clicks with a MouseArea in QML. This controller
// is the bridge from QML to the launcher logic.
class CarUiController : public QObject
{
    Q_OBJECT
public:
    explicit CarUiController(QObject *parent = nullptr) : QObject(parent) {}

    Q_INVOKABLE void tileClicked(int index)
    {
        if (index < 0 || index >= g_apps.size())
            return;
        const AppInfo &a = g_apps[index];
        fprintf(stderr, "carui: launching %s\n", a.name.toUtf8().constData());
        launchApp(a.exec);
    }
};

int main(int argc, char **argv)
{
    QGuiApplication app(argc, argv);
    app.setApplicationName("carlife-ui");
    QQmlApplicationEngine engine;

    g_apps = readApps();
    CarUiController controller;
    engine.rootContext()->setContextProperty("carController", &controller);
    QStringList names;
    for (const AppInfo &a : g_apps)
        names << (a.name.isEmpty() ? a.category : a.name);
    engine.rootContext()->setContextProperty("carAppNames",
                                             QVariant::fromValue(names));
    fprintf(stderr, "carui: %d apps configured\n", g_apps.size());
    for (const AppInfo &a : g_apps)
        fprintf(stderr, "  %s -> %s (%s)\n", a.category.toUtf8().constData(),
                a.name.toUtf8().constData(), a.exec.toUtf8().constData());

    const char *qml = argc > 1 ? argv[1] : "/opt/carlife/carui/main.qml";
    QQmlComponent comp(&engine, QUrl::fromLocalFile(qml));
    if (comp.isError()) {
        for (const auto &e : comp.errors())
            fprintf(stderr, "QML error: %s\n", e.toString().toUtf8().constData());
        return 1;
    }
    QObject *rootObj = comp.create();
    if (!rootObj) {
        fprintf(stderr, "carui: component create failed\n");
        return 1;
    }
    QQuickWindow *win = qobject_cast<QQuickWindow *>(rootObj);
    if (!win) {
        fprintf(stderr, "carui: no window\n");
        return 1;
    }

    int fifo = open("/tmp/carui-touch", O_RDONLY | O_NONBLOCK);
    if (fifo >= 0) {
        QTimer *timer = new QTimer(&app);
        QObject::connect(timer, &QTimer::timeout, [win, fifo]() {
            static char line[128];
            static size_t pos = 0;
            char buf[256];
            ssize_t n;
            while ((n = read(fifo, buf, sizeof(buf))) > 0) {
                for (ssize_t i = 0; i < n; i++) {
                    if (buf[i] == '\n') {
                        line[pos] = 0;
                        int a, x, y;
                        if (sscanf(line, "%d %d %d", &a, &x, &y) == 3) {
                            if (imiraHasApp()) {
                                /* an app window is up: forward the tap to
                                 * imira-comp which injects it into the app */
                                FILE *tf = fopen("/tmp/imira-touch", "a");
                                if (tf) {
                                    fprintf(tf, "%d %d %d\n", a, x, y);
                                    fclose(tf);
                                }
                                fprintf(stderr, "carui: fwd touch a=%d x=%d y=%d\n",
                                        a, x, y);
                                pos = 0;   /* reset line buffer before continue */
                                continue;
                            }
                            if (a == 1) {
                                QQuickItem *content =
                                    qobject_cast<QQuickItem *>(win->contentItem());
                                if (content) {
                                    std::function<void(QQuickItem *)> walk;
                                    bool hit = false;
                                    int tileIdx = -1;
                                    walk = [&](QQuickItem *it) {
                                        if (hit)
                                            return;
                                        if (it->objectName().startsWith("tile_")) {
                                            int idx = it->objectName().mid(5).toInt();
                                            QPointF tl = it->mapToItem(content, QPointF(0, 0));
                                            if (x >= tl.x() && x < tl.x() + it->width() &&
                                                y >= tl.y() && y < tl.y() + it->height()) {
                                                hit = true;
                                                tileIdx = idx;
                                                it->setProperty("scale", 0.85);
                                                QQuickItem *item = it;
                                                QTimer::singleShot(150, [item]() {
                                                    item->setProperty("scale", 1.0);
                                                });
                                                return;
                                            }
                                        }
                                        for (QQuickItem *c : it->childItems())
                                            walk(c);
                                    };
                                    walk(content);
                                    if (hit && tileIdx >= 0 && tileIdx < g_apps.size()) {
                                        fprintf(stderr, "carui: launching %s\n",
                                                g_apps[tileIdx].name.toUtf8().constData());
                                        launchApp(g_apps[tileIdx].exec);
                                    }
                                }
                            }
                        }
                        pos = 0;
                    } else if (pos < sizeof(line) - 1) {
                        line[pos++] = buf[i];
                    }
                }
            }
        });
        timer->start(20);
        fprintf(stderr, "carui: touch reader ready\n");
    }
    fprintf(stderr, "carui: loaded %s\n", qml);
    return app.exec();
}

#include "main.moc"