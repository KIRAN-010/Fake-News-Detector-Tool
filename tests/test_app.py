import pytest
from app import app, analyze, normalize_domain, source_analysis

@pytest.fixture
def client():
    return app.test_client()

def test_valid_analysis_is_deterministic(client):
    assert client.get('/').status_code == 200
    assert client.get('/api/health').json == {'status': 'ok'}
    data = {'text': 'The council published its annual budget report for public review.', 'source': 'https://www.reuters.com/world'}
    first = client.post('/api/analyze', json=data)
    assert first.status_code == 200
    assert first.json == client.post('/api/analyze', json=data).json
    assert first.json['source']['domain'] == 'reuters.com'

@pytest.mark.parametrize('data', [[], [1], None, True, 'hello', {'text': 123}, {'text': ['text']}, {'text': 'x' * 25, 'source': None}, {'text': 'short'}])
def test_json_shape_and_types(client, data):
    assert client.post('/api/analyze', json=data).status_code in (400, 415)

def test_malformed_and_non_json(client):
    assert client.post('/api/analyze', data='{', content_type='application/json').status_code == 400
    assert client.post('/api/analyze', data='hello').status_code == 415

def test_limits_and_bad_sources(client):
    assert client.post('/api/analyze', json={'text': 'x' * 20001}).status_code == 413
    assert client.post('/api/analyze', json={'text': 'x' * 150000}).status_code == 413
    for source in ['ftp://reuters.com', 'https://[broken', 'a b.com', 'https://user@reuters.com', 'https://reuters.com:bad']:
        assert client.post('/api/analyze', json={'text': 'x' * 25, 'source': source}).status_code == 400

def test_domain_spoofing():
    assert source_analysis('https://reuters.com.evil.example')['score'] == 50
    assert source_analysis('https://evil.example/reuters.com')['score'] == 50
    assert source_analysis('https://news.reuters.com')['score'] == 90
    assert normalize_domain('WWW.REUTERS.COM.') == 'reuters.com'

def test_false_claim_wording_does_not_claim_context_verification():
    r = analyze('Researchers reject the claim that vaccines cause autism and explain the evidence.')
    assert r['fact_check']['known_false_claim_pattern']
    assert 'review context' in r['verdict']
    assert r['confidence'] == 'Low'

def test_sensational_punctuation():
    assert analyze('BREAKING!!! A sensational story is circulating online.')['language']['sensational_count'] == 1
