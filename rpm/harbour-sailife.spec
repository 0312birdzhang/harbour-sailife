# harbour-sailife — SailfishOS in-vehicle projection.
#
# The ARM binaries (imira-comp virtual compositor, carui launcher,
# carlife-capture with statically linked x264) are cross-built OUTSIDE this
# spec by rpm/build-arm.sh and only copied in %%install — same approach as
# harbour-imira's casting machinery. Do not add build steps here.
#
Name:       harbour-sailife
Summary:    Sailife in-vehicle projection for Sailfish OS
Version:    0.1.0
Release:    1
License:    GPL-3.0-or-later
Source0:    %{name}-%{version}.tar.bz2
BuildArch:  aarch64

# The proto daemon is a python3 script; everything else is prebuilt and
# vetted by hand, and carlife-capture bundles a static libx264, so switch
# off automatic requires/provides for the package.
Requires:   python3-base
Requires:   sailfishsilica-qt5
AutoReq:    0
AutoProv:   0

%description
Projects the tablet's vehicle UI (a virtual 1920x720 screen running a Qt Quick
launcher) to a compatible head unit over USB AOA, with touch routed back from
the head unit. One systemd service (sailife.service) starts the whole chain:
carlife_proto.py (AOA protocol + staged USB reconnect), imira-comp
(virtual Wayland compositor), carui (launcher UI) and carlife-capture
(lipstick-recorder shm capture + x264 Annex-B H.264).

Derived in part from harbour-imira (GPL-3.0-or-later).

%prep
%setup -q

%build
# nothing: all binaries are prebuilt by rpm/build-arm.sh

%install
install -d %{buildroot}/opt/carlife/carui
install -m 0755 carlife-proto/carlife_proto.py  %{buildroot}/opt/carlife/carlife_proto.py
install -m 0755 carlife-proto/aoa_manager.py    %{buildroot}/opt/carlife/aoa_manager.py
install -m 0755 rpm/payload/imira-comp          %{buildroot}/opt/carlife/imira-comp
install -m 0755 rpm/payload/carlife-capture     %{buildroot}/opt/carlife/carlife-capture
install -m 0755 rpm/payload/carui               %{buildroot}/opt/carlife/carui/carui
install -m 0644 carui/main.qml                  %{buildroot}/opt/carlife/carui/main.qml
install -m 0644 carui/mobile-settings.qml       %{buildroot}/opt/carlife/carui/mobile-settings.qml
install -m 0644 carui/harbour-sailife.png       %{buildroot}/opt/carlife/carui/harbour-sailife.png
install -m 0644 carui/carui-apps.conf           %{buildroot}/opt/carlife/carui-apps.conf
install -m 0755 scripts/start_convergence.sh    %{buildroot}/opt/carlife/start_convergence.sh
install -m 0755 scripts/stop_convergence.sh     %{buildroot}/opt/carlife/stop_convergence.sh
install -m 0755 scripts/audio_bridge.sh         %{buildroot}/opt/carlife/audio_bridge.sh
install -d %{buildroot}%{_sysconfdir}/systemd/system
install -m 0644 rpm/sailife.service              %{buildroot}%{_sysconfdir}/systemd/system/sailife.service
install -d %{buildroot}%{_datadir}/applications
install -m 0644 rpm/harbour-sailife.desktop     %{buildroot}%{_datadir}/applications/harbour-sailife.desktop
install -d %{buildroot}%{_datadir}/icons/hicolor/172x172/apps
install -m 0644 carui/harbour-sailife.png       %{buildroot}%{_datadir}/icons/hicolor/172x172/apps/harbour-sailife.png
install -d %{buildroot}%{_datadir}/polkit-1/rules.d
install -m 0644 rpm/50-sailife.rules            %{buildroot}%{_datadir}/polkit-1/rules.d/50-sailife.rules
install -d %{buildroot}%{_sysconfdir}/pulse/xpolicy.conf.d
install -m 0644 rpm/sailife-xpolicy.conf        %{buildroot}%{_sysconfdir}/pulse/xpolicy.conf.d/sailife.conf
install -d %{buildroot}%{_sysconfdir}/usb-moded/dyn-modes %{buildroot}%{_sysconfdir}/usb-moded/run
install -m 0644 rpm/sailife-usb-mode.ini %{buildroot}%{_sysconfdir}/usb-moded/dyn-modes/sailife_mode.ini
install -m 0644 rpm/sailife-usb-appsync.ini %{buildroot}%{_sysconfdir}/usb-moded/run/sailife.ini
install -m 0644 rpm/90-sailife-usb.ini %{buildroot}%{_sysconfdir}/usb-moded/90-sailife.ini
install -d %{buildroot}/var/lib/environment/usb-moded
install -m 0644 rpm/sailife-usb-environment.conf %{buildroot}/var/lib/environment/usb-moded/sailife-aoa.conf

