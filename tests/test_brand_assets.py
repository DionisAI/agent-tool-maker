import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('build_brand_assets',Path(__file__).resolve().parents[1]/'scripts/build_brand_assets.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

def test_svg_only_shape_bytes_and_color():
    value=builder.image_svg(b'<svg viewBox="0 0 24 24" style="flex:none;line-height:1"><path fill="currentColor" d="M0 0h24v24z"/></svg>','FC682D')
    assert b'fill="#FC682D"' in value and b'style=' not in value
    assert b'xmlns="http://www.w3.org/2000/svg"' in value

@pytest.mark.parametrize('raw',[
    b'<!DOCTYPE svg><svg viewBox="0 0 1 1"/>',
    b'<svg viewBox="0 0 1 1"><script>alert(1)</script></svg>',
    b'<svg viewBox="0 0 1 1" onload="alert(1)"/>',
    b'<svg viewBox="0 0 1 1"><foreignObject/></svg>',
    b'<svg viewBox="0 0 1 1"><image href="https://evil.test/a"/></svg>',
    b'<svg viewBox="0 0 1 1"><path fill="url(https://evil.test/a)"/></svg>',
    b'<svg viewBox="0 0 1 1" style="background:url(https://evil.test/a)"/>',
    b'<svg viewBox="0 0 1 1"><use href="#shape"/></svg>',
    b'<svg/>',b'<html/>',b'',b'x'*120001,
])
def test_active_external_or_unbounded_svg_rejected(raw):
    with pytest.raises(ValueError):builder.image_svg(raw,'182C30')

def test_brand_color_rejects_css_injection():
    with pytest.raises(ValueError):builder.image_svg(b'<svg viewBox="0 0 1 1"/>','red;url(x)')
