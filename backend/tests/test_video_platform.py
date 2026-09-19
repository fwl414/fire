"""视频平台接入测试

覆盖：
- 凭证对称加密（往返、篡改检测、密钥变更）
- 海康 ISAPI / 大华 CGI / 通用 HTTP 三类适配器的真实请求形状（用 MockTransport 断言方法与 URL）
- 台账 CRUD、字段校验、租户隔离、密码不回传
- 抓拍令牌与受控抓拍下发
- 模拟设备全链路（探测 → 抓拍）
"""
import asyncio
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
from fastapi.testclient import TestClient

import main
from database import (
    Role,
    SessionLocal,
    Tenant,
    User,
    VideoChannel,
    get_default_tenant_id,
    hash_password,
    init_db,
)
from services import video_credential_cipher as cipher
from services import video_service
from services.video_platform import get_adapter
from services.video_platform.base import VideoChannelConfig, VideoPlatformError

TEST_USERNAME = "video-tester"
TEST_PASSWORD = "Test#12345"
TEST_ROLE_CODE = "video-tester-role"
OTHER_TENANT_CODE = "video-other-tenant"
CIPHER_KEY = "unit-test-video-credential-key-0123456789"

HIK_DEVICE_INFO = b"""<?xml version="1.0" encoding="UTF-8"?>
<DeviceInfo xmlns="http://www.hikvision.com/ver20/XMLSchema" version="2.0">
<deviceName>\xe6\xa5\xbc\xe5\xb1\x82\xe6\x91\x84\xe5\x83\x8f\xe5\xa4\xb4</deviceName>
<model>DS-2CD3T46</model>
<firmwareVersion>V5.7.3</firmwareVersion>
<deviceType>IPCamera</deviceType>
</DeviceInfo>"""

HIK_CHANNELS = b"""<?xml version="1.0" encoding="UTF-8"?>
<StreamingChannelList>
<StreamingChannel><id>101</id><channelName>Camera 01</channelName><enabled>true</enabled></StreamingChannel>
<StreamingChannel><id>102</id><channelName>Camera 02</channelName><enabled>false</enabled></StreamingChannel>
</StreamingChannelList>"""

# 海康 ISAPI 录像检索的真实响应形状（ContentMgmt/search）
HIK_RECORD_SEARCH = b"""<?xml version="1.0" encoding="UTF-8"?>
<CMSearchResult xmlns="http://www.hikvision.com/ver20/XMLSchema">
<searchID>abc</searchID>
<responseStatusStrg>OK</responseStatusStrg>
<numOfMatches>2</numOfMatches>
<matchList>
<searchMatchItem>
<trackID>101</trackID>
<timeSpan><startTime>2026-01-15T10:00:00Z</startTime><endTime>2026-01-15T10:30:00Z</endTime></timeSpan>
<mediaSegmentDescriptor>
<contentType>video</contentType>
<playbackURI>rtsp://10.20.0.8:554/Streaming/tracks/101?starttime=20260115t100000z</playbackURI>
</mediaSegmentDescriptor>
</searchMatchItem>
<searchMatchItem>
<trackID>101</trackID>
<timeSpan><startTime>2026-01-15T14:00:00Z</startTime><endTime>2026-01-15T14:20:00Z</endTime></timeSpan>
<mediaSegmentDescriptor>
<contentType>video</contentType>
<playbackURI>rtsp://10.20.0.8:554/Streaming/tracks/101?starttime=20260115t140000z</playbackURI>
</mediaSegmentDescriptor>
</searchMatchItem>
</matchList>
</CMSearchResult>"""

HIK_NO_MATCH = b"""<?xml version="1.0" encoding="UTF-8"?>
<CMSearchResult>
<searchID>abc</searchID>
<responseStatusStrg>NO MATCH</responseStatusStrg>
<numOfMatches>0</numOfMatches>
</CMSearchResult>"""


def _jpeg() -> bytes:
    from services.video_platform.mock_adapter import _render_frame

    return _render_frame("测试通道", "CAM-TEST")


