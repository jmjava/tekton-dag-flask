from app import app


def test_root_endpoint():
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.data == b"tekton-dag-flask"
