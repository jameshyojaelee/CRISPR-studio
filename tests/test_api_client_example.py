from __future__ import annotations

from examples.api_client import SAMPLE_DATA_DIR, build_headers, build_submit_payload


def test_build_submit_payload_defaults_use_sample_data(tmp_path):
    counts = tmp_path / "counts.csv"
    lib = tmp_path / "lib.csv"
    meta = tmp_path / "meta.json"
    for path in (counts, lib, meta):
        path.write_text("placeholder")

    payload = build_submit_payload(counts_path=counts, library_path=lib, metadata_path=meta)

    assert payload["counts_path"] == str(counts)
    assert payload["library_path"] == str(lib)
    assert payload["metadata_path"] == str(meta)
    assert payload["use_mageck"] is False
    assert payload["skip_annotations"] is True
    assert payload["enrichr_libraries"] is None


def test_build_submit_payload_enrichr_joining():
    payload = build_submit_payload(
        counts_path=SAMPLE_DATA_DIR / "demo_counts.csv",
        library_path=SAMPLE_DATA_DIR / "demo_library.csv",
        metadata_path=SAMPLE_DATA_DIR / "demo_metadata.json",
        enrichr_libraries=["Reactome_2022", "native_demo"],
        skip_annotations=False,
        use_mageck=True,
    )
    assert payload["enrichr_libraries"] == "Reactome_2022,native_demo"
    assert payload["use_mageck"] is True
    assert payload["skip_annotations"] is False


def test_build_headers_with_api_key():
    headers = build_headers(api_key="secret")
    assert headers["X-API-Key"] == "secret"
    assert "Content-Type" in headers
