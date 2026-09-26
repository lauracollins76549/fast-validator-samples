import os
import unittest
from pathlib import Path

from symlink_validator import resolve, ResolutionStatus


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.mkdtemp())

    def tearDown(self):
        for p in sorted(self.tmp.rglob("*"), reverse=True):
            if p.is_symlink() or p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
        self.tmp.rmdir()

    def mkdtemp(self):
        import tempfile
        return tempfile.mkdtemp(prefix="sv_")


class TestRealTarget(Base):
    def test_existing_file_resolved(self):
        f = self.tmp / "real.txt"
        f.write_text("x")
        r = resolve(f)
        self.assertEqual(r.status, ResolutionStatus.EXISTS)
        self.assertEqual(r.path, os.path.normpath(str(f)))
        self.assertEqual(r.jump_count, 0)
        self.assertEqual(len(r.chain), 1)

    def test_symlink_to_existing_file(self):
        f = self.tmp / "real.txt"
        f.write_text("x")
        l = self.tmp / "link.txt"
        l.symlink_to(f)
        r = resolve(l)
        self.assertEqual(r.status, ResolutionStatus.EXISTS)
        self.assertEqual(r.jump_count, 1)
        self.assertEqual(len(r.chain), 2)

    def test_relative_symlink_resolves(self):
        f = self.tmp / "real.txt"
        f.write_text("x")
        l = self.tmp / "link.txt"
        l.symlink_to("real.txt")
        r = resolve(l)
        self.assertEqual(r.status, ResolutionStatus.EXISTS)
        self.assertEqual(r.path, os.path.normpath(str(f)))

    def test_nested_symlink_chain(self):
        f = self.tmp / "real.txt"
        f.write_text("x")
        a = self.tmp / "a"
        b = self.tmp / "b"
        c = self.tmp / "c"
        a.symlink_to(b)
        b.symlink_to(c)
        c.symlink_to(f)
        r = resolve(a)
        self.assertEqual(r.status, ResolutionStatus.EXISTS)
        self.assertEqual(r.path, os.path.normpath(str(f)))
        self.assertEqual(r.jump_count, 3)
        self.assertEqual(len(r.chain), 4)


class TestMissing(Base):
    def test_nonexistent_plain_path(self):
        r = resolve(self.tmp / "nope.txt")
        self.assertEqual(r.status, ResolutionStatus.MISSING)
        self.assertEqual(r.jump_count, 0)

    def test_dangling_symlink(self):
        l = self.tmp / "dangling"
        l.symlink_to(self.tmp / "ghost")
        r = resolve(l)
        self.assertEqual(r.status, ResolutionStatus.MISSING)
        self.assertEqual(r.jump_count, 1)


class TestCircular(Base):
    def test_direct_cycle(self):
        a = self.tmp / "a"
        b = self.tmp / "b"
        a.symlink_to(b)
        b.symlink_to(a)
        r = resolve(a)
        self.assertEqual(r.status, ResolutionStatus.CIRCULAR)

    def test_self_cycle(self):
        a = self.tmp / "loop"
        a.symlink_to(a)
        r = resolve(a)
        self.assertEqual(r.status, ResolutionStatus.CIRCULAR)

    def test_three_way_cycle(self):
        a = self.tmp / "a"
        b = self.tmp / "b"
        c = self.tmp / "c"
        a.symlink_to(b)
        b.symlink_to(c)
        c.symlink_to(a)
        r = resolve(a)
        self.assertEqual(r.status, ResolutionStatus.CIRCULAR)


class TestDepth(Base):
    def test_max_depth_exceeded(self):
        # Build a chain longer than max_depth.
        f = self.tmp / "end"
        f.write_text("x")
        prev = f
        links = []
        for i in range(5):
            lk = self.tmp / f"l{i}"
            lk.symlink_to(prev)
            links.append(lk)
            prev = lk
        r = resolve(links[-1], max_depth=2)
        self.assertEqual(r.status, ResolutionStatus.TOO_DEEP)
        self.assertEqual(r.jump_count, 2)

    def test_max_depth_exact(self):
        f = self.tmp / "end"
        f.write_text("x")
        a = self.tmp / "a"
        a.symlink_to(f)
        r = resolve(a, max_depth=1)
        self.assertEqual(r.status, ResolutionStatus.EXISTS)
        self.assertEqual(r.jump_count, 1)

    def test_max_depth_zero_exits_immediately(self):
        f = self.tmp / "end"
        f.write_text("x")
        a = self.tmp / "a"
        a.symlink_to(f)
        r = resolve(a, max_depth=0)
        # max_depth=0 means we're not allowed any jumps; current path is a symlink
        # so we bail with TOO_DEEP without resolving.
        self.assertEqual(r.status, ResolutionStatus.TOO_DEEP)
        self.assertEqual(r.jump_count, 0)

    def test_negative_max_depth_raises(self):
        with self.assertRaises(ValueError):
            resolve(self.tmp / "x", max_depth=-1)


class TestTypes(Base):
    def test_chain_is_tuple(self):
        f = self.tmp / "real.txt"
        f.write_text("x")
        r = resolve(f)
        self.assertIsInstance(r.chain, tuple)

    def test_path_is_str(self):
        f = self.tmp / "real.txt"
        f.write_text("x")
        r = resolve(f)
        self.assertIsInstance(r.path, str)

    def test_accepts_pathlib_input(self):
        f = self.tmp / "real.txt"
        f.write_text("x")
        r = resolve(f)
        self.assertEqual(r.status, ResolutionStatus.EXISTS)


if __name__ == "__main__":
    unittest.main()
