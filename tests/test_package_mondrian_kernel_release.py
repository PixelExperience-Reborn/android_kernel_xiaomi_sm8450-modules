"""Release layout of tools/package_mondrian_kernel_release.py with fake modules."""
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import package_mondrian_kernel_release as pkg  # noqa: E402

RELEASE = "5.10.81-gtest"


def elf_module(name, depends="", release=RELEASE):
    """A minimal ELF64 LE file with .shstrtab and .modinfo sections."""
    modinfo = f"name={name}\0depends={depends}\0vermagic={release} SMP preempt mod_unload aarch64\0".encode()
    shstrtab = b"\0.shstrtab\0.modinfo\0"
    body_off = 64
    mod_off = body_off + len(shstrtab)
    sh_off = (mod_off + len(modinfo) + 7) & ~7
    header = bytearray(64)
    header[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<Q", header, 0x28, sh_off)
    struct.pack_into("<HHH", header, 0x3A, 64, 3, 1)
    sections = b"\0" * 64
    sections += struct.pack("<IIQQQQIIQQ", 1, 3, 0, 0, body_off, len(shstrtab), 0, 0, 1, 0)
    sections += struct.pack("<IIQQQQIIQQ", 11, 1, 0, 0, mod_off, len(modinfo), 0, 0, 1, 0)
    data = bytes(header) + shstrtab + modinfo
    return data + b"\0" * (sh_off - len(data)) + sections


class PackageReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.stock = self.tmp / "stock"
        self.stock.mkdir()
        lists = {
            "vendor_ramdisk.modules": "a.ko\nb.ko\n",
            "vendor_ramdisk.modules.load": "a.ko\nb.ko\na.ko\nmissing_first.ko\n",
            "vendor_ramdisk.modules.load.recovery": "b.ko\na.ko\n",
            "vendor_dlkm.modules": "c.ko\n",
            "vendor_dlkm.modules.load": "c.ko\nwlan.ko\n",
            "modules.blocklist": "blocklist x\n",
        }
        for name, text in lists.items():
            (self.stock / name).write_text(text)
        self.mods = self.tmp / "mods"
        self.mods.mkdir()
        self.image = self.tmp / "Image"
        self.image.write_bytes(b"\0" * 64 + f"Linux version {RELEASE} (ci@pe)".encode())
        self.dt = self.tmp / "dt"
        (self.dt / "dtbs").mkdir(parents=True)
        for base in pkg.DTBS:
            (self.dt / "dtbs" / (base + ".dtb")).write_bytes(base.encode())
        (self.dt / "dtbo.img").write_bytes(b"dtbo")

    def write(self, name, depends="", release=RELEASE):
        (self.mods / (name + ".ko")).write_bytes(elf_module(name, depends, release))

    def run_package(self):
        with mock.patch.object(pkg, "STOCK", self.stock):
            return pkg.package(self.image, [self.mods], self.dt, self.tmp / "out", {"sources": {}})

    def test_stock_placement_order_and_dependency_closure(self):
        self.write("a", depends="helper")
        self.write("b")
        self.write("c", depends="b")
        self.write("wlan")
        self.write("helper")
        prov = self.run_package()
        out = self.tmp / "out"
        self.assertEqual(sorted(p.name for p in (out / "vendor_ramdisk").glob("*.ko")),
                         ["a.ko", "b.ko", "helper.ko"])
        self.assertEqual(sorted(p.name for p in (out / "vendor_dlkm").glob("*.ko")), ["c.ko", "wlan.ko"])
        self.assertEqual((out / "vendor_ramdisk/modules.load").read_text(), "a.ko\nb.ko\n")
        self.assertEqual((out / "vendor_ramdisk/modules.load.recovery").read_text(), "b.ko\na.ko\n")
        self.assertEqual((out / "vendor_dlkm/modules.load").read_text(), "c.ko\nwlan.ko\n")
        self.assertEqual(prov["kernel_release"], RELEASE)
        self.assertEqual(prov["modules"]["stock_not_built"], ["missing_first.ko"])
        self.assertIn("helper.ko", prov["modules"]["built_not_in_stock_lists"])
        written = json.loads((out / "provenance.json").read_text())
        self.assertEqual(set(written["files"]), {str(p.relative_to(out)) for p in out.rglob("*")
                                                 if p.is_file() and p.name != "provenance.json"})

    def test_module_of_another_kernel_is_rejected(self):
        self.write("a", release="5.10.236-other")
        with self.assertRaisesRegex(ValueError, "vermagic"):
            self.run_package()

    def test_missing_dependency_is_rejected(self):
        self.write("a", depends="not_built")
        with self.assertRaisesRegex(ValueError, "not built"):
            self.run_package()


if __name__ == "__main__":
    unittest.main()
