"""Run: python -m unittest discover -s tests -v"""
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_OUTPUT = tempfile.TemporaryDirectory()
os.environ["CAD_OUTPUT_DIR"] = _OUTPUT.name
from fastapi.testclient import TestClient
from build123d import import_step
from app.main import app
from app.templates import TEMPLATES, generate_shape, validate_dimensions
from app.vision import extract_part, VisionNotConfigured


def defaults(name):
    return {key: field.default for key, field in TEMPLATES[name]["fields"].items()}


class CADTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_all_templates_api_export_and_step_roundtrip(self):
        for name in TEMPLATES:
            with self.subTest(template=name):
                response = self.client.post('/api/generate', json={"part_type": name, "dimensions": defaults(name)})
                self.assertEqual(response.status_code, 200, response.text)
                result = response.json()
                self.assertTrue(result['validation']['valid'])
                step = self.client.get(result['step_url'])
                stl = self.client.get(result['stl_url'])
                self.assertEqual(step.status_code, 200)
                self.assertEqual(stl.status_code, 200)
                self.assertIn(b'ISO-10303-21', step.content[:100])
                path = Path(_OUTPUT.name) / result['job_id'] / 'part.step'
                shape = import_step(str(path))
                self.assertTrue(shape.is_valid)
                self.assertEqual(len(shape.solids()), 1)
                self.assertAlmostEqual(shape.volume, result['validation']['volume_mm3'], places=4)
                # Independently decode binary STL records and measure tessellated extents.
                count, = struct.unpack_from('<I', stl.content, 80)
                self.assertGreater(count, 0)
                self.assertEqual(len(stl.content), 84+50*count)
                points = []
                signed_volume = 0
                for i in range(count):
                    values = struct.unpack_from('<12fH', stl.content, 84+50*i)
                    a,b,c = values[3:6], values[6:9], values[9:12]
                    points.extend((a,b,c))
                    signed_volume += (a[0]*(b[1]*c[2]-b[2]*c[1]) + a[1]*(b[2]*c[0]-b[0]*c[2]) + a[2]*(b[0]*c[1]-b[1]*c[0]))/6
                self.assertAlmostEqual(abs(signed_volume)/shape.volume, 1, delta=.01)
                for axis, expected in enumerate(result['validation']['bbox_mm']):
                    measured = max(p[axis] for p in points)-min(p[axis] for p in points)
                    self.assertAlmostEqual(measured, expected, delta=.1)

    def test_scaled_dimensions(self):
        for name in TEMPLATES:
            for scale in (.6, 1.7):
                dims = {k:v*scale for k,v in defaults(name).items()}
                _, result = generate_shape(name, dims)
                self.assertTrue(result['valid'])

    def test_invalid_dimensions(self):
        cases = [('bushing', {'inner_diameter':31}), ('plate', {'edge_offset':1}),
                 ('plate', {'hole_diameter':30}), ('bracket', {'thickness':49}),
                 ('enclosure', {'thickness':30}), ('plate', {'length':-1}),
                 ('enclosure', {'height':float('nan')}), ('plate', {'length':float('inf')})]
        for name, updates in cases:
            with self.subTest(template=name, updates=updates):
                with self.assertRaises(ValueError):
                    validate_dimensions(name, {**defaults(name), **updates})
        with self.assertRaises(ValueError):
            validate_dimensions('plate', {})
        with self.assertRaises(ValueError):
            validate_dimensions('anything_else', {})
        response = self.client.post('/api/generate', json={"part_type":"enclosure", "dimensions":{**defaults('enclosure'), 'thickness':30}})
        self.assertEqual(response.status_code, 422)

    def test_unknown_files_are_not_accessible(self):
        self.assertEqual(self.client.get('/api/files/'+'0'*32+'/part.step').status_code, 404)
        self.assertEqual(self.client.get('/api/files/'+'0'*32+'/private.txt').status_code, 404)

    def test_static_assets_offline(self):
        for path in ('/', '/api/templates', '/api/health', '/static/app.js', '/static/viewer.js',
                     '/static/vendor/three.module.js', '/static/vendor/STLLoader.js', '/static/vendor/OrbitControls.js'):
            self.assertEqual(self.client.get(path).status_code, 200)

if __name__ == '__main__':
    unittest.main()
