import zlib, io, binascii
from utils import *


"""Define the macro of object types.
Ref: https://git-scm.com/docs/pack-format
"""
OBJ_COMMIT = 1
OBJ_TREE = 2
OBJ_BLOB = 3
OBJ_TAG = 4
OBJ_OFS_DELTA = 6
OBJ_REF_DELTA = 7

OBJ_TYPES = (OBJ_COMMIT, OBJ_TREE, OBJ_BLOB, OBJ_TAG, OBJ_OFS_DELTA, OBJ_REF_DELTA)
OBJ_UNDELTIFIED = (OBJ_COMMIT, OBJ_TREE, OBJ_BLOB, OBJ_TAG, OBJ_OFS_DELTA)
OBJ_DELTIFIED = (OBJ_OFS_DELTA, OBJ_REF_DELTA)


def createObjectPack(object_idx, filepath):
    """Create the object of pack according to the filepath and related idx object
    https://git-scm.com/docs/pack-format
    """
    readF = io.open(filepath, 'rb').read

    """How to parse pack file's header:
    `The first four bytes spell "PACK" and the next four bytes contain the version number – in our case, [0, 0, 0, 2]. The next four bytes tell us the number of objects contained in the pack.`

    How to get the object contents
    `The packfile starts with 12 bytes of meta-information and ends with a 20-byte checksum`
    """
    if readF(4) != b"PACK":
        raise AssertionError("Not a correct pack {filepath}".format(filepath=filepath))
    version = int(readF(4).hex(), 16)
    if version not in (2, 3):
        raise AssertionError("Not a correct pack, version error: {version}".format(version=version))
    
    pack_objects = []
    for i in range(object_idx.object_num):
        object_offset = object_idx.object_offsets[i]
        object_name = object_idx.object_names[i]
        object_pack = ObjectPack(filepath=filepath, object_offset=object_offset, object_name=object_name)
        pack_objects.append(object_pack)

    print("pause")

class ObjectPack(object):
    """Extract objects according to https://codewords.recurse.com/issues/three/unpacking-git-packfiles.
    And https://git-scm.com/docs/pack-format

    The header is followed by number of object entries, each of which looks like this:
    (undeltified representation)
    n-byte type and length (3-bit type, (n-1)*7+4-bit length)
    compressed data

    (deltified representation)
    n-byte type and length (3-bit type, (n-1)*7+4-bit length)
    base object name if OBJ_REF_DELTA or a negative relative
    offset from the delta object's position in the pack if this
    is an OBJ_OFS_DELTA object
    compressed delta data

    Observation: length of each object is encoded in a variable
    length format and is not constrained to 32-bit or anything.

    extract the following attributes:
    object_type, object_sha, object_chunks, pack_type[This may be a delta type], pack_size, object_offset
    """

    def __init__(self, filepath, object_offset, object_name):

        pack_file = io.open(filepath, 'rb')

        self.object_offset = object_offset

        self.object_name = object_name

        pack_file.seek(self.object_offset) # point to the object
        readF = pack_file.read

        msb_bytes = read_variable_length_bytes(readF)
        self.pack_type = (msb_bytes[0] >> 4) & 0x07

        """This document uses the following "size encoding" of non-negative integers: From each byte, the seven least significant bits are used to form the resulting integer. As long as the most significant bit is 1, this process continues; the byte with MSB 0 provides the last seven bits. The seven-bit chunks are concatenated. Later values are more significant.
        """
        self.pack_size = msb_bytes[0] & 0x0F
        for i, byte in enumerate(msb_bytes[1:]):
            self.pack_size += (byte & 0x7F) << ((i * 7) + 4)
        
        if self.pack_type == OBJ_OFS_DELTA:
            msb_bytes = read_variable_length_bytes(readF)
            base_object_offset = msb_bytes[0] & 0x7F
            for byte in msb_bytes[1:]:
                base_object_offset += 1 # 这里为什么要+1
                base_object_offset <<= 7
                base_object_offset += byte & 0x7F
            self.base_object_rel_offset = base_object_offset # the relative negative offset
        elif self.pack_type == OBJ_REF_DELTA:
            self.base_object = readF(20) # the name (sha value) of the base object
        else:
            # get the decompressed data
            self.object_type = self.pack_type
            self.object_chunks = self.read_zlib_chunks(readF=readF)
    

    def read_zlib_chunks(self, readF):
        """It turns out that zlib is pretty robust and will ignore any extra bytes added to the end of a valid zlib-compressed data stream.

        refer to https://gist.github.com/leonidessaguisagjr/594cd8fbbc9b18a1dde5084d981b8028 to solve the tree decompress error:
        In the case of a 'blob' or 'commit' object, a string is returned.
        In the case of a 'tree' object, a list of tuples is returned where
        each tuple contains the following: (filemode, filename, sha1)
        """
        contents = zlib.decompress(readF())
        if self.object_type in [OBJ_COMMIT, OBJ_BLOB]:
            result_contents = contents.decode()
        elif self.object_type == OBJ_TREE:
            result_contents = list()
            while contents != b'':
                filemode, contents = contents.split(b' ', maxsplit=1)
                filename, contents = contents.split(b'\x00', maxsplit=1)
                sha1, contents = contents[:20], contents[20:]
                filemode = filemode.decode()
                filename = filename.decode()
                sha1 = binascii.hexlify(sha1).decode()
                result_contents.append((filemode, filename, sha1))
        else:
            result_contents = contents
        return result_contents