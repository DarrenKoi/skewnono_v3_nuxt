from backend.afm.profile_sampling import thin_profile


def _grid(nx, ny):
    return [{"x": x * 0.5, "y": y * 0.5, "z": float(x + y)} for y in range(ny) for x in range(nx)]


def test_a_profile_within_budget_is_returned_as_is():
    points = _grid(8, 4)
    assert thin_profile(points, budget=32) is points


def test_a_lattice_stays_a_full_lattice_of_original_samples():
    points = _grid(2048, 256)
    thinned = thin_profile(points)
    xs = {p["x"] for p in thinned}
    ys = {p["y"] for p in thinned}
    assert len(thinned) == len(xs) * len(ys) == 683 * 86
    originals = {id(p) for p in points}
    assert all(id(p) in originals for p in thinned)
    # Both axes thin by the same step, so the scan keeps its proportions.
    assert sorted(xs)[:2] == [0.0, 1.5] and sorted(ys)[:2] == [0.0, 1.5]


def test_a_line_and_a_ragged_scan_keep_every_kth_sample():
    line = [{"x": float(i), "y": 0.0, "z": 1.0} for i in range(100)]
    assert [p["x"] for p in thin_profile(line, budget=30)] == [float(i) for i in range(0, 100, 4)]
    ragged = _grid(10, 10)[:-1]
    assert len(thin_profile(ragged, budget=50)) == 50


def test_a_missing_sample_stays_missing():
    points = _grid(4, 4)
    points[0]["z"] = None
    assert thin_profile(points, budget=4)[0]["z"] is None


def test_the_route_thins_a_dense_scan_and_reports_the_file_size():
    from urllib.parse import quote

    from flask import Flask

    from backend.afm.providers import mock
    from backend.afm.routes import bp

    app = Flask(__name__)
    app.register_blueprint(bp, url_prefix="/api")
    row = next(
        r for r in mock.list_afm_files("MAPC01")
        if r["has_profile"] and mock.get_profile_meta(r["filename"], "any", "MAPC01")["data_size"] == "2048 x 256"
    )
    url = f"/api/afm/files/{quote(row['filename'], safe='')}/profile/any?tool=MAPC01"
    body = app.test_client().get(url).get_json()
    assert body["total"] == 2048 * 256
    assert body["count"] == len(body["data"]) == 683 * 86
    # The file still declares its own size; only the samples sent are fewer.
    assert body["meta"]["data_size"] == "2048 x 256"
