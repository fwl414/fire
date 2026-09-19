"""GB/T 26875 接入测试：数据包编解码 + 上行报文接入链路。

编解码部分不依赖数据库；接入部分直接调用 `server.handle_frame`（不经过 socket），
覆盖火警落库、心跳刷新、遥测写入、未登记/停用设备被拒等关键分支。
"""
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import (
    AlertRecord,
    Device,
    DeviceTelemetry,
    FaultTicket,
    GB26875Device,
    SessionLocal,
    get_default_tenant_id,
    init_db,
)
from services.gb26875 import auth, commands as cmd
from services.gb26875 import server as gb_server
from services.gb26875.frame import (
    AppObject,
    ChecksumError,
    FrameError,
    START_FLAG,
    checksum,
    decode,
    decode_address,
    decode_stream,
    decode_timestamp,
    encode,
    encode_address,
    encode_app_data,
    encode_timestamp,
    parse_app_data,
)

CENTER = "000000000000"
DEVICE_ADDRESS = "110000000001"
DEVICE_CODE = "GBTEST-001"


class TestFrameCodec(unittest.TestCase):
    """数据包编解码（GB/T 26875.3-2011 6.6 / 7 / 8.2.2）。"""

    def test_address_is_bcd_little_endian(self):
        raw = encode_address("340200000001")
        self.assertEqual(raw, b"\x01\x00\x00\x00\x02\x34")
        self.assertEqual(decode_address(raw), "340200000001")

    def test_address_pads_to_twelve_digits(self):
        self.assertEqual(decode_address(encode_address("123")), "000000000123")

    def test_address_rejects_too_long(self):
        with self.assertRaises(FrameError):
            encode_address("1234567890123")

    def test_timestamp_bcd_round_trip(self):
        moment = datetime(2026, 9, 19, 14, 30, 5)
        raw = encode_timestamp(moment)
        self.assertEqual(raw, bytes([0x05, 0x30, 0x14, 0x19, 0x09, 0x26]))
        self.assertEqual(decode_timestamp(raw), moment)

    def test_timestamp_rejects_invalid_bcd(self):
        with self.assertRaises(FrameError):
            decode_timestamp(bytes([0x0A, 0x30, 0x14, 0x19, 0x09, 0x26]))

    def test_checksum_is_low_byte_of_sum(self):
        payload = bytes([0x02, 0x00, 0x01, 0x00, 0xFF, 0x10])
        self.assertEqual(checksum(payload), sum(payload) & 0xFF)
        # 求和溢出时只保留低 8 位
        self.assertEqual(checksum(bytes([0xFF, 0xFF, 0x02])), 0x00)

    def test_encode_decode_round_trip(self):
        app_data = encode_app_data(cmd.TYPE_COMPONENT_ANALOG, [AppObject(body=b"\x01" * 10)])
        raw = encode(cmd.COMMAND_SEND_DATA, DEVICE_ADDRESS, CENTER, app_data, seq=7, timestamp=datetime(2026, 9, 19, 8, 0, 0))

        self.assertTrue(raw.startswith(START_FLAG))
        self.assertTrue(raw.endswith(b"\x23\x23"))

        frame = decode(raw)
        self.assertEqual(frame.command, cmd.COMMAND_SEND_DATA)
        self.assertEqual(frame.source_address, DEVICE_ADDRESS)
        self.assertEqual(frame.dest_address, CENTER)
        self.assertEqual(frame.seq, 7)
        self.assertEqual(frame.app_data, app_data)
        self.assertEqual(frame.app_type, cmd.TYPE_COMPONENT_ANALOG)
        self.assertEqual(frame.timestamp, datetime(2026, 9, 19, 8, 0, 0))

    def test_checksum_mismatch_raises(self):
        raw = bytearray(encode(cmd.COMMAND_CONFIRM, DEVICE_ADDRESS, CENTER, seq=1))
        raw[-3] ^= 0xFF
        with self.assertRaises(ChecksumError):
            decode(bytes(raw))

    def test_bad_end_flag_raises(self):
        raw = bytearray(encode(cmd.COMMAND_CONFIRM, DEVICE_ADDRESS, CENTER, seq=1))
        raw[-1] = 0x00
        with self.assertRaises(FrameError):
            decode(bytes(raw))

    def test_app_data_unit_round_trip(self):
        """一帧多个信息对象（批量上传部件状态）按类型长度精确切分。"""
        objects = [
            AppObject(body=bytes([1]) * 40, timestamp=datetime(2026, 1, 2, 3, 4, 5)),
            AppObject(body=bytes([2]) * 40, timestamp=datetime(2026, 6, 7, 8, 9, 10)),
        ]
        raw = encode_app_data(cmd.TYPE_COMPONENT_STATUS, objects)
        app_type, parsed = parse_app_data(raw)

        self.assertEqual(app_type, cmd.TYPE_COMPONENT_STATUS)
        self.assertEqual([obj.body for obj in parsed], [obj.body for obj in objects])
        self.assertEqual([obj.timestamp for obj in parsed], [obj.timestamp for obj in objects])

    def test_app_data_unit_falls_back_to_equal_length_split(self):
        """类型未收录时退化为等长切分。"""
        objects = [
            AppObject(body=b"\x01\x02\x03", timestamp=datetime(2026, 1, 2, 3, 4, 5)),
            AppObject(body=b"\x04\x05\x06", timestamp=datetime(2026, 1, 2, 3, 4, 6)),
        ]
        app_type, parsed = parse_app_data(encode_app_data(200, objects))
        self.assertEqual(app_type, 200)
        self.assertEqual([obj.body for obj in parsed], [b"\x01\x02\x03", b"\x04\x05\x06"])

    def test_app_data_unit_tolerates_vendor_extended_body(self):
        """已知类型但信息体长度不标准时按等长兜底解析，不因厂商扩展丢报警。"""
        app_data = encode_app_data(cmd.TYPE_COMPONENT_STATUS, [AppObject(body=b"\x00" * 10, timestamp=None)])
        app_type, parsed = parse_app_data(app_data)
        self.assertEqual(app_type, cmd.TYPE_COMPONENT_STATUS)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].body, b"\x00" * 10)

    def test_app_data_unit_rejects_unsplittable_objects(self):
        # 3 个信息对象共 47 字节，既不符类型长度也无法等分
        with self.assertRaises(FrameError):
            parse_app_data(bytes([cmd.TYPE_COMPONENT_STATUS, 3]) + b"\x00" * 47)

    def test_empty_app_data_unit(self):
        self.assertEqual(parse_app_data(b""), (0, []))
        self.assertEqual(parse_app_data(encode_app_data(cmd.TYPE_SYNC_TRANSMITTER_TIME)), (cmd.TYPE_SYNC_TRANSMITTER_TIME, []))

    def test_app_data_unit_rejects_trailing_bytes(self):
        with self.assertRaises(FrameError):
            parse_app_data(bytes([cmd.TYPE_SYSTEM_STATUS, 0x00, 0x01]))


