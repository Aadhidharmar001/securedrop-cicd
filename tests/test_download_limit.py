def test_download_limit(client):
    file_content = b"Download limit test"

    # Upload file with maximum 3 downloads
    upload_response = client.post(
        "/files",
        files={
            "file": (
                "limit-test.txt",
                file_content,
                "text/plain",
            )
        },
        params={
            "expires_in_hours": 1,
            "max_downloads": 3,
        },
    )

    assert upload_response.status_code == 200

    token = upload_response.json()["share_token"]

    # First download
    response = client.get(f"/share/{token}")
    assert response.status_code == 200

    # Second download
    response = client.get(f"/share/{token}")
    assert response.status_code == 200

    # Third download
    response = client.get(f"/share/{token}")
    assert response.status_code == 200

    # Fourth download should be rejected
    response = client.get(f"/share/{token}")

    assert response.status_code == 410
    assert response.json()["detail"] == "Download limit reached."