def _run(handler, factory):
    """在带 MockTransport 的客户端里执行协程，确保客户端被正确关闭。"""

    async def _main():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await factory(client)

    return asyncio.run(_main())


class LocalCameraServer:
    """本地 HTTP 服务，模拟一台只提供抓拍接口的摄像头（用于验证真实网络链路）。"""

    def __init__(self, image: bytes):
        server_self = self
        self.hits = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler 约定
                server_self.hits.append(self.path)
                if self.path.split("?")[0] == "/snap.jpg":
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(image)))
                    self.end_headers()
                    self.wfile.write(image)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class TestVideoCredentialCipher(unittest.TestCase):

    def test_roundtrip_hides_plaintext(self):
        stored = cipher.encrypt_secret("P@ssw0rd-摄像头")
        self.assertNotIn("P@ssw0rd", stored)
        self.assertTrue(cipher.is_encrypted(stored))
        self.assertEqual(cipher.decrypt_secret(stored), "P@ssw0rd-摄像头")

    def test_same_plaintext_produces_different_ciphertext(self):
        self.assertNotEqual(cipher.encrypt_secret("same"), cipher.encrypt_secret("same"))

    def test_empty_value_stays_empty(self):
        self.assertEqual(cipher.encrypt_secret(""), "")
        self.assertEqual(cipher.decrypt_secret(""), "")

    def test_tampered_ciphertext_is_rejected(self):
        stored = cipher.encrypt_secret("secret-value")
        version, nonce, payload, tag = stored.split(":")
        flipped = "A" if payload[0] != "A" else "B"
        tampered = f"{version}:{nonce}:{flipped}{payload[1:]}:{tag}"
        with self.assertRaises(cipher.CredentialCipherError):
            cipher.decrypt_secret(tampered)

    def test_changed_key_cannot_decrypt(self):
        stored = cipher.encrypt_secret("secret-value")
        with mock.patch.dict(os.environ, {"VIDEO_CREDENTIAL_KEY": "another-key-entirely"}):
            with self.assertRaises(cipher.CredentialCipherError):
                cipher.decrypt_secret(stored)

    def test_malformed_value_is_rejected(self):
        with self.assertRaises(cipher.CredentialCipherError):
            cipher.decrypt_secret("not-a-cipher-text")

    def test_key_source_is_reported(self):
        with mock.patch.dict(os.environ, {"VIDEO_CREDENTIAL_KEY": CIPHER_KEY}):
            self.assertEqual(cipher.get_key_source(), "VIDEO_CREDENTIAL_KEY")