class TestFrameStream(unittest.TestCase):
    """TCP 字节流切分：粘包、半包与噪声。"""

    def _frame(self, seq):
        return encode(cmd.COMMAND_SEND_DATA, DEVICE_ADDRESS, CENTER, encode_app_data(cmd.TYPE_TRANSMITTER_STATUS), seq=seq)

    def test_single_frame(self):
        frames, rest, errors = decode_stream(self._frame(1))
        self.assertEqual(len(frames), 1)
        self.assertEqual(rest, b"")
        self.assertEqual(errors, [])

    def test_sticky_packets(self):
        """粘包：一次读到的多帧应全部解析出来。"""
        buffer = self._frame(1) + self._frame(2) + self._frame(3)
        frames, rest, errors = decode_stream(buffer)
        self.assertEqual([f.seq for f in frames], [1, 2, 3])
        self.assertEqual(rest, b"")
        self.assertEqual(errors, [])

    def test_half_packet_kept_for_next_read(self):
        """半包：长度不足的尾部留到下一次读取，不误判为坏包。"""
        whole = self._frame(1)
        buffer = whole + self._frame(2)[:15]
        frames, rest, errors = decode_stream(buffer)
        self.assertEqual([f.seq for f in frames], [1])
        self.assertEqual(rest, self._frame(2)[:15])
        self.assertEqual(errors, [])

        frames2, rest2, _ = decode_stream(rest + self._frame(2)[15:])
        self.assertEqual([f.seq for f in frames2], [2])
        self.assertEqual(rest2, b"")

    def test_noise_before_start_flag_is_dropped(self):
        buffer = b"\x01\x02\x03" + self._frame(1)
        frames, rest, errors = decode_stream(buffer)
        self.assertEqual([f.seq for f in frames], [1])
        self.assertEqual(rest, b"")
        self.assertTrue(any("无效数据" in err for err in errors))

    def test_corrupted_frame_does_not_block_following_frame(self):
        broken = bytearray(self._frame(1))
        broken[-3] ^= 0xFF
        frames, rest, errors = decode_stream(bytes(broken) + self._frame(2))
        self.assertEqual([f.seq for f in frames], [2])
        self.assertEqual(rest, b"")
        self.assertTrue(any("校验和" in err for err in errors))


