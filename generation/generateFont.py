#!/usr/bin/python3

from PIL import ImageFont, Image
import struct
import argparse
import logging

parser = argparse.ArgumentParser()
parser.add_argument("-f", "--font", default="LiberationSans-Regular.ttf", help="Fontfile Default:LiberationSans-Regular.ttf")
parser.add_argument("-s", "--size", type=int, default=20, help="Fontsize Default:20")
parser.add_argument("-v", "--verbose", action='count', default=0)

args = parser.parse_args()

logging.basicConfig(format="%(asctime)s <%(name)-50s> [%(levelname)-10s] %(message)s")
logging.addLevelName(logging.DEBUG - 1, "DEBUG - 1")
logging.addLevelName(logging.DEBUG - 2, "DEBUG - 2")
logging.addLevelName(logging.DEBUG - 3, "DEBUG - 3")
logger = logging.getLogger('Font Generator')
logger.setLevel(logging.DEBUG - 3)


filename = args.font
fontsize = args.size


fName, fSuffix = filename.split(".")


font = ImageFont.truetype(font = filename, size = fontsize)

fontInfo = {
    "size" : fontsize,
    "file" : filename,
    "family" : font.font.family,
    "style" : font.font.style,
    "fileName" : fName,
    "fileSuffix" : fSuffix,
    "filePath" : font.path
}


print(fontInfo)



#print(h)
def font2bitBuffer(font, char):
    w, h = font.getsize(char)
    h = font.font.height

    x, y = font.getoffset(char)
    mask = font.getmask(char)

    cw, ch = mask.size

    print(cw, ch, x, y, w,h)

    bitBuffer = [[0]*h for i in range(w)]
    for i in range(ch):
        for j in range(cw):
            try:
                bitBuffer[j+x][h-(i+y)] = 1 if mask.getpixel((j, i)) > 100 else 0
            except IndexError:
                pass
    return(bitBuffer)

def printBitBuffer(bitBuffer):
    w = len(bitBuffer)
    h = len(bitBuffer[0])
    print("* " + "* " * w + "*")
    for i in range(h):
        print("* ", end="")
        for j in range(w):
            print("# " if bitBuffer[j][i] else "  ", end="")
        print("*")
    print("* " + "* " * w + "*")


def bitBuffer2bytesList(bitBuffer):
    byteList = []

    for col in bitBuffer:
        accumolatur = 0
        position = 0
        for pix in col:
            if pix:
                accumolatur |= 1
            accumolatur <<= 1
            position += 1
            #print(position)
            if position > 7:
                byteList += [accumolatur >> 1]
                accumolatur = 0
                position = 0
        if position > 0:
            accumolatur <<= 8 - position
            byteList += [accumolatur &0xff]
    return(byteList)

def bytesList2bitBuffer(data, h, w):
    bitBuffer = [[0]*h for i in range(w)]
    bpos = 0
    for col in range(w):
        position = 0
        for pix in range(h):
            if data[bpos] & (0x80 >> position):
                bitBuffer[col][pix] = 1
            position += 1
            if position > 7:
                bpos += 1
                position = 0
        bpos += 1
    return bitBuffer

def rleDecompress(rle):
    data = []
    i = 0
    #print(len(rle))
    while i < len(rle):
        n = struct.unpack_from("<b", rle, i)[0]
        #print(n)
        if n < 0:
            d = struct.unpack_from("<B", rle, i + 1)[0]
            #print("R", d, n)
            for j in range(-n):
                data += [d]
            i += 2
        else:
            for j in range(n):
                d = struct.unpack_from("<B", rle, i + j + 1)[0]
                #print("D", d)
                data += [d]
            i += n + 1
    #print(len(data), data)
    return data
            

def lreComress(l):
    lastVal = l[0]
    sameCount = 0
    diffCount = 0

    rle = []

    diffGroup = []

    for b in l:
        if b == lastVal:
            if diffCount:
                rle += [diffCount - 1]
                sameCount += 1
                rle += diffGroup[:-1]
                diffGroup = []
                diffCount = 0
            if sameCount < 120:
                sameCount += 1
            else:
                rle += [-sameCount]
                rle += [lastVal]
                sameCount = 0
        else:
            if sameCount:
                rle += [-sameCount]
                rle += [lastVal]
                sameCount = 0
            if diffCount < 120:
                lastVal = b
                diffGroup += [b]
                diffCount += 1
            else:
                rle += diffGroup[:-1]
                diffGroup = []
                diffCount = 0
    if diffCount:
        rle += [diffCount]
        rle += diffGroup
    if sameCount:
        rle += [-sameCount]
        rle += [lastVal]
    return(rle)


def packSingleMetadatum(key, value, hasNext):
    encKey = str(key).encode("utf8")
    encVal = str(value).encode("utf8")
    nextOffset = len(encKey) + len(encVal) + 12 if hasNext else 0
    header = struct.pack("<iii", nextOffset, len(encKey), len(encVal))
    return(header + encKey + encVal)

def packMetadata(metadata):
    lastId = len(metadata)
    data = b''
    for id, key in enumerate(metadata):
        data += packSingleMetadatum(key, metadata[key], id < lastId - 1)
    return(data)

