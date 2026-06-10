from __future__ import annotations

from gi.repository import GLib as _GLib

__all__: list[str] = []

_SeekType = _GLib.SeekType
_IOStatus = _GLib.IOStatus
_IOChannel = _GLib.IOChannel
_raw_read_to_end = _IOChannel.read_to_end


def _buf_to_bytes(buf) -> bytes:
    if buf is None:
        return b""
    if isinstance(buf, (bytes, bytearray)):
        return bytes(buf)
    try:
        return bytes(buf)
    except TypeError:
        return b""


def _iochannel_read(self, max_count: int = -1) -> bytes:
    result = _raw_read_to_end(self)
    buf = _buf_to_bytes(result[1] if len(result) > 1 else result[0])
    if max_count != -1:
        buf = buf[:max_count]
    return buf


def _iochannel_read_chars(self, max_count: int = -1) -> bytes:
    return _iochannel_read(self, max_count)


def _iochannel_readline(self, size_hint: int = -1) -> str:
    (_status, buf, _length, _terminator_pos) = self.read_line()
    if buf is None:
        return ""
    return buf


def _iochannel_readlines(self, size_hint: int = -1) -> list[str]:
    lines = []
    status = _IOStatus.NORMAL
    while status == _IOStatus.NORMAL:
        (status, buf, _length, _terminator_pos) = self.read_line()
        if buf is None:
            buf = ""
        lines.append(buf)
    return lines


def _iochannel_write(self, buf: str | bytes, buflen: int = -1) -> int:
    if not isinstance(buf, bytes):
        buf = buf.encode("UTF-8")
    if buflen == -1:
        buflen = len(buf)
    (_status, written) = self.write_chars(buf, buflen)
    return written


def _iochannel_writelines(self, lines) -> None:
    for line in lines:
        _iochannel_write(self, line)


_whence_map = {0: _SeekType.SET, 1: _SeekType.CUR, 2: _SeekType.END}


def _iochannel_seek(self, offset: int, whence: int = 0) -> _IOStatus:
    try:
        w = _whence_map[whence]
    except KeyError:
        raise ValueError("invalid 'whence' value")
    return self.seek_position(offset, w)


def _iochannel_iter(self):
    return self


def _iochannel_next(self) -> str:
    (status, buf, _length, _terminator_pos) = self.read_line()
    if status == _IOStatus.NORMAL:
        return buf
    raise StopIteration


def _remove_from_method_infos(cls: type, name: str) -> None:
    try:
        from ginext.gobject.resolve import own_gimeta
        for owner in cls.__mro__:
            gimeta = own_gimeta(owner)
            if gimeta is None:
                continue
            method_infos = getattr(gimeta, "method_infos", {})
            if name in method_infos:
                del method_infos[name]
    except Exception:
        pass


_iochannel_methods = {
    "read": _iochannel_read,
    "read_chars": _iochannel_read_chars,
    "readline": _iochannel_readline,
    "readlines": _iochannel_readlines,
    "write": _iochannel_write,
    "writelines": _iochannel_writelines,
    "seek": _iochannel_seek,
    "__iter__": _iochannel_iter,
    "__next__": _iochannel_next,
}

for _name, _method in _iochannel_methods.items():
    setattr(_IOChannel, _name, _method)
    _remove_from_method_infos(_IOChannel, _name)

# Deprecated IOCondition aliases not yet registered by ginext
# (IO_FLAG_* and IO_STATUS_* are handled by ginext's overlay.deprecated mechanism)
_IO_COND_ALIASES = {
    "IO_IN": "IN",
    "IO_OUT": "OUT",
    "IO_PRI": "PRI",
    "IO_ERR": "ERR",
    "IO_HUP": "HUP",
    "IO_NVAL": "NVAL",
}

_IOCondition = _GLib.IOCondition
for _alias, _member in _IO_COND_ALIASES.items():
    try:
        _val = getattr(_IOCondition, _member)
        setattr(_GLib, _alias, _val)
    except AttributeError:
        pass

# IO_FLAG_IS_READABLE and IO_FLAG_IS_SEEKABLE are not in ginext's deprecations
_IOFlags = _GLib.IOFlags
for _alias, _member in (("IO_FLAG_IS_READABLE", "IS_READABLE"), ("IO_FLAG_IS_SEEKABLE", "IS_SEEKABLE")):
    try:
        setattr(_GLib, _alias, getattr(_IOFlags, _member))
    except AttributeError:
        pass

# IO_STATUS_NORMAL/EOF/AGAIN not in ginext's deprecations
_IOStatus2 = _GLib.IOStatus
for _alias, _member in (("IO_STATUS_NORMAL", "NORMAL"), ("IO_STATUS_EOF", "EOF"), ("IO_STATUS_AGAIN", "AGAIN")):
    try:
        setattr(_GLib, _alias, getattr(_IOStatus2, _member))
    except AttributeError:
        pass
