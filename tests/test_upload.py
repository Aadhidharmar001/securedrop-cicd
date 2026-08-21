def test_upload_file(client):
    file_content = b"Hello SecureDrop!"

    response = client.post(
        "/files",
        files={
            "file": (
                "test.txt",
                file_content,
                "text/plain",
            )
        },
        params={
            "expires_in_hours": 1,
            "max_downloads": 3,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["filename"] == "test.txt"
    assert data["max_downloads"] == 3
    assert "share_token" in data
    assert "share_url" in data
    assert "expires_at" in data