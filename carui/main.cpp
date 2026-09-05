#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlComponent>
#include <QQmlContext>
#include <QUrl>
#include <QQuickWindow>
#include <QObject>
#include <QProcess>
#include <QFile>
#include <QFileInfo>
#include <QDir>
#include <QVariantList>
#include <QVariantMap>
#include <QStringList>
#include <QSet>
#include <algorithm>
#include <cstdio>

static const char *kSystemConfig = "/opt/carlife/carui-apps.conf";

struct AppInfo {
    QString category;
    QString appId;
    QString name;
    QString exec;
    QString icon;
};

// An installed application: id = desktop-file basename. fullExec apps run
// their Exec line verbatim ("flatpak-runner com.qq.QQ", "apkd-launcher …" —
// runner-style commands whose arguments matter); everything else runs the
// extracted plain binary (sailjail/invoker would wire the app to lipstick
// instead of our virtual display imira-comp-0).
struct AvailableApp {
    QString id;
    QString name;
    QString exec;
    QString icon;
};
static QVector<AvailableApp> g_available;

static QString userConfigPath()
{
    return QDir::home().filePath(QStringLiteral(".config/carlife/carui-apps.conf"));
}

static QString recentPath()
{
    return QDir::home().filePath(QStringLiteral(".config/carlife/carui-recent"));
}

// Resolve a desktop Icon= entry to a loadable image path.
static QString resolveIcon(const QString &iconName)
{
    if (iconName.startsWith(QLatin1Char('/')))
        return QFile::exists(iconName) ? iconName : QString();
    if (iconName.isEmpty())
        return QString();
    const QStringList sizes = {
        QStringLiteral("86x86"), QStringLiteral("128x128"),
        QStringLiteral("108x108"), QStringLiteral("172x172"),
        QStringLiteral("512x512")
    };
    for (const QString &s : sizes) {
        const QString p = QStringLiteral("/usr/share/icons/hicolor/") + s
                          + QStringLiteral("/apps/") + iconName
                          + QStringLiteral(".png");
        if (QFile::exists(p))
            return p;
    }
    QDir theme(QStringLiteral("/usr/share/themes/sailfish-default/silica"));
    for (const QString &z : theme.entryList(QStringList() << QStringLiteral("z*"),
                                            QDir::Dirs)) {
        const QString p = theme.filePath(z) + QStringLiteral("/icons/")
                          + iconName + QStringLiteral(".png");
        if (QFile::exists(p))
            return p;
    }
    return QString();
}

static bool parseDesktopFile(const QString &path, QString *name, QString *exec,
                             bool *hidden, QString *icon)
{
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly | QIODevice::Text))
        return false;
    *name = QFileInfo(path).completeBaseName();
    *exec = QString();
    *icon = QString();
    *hidden = false;
    while (!f.atEnd()) {
        QString line = QString::fromUtf8(f.readLine()).trimmed();
        int eq = line.indexOf(QLatin1Char('='));
        if (eq < 0)
            continue;
        // some generated desktops (flatpak-runner-autogen) write "Name = x"
        QString key = line.left(eq).trimmed();
        QString val = line.mid(eq + 1).trimmed();
        if (key == QStringLiteral("Name"))
            *name = val;
        else if (key == QStringLiteral("Exec") && exec->isEmpty())
            *exec = val;
        else if (key == QStringLiteral("Icon") && icon->isEmpty())
            *icon = val;
        else if ((key == QStringLiteral("NoDisplay")
                  || key == QStringLiteral("Hidden")) && val == QStringLiteral("true"))
            *hidden = true;
    }
    return !exec->isEmpty();
}

// Native desktops carry an absolute binary in Exec ("sailjail -p x
// /usr/bin/app"); runner-style desktops ("flatpak-runner com.qq.QQ") have
// arguments but no path, and must be executed verbatim.
static bool execIsRunnerStyle(const QString &exec)
{
    QStringList parts = exec.split(QLatin1Char(' '), QString::SkipEmptyParts);
    bool hasPath = false;
    int argc = 0;
    for (const QString &p : parts) {
        if (p.startsWith(QLatin1Char('%')))
            continue;   // desktop field codes
        if (p.startsWith(QLatin1Char('/')))
            hasPath = true;
        argc++;
    }
    return !hasPath && argc > 1;
}

