def test_app_registers_msr_image(monkeypatch):
    monkeypatch.setenv("SKEWNONO_MSR_IMAGE_PROVIDER", "mock")
    from back_dev_home import create_app

    app = create_app()
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert "/api/msr-images" in rules
    assert "/api/msr-image" in rules
    assert "/api/msr-images/<job_id>" in rules

    client = app.test_client()
    r = client.get("/api/msr-images?eqp_ip=10.0.0.1&class_name=ADI&msr=MSR_1")
    assert r.status_code == 200
