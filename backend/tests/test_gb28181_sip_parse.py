"""GB28181 SIP 报文解析/构造、Digest 认证与 SDP 测试。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.gb28181.sip_stack import (
    SipParseError,
    build_authorization,
    build_request,
    build_response,
    build_sdp,
    extract_tag,
    extract_uri,
    extract_user,
    parse_message,
    parse_sdp,
    split_stream,
    verify_authorization,
)

REGISTER_REQUEST = (
    "REGISTER sip:34020000002000000001@3402000000 SIP/2.0\r\n"
    "Via: SIP/2.0/UDP 192.168.1.100:5060;rport;branch=z9hG4bK123456\r\n"
    "From: <sip:34020000001320000001@3402000000>;tag=abcdef\r\n"
    "To: <sip:34020000001320000001@3402000000>\r\n"
    "Call-ID: 0a1b2c3d4e5f\r\n"
    "CSeq: 1 REGISTER\r\n"
    "Contact: <sip:34020000001320000001@192.168.1.100:5060>\r\n"
    "Max-Forwards: 70\r\n"
    "Expires: 3600\r\n"
    "Content-Length: 0\r\n"
    "\r\n"
).encode("utf-8")

MESSAGE_REQUEST = (
    "MESSAGE sip:34020000002000000001@3402000000 SIP/2.0\r\n"
    "Via: SIP/2.0/UDP 192.168.1.100:5060;branch=z9hG4bK999\r\n"
    "From: <sip:34020000001320000001@3402000000>;tag=keepalive\r\n"
    "To: <sip:34020000002000000001@3402000000>\r\n"
    "Call-ID: keepalive-call\r\n"
    "CSeq: 20 MESSAGE\r\n"
    "Content-Type: Application/MANSCDP+xml\r\n"
    "Content-Length: {length}\r\n"
    "\r\n"
).encode("utf-8")


class TestSipParse(unittest.TestCase):

    def test_parse_register_request(self):
        msg = parse_message(REGISTER_REQUEST, ("192.168.1.100", 5060))

        self.assertTrue(msg.is_request)
        self.assertEqual(msg.method, "REGISTER")
        self.assertEqual(msg.uri, "sip:34020000002000000001@3402000000")
        self.assertEqual(msg.call_id, "0a1b2c3d4e5f")
        self.assertEqual(msg.cseq_number, 1)
        self.assertEqual(msg.cseq_method, "REGISTER")
        self.assertEqual(msg.get("expires"), "3600")
        self.assertEqual(msg.source, ("192.168.1.100", 5060))

    def test_parse_message_with_body(self):
        body = "<Notify><CmdType>Keepalive</CmdType><SN>1</SN></Notify>".encode("utf-8")
        raw = MESSAGE_REQUEST.decode("utf-8").format(length=len(body)).encode("utf-8") + body

        msg = parse_message(raw)
        self.assertEqual(msg.method, "MESSAGE")
        self.assertEqual(msg.get("content-type"), "Application/MANSCDP+xml")
        self.assertIn("Keepalive", msg.body_text)

    def test_parse_response(self):
        raw = (
            "SIP/2.0 200 OK\r\n"
            "Via: SIP/2.0/UDP 10.0.0.1:5060;branch=z9hG4bK1\r\n"
            "From: <sip:34020000002000000001@3402000000>;tag=platform\r\n"
            "To: <sip:34020000001320000001@3402000000>;tag=device\r\n"
            "Call-ID: invite-call\r\n"
            "CSeq: 5 INVITE\r\n"
            "Content-Length: 0\r\n\r\n"
        ).encode("utf-8")

        msg = parse_message(raw)
        self.assertFalse(msg.is_request)
        self.assertEqual(msg.status_code, 200)
        self.assertEqual(msg.reason, "OK")
        self.assertEqual(extract_tag(msg.get("To")), "device")

    def test_empty_and_malformed_are_rejected(self):
        with self.assertRaises(SipParseError):
            parse_message(b"")
        with self.assertRaises(SipParseError):
            parse_message(b"NOT-A-SIP-LINE\r\n\r\n")

    def test_uri_and_user_extraction(self):
        self.assertEqual(extract_uri("<sip:34020000001320000001@3402000000>;tag=x"),
                         "sip:34020000001320000001@3402000000")
        self.assertEqual(extract_user("sip:34020000001320000001@3402000000"), "34020000001320000001")
        self.assertEqual(extract_tag("<sip:a@b>;tag=abc123"), "abc123")


class TestSipBuild(unittest.TestCase):

    def test_build_response_copies_dialog_headers(self):
        request = parse_message(REGISTER_REQUEST)
        raw = build_response(request, 200, "OK", extra_headers={"Expires": "3600"}, to_tag="newtag")
        response = parse_message(raw)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.call_id, "0a1b2c3d4e5f")
        self.assertEqual(response.cseq, "1 REGISTER")
        self.assertEqual(response.get("Expires"), "3600")
        self.assertIn("newtag", response.get("To"))
        self.assertTrue(response.get("Via"))

    def test_build_request_sets_content_length(self):
        body = b"<Query></Query>"
        raw = build_request("MESSAGE", "sip:x@y", {"Call-ID": "c1", "CSeq": "1 MESSAGE"}, body,
                            content_type="Application/MANSCDP+xml")
        msg = parse_message(raw)
        self.assertEqual(msg.get("Content-Length"), str(len(body)))
        self.assertEqual(msg.body, body)


class TestDigestAuth(unittest.TestCase):

    def test_authorization_round_trip(self):
        header = build_authorization(
            "34020000001320000001", "Passw0rd", "3402000000", "nonce123", "REGISTER",
            "sip:34020000002000000001@3402000000",
        )
        self.assertTrue(verify_authorization(header, "Passw0rd", "REGISTER"))
        self.assertFalse(verify_authorization(header, "WrongPass", "REGISTER"))

    def test_authorization_with_qop(self):
        header = build_authorization(
            "user", "secret", "realm", "nonce", "INVITE", "sip:a@b",
            qop="auth", nc="00000002", cnonce="cnoncevalue",
        )
        self.assertTrue(verify_authorization(header, "secret", "INVITE"))
        self.assertFalse(verify_authorization(header, "secret", "MESSAGE"))

    def test_empty_authorization_or_password_is_rejected(self):
        self.assertFalse(verify_authorization("", "pwd", "REGISTER"))
        self.assertFalse(verify_authorization('Digest username="u"', "", "REGISTER"))


class TestSdp(unittest.TestCase):

    def test_build_and_parse_sdp(self):
        sdp = build_sdp("10.0.0.9", 10086, "0123456789", channel_uri="sip:34020000001320000001@10.0.0.5:5060")
        self.assertIn("c=IN IP4 10.0.0.9", sdp)
        self.assertIn("m=video 10086 RTP/AVP 96 98 97", sdp)
        self.assertIn("y=0123456789", sdp)

        parsed = parse_sdp("v=0\r\nc=IN IP4 192.168.1.100\r\nm=video 30000 RTP/AVP 96\r\ny=9876543210\r\n")
        self.assertEqual(parsed.address, "192.168.1.100")
        self.assertEqual(parsed.port, 30000)
        self.assertEqual(parsed.ssrc, "9876543210")
        self.assertEqual(parsed.media, "video")


class TestStreamSplit(unittest.TestCase):

    def test_split_multiple_messages(self):
        buffer = REGISTER_REQUEST + REGISTER_REQUEST + REGISTER_REQUEST
        messages, rest = split_stream(buffer)
        self.assertEqual(len(messages), 3)
        self.assertEqual(rest, b"")

    def test_split_keeps_half_message(self):
        body = b"<Notify><CmdType>Keepalive</CmdType></Notify>"
        full = MESSAGE_REQUEST.decode("utf-8").format(length=len(body)).encode("utf-8") + body
        messages, rest = split_stream(REGISTER_REQUEST + full[:40])
        self.assertEqual(len(messages), 1)
        self.assertEqual(rest, full[:40])

        messages2, rest2 = split_stream(rest + full[40:])
        self.assertEqual(len(messages2), 1)
        self.assertEqual(rest2, b"")

    def test_split_waits_for_full_body(self):
        body = b"<Notify/>"
        head = MESSAGE_REQUEST.decode("utf-8").format(length=len(body)).encode("utf-8")
        messages, rest = split_stream(head + body[:-1])
        self.assertEqual(messages, [])
        self.assertEqual(rest, head + body[:-1])


if __name__ == "__main__":
    unittest.main()
