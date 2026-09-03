#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QUrl>
#include <QQuickWindow>
#include <QQuickItem>
#include <QTimer>
#include <QObject>
#include <functional>
#include <cstdio>
#include <fcntl.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    QGuiApplication app(argc, argv);
    app.setApplicationName("carlife-ui");
    QQmlApplicationEngine engine;
    const char *qml = argc > 1 ? argv[1] : "/opt/carlife/carui/main.qml";
    engine.load(QUrl::fromLocalFile(qml));
    if (engine.rootObjects().isEmpty()) {
        fprintf(stderr, "carui: failed to load %s\n", qml);
        return 1;
    }
    QQuickWindow *win = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
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
                            fprintf(stderr, "carui touch: %d %d %d\n", a, x, y);
                            if (a == 1) {
                                QQuickItem *content =
                                    qobject_cast<QQuickItem *>(win->contentItem());
                                if (content) {
                                    fprintf(stderr, "content ptr=%p children=%d\n",
                                            (void *)content,
                                            content->childItems().size());
                                    std::function<void(QQuickItem *)> walk;
                                    bool hit = false;
                                    walk = [&](QQuickItem *it) {
                                        if (hit)
                                            return;
                                        if (it->objectName().startsWith("tile_")) {
                                            QPointF tl = it->mapToItem(content, QPointF(0, 0));
                                            fprintf(stderr, "  %s at %d,%d size %dx%d\n",
                                                    it->objectName().toUtf8().constData(),
                                                    (int)tl.x(), (int)tl.y(),
                                                    (int)it->width(), (int)it->height());
                                            if (x >= tl.x() && x < tl.x() + it->width() &&
                                                y >= tl.y() && y < tl.y() + it->height()) {
                                                fprintf(stderr, "carui tile hit: %s\n",
                                                        it->objectName().toUtf8().constData());
                                                it->setProperty("scale", 0.85);
                                                QQuickItem *item = it;
                                                QTimer::singleShot(150, [item]() {
                                                    item->setProperty("scale", 1.0);
                                                });
                                                hit = true;
                                                return;
                                            }
                                        }
                                        for (QQuickItem *c : it->childItems())
                                            walk(c);
                                    };
                                    walk(content);
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