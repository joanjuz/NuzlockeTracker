"""OBS high-fidelity sprite pipeline: native RGBA, WebP animation, and aliases."""
import io
import tempfile
import threading
import unittest
from pathlib import Path
from PIL import Image, features
from tracker.layout_export import (
    PartyLayoutExporter, custom_media_names, normalize_custom_sprite,
    png_to_gif, validate_png, gif_to_outputs)
from tracker.overlay import OverlayManager, DEFAULT, validated_settings


def raster(fmt, size=(50, 55), color=(100, 130, 210, 140)):
    image=Image.new('RGBA',size,color)
    output=io.BytesIO()
    if fmt in ('JPEG','BMP'):
        image=image.convert('RGB')
    image.save(output,format=fmt)
    return output.getvalue()


def animated_webp():
    images=[Image.new('RGBA',(40,32),(200,10,40,120)),
            Image.new('RGBA',(40,32),(10,150,40,230))]
    output=io.BytesIO()
    images[0].save(output,format='WEBP',save_all=True,append_images=images[1:],
                   duration=[80,120],loop=0,lossless=True)
    return output.getvalue()


class FakeService:
    def __init__(self, mon):
        self.party=[mon]+[None]*5
        self.condition=threading.Condition()
        self.deaths={}
    def snapshot(self):
        return {'party':self.party,'progress':{'deaths':self.deaths},'stale':False}


class HDOBS(unittest.TestCase):
    def test_safe_aliases_and_regional_priority(self):
        variants=custom_media_names({'species_id':25,'species':'Pikachu','form':0},25)
        for filename in ('25.png','025.png','pikachu.webp','Pikachu.png'.lower()):
            self.assertIn(filename,variants)
        self.assertLess(variants.index('25.gif'),variants.index('25.png'))
        alola=custom_media_names({'species_id':37,'species':'Vulpix','form':1},10103)
        self.assertIn('37-alola.png',alola)
        self.assertIn('10103.webp',alola)
        shiny=custom_media_names({'species_id':25,'species':'Pikachu','shiny':True},25)
        self.assertIn('25-shiny.webp',shiny)
        self.assertNotIn('../25.png',variants)

    def test_static_webp_jpg_and_bmp_become_alpha_png(self):
        for extension,format in (('.webp','WEBP'),('.jpg','JPEG'),('.bmp','BMP')):
            with self.subTest(format=format):
                data=raster(format)
                out,kind=normalize_custom_sprite(data,extension)
                self.assertEqual(kind,'png')
                with Image.open(io.BytesIO(out)) as image:
                    self.assertEqual(image.size,(50,55))
                    self.assertEqual(image.mode,'RGBA')

    def test_real_high_resolution_rgba_is_not_quantized_in_overlay(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            custom=root/'sprites_personalizados'
            custom.mkdir()
            asset=raster('PNG',(1080,720),(40,110,205,126))
            (custom/'PiKaChU.PNG').write_bytes(asset)
            service=FakeService({'species_id':25,'species':'Pikachu','form':0})
            exporter=PartyLayoutExporter(service,root/'layout',
                                         cache_dir=root/'cache',custom_dir=custom)
            try:
                exporter.refresh()
                file=exporter.directory/'pokemon_1.png'
                self.assertEqual(file.read_bytes(),asset)
                self.assertEqual((exporter.directory/'pokemon_1.media').read_text(),'png')
                with Image.open(file) as output:
                    self.assertEqual(output.size,(1080,720))
                    self.assertEqual(output.getpixel((0,0)),(40,110,205,126))
                # Legacy GIF is a separate 512px thumbnail.
                with Image.open(exporter.directory/'pokemon_1.gif') as gif:
                    self.assertLessEqual(gif.width,512)
                manager=OverlayManager(service,root/'runtime',exporter.directory)
                party=manager.public_state()['party']
                self.assertEqual(party[0]['image_format'],'png')
                self.assertNotEqual(party[0]['image_rev'],'0')
            finally:
                exporter.close()

    @unittest.skipUnless(features.check('webp_anim'),'Pillow WebP animation not enabled')
    def test_animated_webp_is_preserved_in_webp_not_reencoded_as_gif(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            custom=root/'sprites_personalizados'
            custom.mkdir()
            original=animated_webp()
            (custom/'025.webp').write_bytes(original)
            service=FakeService({'species_id':25,'form':0,'origin_version':33,
                                 'encryption_constant':50})
            exporter=PartyLayoutExporter(service,root/'layout',custom_dir=custom)
            try:
                exporter.refresh()
                self.assertEqual((exporter.directory/'pokemon_1.media').read_text(),'webp')
                file=exporter.directory/'pokemon_1.webp'
                with Image.open(file) as animated:
                    self.assertEqual(animated.n_frames,2)
                manager=OverlayManager(service,root/'runtime',exporter.directory)
                self.assertEqual(manager.public_state()['party'][0]['image_format'],'webp')
                service.deaths['33:50']={'pokemon':service.party[0]}
                exporter.refresh()
                with Image.open(file) as gray:
                    self.assertEqual(gray.n_frames,2)
                    for i in range(2):
                        gray.seek(i)
                        r,g,b,a=gray.convert('RGBA').getpixel((5,5))
                        self.assertEqual(r,g)
                        self.assertEqual(g,b)
                self.assertEqual((custom/'025.webp').read_bytes(),original)
            finally:
                exporter.close()

    def test_visual_controls_are_strict_and_defaults_are_safe(self):
        config=validated_settings({**DEFAULT,'render_scale':4,'sprite_scaling':'smooth',
              'sprite_shadow':True,'sprite_padding':12,'hp_animation_ms':400})
        self.assertEqual(config['render_scale'],4)
        for change in ({'render_scale':5},{'render_scale':0},
                       {'sprite_scaling':'smooth<script>'},
                       {'sprite_shadow':'on'}, {'sprite_padding':-1},
                       {'hp_animation_ms':2000}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                validated_settings(change)

    def test_unsupported_and_corrupt_image_rejected(self):
        with self.assertRaises(ValueError):
            normalize_custom_sprite(b'<svg/>','.svg')
        with self.assertRaises(ValueError):
            normalize_custom_sprite(b'GIF89aBROKEN','.webp')
        with self.assertRaises(ValueError):
            normalize_custom_sprite(b'x'*(8_000_001),'.png')
