# Symlink Validator

Resolves a symlink chain and reports whether the target exists, is circular, or exceeds a max depth. Standard library only.

```python
from symlink_validator import resolve, ResolutionStatus

result = resolve("/some/path/or/symlink", max_depth=40)

if result.status is ResolutionStatus.EXISTS:
    print("points to", result.path)
elif result.status is ResolutionStatus.MISSING:
    print("dangling")
elif result.status is ResolutionStatus.CIRCULAR:
    print("loop")
elif result.status is ResolutionStatus.TOO_DEEP:
    print("too deep")
```

## Why

`os.path.realpath` will follow symlinks until they resolve or fail, but it doesn't tell you *why* resolution stopped. If a path is a self-loop, `realpath` typically returns the loop point silently; if it's too deep, behavior is platform-dependent. This library walks the chain one link at a time so you can distinguish the four outcomes that matter for validation: a real target, a dangling link, a circular reference, or a chain too long to be legitimate.

The trade-off is speed: doing our own per-link walk is slower than letting the kernel resolve in one shot, and we don't canonicalize `..` components beyond what `os.path.normpath` does. If you only need a final path, use `os.path.realpath`.

## Edge cases

- `max_depth=0` means no symlink jumps are allowed; if the input is itself a symlink, you get `TOO_DEEP` immediately. This is deliberate — it lets you say "don't follow anything."
- Relative symlinks are resolved relative to the directory of the link that contains them, per POSIX. A link `/foo/bar` pointing to `baz` resolves to `/foo/baz`, not `./baz`.
- The `chain` includes the starting path and every link followed, so a 3-link chain has 4 entries. `jump_count` excludes the starting path.
- Cycles are detected by exact path string match after `normpath`. Two different paths that point to the same inode via different route strings are treated as distinct; if you need inode-level detection, use `os.stat` on the final result.
