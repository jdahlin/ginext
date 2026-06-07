FROM debian:testing

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/root/.local/bin:${PATH}"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
      curl \
      dbus-daemon \
      git \
      gobject-introspection \
      gir1.2-gee-0.8 \
      gir1.2-girepository-3.0 \
      gir1.2-gtk-3.0 \
      gir1.2-adw-1 \
      gir1.2-gtk-4.0 \
      libadwaita-1-dev \
      libatk1.0-dev \
      libcairo2-dev \
      libffi-dev \
      libgdk-pixbuf-2.0-dev \
      libgee-0.8-2 \
      libgirepository-2.0-dev \
      libglib2.0-bin \
      libglib2.0-dev \
      libgtk-3-dev \
      libgtk-4-dev \
      libgstreamer1.0-dev \
      libgstreamer-plugins-base1.0-dev \
      gstreamer1.0-plugins-base \
      gir1.2-gstreamer-1.0 \
      gir1.2-gst-plugins-base-1.0 \
      gir1.2-soup-3.0 \
      libsoup-3.0-0 \
      gir1.2-vte-3.91 \
      libvte-2.91-gtk4-dev \
      gir1.2-webkit-6.0 \
      libwebkitgtk-6.0-dev \
      gir1.2-gtksource-5 \
      libgtksourceview-5-dev \
      meson \
      ninja-build \
      pkg-config \
      python3 \
      weston \
      xvfb && \
    rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