static QString extractBinary(const QString &exec)
{
    QStringList parts = exec.split(QLatin1Char(' '), QString::SkipEmptyParts);
    QString binary = parts.value(0);
    for (int i = parts.count() - 1; i > 0; --i) {
        if (parts.at(i).startsWith(QLatin1Char('/'))) {
            binary = parts.at(i);
            break;
        }
    }
    return binary;
}

// System desktops first, user-local ones (flatpak/AppSupport) override.
static void scanAvailableApps()
{
    g_available.clear();
    const QStringList dirs = {
        QStringLiteral("/usr/share/applications"),
        QDir::home().filePath(QStringLiteral(".local/share/applications")),
    };
    for (const QString &dn : dirs) {
        QDir dir(dn);
        if (!dir.exists())
            continue;
        const QStringList files = dir.entryList(
            QStringList() << QStringLiteral("*.desktop"), QDir::Files);
        for (const QString &fn : files) {
            QString name, exec, icon;
            bool hidden = false;
            if (!parseDesktopFile(dir.filePath(fn), &name, &exec, &hidden,
                                  &icon))
                continue;
            if (hidden || name.isEmpty())
                continue;
            AvailableApp a;
            a.id = fn.left(fn.size() - 8);
            a.name = name;
            a.exec = execIsRunnerStyle(exec) ? exec : extractBinary(exec);
            a.icon = resolveIcon(icon);
            int found = -1;
            for (int i = 0; i < g_available.size(); ++i) {
                if (g_available[i].id == a.id) {
                    found = i;
                    break;
                }
            }
            if (found >= 0)
                g_available[found] = a;
            else
                g_available.append(a);
        }
    }
    std::sort(g_available.begin(), g_available.end(),
              [](const AvailableApp &a, const AvailableApp &b) {
                  return a.name.compare(b.name, Qt::CaseInsensitive) < 0;
              });
    fprintf(stderr, "carui: %d installed apps\n", g_available.size());
}

static const AvailableApp *findAvailable(const QString &id)
{
    for (const AvailableApp &a : g_available)
        if (a.id == id)
            return &a;
    return nullptr;
}

static QVector<AppInfo> readApps()
{
    QVector<AppInfo> apps;
    QString path = userConfigPath();
    QFile f(QFile::exists(path) ? path : QString::fromLatin1(kSystemConfig));
    if (!f.open(QIODevice::ReadOnly | QIODevice::Text))
        return apps;
    while (!f.atEnd()) {
        QString line = QString::fromUtf8(f.readLine()).trimmed();
        if (line.isEmpty() || line.startsWith(QLatin1Char('#')))
            continue;
        // appId = everything after the FIRST colon; a missing trailing
        // newline on the last line once glued two lines together here
        int colon = line.indexOf(QLatin1Char(':'));
        if (colon <= 0)
            continue;
        QString category = line.left(colon).trimmed();
        QString appId = line.mid(colon + 1).trimmed();
        const AvailableApp *a = findAvailable(appId);
        if (!a || a->exec.isEmpty())
            continue;
        AppInfo ai;
        ai.category = category;
        ai.appId = appId;
        ai.name = a->name;
        ai.exec = a->exec;
        ai.icon = a->icon;
        apps.append(ai);
    }
    return apps;
}

static qint64 launchApp(const QString &exec)
{
    QString cmd = QStringLiteral(
        "QT_QPA_PLATFORM=wayland WAYLAND_DISPLAY=imira-comp-0 "
        "QT_IM_MODULE=none "
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/100000/dbus/"
        "user_bus_socket ");
    cmd += QStringLiteral("exec ") + exec;
    qint64 pid = 0;
    QProcess::startDetached(QStringLiteral("/bin/sh"),
                            QStringList() << QStringLiteral("-c") << cmd,
                            QString(), &pid);
    return pid;
}

static QVector<AppInfo> g_apps;

// CarPlay-like shell state: dockApps = configured apps ordered by launch
// recency (most recent first); the home grid hides under the app window,
// so carui tracks which app is on screen and every still-running hidden app;
// dock taps switch between them without creating duplicate processes.
static QStringList g_recent;

static void loadRecent()
{
    g_recent.clear();
    QFile f(recentPath());
    if (f.open(QIODevice::ReadOnly | QIODevice::Text)) {
        while (!f.atEnd()) {
            const QString id = QString::fromUtf8(f.readLine()).trimmed();
            if (!id.isEmpty())
                g_recent.append(id);
        }
    }
}

