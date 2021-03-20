# Native imports
import ctypes
import ctypes.wintypes
from os import path

# Third-party imports
import numpy as np
import cv2

# Custom imports
from .window import Window


user32 = ctypes.WinDLL("user32.dll")
gdi32 = ctypes.WinDLL("gdi32.dll")

# Converted to python from https://docs.microsoft.com/en-us/windows/win32/gdi/capturing-an-image
# by Starrfox


class _BITMAPINFOHEADER(ctypes.Structure):
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


least_gray = 0


class _BITMAP(ctypes.Structure):
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
    """
    Base class for accessing the Window's Device Context (pixels, image captures, etc..)
    """

    def __init__(self, handle):
        super().__init__(handle)
        self.window_handle = handle

    def get_image(self, region=None):
        """
        returns a byte array with the pixel data of the ``region`` from the ``window_handle`` window. ``region`` is relative to the ``window_handle`` window. If no ``region`` is specified, it will capture the entire window. If no ``window_handle`` is provided on initiation, monitor 1 is used as the context.
        
        Args:
            region: (x, y, width, height) tuple relative to the ``window_handle`` context. Defaults to None
            
        Returns:
            A 2d numpy array representing the pixel data of the captured region.
        """

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

        bitmap = _BITMAP()

        # If this function fails, we get a ZeroDevision error.
        bits_transfered = gdi32.GetObjectA(
            mBM, ctypes.sizeof(_BITMAP), ctypes.byref(bitmap)
        )
        # Account for the ZeroDevision error
        bits_transfered = 0
        while bits_transfered == 0:
          bits_transfered = gdi32.GetObjectA(
            mBM, ctypes.sizeof(_BITMAP), ctypes.byref(bitmap)
          )

        bi = _BITMAPINFOHEADER()
        bi.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
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

    def get_pixel(self, x, y) -> tuple:
        """
        Returns the (red, green, blue) channel's of the pixel at ``x``, ``y`` relative to the ``window_handle`` context.
        
        Args:
            x
            y
        
        Returns:
            (r, g, b) tuple
        """
        hDC = user32.GetWindowDC(self.window_handle)
        rgb = gdi32.GetPixel(hDC, x, y)
        user32.ReleaseDC(self.window_handle, hDC)
        r = rgb & 0xFF
        g = (rgb >> 8) & 0xFF
        b = (rgb >> 16) & 0xFF
        return (r, g, b)

    def screenshot(self, filename, region=None):
        """
        captures a screenshot of the provided ``region``, saves it to file as ``filename``.
        
        Args:
            filename: what to save to image as
            region: (x, y, width, height) tuple relative to the ``window_handle`` context. Defaults to None
        """
        image = self.get_image(region=region)
        cv2.imshow("mat", image)
        cv2.waitKey(0)
        cv2.imwrite(filename, image)

    def pixel_matches_color(self, xy, expected_rgb, tolerance=0):
        """
        gets the value of a pixel with ``get_pixel`` and checks it against ``expected_rgb``. Accepts ``tolerance`` amount of differences between the pixel and its expected value.
        """
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

    def is_gray_rect(self, region, threshold=25):
        """
        calculates if a ``(x, y, width, height)`` ``region`` is gray by iterating through all its pixels and calculating the difference between the channel with the lowest value, and the one with the highest value. Stops iterating if that value is greater than ``threshold``. Returns the highest of the values calculated.
        
        Args:
            region: (x, y, width, height) tuple relative to the ``window_handle`` context.
            threshold: difference allowed between highest channel and lowest channel to still be considered gray.
            
        Returns:
            the greatest difference between the highest channel and lowest channel.
        """
        # global least_gray
        least_gray = 0

        w, h = region[2:]
        img = self.get_image(region)

        gray = True

        # Check if all pixels in image are gray
        for x in range(h):
            if not gray:
                break

            for y in range(w):
                pixel = img[x][y]

                # Determine if a pixel is gray enough
                color = abs(int(min(*pixel)) - int(max(*pixel)))
                if color > least_gray:
                    least_gray = color

                if color > threshold:
                    gray = False
                    break

        return least_gray

    def locate_on_screen(
        self, match_img, region=None, *, threshold=0.1, debug=False, folder=None
    ):
        """
        Attempts to locate `match_img` in the Wizard101 window.
        pass a rect tuple `(x, y, width, height)` as the `region` argument to narrow 
        down the area to look for the image.
        Adjust `threshold` for the precision of the match (between 0 and 1, the lowest being more precise).
        Set `debug` to True for extra debug info
        
        Args:
            match_img: to image to locate, can be a file name or a numpy array
            region: (x, y, width, height) tuple relative to the ``window_handle`` context. Defaults to None
            theshold: precision of the match -- between 0 and 1, the lowest being more precise
            debug: set to True to show a pop up of the area that matched the image provided.
            folder: folder to look in. Overrides ``IMAGE_FOLDER`` default
            
        Returns:
            (x, y) tuple for center of match if found. False otherwise.
        
        """
        to_match = (
            path.join(folder or self._default_image_folder or "", match_img)
            if type(match_img) == str
            else match_img
        )
        match = match_image(
            self.get_image(region=region), to_match, threshold, debug=debug
        )

        if not match or not region:
            return match

        region_x, region_y = region[:2]
        x, y = match
        return x + region_x, y + region_y


def _to_cv2_img(data):
    if type(data) is str:
        # It's a file name
        # cv2.IMREAD_COLOR ignores alpha channel, loads only rgb
        img = cv2.imdecode(np.fromfile(data, dtype=np.uint8), cv2.IMREAD_COLOR)

        return img

    elif type(data) is np.ndarray:
        # It's a np array
        return data

    return None


def match_image(largeImg, smallImg, threshold=0.1, debug=False):
    """ 
    Finds smallImg in largeImg using template matching 
    Adjust threshold for the precision of the match (between 0 and 1, the lowest being more precise)
    
    Returns:
        tuple (x, y) of the center of the match if it's found, False otherwise.
    """

    method = cv2.TM_SQDIFF_NORMED

    small_image = _to_cv2_img(smallImg)
    large_image = _to_cv2_img(largeImg)

    if (small_image is None) or (large_image is None):
        print("Error: large_image or small_image is None")
        return False

    h, w = small_image.shape[:-1]

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
    return (x + (w // 2), y + (h // 2))

