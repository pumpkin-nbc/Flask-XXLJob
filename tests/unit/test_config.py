"""Configuration loading and validation tests."""

from __future__ import annotations

import pytest

from flask_xxljob.config import XXLJobConfig
from flask_xxljob.exceptions import XXLJobConfigError


def base_mapping(**overrides):
    mapping = {
        "XXL_JOB_ADMIN_ADDRESSES": ["http://admin:8080/xxl-job-admin"],
        "XXL_JOB_EXECUTOR_APP_NAME": "app",
        "XXL_JOB_EXECUTOR_ADDRESS": "http://127.0.0.1:5001",
    }
    mapping.update(overrides)
    return mapping


def test_defaults_applied():
    config = XXLJobConfig.from_mapping(base_mapping())
    assert config.registry_interval == 30
    assert config.http_connect_timeout == 3
    assert config.http_read_timeout == 5
    assert config.callback_message_max_length == 10000
    assert config.max_request_size == 1048576
    assert config.max_param_length == 65536
    assert config.timeout == (3, 5)
    assert config.log_enabled is False
    assert config.log_file_enabled is True
    assert config.log_console_enabled is True
    assert config.log_level == "INFO"
    assert config.log_path == "./logs"
    assert config.log_filename == "flask-xxljob.log"
    assert config.log_encoding == "utf-8"
    assert config.log_max_bytes == 10 * 1024 * 1024
    assert config.log_backup_count == 5
    assert config.log_propagate is False


def test_log_level_is_case_insensitive():
    config = XXLJobConfig.from_mapping(base_mapping(XXL_JOB_LOG_LEVEL="debug"))
    assert config.log_level == "DEBUG"


def test_missing_admin_addresses_raises():
    with pytest.raises(XXLJobConfigError):
        XXLJobConfig.from_mapping(base_mapping(XXL_JOB_ADMIN_ADDRESSES=[]))


def test_missing_app_name_raises():
    with pytest.raises(XXLJobConfigError):
        XXLJobConfig.from_mapping(base_mapping(XXL_JOB_EXECUTOR_APP_NAME=""))


def test_wrong_type_raises():
    with pytest.raises(XXLJobConfigError):
        XXLJobConfig.from_mapping(base_mapping(XXL_JOB_REGISTRY_INTERVAL="30"))


def test_non_positive_int_raises():
    with pytest.raises(XXLJobConfigError):
        XXLJobConfig.from_mapping(base_mapping(XXL_JOB_HTTP_READ_TIMEOUT=0))


def test_disabled_skips_required_validation():
    config = XXLJobConfig.from_mapping(
        {"XXL_JOB_ENABLED": False, "XXL_JOB_ADMIN_ADDRESSES": []}
    )
    assert config.enabled is False


def test_comma_separated_admin_addresses():
    config = XXLJobConfig.from_mapping(
        base_mapping(XXL_JOB_ADMIN_ADDRESSES="http://a:8080, http://b:8080")
    )
    assert config.admin_addresses == ["http://a:8080", "http://b:8080"]


def test_route_prefix_normalized():
    config = XXLJobConfig.from_mapping(base_mapping(XXL_JOB_ROUTE_PREFIX="exec/"))
    assert config.route_prefix == "/exec"


def test_auto_register_off_relaxes_admin_requirement():
    # 关闭自动注册后不再强制要求 Admin/执行器地址。
    # With auto-register off, admin/executor addresses are no longer required.
    config = XXLJobConfig.from_mapping(
        {"XXL_JOB_AUTO_REGISTER": False, "XXL_JOB_ADMIN_ADDRESSES": []}
    )
    assert config.enabled is True
    assert config.auto_register is False


def test_missing_executor_address_raises_when_auto_register():
    with pytest.raises(XXLJobConfigError):
        XXLJobConfig.from_mapping(base_mapping(XXL_JOB_EXECUTOR_ADDRESS=""))


def test_bad_admin_url_scheme_raises():
    with pytest.raises(XXLJobConfigError):
        XXLJobConfig.from_mapping(base_mapping(XXL_JOB_ADMIN_ADDRESSES=["ftp://admin"]))


