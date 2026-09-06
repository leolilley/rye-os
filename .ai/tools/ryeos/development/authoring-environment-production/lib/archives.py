# ryeos:signed:2026-09-06T04:58:49Z:2b2f29c40c62110bc1519d0b48d8a5b1c04baf894558904ebbd17c3e10213273:dcvlnD8Rl8I8WDz1lYxKIkLU9i8EpOAZhcvR30Ya6B7rwIM6JIC7SgVyM7zPsvlEtB2RqgMNBZ4KyA7Gg+0wBA==:741a8bc609b398aaec0685e5aefb682faf5129a66bd192f888d23bb642c18eea
"""Bounded selection from admitted source archives; no filesystem extraction."""

from __future__ import annotations

import bz2
from contextlib import ExitStack, contextmanager
import gzip
import lzma
from pathlib import Path
import tarfile

from production import MAX_FILE_BYTES, MAX_TOTAL_BYTES, relative

MAX_ARCHIVE_ENTRIES = 100_000
MAX_EXPANDED_BYTES = 3 * 1024 * 1024 * 1024
MAX_METADATA_BYTES = 64 * 1024
MAX_TOTAL_METADATA_BYTES = 8 * 1024 * 1024


@contextmanager
def open_archive(path_or_fileobj, *, maximum_expanded_bytes: int = MAX_EXPANDED_BYTES):
    """Bound stdlib decoding and hidden metadata before internal allocation.

    PAX/GNU headers are consumed before tarfile yields a logical member. Count
    their standard parsed headers too, and limit their size before tarfile reads
    the body. No archive fields are parsed here.
    """
    with ExitStack() as stack:
        raw = (stack.enter_context(open(path_or_fileobj, "rb"))
               if isinstance(path_or_fileobj, (str, Path)) else path_or_fileobj)
        position = raw.tell()
        magic = raw.read(6)
        raw.seek(position)
        if magic.startswith(b"\x1f\x8b"):
            decoded = stack.enter_context(gzip.GzipFile(fileobj=raw))
        elif magic.startswith(b"\xfd7zXZ\x00"):
            decoded = stack.enter_context(lzma.LZMAFile(raw))
        elif magic.startswith(b"BZh"):
            decoded = stack.enter_context(bz2.BZ2File(raw))
        else:
            decoded = raw

        class BoundedReader:
            used = 0

            def read(self, size):
                remaining = maximum_expanded_bytes - self.used
                data = decoded.read(min(size, remaining + 1) if size >= 0 else remaining + 1)
                self.used += len(data)
                if self.used > maximum_expanded_bytes:
                    raise ValueError("archive decoded bytes exceed their expansion bound")
                return data

        headers, metadata_bytes = 0, 0

        class BoundedInfo(tarfile.TarInfo):
            # tarfile's member-processing extension point sees both ordinary
            # and recursive metadata headers before their bodies are allocated.
            # Overriding public frombuf alone does not guard Python 3.14 reads.
            def _proc_member(self, archive):
                nonlocal headers, metadata_bytes
                headers += 1
                if headers > MAX_ARCHIVE_ENTRIES:
                    raise ValueError("archive header count exceeds its expansion bound")
                metadata = (tarfile.XHDTYPE, tarfile.XGLTYPE, tarfile.SOLARIS_XHDTYPE,
                            tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK)
                if self.type in metadata:
                    metadata_bytes += self.size
                    if self.size > MAX_METADATA_BYTES or metadata_bytes > MAX_TOTAL_METADATA_BYTES:
                        raise ValueError("archive metadata exceeds its bound")
                if self.size < 0:
                    raise ValueError("archive has a negative member size")
                return super()._proc_member(archive)

            def _proc_sparse(self, *args):
                raise ValueError("sparse source archives are outside the selection contract")

            _proc_gnusparse_00 = _proc_sparse
            _proc_gnusparse_01 = _proc_sparse
            _proc_gnusparse_10 = _proc_sparse

        yield stack.enter_context(tarfile.open(fileobj=BoundedReader(), mode="r|",
                                               stream=True, tarinfo=BoundedInfo))


def read_members(path_or_fileobj, names: set[str], *,
                 maximum_member_bytes: int = MAX_FILE_BYTES,
                 maximum_selected_bytes: int = MAX_TOTAL_BYTES) -> dict[str, bytes]:
    """Read exact regular members, rejecting duplicates, links and missing names.

    Unselected upstream entries are never materialized. Full traversal catches a
    later duplicate and bounds expansion even when the selection appeared early.
    The caller verifies the archive's admitted size/hash before calling this.
    """
    if not names or len(names) > 1024:
        raise ValueError("archive selection must be finite and nonempty")
    for name in names:
        relative(name)
    selected, expanded, used = {}, 0, 0
    with open_archive(path_or_fileobj, maximum_expanded_bytes=MAX_EXPANDED_BYTES) as archive:
        for count, member in enumerate(archive, 1):
            expanded += member.size
            if (count > MAX_ARCHIVE_ENTRIES or member.size < 0 or
                    expanded > MAX_EXPANDED_BYTES):
                raise ValueError("archive expansion exceeds its bound")
            if member.name not in names:
                continue
            if member.name in selected or not member.isfile():
                raise ValueError("selected archive member is duplicate or not regular")
            used += member.size
            if member.size > maximum_member_bytes or used > maximum_selected_bytes:
                raise ValueError("selected archive bytes exceed their bound")
            with archive.extractfile(member) as stream:
                data = stream.read(member.size + 1)
            if len(data) != member.size:
                raise ValueError("selected archive member is truncated")
            selected[member.name] = data
    if selected.keys() != names:
        raise ValueError("archive is missing selected members")
    return selected
