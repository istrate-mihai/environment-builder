from pathlib import Path

import pytest

from validate import DEFAULT_SUPPORTED, load_supported, main, validate


@pytest.fixture(scope="module")
def supported():
    return load_supported(DEFAULT_SUPPORTED)


def test_valid_config(supported):
    cfg = {"technologies": [{"name": "python", "version": "3.12"}, {"name": "Docker"}, "java"]}
    techs, errors = validate(cfg, supported)
    assert errors == []
    assert [(t.name, t.version) for t in techs] == [("python", "3.12"), ("docker", "latest"), ("java", "21")]


def test_unknown_technology(supported):
    _, errors = validate({"technologies": [{"name": "php"}]}, supported)
    assert len(errors) == 1 and "'php' is not supported" in errors[0]


def test_invalid_version(supported):
    _, errors = validate({"technologies": [{"name": "nodejs", "version": "12"}]}, supported)
    assert "version '12' is not valid" in errors[0]


def test_unquoted_decimal_version(supported):
    _, errors = validate({"technologies": [{"name": "python", "version": 3.1}]}, supported)
    assert "must be quoted" in errors[0]


def test_integer_version_is_accepted(supported):
    techs, errors = validate({"technologies": [{"name": "nodejs", "version": 22}]}, supported)
    assert errors == [] and techs[0].version == "22"


def test_duplicates_and_all_errors_reported(supported):
    cfg = {"technologies": [{"name": "java"}, {"name": "java"}, {"name": "rust"}]}
    _, errors = validate(cfg, supported)
    assert len(errors) == 2


@pytest.mark.parametrize("cfg", [None, {}, {"technologies": []}, {"technologies": "docker"}])
def test_bad_structure(supported, cfg):
    _, errors = validate(cfg, supported)
    assert errors


def test_main_generates_files(tmp_path: Path):
    cfg = tmp_path / "env.yml"
    cfg.write_text('technologies:\n  - name: python\n    version: "3.11"\n  - name: mysql\n')
    out = tmp_path / "out"

    assert main(["--config", str(cfg), "--out-dir", str(out)]) == 0
    assert "python:\n    version: '3.11'" in (out / "install_vars.yml").read_text()
    assert (out / "verify.conf").read_text().splitlines() == [
        "python|3.11|python3.11 --version|Python 3.11.|",
        "mysql|8.0|mysql --version|Ver 8.0.|mysql",
    ]


def test_main_fails_without_writing(tmp_path: Path):
    cfg = tmp_path / "env.yml"
    cfg.write_text("technologies:\n  - name: mongodb\n")
    out = tmp_path / "out"

    assert main(["--config", str(cfg), "--out-dir", str(out)]) == 1
    assert not out.exists()