def test_bad_executor_url_scheme_raises():
    with pytest.raises(XXLJobConfigError):
        XXLJobConfig.from_mapping(base_mapping(XXL_JOB_EXECUTOR_ADDRESS="admin:8080"))


def test_admin_address_trailing_slash_normalized():
    config = XXLJobConfig.from_mapping(
        base_mapping(
            XXL_JOB_ADMIN_ADDRESSES=[
                "http://admin-1:8080/xxl-job-admin/",
                "  http://admin-2:8080/  ",
            ]
        )
    )
    assert config.admin_addresses == [
        "http://admin-1:8080/xxl-job-admin",
        "http://admin-2:8080",
    ]


def test_executor_address_trailing_slash_normalized():
    config = XXLJobConfig.from_mapping(
        base_mapping(XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001/")
    )
    assert config.executor_address == "http://127.0.0.1:5001"


def test_route_prefix_appended_to_executor_address():
    config = XXLJobConfig.from_mapping(
        base_mapping(
            XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001",
            XXL_JOB_ROUTE_PREFIX="/xxl-job",
        )
    )
    assert config.route_prefix == "/xxl-job"
    assert config.executor_address == "http://127.0.0.1:5001/xxl-job"


def test_route_prefix_appended_after_existing_context_path():
    config = XXLJobConfig.from_mapping(
        base_mapping(
            XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001/myapp/",
            XXL_JOB_ROUTE_PREFIX="xxl-job",
        )
    )
    assert config.executor_address == "http://127.0.0.1:5001/myapp/xxl-job"


def test_route_prefix_always_appended_even_when_already_present():
    config = XXLJobConfig.from_mapping(
        base_mapping(
            XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001/xxl-job/",
            XXL_JOB_ROUTE_PREFIX="/xxl-job",
        )
    )
    assert config.executor_address == "http://127.0.0.1:5001/xxl-job/xxl-job"


def test_empty_route_prefix_keeps_executor_address():
    config = XXLJobConfig.from_mapping(
        base_mapping(
            XXL_JOB_EXECUTOR_ADDRESS="http://127.0.0.1:5001/api",
            XXL_JOB_ROUTE_PREFIX="",
        )
    )
    assert config.executor_address == "http://127.0.0.1:5001/api"


def test_https_admin_address_supported():
    config = XXLJobConfig.from_mapping(
        base_mapping(XXL_JOB_ADMIN_ADDRESSES=["https://admin:8443/xxl-job-admin"])
    )
    assert config.admin_addresses == ["https://admin:8443/xxl-job-admin"]


@pytest.mark.parametrize(
    "address",
    ["http://", "https:///missing-host", "http://admin:not-a-port", "http://admin:70000"],
)
def test_invalid_admin_url_components_raise(address):
    with pytest.raises(XXLJobConfigError):
        XXLJobConfig.from_mapping(base_mapping(XXL_JOB_ADMIN_ADDRESSES=[address]))


def test_access_token_whitespace_only_normalized_to_empty():
    config = XXLJobConfig.from_mapping(base_mapping(XXL_JOB_ACCESS_TOKEN=" \t "))
    assert config.access_token == ""


def test_nonblank_access_token_preserves_exact_value():
    config = XXLJobConfig.from_mapping(base_mapping(XXL_JOB_ACCESS_TOKEN=" token "))
    assert config.access_token == " token "


def test_admin_address_order_preserved():
    config = XXLJobConfig.from_mapping(
        base_mapping(
            XXL_JOB_ADMIN_ADDRESSES=["http://a:8080", "http://b:8080", "http://c:8080"]
        )
    )
    assert config.admin_addresses == ["http://a:8080", "http://b:8080", "http://c:8080"]


@pytest.mark.parametrize(
    "prefix,expected",
    [
        ("", ""),
        ("   ", ""),
        ("/", ""),
        ("///", ""),
        ("/xxl-job", "/xxl-job"),
        ("/xxl-job/", "/xxl-job"),
        ("xxl-job", "/xxl-job"),
        ("//xxl-job//", "/xxl-job"),
    ],
)
def test_route_prefix_normalization_variants(prefix, expected):
    config = XXLJobConfig.from_mapping(base_mapping(XXL_JOB_ROUTE_PREFIX=prefix))
    assert config.route_prefix == expected
