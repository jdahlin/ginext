# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import types
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

from ginext.namespace import Namespace


@pytest.fixture(scope="module")
def ginext_module() -> types.ModuleType:
    import ginext

    return ginext


@pytest.fixture(scope="module")
def namespace_loader(ginext_module: types.ModuleType) -> Callable[[str], Namespace]:
    def load(name: str) -> Namespace:
        try:
            namespace: Namespace = getattr(ginext_module, name)
            return namespace
        except AttributeError:
            pytest.skip(f"{name} namespace not available")

    return load


@pytest.mark.parametrize(
    ("namespace_name", "members"),
    [
        ("GstApp", ["AppSrc", "AppSink"]),
        ("GstPbutils", ["Discoverer", "EncodingAudioProfile"]),
        ("GstController", ["InterpolationControlSource", "TimedValueControlSource"]),
        ("GstNet", ["NetClientClock", "NetTimeProvider"]),
        ("GstRtp", ["RTPBuffer", "RTCPBuffer"]),
        ("GstSdp", ["SDPMessage"]),
        ("GstRtsp", ["RTSPUrl", "RTSPMessage"]),
        ("GstTag", ["tag_check_language_code", "tag_list_new_from_id3v1"]),
        ("GstPlay", ["Play", "PlaySignalAdapter"]),
        ("GstPlayer", ["Player", "PlayerGMainContextSignalDispatcher"]),
        ("GstWebRTC", ["WebRTCSessionDescription", "WebRTCSDPType"]),
        ("GstAllocators", ["FdAllocator", "fd_memory_get_fd"]),
    ],
)
def test_namespace_loads_and_exposes_documented_members(
    namespace_loader: Callable[[str], Namespace],
    namespace_name: str,
    members: list[str],
) -> None:
    namespace = namespace_loader(namespace_name)

    assert namespace.gimeta is not None
    for member in members:
        assert hasattr(namespace, member), f"{namespace_name}.{member} missing"


def test_gst_pbutils_core_paths(
    namespace_loader: Callable[[str], Namespace], Gst: types.ModuleType
) -> None:
    GstPbutils = namespace_loader("GstPbutils")

    caps = Gst.Caps.from_string(
        "audio/mpeg,mpegversion=(int)4,stream-format=(string)raw,"
        "base-profile=(string)lc"
    )
    discoverer = GstPbutils.Discoverer.new(5 * Gst.SECOND)
    profile = GstPbutils.EncodingAudioProfile.new(caps, None, None, 0)

    assert discoverer is not None
    assert profile.get_format().to_string() == (
        "audio/mpeg, mpegversion=(int)4, stream-format=(string)raw, "
        "base-profile=(string)lc"
    )
    assert profile.get_presence() == 0
    assert GstPbutils.codec_utils_caps_get_mime_codec(caps) == "mp4a.40"
    assert GstPbutils.codec_utils_aac_get_sample_rate_from_index(4) == 44100
    assert GstPbutils.codec_utils_aac_get_index_from_sample_rate(44100) == 4
    assert "video/x-h264" in str(
        GstPbutils.codec_utils_caps_from_mime_codec("avc1.64001f")
    )


def test_gst_controller_core_paths(namespace_loader: Callable[[str], Namespace]) -> None:
    GstController = namespace_loader("GstController")

    source = GstController.InterpolationControlSource()

    assert source.get_all() == []
    assert source.set(0, 0.0) is True
    assert source.set(1_000_000_000, 1.0) is True
    control_points = source.get_all()
    assert len(control_points) == 2
    assert source.unset_all() is None
    assert source.get_all() == []
    assert GstController.InterpolationMode.LINEAR >= 0
    assert GstController.LFOWaveform.SINE >= 0


def test_gst_net_core_paths(namespace_loader: Callable[[str], Namespace], Gst: types.ModuleType) -> None:
    GstNet = namespace_loader("GstNet")

    clock = Gst.SystemClock.obtain()
    provider = GstNet.NetTimeProvider.new(clock, "127.0.0.1", 0)
    port = provider.get_property("port")
    client = GstNet.NetClientClock.new("test", "127.0.0.1", port, 0)

    assert type(provider).__name__ == "NetTimeProvider"
    assert isinstance(port, int)
    assert port > 0
    assert client.get_property("port") == port
    assert client.get_name() == "test"
    assert GstNet.PTP_CLOCK_ID_NONE == (2**64) - 1
    assert callable(GstNet.buffer_add_net_address_meta)
    assert callable(GstNet.buffer_get_net_address_meta)


def test_gst_rtp_core_paths(namespace_loader: Callable[[str], Namespace]) -> None:
    GstRtp = namespace_loader("GstRtp")

    rtp = GstRtp.rtp_buffer_new_allocate(12, 0, 0)
    rtcp = GstRtp.rtcp_buffer_new(1500)

    assert rtp.get_size() == 24
    assert rtcp.get_size() == 0
    assert GstRtp.RTP_VERSION == 2
    assert GstRtp.RTCP_MAX_RB_COUNT > 0
    assert GstRtp.RTCPType.SR >= 0
    assert GstRtp.RTPProfile.AVP >= 0


def test_gst_sdp_core_paths(namespace_loader: Callable[[str], Namespace]) -> None:
    GstSdp = namespace_loader("GstSdp")

    msg = GstSdp.SDPMessage.new().msg

    assert msg.set_version("0") == GstSdp.SDPResult.OK
    assert msg.set_session_name("test") == GstSdp.SDPResult.OK
    assert msg.set_uri("https://example.com") == GstSdp.SDPResult.OK
    text = msg.as_text()
    parsed = GstSdp.SDPMessage.new_from_text(text).msg
    assert parsed.get_version() == "0"
    assert parsed.get_session_name() == "test"
    assert parsed.get_uri() == "https://example.com"