class TestHikvisionAdapter(unittest.TestCase):

    def _config(self, **kwargs):
        base = dict(
            id=1, channel_code="HIK-1", channel_name="大厅", platform="hikvision",
            protocol="http", host="10.20.0.8", port=80, channel_no="1",
            username="admin", password="Admin@123",
        )
        base.update(kwargs)
        return VideoChannelConfig(**base)

    def test_probe_reads_device_info_and_channels(self):
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append((request.method, request.url.path))
            if request.url.path == "/ISAPI/System/deviceInfo":
                return httpx.Response(200, content=HIK_DEVICE_INFO)
            if request.url.path == "/ISAPI/Streaming/channels":
                return httpx.Response(200, content=HIK_CHANNELS)
            return httpx.Response(404)

        adapter = get_adapter(self._config())
        result = _run(handler, lambda client: get_adapter(self._config(), client=client).probe())

        self.assertTrue(result.online, result.message)
        self.assertEqual(result.device_model, "DS-2CD3T46")
        self.assertEqual(result.firmware, "V5.7.3")
        self.assertEqual(len(result.channels), 2)
        self.assertEqual(result.channels[0]["id"], "101")
        self.assertFalse(result.channels[1]["enabled"])
        self.assertIn("/ISAPI/Streaming/channels", [path for _, path in seen])
        self.assertTrue(adapter.picture_path().endswith("/101/picture"))

    def test_probe_reports_offline_on_auth_failure(self):
        handler = lambda request: httpx.Response(401)  # noqa: E731
        result = _run(handler, lambda client: get_adapter(self._config(), client=client).probe())
        self.assertFalse(result.online)
        self.assertIn("账号密码", result.message)

    def test_snapshot_requests_picture_endpoint(self):
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.url.path)
            return httpx.Response(200, content=_jpeg())

        data = _run(handler, lambda client: get_adapter(self._config(), client=client).snapshot())
        self.assertTrue(data.startswith(b"\xff\xd8\xff"))
        self.assertEqual(seen, ["/ISAPI/Streaming/channels/101/picture"])

    def test_snapshot_rejects_non_image_body(self):
        handler = lambda request: httpx.Response(200, text="<ResponseStatus>error</ResponseStatus>")  # noqa: E731
        with self.assertRaises(VideoPlatformError) as ctx:
            _run(handler, lambda client: get_adapter(self._config(), client=client).snapshot())
        self.assertIn("不是图片", str(ctx.exception))

    def test_ptz_sends_put_with_direction_payload(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["path"] = request.url.path
            captured["body"] = request.content.decode("utf-8")
            return httpx.Response(200, content=b"<ResponseStatus><statusCode>1</statusCode></ResponseStatus>")

        result = _run(
            handler,
            lambda client: get_adapter(self._config(ptz_enabled=True), client=client).ptz("up", 5),
        )
        self.assertEqual(captured["method"], "PUT")
        self.assertEqual(captured["path"], "/ISAPI/PTZCtrl/channels/1/continuous")
        self.assertIn("<tilt>50</tilt>", captured["body"])
        self.assertEqual(result["speed"], 50)

    def test_ptz_reports_device_error_status(self):
        handler = lambda request: httpx.Response(  # noqa: E731
            200,
            content=b"<ResponseStatus><statusCode>4</statusCode><statusString>Invalid Operation</statusString></ResponseStatus>",
        )
        with self.assertRaises(VideoPlatformError) as ctx:
            _run(handler, lambda client: get_adapter(self._config(), client=client).ptz("up"))
        self.assertIn("Invalid Operation", str(ctx.exception))


class TestRecordingSearch(unittest.TestCase):
    """录像检索：能力差异必须如实反映，不能编造片段。

    改造前录像回放页签整块是写死的 2024-01 演示数据（7 段时间轴 + 8 条录像清单），
    点「检索」只弹一句「当前版本未接入」。现在按平台真实能力检索：
    海康走 ISAPI，其余平台明确返回 supported=False。
    """

    def _config(self, **kwargs):
        base = dict(
            id=1, channel_code="HIK-1", channel_name="大厅", platform="hikvision",
            protocol="http", host="10.20.0.8", port=80, channel_no="1",
            username="admin", password="Admin@123",
        )
        base.update(kwargs)
        return VideoChannelConfig(**base)

    def test_platforms_without_recording_support_say_so(self):
        for platform in ("generic", "dahua", "mock"):
            result = asyncio.run(
                get_adapter(self._config(platform=platform)).query_recordings(
                    "2026-01-15 00:00:00", "2026-01-15 23:59:59"
                )
            )
            self.assertFalse(result["supported"], platform)
            self.assertEqual(result["items"], [], platform)
            self.assertIn("未实现录像检索", result["message"], platform)

    def test_hikvision_search_posts_cms_search_and_parses_matches(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["path"] = request.url.path
            captured["body"] = request.content.decode("utf-8")
            return httpx.Response(200, content=HIK_RECORD_SEARCH)

        result = _run(
            handler,
            lambda client: get_adapter(self._config(), client=client).query_recordings(
                "2026-01-15 00:00:00", "2026-01-15 23:59:59"
            ),
        )

        self.assertTrue(result["supported"])
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["path"], "/ISAPI/ContentMgmt/search")
        self.assertIn("<trackID>101</trackID>", captured["body"])
        # ISAPI 的时间按 UTC 规范格式下发
        self.assertIn("<startTime>2026-01-15T00:00:00Z</startTime>", captured["body"])
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0]["start_time"], "2026-01-15T10:00:00Z")
        self.assertEqual(result["items"][0]["end_time"], "2026-01-15T10:30:00Z")
        self.assertIn("tracks/101", result["items"][0]["playback_uri"])

    def test_hikvision_no_match_is_empty_and_explained(self):
        handler = lambda request: httpx.Response(200, content=HIK_NO_MATCH)  # noqa: E731
        result = _run(
            handler,
            lambda client: get_adapter(self._config(), client=client).query_recordings(
                "2026-01-15 00:00:00", "2026-01-15 23:59:59"
            ),
        )
        self.assertTrue(result["supported"])
        self.assertEqual(result["items"], [])
        self.assertIn("没有录像", result["message"])

    def test_unparsable_time_is_rejected(self):
        with self.assertRaises(VideoPlatformError) as ctx:
            asyncio.run(
                get_adapter(self._config()).query_recordings("昨天", "今天")
            )
        self.assertIn("时间格式", str(ctx.exception))


