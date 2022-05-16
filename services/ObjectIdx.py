# git has two versions where the index files are different
# see https://git-scm.com/docs/pack-format for the construction of index object

import io
import struct


def createObjectIdx(filepath):
    """Create the object of pack index according to the filepath
    https://git-scm.com/docs/pack-format
    """
    with io.open(filepath, "rb") as f:
        content = f.read()
        # A 4-byte magic number \377tOc which is an unreasonable fanout[0] value.
        if content[:4] == b"\377tOc":
            # A 4-byte version number (= 2)
            version = int(content[4:8].hex(), 16)
            if version == 2:
                return ObjectIdxV2(filepath, content)
            else:
                raise KeyError(
                    "Version is not supported {version}".format(
                        version=version
                    )
                )
        else:
            # The first version of the index file did not have any header information
            return ObjectIdxV1(filepath, content)


class ObjectIdx(object):
    def __init__(self, filepath, content):
        """attributes included:
        filepath, content
        """
        self.filepath = filepath
        self.content = content
        self.object_num = None
        self.object_names = None
        self.object_offsets = None


class ObjectIdxV1(ObjectIdx):
    def __init__(self, filepath, content):
        """Add three attributes: object_num, object_names, object_offsets"""
        super().__init__(filepath, content)
        offset_index = 0  # iterate the file from the very beginning
        # A 256-entry fan-out table.
        self.object_num = int(
            self.content[offset_index : offset_index + 256 * 4][-4:].hex(), 16
        )
        offset_index += 256 * 4
        # The header is followed by sorted 24-byte entries, one entry per object in the pack. Each entry is:
        # 4-byte network byte order integer, recording where the object is stored in the packfile as the offset from the beginning.
        # one object name of the appropriate size.
        self.object_names, self.object_offsets = self.extract_entries(
            self.content[offset_index : offset_index + 24 * self.object_num]
        )

    def extract_entries(self, content_entries):
        object_names = []
        object_offsets = []
        for i in range(0, len(content_entries), 24):
            content_entry = content_entries[i : i + 24]
            object_offset = int(content_entry[:4].hex(), 16)
            object_name = content_entry[4:].hex()
            object_names.append(object_name)
            object_offsets.append(object_offset)
        return object_names, object_offsets


class ObjectIdxV2(ObjectIdx):
    def __init__(self, filepath, content):
        """Add three attributes: object_num, object_names, object_offsets"""
        super().__init__(filepath, content)
        offset_index = 0  # iterate the file from the very beginning
        # A 4-byte magic number \377tOc which is an unreasonable fanout[0] value.
        offset_index += 4
        # A 4-byte version number (= 2)
        offset_index += 4
        # A 256-entry fan-out table just like v1.
        self.object_num = int(
            self.content[offset_index : offset_index + 256 * 4][-4:].hex(), 16
        )
        offset_index += 256 * 4
        # A table of sorted object names. These are packed together without offset values to reduce the cache footprint of the binary search for a specific object name.
        self.object_names = self.extract_names(
            self.content[offset_index : offset_index + 20 * self.object_num]
        )
        offset_index += 20 * self.object_num
        # A table of 4-byte CRC32 values of the packed object data. This is new in v2 so compressed data can be copied directly from pack to pack during repacking without undetected data corruption.
        offset_index += 4 * self.object_num
        # A table of 4-byte offset values (in network byte order). These are usually 31-bit pack file offsets, but large offsets are encoded as an index into the next table with the msbit set.
        # A table of 8-byte offset entries (empty for pack files less than 2 GiB). Pack files are organized with heavily used objects toward the front, so most object references should not need to refer to this table.
        self.object_offsets = self.extract_object_offsets(offset_index)

    def extract_names(self, content_names):
        return [
            content_names[i : i + 20].hex()
            for i in range(0, len(content_names), 20)
        ]

    def extract_object_offsets(self, offset_offset_index):
        """offset_offset_index represents the offset of object offsets in the idx file"""
        large_offset_offset_index = offset_offset_index + self.object_num * 4
        result = []
        small_offset_content = self.content[
            offset_offset_index:large_offset_offset_index
        ]
        for i in range(0, len(small_offset_content), 4):
            offset = struct.unpack_from(">L", small_offset_content, i)[0]
            if offset >= 2**31:
                offset = struct.unpack_from(
                    ">Q",
                    self.content,
                    large_offset_offset_index + (offset & (2**31 - 1)) * 8,
                )[0]
            result.append(offset)
        return result
