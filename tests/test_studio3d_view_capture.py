import hashlib
import io
import unittest
from PIL import Image
from tools.studio3d_view_control import png_reference


class CaptureReferenceTests(unittest.TestCase):
    def test_png_preserves_decoded_jpeg_pixels(self):
        source = Image.new('RGB', (37, 29))
        source.putdata([(i % 256, (i * 3) % 256, (i * 7) % 256) for i in range(37 * 29)])
        encoded = io.BytesIO()
        source.save(encoded, format='JPEG', quality=75)
        raw = encoded.getvalue()
        png, pixel_hash = png_reference(raw)
        with Image.open(io.BytesIO(raw)) as jpg, Image.open(io.BytesIO(png)) as result:
            self.assertEqual(result.format, 'PNG')
            self.assertEqual(result.size, jpg.size)
            self.assertEqual(result.tobytes(), jpg.convert('RGB').tobytes())
            self.assertEqual(pixel_hash, hashlib.sha256(result.tobytes()).hexdigest())

    def test_reject_wrong_format_and_oversized_capture(self):
        for fmt, size in [('PNG', (30, 20)), ('JPEG', (769, 100)), ('JPEG', (100, 513))]:
            data = io.BytesIO()
            Image.new('RGB', size).save(data, format=fmt)
            with self.assertRaises(ValueError):
                png_reference(data.getvalue())