static void saveRecent()
{
    QDir().mkpath(QDir::home().filePath(QStringLiteral(".config/carlife")));
    QFile f(recentPath());
    if (!f.open(QIODevice::WriteOnly | QIODevice::Text | QIODevice::Truncate))
        return;
    for (const QString &id : g_recent)
        f.write(id.toUtf8() + QByteArray("\n"));
}

static void moveToFront(const QString &appId)
{
    g_recent.removeAll(appId);
    g_recent.prepend(appId);
    // keep the file bounded: the dock shows the head of the list anyway
    while (g_recent.size() > 32)
        g_recent.removeLast();
    saveRecent();
}

// The compositor is the unmodified harbour-imira one: head-unit taps arrive
// as a REAL input-device mouse (uinput) and hit the Qt Quick scene, so
// carui must handle its own clicks with a MouseArea in QML. This controller
// is the bridge from QML to the launcher logic and the settings editor.
class CarUiController : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QVariantList tiles READ tiles NOTIFY tilesChanged)
    Q_PROPERTY(QVariantList rows READ rows NOTIFY rowsChanged)
    Q_PROPERTY(QVariantList dockApps READ dockApps NOTIFY dockChanged)
    Q_PROPERTY(QString currentApp READ currentApp NOTIFY currentAppChanged)

public:
    explicit CarUiController(QObject *parent = nullptr) : QObject(parent) {}

    // one tile per config row (a category may appear several times)
    QVariantList tiles() const
    {
        QVariantList l;
        for (const AppInfo &a : g_apps) {
            QVariantMap m;
            m.insert(QStringLiteral("category"), a.category);
            m.insert(QStringLiteral("name"), a.name);
            m.insert(QStringLiteral("icon"), a.icon);
            l.append(m);
        }
        return l;
    }

    // dock: configured apps, most recently used first
    QVariantList dockApps() const
    {
        QVariantList l;
        for (const QString &id : g_recent) {
            const AvailableApp *a = findAvailable(id);
            if (!a)
                continue;
            QVariantMap m;
            m.insert(QStringLiteral("appId"), id);
            m.insert(QStringLiteral("name"), a->name);
            m.insert(QStringLiteral("icon"), a->icon);
            l.append(m);
        }
        return l;
    }

    // current editor state: [{category, appId, appName}, …]
    QVariantList rows() const { return m_rows; }

    // appId of the app currently on screen ("" = home grid visible)
    QString currentApp() const { return m_currentApp; }

    Q_INVOKABLE void reloadConfig()
    {
        scanAvailableApps();
        // recency entries for apps that no longer resolve are dead weight
        QStringList valid;
        for (const QString &id : g_recent) {
            if (findAvailable(id) && !valid.contains(id))
                valid.append(id);
        }
        for (const AppInfo &a : g_apps) {
            if (!valid.contains(a.appId))
                valid.append(a.appId);
        }
        g_recent = valid;
        g_apps = readApps();
        m_rows.clear();
        for (const AppInfo &a : g_apps) {
            QVariantMap m;
            m.insert(QStringLiteral("category"), a.category);
            m.insert(QStringLiteral("appId"), a.appId);
            m.insert(QStringLiteral("appName"), a.name);
            m_rows.append(m);
        }
        emit tilesChanged();
        emit rowsChanged();
        emit dockChanged();
        fprintf(stderr, "carui: %d apps configured\n", g_apps.size());
    }

    Q_INVOKABLE QVariantList availableApps() const
    {
        QVariantList l;
        for (const AvailableApp &a : g_available) {
            QVariantMap m;
            m.insert(QStringLiteral("id"), a.id);
            m.insert(QStringLiteral("name"), a.name);
            l.append(m);
        }
        return l;
    }

    Q_INVOKABLE void addMapping(const QString &category, const QString &appId)
    {
        for (const QVariant &v : m_rows) {
            QVariantMap m = v.toMap();
            if (m.value("category").toString() == category
                && m.value("appId").toString() == appId)
                return;
        }
        QVariantMap m;
        m.insert(QStringLiteral("category"), category);
        m.insert(QStringLiteral("appId"), appId);
        const AvailableApp *a = findAvailable(appId);
        m.insert(QStringLiteral("appName"),
                 a ? a->name : appId);
        m_rows.append(m);
        emit rowsChanged();
    }

    Q_INVOKABLE void removeMapping(int index)
    {
        if (index < 0 || index >= m_rows.size())
            return;
        m_rows.removeAt(index);
        emit rowsChanged();
    }

    Q_INVOKABLE bool saveConfig()
    {
        QFile f(userConfigPath());
        QDir().mkpath(QDir::home().filePath(QStringLiteral(".config/carlife")));
        if (!f.open(QIODevice::WriteOnly | QIODevice::Text | QIODevice::Truncate))
            return false;
        for (const QVariant &v : m_rows) {
            QVariantMap m = v.toMap();
            f.write(m.value("category").toString().toUtf8());
            f.write(":");
            f.write(m.value("appId").toString().toUtf8());
            f.write("\n");
        }
        f.close();
        if (f.error() != QFile::NoError)
            return false;
        g_apps = readApps();
        emit tilesChanged();
        emit dockChanged();
        fprintf(stderr, "carui: config saved, %d apps\n", g_apps.size());
        return true;
    }

    Q_INVOKABLE void tileClicked(int index)
    {
        if (index < 0 || index >= g_apps.size())
            return;
        const AppInfo &a = g_apps[index];
        activate(a.appId, a.exec, a.name);
    }

    Q_INVOKABLE void dockClicked(const QString &appId)
    {
        const AvailableApp *a = findAvailable(appId);
        if (!a)
            return;
        activate(appId, a->exec, a->name);
    }

    // gear: hide whatever is on screen, then open the settings overlay
    Q_INVOKABLE void openSettings()
    {
        if (!m_currentApp.isEmpty()) {
            hideCurrent();
            emit currentAppChanged();
        }
        reloadConfig();
    }

    Q_INVOKABLE void homeClicked()
    {
        if (m_currentApp.isEmpty())
            return;
        const QString appId = m_currentApp;
        hideCurrent();
        fprintf(stderr, "carui: home (hid %s)\n",
                appId.toUtf8().constData());
        emit currentAppChanged();
    }

