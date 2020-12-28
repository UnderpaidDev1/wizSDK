# Native imports
import ctypes
import ctypes.wintypes

# Third-party imports
import numpy as np
import cv2

# Custom imports
from .window import Window

user32 = ctypes.WinDLL("user32.dll")
gdi32 = ctypes.WinDLL("gdi32.dll")

# Converted to python from https://docs.microsoft.com/en-us/windows/win32/gdi/capturing-an-image
# by Starrfox


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int),
        ("biHeight", ctypes.c_int),
        ("biPlanes", ctypes.c_short),
        ("biBitCount", ctypes.c_short),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


class BITMAP(ctypes.Structure):
    _fields_ = [
        ("bmType", ctypes.c_long),
        ("bmWidth", ctypes.c_long),
        ("bmHeight", ctypes.c_long),
        ("bmWidthBytes", ctypes.c_long),
        ("bmPlanes", ctypes.wintypes.WORD),
        ("bmBitsPixel", ctypes.wintypes.WORD),
        ("bmBits", ctypes.wintypes.LPVOID),
    ]


class DeviceContext(Window):
    def __init__(self, handle):
        super().__init__(handle)
        self.window_handle = handle

    def get_image(self, region=None):
        _, _, w, h = self.get_rect()
        x, y = 0, 0

        if region and len(region) == 4:
            x, y, w, h = region

        # Get devices context
        wDC = user32.GetWindowDC(self.window_handle)
        # Where we will move the pixels to
        mDC = gdi32.CreateCompatibleDC(wDC)

        gdi32.SetStretchBltMode(wDC, 4)
        # Create empty bitmap
        mBM = gdi32.CreateCompatibleBitmap(wDC, w, h)

        # Select wDC into bitmap
        gdi32.SelectObject(mDC, mBM)

        gdi32.BitBlt(mDC, 0, 0, w, h, wDC, x, y, 0x00CC0020)

        bitmap = BITMAP()

        # Don't know what that does
        gdi32.GetObjectA(mBM, ctypes.sizeof(BITMAP), ctypes.byref(bitmap))

        bi = BITMAPINFOHEADER()
        bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bi.biWidth = bitmap.bmWidth
        bi.biHeight = bitmap.bmHeight
        bi.biPlanes = 1
        bi.biBitCount = 32
        bi.biCompression = 0
        bi.biSizeImage = 0
        bi.biXPelsPerMeter = 0
        bi.biYPelsPerMeter = 0
        bi.biClrUsed = 0
        bi.biClrImportant = 0

        bitmap_size = (
            (
                (bitmap.bmWidth * bitmap.bmBitsPixel + bitmap.bmBitsPixel - 1)
                // bitmap.bmBitsPixel
            )
            * 4
            * bitmap.bmHeight
        )

        bitmap_buffer = (ctypes.c_char * bitmap_size)()

        gdi32.GetDIBits(
            wDC,
            mBM,
            0,
            bitmap.bmHeight,
            ctypes.byref(bitmap_buffer),
            ctypes.byref(bi),
            0,
        )

        img = np.frombuffer(bitmap_buffer.raw, dtype="uint8")
        img = img.reshape((bitmap.bmHeight, bitmap.bmWidth, 4))
        img = np.flip(img, 0)
        # Remove the alpha channel
        img = img[:, :, :3]
        return img

    def get_pixel(self, x, y):
        hDC = user32.GetWindowDC(self.window_handle)
        rgb = gdi32.GetPixel(hDC, x, y)
        user32.ReleaseDC(self.window_handle, hDC)
        r = rgb & 0xFF
        g = (rgb >> 8) & 0xFF
        b = (rgb >> 16) & 0xFF
        return (r, g, b)

    def screenshot(self, name, region=None):
        image = self.get_image(region=region)
        cv2.imshow("mat", image)
        cv2.waitKey(0)
        cv2.imwrite(name, image)

    def pixel_matches_color(self, xy, expected_rgb, tolerance=0):
        pixel = self.get_pixel(*xy)
        if len(pixel) == 3 or len(expected_rgb) == 3:  # RGB mode
            r, g, b = pixel[:3]
            exR, exG, exB = expected_rgb[:3]
            return (
                (abs(r - exR) <= tolerance)
                and (abs(g - exG) <= tolerance)
                and (abs(b - exB) <= tolerance)
            )
        else:
            assert (
                False
            ), f"Color mode was expected to be length 3 (RGB), but pixel is length {len(pix)} and expected_RGB is length { len(expected_rgb)}"


def to_cv2_img(data):
    if type(data) is str:
        # It's a file name
        # cv2.IMREAD_COLOR ignores alpha channel, loads only rgb
        img = cv2.imdecode(np.fromfile(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            print(f"Unable to find `{data}`")
        return img

    elif type(data) is np.ndarray:
        # It's a np array
        return data

    return None


def match_image(largeImg, smallImg, threshold=0.1, debug=False):
    """ 
    Finds smallImg in largeImg using template matching 
    Adjust threshold for the precision of the match (between 0 and 1, the lowest being more precise)
    Returns false if no match was found with the given threshold
    """

    method = cv2.TM_SQDIFF_NORMED

    small_image = to_cv2_img(smallImg)
    large_image = to_cv2_img(largeImg)

    if (small_image is None) or (large_image is None):
        print("Error: large_image or small_image is None")
        return False

    w, h = small_image.shape[:-1]

    if debug:
        print("large_image:", large_image.shape)
        print("small_image:", small_image.shape)

    try:
        result = cv2.matchTemplate(small_image, large_image, method)
    except cv2.error as e:
        # The image was not found. like, not even close. :P
        print(e)
        return False

    # We want the minimum squared difference
    mn, _, mnLoc, _ = cv2.minMaxLoc(result)

    if mn >= threshold:
        if debug:
            cv2.imshow("output", large_image)
            cv2.waitKey(0)
        return False

    # Extract the coordinates of our best match
    x, y = mnLoc

    if debug:
        print(f"Match at ({x}, {y}) relative to region")
        # Draw the rectangle:
        # Get the size of the template. This is the same size as the match.
        trows, tcols = small_image.shape[:2]

        # If I don't call this a get a TypeError :P
        large_image = np.array(large_image)
        # Draw the rectangle on large_image
        cv2.rectangle(large_image, (x, y), (x + tcols, y + trows), (0, 0, 255), 2)

        # Display the original image with the rectangle around the match.
        cv2.imshow("output", large_image)

        # The image is only displayed if we call this
        cv2.waitKey(0)

    # Return coordinates to center of match
    return (x + (w * 0.5), y + (h * 0.5))

