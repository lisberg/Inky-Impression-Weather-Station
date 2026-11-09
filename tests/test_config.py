import pytest

from station import config


def test_display_model_is_checked(tmp_path):
    path = str(tmp_path / "c.json")
    cfg = config.load(path)
    assert cfg["display"]["model"] == "auto"
    cfg["display"]["model"] = "spectra73"
    config.save(cfg, path)
    cfg["display"]["model"] = "bogus"
    with pytest.raises(config.ConfigError):
        config.save(cfg, path)