class TestDahuaAdapter(unittest.TestCase):

    def _config(self, **kwargs):
        base = dict(
            id=2, channel_code="DH-1", channel_name="车库", platform="dahua",
            protocol="http", host="10.20.0.9", port=80, channel_no="2",
            username="admin", password="Admin@123",
        )
        base.update(kwargs)
        return VideoChannelConfig(**base)

    def test_probe_parses_cgi_key_values(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.params.get("action") == "getDeviceType":
                return httpx.Response(200, text="type=IPC-HFW2439M\n")
            if request.url.params.get("action") == "getSoftwareVersion":
                return httpx.Response(200, text="version=2.820.15OG\n")
            return httpx.Response(404)

        result = _run(handler, lambda client: get_adapter(self._config(), client=client).probe())
        self.assertTrue(result.online, result.message)
        self.assertEqual(result.device_model, "IPC-HFW2439M")
        self.assertEqual(result.firmware, "2.820.15OG")

    def test_probe_reports_cgi_error_text(self):
        handler = lambda request: httpx.Response(200, text="Error\nBad Request!\n")  # noqa: E731
        result = _run(handler, lambda client: get_adapter(self._config(), client=client).probe())
        self.assertFalse(result.online)
        self.assertIn("设备返回错误", result.message)

    def test_snapshot_uses_channel_number(self):
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append((request.url.path, dict(request.url.params)))
            return httpx.Response(200, content=_jpeg())

        data = _run(handler, lambda client: get_adapter(self._config(), client=client).snapshot())
        self.assertTrue(data)
        self.assertEqual(seen[0][0], "/cgi-bin/snapshot.cgi")
        self.assertEqual(seen[0][1]["channel"], "2")

    def test_ptz_maps_action_to_dahua_code(self):
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(dict(request.url.params))
            return httpx.Response(200, text="OK")

        _run(handler, lambda client: get_adapter(self._config(), client=client).ptz("right", 4))
        self.assertEqual(seen[0]["code"], "Right")
        self.assertEqual(seen[0]["action"], "start")
        self.assertEqual(seen[0]["arg2"], "4")

    def test_ptz_stop_sends_stop_for_every_direction(self):
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(dict(request.url.params))
            return httpx.Response(200, text="OK")

        _run(handler, lambda client: get_adapter(self._config(), client=client).ptz("stop"))
        self.assertTrue(seen)
        self.assertTrue(all(item["action"] == "stop" for item in seen))
        # Up/Down/Left/Right/ZoomTele/ZoomWide
        self.assertEqual(len({item["code"] for item in seen}), 6)

    def test_unknown_ptz_action_is_rejected(self):
        handler = lambda request: httpx.Response(200, text="OK")  # noqa: E731
        with self.assertRaises(VideoPlatformError):
            _run(handler, lambda client: get_adapter(self._config(), client=client).ptz("fly"))


class TestGenericAdapter(unittest.TestCase):

    def _config(self, **kwargs):
        base = dict(
            id=3, channel_code="GEN-1", channel_name="通道", platform="generic",
            protocol="http", host="camera.local", port=8080, snapshot_path="/snap.jpg",
        )
        base.update(kwargs)
        return VideoChannelConfig(**base)

    def test_snapshot_url_is_built_from_host_and_path(self):
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            return httpx.Response(200, content=_jpeg())

        _run(handler, lambda client: get_adapter(self._config(), client=client).snapshot())
        self.assertEqual(seen[0], "http://camera.local:8080/snap.jpg")

    def test_missing_snapshot_path_is_config_error(self):
        handler = lambda request: httpx.Response(200, content=_jpeg())  # noqa: E731
        with self.assertRaises(VideoPlatformError) as ctx:
            _run(handler, lambda client: get_adapter(self._config(snapshot_path=""), client=client).snapshot())
        self.assertEqual(ctx.exception.status_code, 400)

    def test_probe_reports_offline_when_device_errors(self):
        handler = lambda request: httpx.Response(404)  # noqa: E731
        result = _run(handler, lambda client: get_adapter(self._config(), client=client).probe())
        self.assertFalse(result.online)
        self.assertIn("404", result.message)

    def test_connection_failure_is_reported_with_host(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        result = _run(handler, lambda client: get_adapter(self._config(), client=client).probe())
        self.assertFalse(result.online)
        self.assertIn("camera.local", result.message)


class TestMockAdapter(unittest.TestCase):

    def test_probe_and_snapshot_without_network(self):
        config = VideoChannelConfig(channel_code="MOCK-1", channel_name="模拟通道", platform="mock")
        adapter = get_adapter(config)

        async def _main():
            return await adapter.probe(), await adapter.snapshot()

        probe, data = asyncio.run(_main())
        self.assertTrue(probe.online)
        self.assertEqual(probe.device_model, "MOCK-IPC-2000")
        self.assertTrue(data.startswith(b"\xff\xd8\xff"))


class TestVideoApi(unittest.TestCase):

    client = None
    headers = {}
    tenant_id = None
    other_tenant_id = None
    role_id = None
    user_id = None
    other_tenant_created = False
    channel_ids = []

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_id = get_default_tenant_id(db)

            other = db.query(Tenant).filter(Tenant.tenant_code == OTHER_TENANT_CODE).first()
            if not other:
                other = Tenant(tenant_code=OTHER_TENANT_CODE, tenant_name="视频隔离租户", status="active")
                db.add(other)
                db.commit()
                db.refresh(other)
                cls.other_tenant_created = True
            cls.other_tenant_id = other.id

            role = db.query(Role).filter(Role.role_code == TEST_ROLE_CODE).first()
            if not role:
                role = Role(
                    tenant_id=cls.tenant_id,
                    role_code=TEST_ROLE_CODE,
                    role_name="视频接入测试角色",
                    permissions='["*"]',
                )
                db.add(role)
                db.commit()
                db.refresh(role)
            cls.role_id = role.id

            user = db.query(User).filter(User.username == TEST_USERNAME).first()
            if not user:
                hashed, salt = hash_password(TEST_PASSWORD)
                user = User(
                    username=TEST_USERNAME,
                    password_hash=hashed,
                    password_salt=salt,
                    real_name="视频接入测试员",
                    role_id=role.id,
                    status="active",
                    tenant_id=cls.tenant_id,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            cls.user_id = user.id
        finally:
            db.close()

        cls.client = TestClient(main.app)
        resp = cls.client.post(
            "/api/auth/login",
            data={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        assert resp.status_code == 200, f"登录失败: {resp.text}"
        cls.headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            db.query(VideoChannel).filter(VideoChannel.tenant_id == cls.tenant_id).delete(
                synchronize_session=False
            )
            if cls.user_id:
                db.query(User).filter(User.id == cls.user_id).delete(synchronize_session=False)
            if cls.role_id:
                db.query(Role).filter(Role.id == cls.role_id).delete(synchronize_session=False)
            if cls.other_tenant_created:
                db.query(Tenant).filter(Tenant.tenant_code == OTHER_TENANT_CODE).delete(
                    synchronize_session=False
                )
            db.commit()
        finally:
            db.close()

    def _create(self, **overrides):
        payload = {
            "channel_code": "MOCK-CAM-01",
            "channel_name": "大厅入口",
            "location": "一号楼大厅",
            "platform": "mock",
            "host": "127.0.0.1",
            "port": 80,
            "username": "admin",
            "password": "Camera@123",
        }
        payload.update(overrides)
        resp = self.client.post("/api/video/channels", json=payload, headers=self.headers)
        return resp

    def test_api_requires_authentication(self):
        self.assertEqual(self.client.get("/api/video/channels").status_code, 401)
        self.assertEqual(self.client.post("/api/video/channels", json={}).status_code, 401)

    def test_platforms_are_listed(self):
        resp = self.client.get("/api/video/platforms", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        items = resp.json()["platforms"]
        platforms = {item["platform"] for item in items}
        self.assertTrue({"generic", "hikvision", "dahua", "mock"}.issubset(platforms))
        self.assertEqual(resp.json()["playback"]["mode"], "snapshot_polling")
        # 录像检索能力按平台如实标注：只有海康已实现
        by_platform = {item["platform"]: item for item in items}
        self.assertTrue(by_platform["hikvision"]["recordings"])
        for platform in ("generic", "dahua", "mock"):
            self.assertFalse(by_platform[platform]["recordings"], platform)

    def test_create_channel_encrypts_password_and_hides_it(self):
        resp = self._create()
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.__class__.channel_ids.append(body["id"])

        self.assertTrue(body["has_password"])
        self.assertNotIn("password", body)
        self.assertNotIn("password_cipher", body)

        db = SessionLocal()
        try:
            row = db.query(VideoChannel).filter(VideoChannel.id == body["id"]).first()
            self.assertTrue(row.password_cipher.startswith("v1:"))
            self.assertNotIn("Camera@123", row.password_cipher)
            self.assertEqual(video_service.build_config(row).password, "Camera@123")
        finally:
            db.close()

    def test_duplicate_channel_code_is_rejected(self):
        first = self._create(channel_code="DUP-CAM")
        self.assertEqual(first.status_code, 200, first.text)
        self.__class__.channel_ids.append(first.json()["id"])

        second = self._create(channel_code="DUP-CAM", channel_name="重复通道")
        self.assertEqual(second.status_code, 400)
        self.assertIn("已存在", second.json()["message"])

    def test_snapshot_path_with_scheme_is_rejected(self):
        resp = self._create(channel_code="SSRF-CAM", snapshot_path="http://169.254.169.254/latest")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("抓拍路径", resp.json()["message"])

    def test_host_with_scheme_is_rejected(self):
        resp = self._create(channel_code="BAD-HOST", host="http://10.0.0.1")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("设备地址", resp.json()["message"])

    def test_unsupported_platform_is_rejected(self):
        resp = self._create(channel_code="BAD-PLATFORM", platform="hikvision-x")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("不支持的视频平台", resp.json()["message"])

    def test_ptz_on_generic_channel_is_rejected(self):
        created = self._create(channel_code="GEN-CAM", platform="generic", snapshot_path="/snap.jpg")
        self.assertEqual(created.status_code, 200, created.text)
        channel_id = created.json()["id"]
        self.__class__.channel_ids.append(channel_id)

        resp = self.client.put(
            f"/api/video/channels/{channel_id}",
            json={"ptz_enabled": True},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("云台", resp.json()["message"])

    def test_mock_channel_probe_and_snapshot(self):
        created = self._create(channel_code="MOCK-PROBE")
        channel_id = created.json()["id"]
        self.__class__.channel_ids.append(channel_id)

        probe = self.client.post(f"/api/video/channels/{channel_id}/probe", headers=self.headers)
        self.assertEqual(probe.status_code, 200, probe.text)
        self.assertTrue(probe.json()["online"])
        self.assertEqual(probe.json()["device_model"], "MOCK-IPC-2000")

        token_resp = self.client.post(
            f"/api/video/channels/{channel_id}/snapshot-token", headers=self.headers
        )
        self.assertEqual(token_resp.status_code, 200, token_resp.text)
        token = token_resp.json()["token"]

        snapshot = self.client.get(f"/api/video/channels/{channel_id}/snapshot?token={token}")
        self.assertEqual(snapshot.status_code, 200, snapshot.text)
        self.assertEqual(snapshot.headers["content-type"].split(";")[0], "image/jpeg")
        self.assertTrue(snapshot.content.startswith(b"\xff\xd8\xff"))

        detail = self.client.get(f"/api/video/channels/{channel_id}", headers=self.headers).json()
        self.assertEqual(detail["status"], "online")

    def test_snapshot_requires_valid_token(self):
        created = self._create(channel_code="TOKEN-CAM")
        channel_id = created.json()["id"]
        self.__class__.channel_ids.append(channel_id)

        self.assertEqual(
            self.client.get(f"/api/video/channels/{channel_id}/snapshot").status_code, 422
        )
        self.assertEqual(
            self.client.get(f"/api/video/channels/{channel_id}/snapshot?token=bogus").status_code, 401
        )

        token = self.client.post(
            f"/api/video/channels/{channel_id}/snapshot-token", headers=self.headers
        ).json()["token"]
        # 令牌与通道绑定，换一个通道即失效
        other = self._create(channel_code="TOKEN-CAM-2")
        other_id = other.json()["id"]
        self.__class__.channel_ids.append(other_id)
        self.assertEqual(
            self.client.get(f"/api/video/channels/{other_id}/snapshot?token={token}").status_code, 401
        )

    def test_ptz_on_mock_channel(self):
        created = self._create(channel_code="PTZ-CAM", ptz_enabled=True)
        self.assertEqual(created.status_code, 200, created.text)
        channel_id = created.json()["id"]
        self.__class__.channel_ids.append(channel_id)

        resp = self.client.post(
            f"/api/video/channels/{channel_id}/ptz",
            json={"action": "left", "speed": 3},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["action"], "left")

        bad = self.client.post(
            f"/api/video/channels/{channel_id}/ptz", json={"action": "fly"}, headers=self.headers
        )
        self.assertEqual(bad.status_code, 400)

    def test_stream_info_is_masked_and_honest(self):
        created = self._create(
            channel_code="STREAM-CAM",
            rtsp_url="rtsp://admin:secret@10.0.0.5:554/Streaming/Channels/101",
        )
        self.assertEqual(created.status_code, 200, created.text)
        channel_id = created.json()["id"]
        self.__class__.channel_ids.append(channel_id)

        masked = self.client.get(
            f"/api/video/channels/{channel_id}/stream-info", headers=self.headers
        ).json()
        self.assertNotIn("secret", masked["rtsp_url"])
        self.assertIn("***", masked["rtsp_url"])
        self.assertFalse(masked["playable_in_browser"])

        revealed = self.client.get(
            f"/api/video/channels/{channel_id}/stream-info?reveal=true", headers=self.headers
        ).json()
        self.assertIn("secret", revealed["rtsp_url"])

    def test_rtsp_url_scheme_is_validated(self):
        resp = self._create(channel_code="BAD-RTSP", rtsp_url="http://10.0.0.5/live")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("rtsp://", resp.json()["message"])

    def test_recording_search_requires_authentication(self):
        created = self._create(channel_code="REC-AUTH")
        channel_id = created.json()["id"]
        self.__class__.channel_ids.append(channel_id)
        resp = self.client.post(
            f"/api/video/channels/{channel_id}/recordings/search", json={}
        )
        self.assertEqual(resp.status_code, 401)

    def test_recording_search_rejects_missing_time_range(self):
        created = self._create(channel_code="REC-NO-TIME")
        channel_id = created.json()["id"]
        self.__class__.channel_ids.append(channel_id)
        resp = self.client.post(
            f"/api/video/channels/{channel_id}/recordings/search",
            json={"start_time": "2026-01-15 00:00:00"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("end_time", resp.text)

    def test_recording_search_on_unsupported_platform_is_honest(self):
        """平台没有录像检索能力时明确回 supported=false，而不是给一份编造的清单。"""
        created = self._create(channel_code="REC-MOCK")
        channel_id = created.json()["id"]
        self.__class__.channel_ids.append(channel_id)
        resp = self.client.post(
            f"/api/video/channels/{channel_id}/recordings/search",
            json={"start_time": "2026-01-15 00:00:00", "end_time": "2026-01-15 23:59:59"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertFalse(payload["supported"])
        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["channel_id"], channel_id)
        self.assertIn("未实现录像检索", payload["message"])

    def test_tenant_isolation(self):
        created = self._create(channel_code="ISO-CAM")
        channel_id = created.json()["id"]
        self.__class__.channel_ids.append(channel_id)

        db = SessionLocal()
        try:
            self.assertIsNone(video_service.get_channel(db, self.other_tenant_id, channel_id))
            self.assertEqual(video_service.list_channels(db, self.other_tenant_id), [])
        finally:
            db.close()

    def test_delete_channel(self):
        created = self._create(channel_code="DEL-CAM")
        channel_id = created.json()["id"]

        resp = self.client.delete(f"/api/video/channels/{channel_id}", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(
            self.client.get(f"/api/video/channels/{channel_id}", headers=self.headers).status_code,
            404,
        )

    def test_generic_channel_end_to_end_over_real_http(self):
        """起一个本地 HTTP 设备，验证「探测 → 抓拍 → 受控下发」走的是真实网络请求。"""
        image = _jpeg()
        camera = LocalCameraServer(image)
        try:
            created = self._create(
                channel_code="LOCAL-REAL-01",
                channel_name="本地真实设备",
                platform="generic",
                host="127.0.0.1",
                port=camera.port,
                snapshot_path="/snap.jpg",
                password="",
            )
            self.assertEqual(created.status_code, 200, created.text)
            channel_id = created.json()["id"]
            self.__class__.channel_ids.append(channel_id)

            probe = self.client.post(f"/api/video/channels/{channel_id}/probe", headers=self.headers)
            self.assertEqual(probe.status_code, 200, probe.text)
            self.assertTrue(probe.json()["online"], probe.text)

            token = self.client.post(
                f"/api/video/channels/{channel_id}/snapshot-token", headers=self.headers
            ).json()["token"]
            snapshot = self.client.get(f"/api/video/channels/{channel_id}/snapshot?token={token}")
            self.assertEqual(snapshot.status_code, 200, snapshot.text)
            self.assertEqual(snapshot.content, image, "应原样返回设备提供的抓拍图")
            self.assertEqual(snapshot.headers["x-video-channel"], "LOCAL-REAL-01")
            self.assertTrue(
                any(path.startswith("/snap.jpg") for path in camera.hits),
                f"设备未收到抓拍请求：{camera.hits}",
            )
        finally:
            camera.stop()

    def test_list_returns_created_channels(self):
        created = self._create(channel_code="LIST-CAM")
        self.__class__.channel_ids.append(created.json()["id"])

        listing = self.client.get("/api/video/channels", headers=self.headers)
        self.assertEqual(listing.status_code, 200, listing.text)
        codes = [item["channel_code"] for item in listing.json()["items"]]
        self.assertIn("LIST-CAM", codes)
        self.assertEqual(listing.json()["total"], len(codes))


def setUpModule():
    init_db()
    # 固定凭证密钥，保证加解密用例可重复
    os.environ["VIDEO_CREDENTIAL_KEY"] = CIPHER_KEY


def tearDownModule():
    os.environ.pop("VIDEO_CREDENTIAL_KEY", None)


if __name__ == "__main__":
    unittest.main()
