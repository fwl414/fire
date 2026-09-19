"""DWG 批量转换脚本（tools/dwg_batch_convert.py）的测试

这个脚本要调用本机安装的 ODA File Converter，测试环境里通常没有它，
所以这里只测不依赖外部程序的核心判断——这几处恰好也是最容易出错的：

- 输出路径必须镜像输入的目录结构（图纸集合里大量重名，平铺会互相覆盖）
- 增量跳过：已转好且不比源文件旧的要跳过，中断后能续跑
- 等待 ODA 写完：启动器可能立刻返回，文件数稳定下来才算完成
"""
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools import dwg_batch_convert as conv  # noqa: E402


class TestTargetPath(unittest.TestCase):
    def test_mirrors_subdirectory(self):
        """同名文件在不同子目录里必须落到不同输出路径。"""
        out = Path("F:/out")
        a = conv.target_dxf_path(out, Path("."), Path("F:/in/厂房建筑图.dwg"))
        b = conv.target_dxf_path(out, Path("厂房建筑图"), Path("F:/in/厂房建筑图/厂房建筑图.dwg"))
        self.assertEqual(a, out / "厂房建筑图.dxf")
        self.assertEqual(b, out / "厂房建筑图" / "厂房建筑图.dxf")
        self.assertNotEqual(a, b)

    def test_keeps_dxf_extension_and_stem(self):
        out = Path("F:/out")
        self.assertEqual(
            conv.target_dxf_path(out, Path("东芝电梯厂房建筑图全套"), Path("A-06一,二层平面图.dwg")),
            out / "东芝电梯厂房建筑图全套" / "A-06一,二层平面图.dxf",
        )


class TestCollectGroups(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _touch(self, rel: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"AC1015")
        return path

    def test_groups_by_relative_directory(self):
        self._touch("根图.dwg")
        self._touch("子目录A/平面.dwg")
        self._touch("子目录A/立面.dwg")
        self._touch("子目录B/深层/详图.dwg")
        # 非 dwg 不该被收进来
        self._touch("子目录A/效果图.jpg")
        self._touch("acaddoc.lsp")

        groups = conv.collect_groups(self.root)
        self.assertEqual(set(groups.keys()), {Path("."), Path("子目录A"), Path("子目录B/深层")})
        self.assertEqual(len(groups[Path(".")]), 1)
        self.assertEqual(len(groups[Path("子目录A")]), 2)
        self.assertEqual(sum(len(v) for v in groups.values()), 4)

    def test_is_up_to_date_skips_fresh_output(self):
        dwg = self._touch("子目录A/平面.dwg")
        out = self.root / "out"
        (out / "子目录A").mkdir(parents=True)
        dxf = out / "子目录A" / "平面.dxf"

        # 还没转换过：需要转
        self.assertFalse(conv.is_up_to_date(dxf, dwg, overwrite=False))

        # 转好了且比源文件新：跳过
        dxf.write_text("0\nSECTION\n")
        newer = dwg.stat().st_mtime + 10
        os.utime(dxf, (newer, newer))
        self.assertTrue(conv.is_up_to_date(dxf, dwg, overwrite=False))

        # --overwrite 时不跳过
        self.assertFalse(conv.is_up_to_date(dxf, dwg, overwrite=True))


class TestWaitUntilSettled(unittest.TestCase):
    """ODA 的启动器可能是异步的：退出不等于写完，必须等文件数稳定。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)
        # 缩短等待窗口，避免测试跑几秒
        self._saved = (conv.SETTLE_SECONDS, conv.POLL_INTERVAL_SECONDS)
        conv.SETTLE_SECONDS = 1
        conv.POLL_INTERVAL_SECONDS = 0.1

    def tearDown(self):
        conv.SETTLE_SECONDS, conv.POLL_INTERVAL_SECONDS = self._saved
        self._tmp.cleanup()

    def test_waits_for_late_files(self):
        (self.out / "a.dxf").write_text("x")

        def writer():
            time.sleep(0.4)
            (self.out / "b.dxf").write_text("x")
            time.sleep(0.4)
            (self.out / "c.dxf").write_text("x")

        thread = threading.Thread(target=writer)
        thread.start()
        try:
            count = conv.wait_until_settled(self.out, time.monotonic() + 15)
        finally:
            thread.join()
        self.assertEqual(count, 3, "应等到后写入的文件都落盘")

    def test_returns_early_when_already_stable(self):
        (self.out / "a.dxf").write_text("x")
        start = time.monotonic()
        count = conv.wait_until_settled(self.out, start + 30)
        elapsed = time.monotonic() - start
        self.assertEqual(count, 1)
        self.assertLess(elapsed, 5, "已经稳定就不该等满 deadline")


class TestFindOda(unittest.TestCase):
    def test_explicit_path_must_exist(self):
        self.assertIsNone(conv.find_oda("Z:/definitely/not/here/ODAFileConverter.exe"))

    def test_explicit_path_is_returned_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "ODAFileConverter.exe"
            exe.write_bytes(b"MZ")
            self.assertEqual(conv.find_oda(str(exe)), exe)


if __name__ == "__main__":
    unittest.main()