%post
# Guarded: during image builds there is no running systemd.
systemctl stop carlife.service >/dev/null 2>&1 || :
systemctl disable carlife.service >/dev/null 2>&1 || :
systemctl daemon-reload >/dev/null 2>&1 || :
# Projection is opt-in from the Sailife app. Keeping the compositor and
# encoder alive while no head unit is connected wastes significant power.
systemctl disable sailife.service >/dev/null 2>&1 || :
systemctl stop sailife.service >/dev/null 2>&1 || :
pkill -x pulseaudio >/dev/null 2>&1 || :
systemctl restart usb-moded.service >/dev/null 2>&1 || :
sleep 1
dbus-send --system --type=method_call --dest=com.meego.usb_moded /com/meego/usb_moded com.meego.usb_moded.set_whitelisted string:sailife_mode boolean:true >/dev/null 2>&1 || :
if dbus-send --system --print-reply --dest=com.meego.usb_moded /com/meego/usb_moded com.meego.usb_moded.mode_request 2>/dev/null | grep -q 'sailife_mode'; then
    systemctl start sailife.service >/dev/null 2>&1 || :
fi

%preun
# $1 = 0 on erase, >= 1 on upgrade — only stop the service when going away.
if [ "$1" = "0" ]; then
    dbus-send --system --type=method_call --dest=com.meego.usb_moded /com/meego/usb_moded com.meego.usb_moded.set_whitelisted string:sailife_mode boolean:false >/dev/null 2>&1 || :
    systemctl stop sailife.service >/dev/null 2>&1 || :
    systemctl disable sailife.service >/dev/null 2>&1 || :
fi

%postun
systemctl restart usb-moded.service >/dev/null 2>&1 || :
systemctl daemon-reload >/dev/null 2>&1 || :

%files
%defattr(-,root,root,-)
%dir /opt/carlife
%dir /opt/carlife/carui
/opt/carlife/carlife_proto.py
/opt/carlife/aoa_manager.py
# setgid privileged: the Lipstick recorder socket is only reachable for the
# privileged group; without the 2 bit capture records nothing.
%attr(2755,root,privileged) /opt/carlife/imira-comp
%attr(2755,root,privileged) /opt/carlife/carlife-capture
/opt/carlife/carui/carui
/opt/carlife/carui/main.qml
/opt/carlife/carui/mobile-settings.qml
/opt/carlife/carui/harbour-sailife.png
%config(noreplace) /opt/carlife/carui-apps.conf
/opt/carlife/start_convergence.sh
/opt/carlife/stop_convergence.sh
/opt/carlife/audio_bridge.sh
%{_sysconfdir}/systemd/system/sailife.service
%{_datadir}/applications/harbour-sailife.desktop
%{_datadir}/icons/hicolor/172x172/apps/harbour-sailife.png
%{_datadir}/polkit-1/rules.d/50-sailife.rules
%{_sysconfdir}/pulse/xpolicy.conf.d/sailife.conf

%{_sysconfdir}/usb-moded/dyn-modes/sailife_mode.ini
%{_sysconfdir}/usb-moded/run/sailife.ini

%{_sysconfdir}/usb-moded/90-sailife.ini
/var/lib/environment/usb-moded/sailife-aoa.conf
%changelog
* Thu Sep 04 2026 harbour-sailife 0.1.0-1
- Initial RPM: vehicle projection daemon with staged USB reconnect, virtual
  compositor, launcher UI, x264 capture, boot-autostart systemd service.