def test_gst_rtsp_core_paths(namespace_loader: Callable[[str], Namespace], Gst: types.ModuleType) -> None:
    GstRtsp = namespace_loader("GstRtsp")

    url = GstRtsp.RTSPUrl.parse("rtsp://example.com/test").url
    parse_result, transport = GstRtsp.rtsp_transport_parse(
        "RTP/AVP;unicast;client_port=5000-5001"
    )
    message_result, message = GstRtsp.rtsp_message_new_request(
        GstRtsp.RTSPMethod.DESCRIBE, "rtsp://example.com/test"
    )

    assert url.get_request_uri() == "rtsp://example.com/test"
    assert url.get_port().port == 554
    assert url.copy().get_request_uri_with_control("trackID=1") is not None
    assert parse_result == GstRtsp.RTSPResult.OK
    assert transport is not None
    assert message_result == GstRtsp.RTSPResult.OK
    parsed = message.parse_request()
    assert parsed.method == GstRtsp.RTSPMethod.DESCRIBE
    assert parsed.uri == "rtsp://example.com/test"


def test_gst_tag_core_paths(namespace_loader: Callable[[str], Namespace]) -> None:
    GstTag = namespace_loader("GstTag")

    parsed = GstTag.tag_parse_extended_comment("key[en]=value", True)
    id3v1 = bytearray(128)
    id3v1[:3] = b"TAG"
    id3v1[3:8] = b"Title"
    tag_list = GstTag.tag_list_new_from_id3v1(bytes(id3v1))

    assert GstTag.tag_check_language_code("en") is True
    assert GstTag.tag_get_language_name("en") == "English"
    assert GstTag.tag_get_language_code_iso_639_2T("en") == "eng"
    assert parsed.key == "key"
    assert parsed.lang == "en"
    assert parsed.value == "value"
    assert GstTag.tag_id3_genre_count() > 0
    assert isinstance(GstTag.tag_id3_genre_get(0), str)
    assert type(tag_list).__name__ == "TagList"
    assert tag_list.n_tags() > 0


def test_gst_play_core_paths(namespace_loader: Callable[[str], Namespace]) -> None:
    GstPlay = namespace_loader("GstPlay")

    play = GstPlay.Play.new(None)
    adapter = GstPlay.PlaySignalAdapter.new_sync_emit(play)
    config = play.get_config()

    assert play.get_uri() is None
    play.set_uri("file:///tmp/example.ogg")
    assert play.get_uri() == "file:///tmp/example.ogg"
    assert adapter.get_play() is play
    assert play.config_set_position_update_interval(config, 250) is None
    assert play.config_get_position_update_interval(config) == 250
    assert play.config_set_seek_accurate(config, True) is None
    assert play.config_get_seek_accurate(config) is True
    assert play.set_config(config) is True
    assert GstPlay.PlayState.STOPPED >= 0
    assert GstPlay.PlayMessage.ERROR >= 0


def test_gst_player_core_paths(namespace_loader: Callable[[str], Namespace]) -> None:
    GstPlayer = namespace_loader("GstPlayer")

    player = GstPlayer.Player.new(None, None)
    config = player.get_config()

    assert player.get_uri() is None
    player.set_uri("file:///tmp/example.ogg")
    assert player.get_uri() == "file:///tmp/example.ogg"
    assert player.config_set_position_update_interval(config, 250) is None
    assert player.config_get_position_update_interval(config) == 250
    assert player.config_set_seek_accurate(config, True) is None
    assert player.config_get_seek_accurate(config) is True
    assert player.set_config(config) is True
    assert hasattr(GstPlayer.PlayerGMainContextSignalDispatcher, "newv")
    assert GstPlayer.PlayerState.STOPPED >= 0
    assert GstPlayer.PlayerColorBalanceType.HUE >= 0


def test_gst_webrtc_core_paths(namespace_loader: Callable[[str], Namespace]) -> None:
    GstWebRTC = namespace_loader("GstWebRTC")
    GstSdp = namespace_loader("GstSdp")

    msg = GstSdp.SDPMessage.new_from_text("v=0\r\ns=-\r\nt=0 0\r\n").msg
    desc = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.OFFER, msg)
    copy = desc.copy()

    assert desc.type == GstWebRTC.WebRTCSDPType.OFFER
    assert copy.type == GstWebRTC.WebRTCSDPType.OFFER
    assert copy.sdp.get_session_name() == "-"
    assert GstWebRTC.WebRTCSDPType.ANSWER >= 0
    assert GstWebRTC.WebRTCICEConnectionState.NEW >= 0
    assert GstWebRTC.WebRTCDTLSRole.UNKNOWN >= 0
    assert GstWebRTC.WebRTCBundlePolicy.NONE >= 0
    with pytest.raises(TypeError):
        GstWebRTC.WebRTCDataChannel()


def test_gst_allocators_core_paths(namespace_loader: Callable[[str], Namespace]) -> None:
    GstAllocators = namespace_loader("GstAllocators")

    allocator = GstAllocators.FdAllocator()

    assert type(allocator).__name__ == "FdAllocator"
    assert GstAllocators.ALLOCATOR_FD == "fd"
    assert GstAllocators.CAPS_FEATURE_MEMORY_DMABUF == "memory:DMABuf"
    assert GstAllocators.FdMemoryFlags.KEEP_MAPPED >= 0
    assert callable(GstAllocators.fd_memory_get_fd)
    assert callable(GstAllocators.is_dmabuf_memory)