class TestGb26875Ingest(unittest.TestCase):
    """上行报文接入：身份校验与统一落库链路。"""

    tenant_id = None
    device_id = None
    gb_device_id = None

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            cls.tenant_id = get_default_tenant_id(db)
            device = db.query(Device).filter(Device.device_code == DEVICE_CODE).first()
            if not device:
                device = Device(
                    tenant_id=cls.tenant_id,
                    device_code=DEVICE_CODE,
                    device_name="接入测试传输装置",
                    device_type="用户信息传输装置",
                    location="测试楼GB区",
                    status="正常",
                )
                db.add(device)
                db.commit()
                db.refresh(device)
            cls.device_id = device.id

            gb_device = db.query(GB26875Device).filter(GB26875Device.gb_address == DEVICE_ADDRESS).first()
            if not gb_device:
                gb_device = GB26875Device(
                    tenant_id=cls.tenant_id,
                    device_code=DEVICE_CODE,
                    gb_address=DEVICE_ADDRESS,
                    device_system_type=1,
                )
                db.add(gb_device)
                db.commit()
                db.refresh(gb_device)
            cls.gb_device_id = gb_device.id
        finally:
            db.close()

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            db.query(AlertRecord).filter(AlertRecord.device_code == DEVICE_CODE).delete(synchronize_session=False)
            db.query(FaultTicket).filter(FaultTicket.device_id == cls.device_id).delete(synchronize_session=False)
            db.query(DeviceTelemetry).filter(DeviceTelemetry.device_id == cls.device_id).delete(synchronize_session=False)
            db.query(GB26875Device).filter(GB26875Device.id == cls.gb_device_id).delete(synchronize_session=False)
            db.query(Device).filter(Device.id == cls.device_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def setUp(self):
        db = SessionLocal()
        try:
            row = db.query(GB26875Device).filter(GB26875Device.id == self.gb_device_id).first()
            row.enabled = True
            row.username = ""
            row.password_cipher = ""
            db.commit()
        finally:
            db.close()

    def _send(self, frame, address=DEVICE_ADDRESS):
        """构造上行报文并交给服务处理，返回解析后的响应帧。"""
        raw = encode(
            frame["command"],
            source_address=address,
            dest_address=CENTER,
            app_data=frame.get("app_data", b""),
            seq=frame.get("seq", 1),
        )
        db = SessionLocal()
        try:
            response = gb_server.handle_frame(db, decode(raw), peer_ip="127.0.0.1", peer_port=30001)
        finally:
            db.close()
        self.assertIsNotNone(response, "服务端未返回响应帧")
        return decode(response)

    def test_system_status_fire_alarm_creates_alert(self):
        # 系统状态：系统类型=1（火灾报警系统）、系统地址=1、状态位 bit1=火警
        body = bytes([1, 1]) + (0x02).to_bytes(2, "little")
        app_data = encode_app_data(cmd.TYPE_SYSTEM_STATUS, [AppObject(body=body)])
        response = self._send({"command": cmd.COMMAND_SEND_DATA, "app_data": app_data})

        self.assertEqual(response.command, cmd.COMMAND_CONFIRM)

        db = SessionLocal()
        try:
            alerts = db.query(AlertRecord).filter(AlertRecord.device_code == DEVICE_CODE).all()
            self.assertTrue(alerts, "火警未生成告警")
            self.assertTrue(any("火警" in (a.description or "") for a in alerts))
        finally:
            db.close()

    def test_heartbeat_marks_device_registered(self):
        app_data = encode_app_data(cmd.TYPE_TRANSMITTER_STATUS, [AppObject(body=bytes([0x00]))])
        response = self._send({"command": cmd.COMMAND_SEND_DATA, "app_data": app_data})
        self.assertEqual(response.command, cmd.COMMAND_CONFIRM)

        db = SessionLocal()
        try:
            row = db.query(GB26875Device).filter(GB26875Device.id == self.gb_device_id).first()
            self.assertTrue(row.registered)
            self.assertIsNotNone(row.last_heartbeat_at)
            self.assertEqual(row.remote_ip, "127.0.0.1")
        finally:
            db.close()

    def test_analog_voltage_writes_telemetry(self):
        # 模拟量信息体：系统类型+系统地址+部件类型+部件地址(4)+模拟量类型(8=电压)+值(2200 → 220.0V)
        body = bytes([1, 1, 2]) + b"\x01\x02\x03\x04" + bytes([8]) + (2200).to_bytes(2, "little", signed=True)
        app_data = encode_app_data(cmd.TYPE_COMPONENT_ANALOG, [AppObject(body=body)])
        response = self._send({"command": cmd.COMMAND_SEND_DATA, "app_data": app_data})
        self.assertEqual(response.command, cmd.COMMAND_CONFIRM)

        db = SessionLocal()
        try:
            row = (
                db.query(DeviceTelemetry)
                .filter(DeviceTelemetry.device_id == self.device_id, DeviceTelemetry.voltage.isnot(None))
                .order_by(DeviceTelemetry.id.desc())
                .first()
            )
            self.assertIsNotNone(row, "模拟量电压未写入遥测")
            self.assertAlmostEqual(row.voltage, 220.0, places=3)
        finally:
            db.close()

    def test_unregistered_address_is_denied(self):
        app_data = encode_app_data(cmd.TYPE_TRANSMITTER_STATUS, [AppObject(body=b"\x00")])
        response = self._send(
            {"command": cmd.COMMAND_SEND_DATA, "app_data": app_data},
            address="999999999999",
        )
        self.assertEqual(response.command, cmd.COMMAND_DENY)

    def test_disabled_device_is_denied(self):
        db = SessionLocal()
        try:
            row = db.query(GB26875Device).filter(GB26875Device.id == self.gb_device_id).first()
            row.enabled = False
            db.commit()
        finally:
            db.close()

        app_data = encode_app_data(cmd.TYPE_TRANSMITTER_STATUS, [AppObject(body=b"\x00")])
        response = self._send({"command": cmd.COMMAND_SEND_DATA, "app_data": app_data})
        self.assertEqual(response.command, cmd.COMMAND_DENY)

    def test_credentials_required_when_configured(self):
        db = SessionLocal()
        try:
            row = db.query(GB26875Device).filter(GB26875Device.id == self.gb_device_id).first()
            username, password = auth.issue_credentials(db, row)
        finally:
            db.close()

        heartbeat = encode_app_data(cmd.TYPE_TRANSMITTER_STATUS, [AppObject(body=b"\x00")])
        denied = self._send({"command": cmd.COMMAND_SEND_DATA, "app_data": heartbeat})
        self.assertEqual(denied.command, cmd.COMMAND_DENY, "启用口令后未携带凭证应被拒绝")

        # 注册报文（类型 26）携带用户名/口令才放行
        register = encode_app_data(
            cmd.TYPE_TRANSMITTER_CONFIG,
            [AppObject(body=f"USER={username};PWD={password}".encode("gb18030"))],
        )
        accepted = self._send({"command": cmd.COMMAND_SEND_DATA, "app_data": register})
        self.assertEqual(accepted.command, cmd.COMMAND_CONFIRM)

    def test_unknown_app_type_is_denied(self):
        app_data = encode_app_data(120, [AppObject(body=b"\x01\x02")])
        response = self._send({"command": cmd.COMMAND_SEND_DATA, "app_data": app_data})
        self.assertEqual(response.command, cmd.COMMAND_DENY)

    def test_read_transmitter_time_returns_response(self):
        app_data = encode_app_data(cmd.TYPE_READ_TRANSMITTER_TIME)
        response = self._send({"command": cmd.COMMAND_REQUEST, "app_data": app_data})
        self.assertEqual(response.command, cmd.COMMAND_RESPONSE)
        app_type, objects = parse_app_data(response.app_data)
        self.assertEqual(app_type, cmd.TYPE_READ_TRANSMITTER_TIME)
        self.assertEqual(len(objects), 1)


if __name__ == "__main__":
    unittest.main()
