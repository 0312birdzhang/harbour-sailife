# harbour-sailife — SailfishOS tablet → CarLife head-unit projection.
#
# The ARM binaries (imira-comp virtual compositor, carui launcher,
# carlife-capture with statically linked x264) are cross-built OUTSIDE this
# spec by rpm/build-arm.sh and only copied in %%install — same approach as
# harbour-imira's casting machinery. Do not add build steps here.
#
Name:       harbour-sailife
Summary:    CarLife projection: Sailfish tablet UI on a CarLife head unit
Version:    0.1.0
Release:    1
License:    GPL-3.0-or-later
Source0:    %{name}-%{version}.tar.bz2
BuildArch:  aarch64

# The proto daemon is a python3 script; everything else is prebuilt and
# vetted by hand, and carlife-capture bundles a static libx264, so switch
# off automatic requires/provides for the package.
Requires:   python3-base
AutoReq:    0
AutoProv:   0

%description
Projects the tablet's car UI (a virtual 1920x720 screen running a Qt Quick
launcher) to a CarLife head unit over USB AOA, with touch routed back from
the head unit. One systemd service (carlife.service) starts the whole chain:
carlife_proto.py (AOA + CarLife protocol + staged USB reconnect), imira-comp
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
install -m 0644 carui/carui-apps.conf           %{buildroot}/opt/carlife/carui-apps.conf
install -m 0755 scripts/start_convergence.sh    %{buildroot}/opt/carlife/start_convergence.sh
install -d %{buildroot}%{_sysconfdir}/systemd/system
install -m 0644 rpm/carlife.service             %{buildroot}%{_sysconfdir}/systemd/system/carlife.service

%post
# Guarded: during image builds there is no running systemd.
systemctl daemon-reload >/dev/null 2>&1 || :
systemctl enable carlife.service >/dev/null 2>&1 || :
# restart (not just start) so upgrades swap in the new binaries at once
systemctl try-restart carlife.service >/dev/null 2>&1 || :

%preun
# $1 = 0 on erase, >= 1 on upgrade — only stop the service when going away.
if [ "$1" = "0" ]; then
    systemctl stop carlife.service >/dev/null 2>&1 || :
    systemctl disable carlife.service >/dev/null 2>&1 || :
fi

%postun
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
%config(noreplace) /opt/carlife/carui-apps.conf
/opt/carlife/start_convergence.sh
%{_sysconfdir}/systemd/system/carlife.service

%changelog
* Thu Sep 04 2026 harbour-sailife 0.1.0-1
- Initial RPM: CarLife proto daemon with staged USB reconnect, virtual
  compositor, launcher UI, x264 capture, boot-autostart systemd service.