signals:
    void tilesChanged();
    void rowsChanged();
    void dockChanged();
    void currentAppChanged();

private:
    QVariantList m_rows;
    QString m_currentApp;
    QSet<QString> m_hiddenApps;
    // CarPlay semantics: the tapped app replaces whatever is on screen; a
    // hidden app comes back instead of being launched twice (native apps
    // launched as bare binaries have no single-instance guard).
    void activate(const QString &appId, const QString &exec,
                  const QString &name)
    {
        if (appId == m_currentApp)
            return;   // already on screen
        if (m_hiddenApps.contains(appId)) {
            // Switching between two already-running apps must hide the
            // current one before restoring the requested one. Otherwise the
            // compositor has two visible/input-capable content surfaces.
            if (!m_currentApp.isEmpty())
                hideCurrent();
            writeCmd(QStringLiteral("S ") + name);
            m_currentApp = appId;
            m_hiddenApps.remove(appId);
            fprintf(stderr, "carui: showing %s\n",
                    name.toUtf8().constData());
            emit currentAppChanged();
            return;
        }
        fprintf(stderr, "carui: launching %s\n", name.toUtf8().constData());
        launchApp(exec);
        moveToFront(appId);
        if (!m_currentApp.isEmpty())
            hideCurrent();   // the new app replaces the one on screen
        m_currentApp = appId;
        emit dockChanged();
        emit currentAppChanged();
    }

    void writeCmd(const QString &cmd)
    {
        FILE *tf = fopen("/tmp/imira-touch", "a");
        if (tf) {
            fprintf(tf, "%s\n", cmd.toUtf8().constData());
            fclose(tf);
        }
    }

    // H <name>: hide the app on screen (named so the compositor can tell
    // stacked hidden apps apart)
    void hideCurrent()
    {
        const AvailableApp *a = findAvailable(m_currentApp);
        writeCmd(QStringLiteral("H ") + (a ? a->name : m_currentApp));
        m_hiddenApps.insert(m_currentApp);
        m_currentApp.clear();
    }
};

int main(int argc, char **argv)
{
    QGuiApplication app(argc, argv);
    app.setApplicationName("carlife-ui");
    QQmlApplicationEngine engine;

    CarUiController controller;
    engine.rootContext()->setContextProperty("carController", &controller);
    loadRecent();
    controller.reloadConfig();

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

    fprintf(stderr, "carui: loaded %s\n", qml);
    return app.exec();
}

#include "main.moc"
