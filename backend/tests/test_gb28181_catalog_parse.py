"""GB28181 目录/设备信息/报警 XML 解析与查询、云台命令构造测试。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.gb28181 import catalog
from services.gb28181.catalog import CatalogParseError

CATALOG_XML = """<?xml version="1.0" encoding="GB2312"?>
<Response>
<CmdType>Catalog</CmdType>
<SN>17430</SN>
<DeviceID>34020000001320000001</DeviceID>
<SumNum>2</SumNum>
<DeviceList Num="2">
<Item>
<DeviceID>34020000001320000001</DeviceID>
<Name>大门口摄像机</Name>
<Manufacturer>Hikvision</Manufacturer>
<Model>DS-2CD3T46</Model>
<Owner>消防科</Owner>
<Address>1号办公楼大门口</Address>
<Parental>0</Parental>
<ParentID>34020000001320000001</ParentID>
<RegisterWay>1</RegisterWay>
<Secrecy>0</Secrecy>
<Status>ON</Status>
<IPAddress>192.168.1.101</IPAddress>
<Port>5060</Port>
</Item>
<Item>
<DeviceID>34020000001320000002</DeviceID>
<Name>车库摄像机</Name>
<Manufacturer>Dahua</Manufacturer>
<Model>IPC-HFW2439M</Model>
<Address>地下车库B1区</Address>
<ParentID>34020000001320000001</ParentID>
<Status>OFF</Status>
<IPAddress>192.168.1.102</IPAddress>
<Port>5060</Port>
</Item>
</DeviceList>
</Response>
"""

DEVICE_INFO_XML = """<?xml version="1.0" encoding="GB2312"?>
<Response>
<CmdType>DeviceInfo</CmdType>
<SN>1</SN>
<DeviceID>34020000001320000001</DeviceID>
<DeviceName>NVR-01</DeviceName>
<Result>OK</Result>
<Manufacturer>Hikvision</Manufacturer>
<Model>DS-7808N</Model>
<Firmware>V4.30</Firmware>
<Channel>8</Channel>
<DeviceType>NVR</DeviceType>
<IPAddress>192.168.1.101</IPAddress>
<Port>5060</Port>
</Response>
"""

KEEPALIVE_XML = """<?xml version="1.0"?>
<Notify>
<CmdType>Keepalive</CmdType>
<SN>5</SN>
<DeviceID>34020000001320000001</DeviceID>
<Status>OK</Status>
</Notify>
"""

ALARM_XML = """<?xml version="1.0"?>
<Notify>
<CmdType>Alarm</CmdType>
<SN>9</SN>
<DeviceID>34020000001320000001</DeviceID>
<AlarmPriority>1</AlarmPriority>
<AlarmMethod>5</AlarmMethod>
<AlarmTime>2026-09-19T10:20:30</AlarmTime>
<AlarmDescription>设备报警：视频遮挡</AlarmDescription>
</Notify>
"""


class TestCatalogParse(unittest.TestCase):

    def test_parse_catalog(self):
        parsed = catalog.parse_catalog(CATALOG_XML)

        self.assertEqual(parsed["cmd_type"], "Catalog")
        self.assertEqual(parsed["sn"], 17430)
        self.assertEqual(parsed["device_id"], "34020000001320000001")
        self.assertEqual(parsed["sum_num"], 2)
        self.assertEqual(len(parsed["items"]), 2)

        first = parsed["items"][0]
        self.assertEqual(first["device_id"], "34020000001320000001")
        self.assertEqual(first["name"], "大门口摄像机")
        self.assertEqual(first["manufacturer"], "Hikvision")
        self.assertEqual(first["model"], "DS-2CD3T46")
        self.assertEqual(first["address"], "1号办公楼大门口")
        self.assertEqual(first["parent_id"], "34020000001320000001")
        self.assertEqual(first["status"], "ON")
        self.assertEqual(parsed["items"][1]["status"], "OFF")

    def test_parse_catalog_from_gb18030_bytes(self):
        parsed = catalog.parse_catalog(CATALOG_XML.encode("gb18030"))
        self.assertEqual(parsed["items"][0]["name"], "大门口摄像机")

    def test_parse_device_info(self):
        parsed = catalog.parse_device_info(DEVICE_INFO_XML)
        self.assertEqual(parsed["name"], "NVR-01")
        self.assertEqual(parsed["manufacturer"], "Hikvision")
        self.assertEqual(parsed["model"], "DS-7808N")
        self.assertEqual(parsed["firmware"], "V4.30")
        self.assertEqual(parsed["channel_count"], "8")

    def test_parse_keepalive_and_alarm(self):
        keepalive = catalog.parse_keepalive(KEEPALIVE_XML)
        self.assertEqual(keepalive["cmd_type"], "Keepalive")
        self.assertEqual(keepalive["device_id"], "34020000001320000001")
        self.assertEqual(keepalive["status"], "OK")

        alarm = catalog.parse_alarm(ALARM_XML)
        self.assertEqual(alarm["alarm_priority"], "1")
        self.assertEqual(alarm["alarm_method"], "5")
        self.assertEqual(alarm["alarm_time"], "2026-09-19T10:20:30")
        self.assertIn("视频遮挡", alarm["alarm_description"])

    def test_cmd_type_and_sn_helpers(self):
        self.assertEqual(catalog.parse_cmd_type(CATALOG_XML), "Catalog")
        self.assertEqual(catalog.parse_sn(KEEPALIVE_XML), 5)
        self.assertEqual(catalog.parse_cmd_type("not xml"), "")

    def test_invalid_xml_raises(self):
        with self.assertRaises(CatalogParseError):
            catalog.parse_catalog("<Response><CmdType>Catalog</CmdType>")
        with self.assertRaises(CatalogParseError):
            catalog.parse_catalog("")


class TestCatalogBuild(unittest.TestCase):

    def test_build_catalog_query(self):
        body = catalog.build_catalog_query("34020000001320000001", 123)
        text = body.decode("gb18030")

        self.assertIn("<CmdType>Catalog</CmdType>", text)
        self.assertIn("<SN>123</SN>", text)
        self.assertIn("<DeviceID>34020000001320000001</DeviceID>", text)
        # 查询命令用标准 XML 声明，可直接被设备解析
        self.assertTrue(text.startswith("<?xml"))

    def test_build_device_control(self):
        body = catalog.build_device_control(
            "34020000001320000001", "34020000001320000001", 7, action="up", speed=5
        )
        text = body.decode("gb18030")
        self.assertIn("<CmdType>DeviceControl</CmdType>", text)
        self.assertIn("<SN>7</SN>", text)
        self.assertIn("<PTZCmd>", text)

    def test_build_ptz_cmd_layout_and_checksum(self):
        raw = catalog.build_ptz_cmd("up", 5)
        self.assertEqual(len(raw), 16)  # 8 字节
        data = bytes.fromhex(raw)

        self.assertEqual(data[0], 0xA5)
        self.assertEqual(data[1], 0x0F)
        self.assertEqual(data[2], 0x01)
        self.assertEqual(data[3], catalog.PTZ_COMMAND_BITS["up"])
        self.assertEqual(data[7], sum(data[:7]) & 0xFF)

    def test_build_ptz_cmd_stop_has_zero_speed(self):
        data = bytes.fromhex(catalog.build_ptz_cmd("stop", 10))
        self.assertEqual(data[3], 0x00)
        self.assertEqual(data[4:7], b"\x00\x00\x00")

    def test_build_ptz_cmd_rejects_unknown_action(self):
        with self.assertRaises(CatalogParseError):
            catalog.build_ptz_cmd("fly", 5)

    def test_build_device_control_accepts_raw_command(self):
        body = catalog.build_device_control(
            "34020000001320000001", "34020000001320000002", 8, ptz_cmd="A50F0108000000B8"
        )
        self.assertIn("A50F0108000000B8", body.decode("gb18030"))


if __name__ == "__main__":
    unittest.main()