"""
struct RLEFontGlyph_s
{
    int32_t length; // length of data excluding padding
    uint8_t width; // width of the glyph in pixels
    uint8_t flags; // 0x80 == rleCompressed
    uint8_t glyphData[]; // padded to make length of RLEFontGlyph_s 32bit aligned
};
"""

def packSingleGlyph(char, font):
    bb = font2bitBuffer(font, char)
    raw = bitBuffer2bytesList(bb)
    rle = lreComress(raw)
    flags = 0
    if len(rle) < len(raw):
        length = len(rle)
        glyphData = bytes()
        for b in rle:
            if b <= 0:
                glyphData += struct.pack("<b", b)
            else:
                glyphData += struct.pack("<B", b)
        flags |= 0x80
    else:
        length = len(raw)
        glyphData = bytes(raw)
    width = len(bb)
    header = struct.pack("<iBB", length, width, flags)
    data = header + glyphData
    #print(glyphData)
    return data + bytes(len(data) % 4)


"""
struct RLEFontGlyphTable_s
{
    int32_t nextOffset;
    int32_t start; // ordinal of first glyph
    int32_t end;   // ordinal of last glyph
    int32_t glyphDataOffset;
    int32_t glyphOffsetsAndData[];
};
"""
def packGlyphTable(font, start, end, hasNext):

    
    glyphOffsets = bytes()
    glyphData = bytes()
    for char in range(start, end + 1):
        glyph = packSingleGlyph(chr(char), font)
        glyphOffsets += struct.pack("<i", len(glyphData))
        glyphData += glyph 
    data_offset = struct.pack("<i", len(glyphOffsets) + 16)
    nextOffset = (16 + len(glyphOffsets) + len(glyphData)) if hasNext else 0
    padSize = (4 - (nextOffset % 4)) if nextOffset else 0
    nextOffset += padSize
    header = struct.pack("<iii", nextOffset, start, end)
    data = header + data_offset + glyphOffsets + glyphData + bytes(padSize)
    return(data)

"""
struct RLEFont_s
{
    int32_t height;
    int32_t metadataOffset;
    int32_t glyphTableOffset;
    uint8_t data[];             // length Bytes
};
"""
def packFontFile(font, fontInfo):

    packedMetadata = packMetadata(fontInfo)
    height = font.font.height # heigth of glyphs
    metadataOffset = 0
    glyphTableOffset = metadataOffset + len(packedMetadata)
    padSize = 4 - (glyphTableOffset % 4)
    glyphTableOffset += padSize
    header = struct.pack("<iii", height, metadataOffset, glyphTableOffset)
    data = header + packedMetadata + bytes(padSize) + packGlyphTable(font, 0x20, 0x7E, True) + packGlyphTable(font, 0xA1, 0xFE, False)
    return(data)





def unpackMetadata(fontFile):
    nextOffset, lenKey, lenVal = struct.unpack("<iii", fontFile[:12])
    keyStart = 12
    valStart = keyStart+lenKey
    key = fontFile[keyStart:keyStart+lenKey].decode("utf8")
    val = fontFile[valStart:valStart+lenVal].decode("utf8")
    print("Next Metadatum at Offset %3d key=%-20s val=%s" % (nextOffset, key, val))
    if nextOffset:
        unpackMetadata(fontFile[nextOffset:])

def unpackGlyphTable(fontFile, height):
    nextOffset, start, end, dataOffset = struct.unpack_from("<iiii", fontFile)
    print("Table from %3i to %3i. Next offset %i. Data at %i" % (start, end, nextOffset, dataOffset))
    for char in range(start, end + 1):
        offset = struct.unpack_from("<i", fontFile, (char - start)*4 + 16)[0]
        length = struct.unpack_from("<i", fontFile, dataOffset + offset)[0]
        width, flags = struct.unpack_from("<BB", fontFile, dataOffset + offset + 4)
        dataStart = dataOffset + offset + 6
        data = fontFile[dataStart:dataStart + length]
        print("Glyph for %3i '%c' offset %5i length %3i width %2i, flags %02X" % (char, char, offset, length, width, flags))
        print(data)
        if flags & 0x80:
            #print(data)
            data = rleDecompress(data)    
        bb = bytesList2bitBuffer(data, height, width)
        #print(data)
        #printBitBuffer(bb)
    if nextOffset > 0:
        unpackGlyphTable(fontFile[nextOffset:], height)


def unpackFontFile(fontFile):
     height, metadataOffset, glyphTableOffset = struct.unpack("<iii", fontFile[:12])
     print("Height: %d" % height)
     print("Metadata at Offset %d" % metadataOffset)
     print("Glyph Table at Offset %d" % glyphTableOffset)
     unpackMetadata(fontFile[12+metadataOffset:])
     unpackGlyphTable(fontFile[12+glyphTableOffset:], height)

char = "Ä"

fontFileImage = packFontFile(font, fontInfo)

print("\nSize of Font File: %d Bytes\n\n" % len(fontFileImage))

unpackFontFile(fontFileImage)

with open("test.bin", "wb") as f:
    f.write(fontFileImage)
    f.flush()
    f.close()

#print(l, len(l))
#print(rle, len(rle))
