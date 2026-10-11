from io import BytesIO

import ezdxf
import pytest

from cad_extractor.web import create_app


@pytest.fixture
def client():
    app=create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_demo_and_assets(client):
    assert client.get('/').status_code == 200
    assert client.get('/static/app.js').status_code == 200
    assert client.get('/api/status').json['max_upload_mb'] == 50
    data=client.get('/api/demo').json
    assert data['summary']['by_type']['CIRCLE'] == 3
    attrs=[a for e in data['entities'] for a in e.get('attributes',[])]
    assert any(a['tag']=='DRAWING_NO' and a['text']=='M-001' for a in attrs)


def test_upload_dxf_and_temp_cleanup(client,tmp_path,monkeypatch):
    doc=ezdxf.new('R2000')
    doc.modelspace().add_text('UPLOAD-101')
    path=tmp_path/'source.dxf'
    doc.saveas(path)
    from cad_extractor import web
    original=web.extract_drawing
    uploaded=[]
    def track_temp(path, **kwargs):
        uploaded.append(path)
        return original(path, **kwargs)
    monkeypatch.setattr(web,'extract_drawing',track_temp)
    response=client.post('/api/extract',data={'drawing':(BytesIO(path.read_bytes()),'../../source.dxf')})
    assert response.status_code == 200
    assert response.json['source']['filename']=='source.dxf'
    assert response.json['entities'][0]['text']=='UPLOAD-101'
    assert uploaded and not uploaded[0].exists()


def test_upload_failures(client):
    assert client.post('/api/extract').status_code == 400
    assert client.post('/api/extract',data={'drawing':(BytesIO(b'bad'),'bad.pdf')}).status_code == 400
    response=client.post('/api/extract',data={'drawing':(BytesIO(b'bad'),'bad.dxf')})
    assert response.status_code == 422
    assert 'Cannot read' in response.json['error']
    client.application.config['MAX_CONTENT_LENGTH']=10
    assert client.post('/api/extract',data={'drawing':(BytesIO(b'x'*100),'big.dxf')}).status_code == 413


def test_local_only_requests(client):
    assert client.get('/api/status',headers={'Host':'untrusted.example'}).status_code == 403
    assert client.post('/api/extract',headers={'Origin':'https://untrusted.example'}).status_code == 403
    assert client.post('/api/extract',headers={'Origin':'http://localhost'}).status_code == 400
