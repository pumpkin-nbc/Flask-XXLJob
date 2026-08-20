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
    assert config.auto_register is True
    assert config.deregister_on_exit is False
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


@pytest.mark.parametrize("value", [None, 0, 1, "true", [], {}])
def test_deregister_on_exit_requires_real_boolean(value):
    with pytest.raises(XXLJobConfigError, match="XXL_JOB_DEREGISTER_ON_EXIT"):
        XXLJobConfig.from_mapping(
            base_mapping(XXL_JOB_DEREGISTER_ON_EXIT=value)
        )


def test_removed_auto_register_on_init_false_has_exact_migration_help():
    with pytest.raises(XXLJobConfigError) as raised:
        XXLJobConfig.from_mapping(
            base_mapping(XXL_JOB_AUTO_REGISTER_ON_INIT=False)
        )
    assert str(raised.value) == (
        "XXL_JOB_AUTO_REGISTER_ON_INIT 已删除。\n\n"
        "如需保持手动 Registry 启动，请设置：\n\n"
        "XXL_JOB_AUTO_REGISTER=False\n\n"
        "然后在需要的生命周期显式调用：\n\n"
        "start_registry()"
    )


def test_removed_auto_register_on_init_true_has_exact_migration_help():
    with pytest.raises(XXLJobConfigError) as raised:
        XXLJobConfig.from_mapping(
            base_mapping(XXL_JOB_AUTO_REGISTER_ON_INIT=True)
        )
    assert str(raised.value) == (
        "XXL_JOB_AUTO_REGISTER_ON_INIT 已删除。\n\n"
        "请删除该配置，并保留：\n\n"
        "XXL_JOB_AUTO_REGISTER=True"
    )


@pytest.mark.parametrize("value", [None, 0, 1, "false", [], {}])
def test_removed_auto_register_on_init_other_values_always_raise(value):
    with pytest.raises(XXLJobConfigError, match="已删除"):
        XXLJobConfig.from_mapping(
            base_mapping(XXL_JOB_AUTO_REGISTER_ON_INIT=value)
        )


def test_log_level_is_case_insensitive():
    config = XXLJobConfig.from_mapping(base_mapping(XXL_JOB_LOG_LEVEL="debug"))
    assert config.log_level == "DEBUG"


def test_missing_admin_addresses_raises():
    config = XXLJobConfig.from_mapping(
        base_mapping(XXL_JOB_ADMIN_ADDRESSES=[])
    )
    with pytest.raises(XXLJobConfigError):
        config.validate_registry()


def test_missing_app_name_raises():
    config = XXLJobConfig.from_mapping(
        base_mapping(XXL_JOB_EXECUTOR_APP_NAME="")
    )
    with pytest.raises(XXLJobConfigError):
        config.validate_registry()


def test_wrong_type_raises():
    with pytest.raises(XXLJobConfigError):
        XXLJobConfig.from_mapping(base_mapping(XXL_JOB_REGISTRY_INTERVAL="30"))


def test_non_positive_int_raises():
    with pytest.raises(XXLJobConfigError):
        XXLJobConfig.from_mapping(base_mapping(XXL_JOB_HTTP_READ_TIMEOUT=0))


def test_disabled_skips_required_validation():
    config = XXLJobConfig.from_mapping(
        {
            "XXL_JOB_ENABLED": False,
            "XXL_JOB_ADMIN_ADDRESSES": ["not a URL"],
            "XXL_JOB_EXECUTOR_ADDRESS": "also not a URL?x=1",
            "XXL_JOB_ROUTE_PREFIX": "/<invalid path>",
        }
    )
    assert config.enabled is False
    assert config.route_prefix == "/<invalid path>"


def test_comma_separated_admin_addresses():
    config = XXLJobConfig.from_mapping(
        base_mapping(XXL_JOB_ADMIN_ADDRESSES="http://a:8080,http://b:8080")
    )
    assert config.admin_addresses == ["http://a:8080", "http://b:8080"]


def test_comma_separated_admin_address_whitespace_is_rejected():
    with pytest.raises(XXLJobConfigError, match="whitespace"):
        XXLJobConfig.from_mapping(
            base_mapping(
                XXL_JOB_ADMIN_ADDRESSES="http://a:8080, http://b:8080"
            )
        )


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
    config = XXLJobConfig.from_mapping(
        base_mapping(XXL_JOB_EXECUTOR_ADDRESS="")
    )
    with pytest.raises(XXLJobConfigError):
        config.validate_registry()


@pytest.mark.parametrize(
    "attribute,value",
    [
        ("registry_interval", 0),
        ("http_connect_timeout", 0),
        ("http_read_timeout", "5"),
        ("admin_retry_count", -1),
        ("admin_retry_backoff", -0.1),
    ],
)
def test_validate_registry_rechecks_mutable_numeric_fields(attribute, value):
    config = XXLJobConfig.from_mapping(base_mapping())
    setattr(config, attribute, value)
    with pytest.raises(XXLJobConfigError):
        config.validate_registry()


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
                "http://admin-2:8080/",
            ]
        )
    )
    assert config.admin_addresses == [
        "http://admin-1:8080/xxl-job-admin",
        "http://admin-2:8080",
    ]


def test_admin_address_surrounding_whitespace_is_rejected():
    with pytest.raises(XXLJobConfigError, match="whitespace"):
        XXLJobConfig.from_mapping(
            base_mapping(
                XXL_JOB_ADMIN_ADDRESSES=["  http://admin:8080/  "]
            )
        )


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


def test_ipv6_admin_address_supported():
    config = XXLJobConfig.from_mapping(
        base_mapping(
            XXL_JOB_ADMIN_ADDRESSES=["http://[::1]:8080/xxl-job-admin"]
        )
    )
    assert config.admin_addresses == ["http://[::1]:8080/xxl-job-admin"]


def test_ipv6_executor_address_with_path_supported():
    config = XXLJobConfig.from_mapping(
        base_mapping(
            XXL_JOB_EXECUTOR_ADDRESS="https://[2001:db8::1]:8443/context",
            XXL_JOB_ROUTE_PREFIX="/xxl-job",
        )
    )
    assert config.executor_address == (
        "https://[2001:db8::1]:8443/context/xxl-job"
    )


@pytest.mark.parametrize(
    "address",
    [
        "http://",
        "https:///missing-host",
        "http://admin:not-a-port",
        "http://admin:0",
        "http://admin:70000",
        "http://bad_host:8080",
        "http://-admin:8080",
        "http://admin..internal:8080",
        "http://999.999.999.999:8080",
        "http://%41dmin:8080",
    ],
)
def test_invalid_admin_url_components_raise(address):
    with pytest.raises(XXLJobConfigError):
        XXLJobConfig.from_mapping(base_mapping(XXL_JOB_ADMIN_ADDRESSES=[address]))


@pytest.mark.parametrize(
    "address",
    [
        "http://user:pass@admin:8080",
        "http://admin:8080/root?tenant=a",
        "http://admin:8080/root#fragment",
        "http://admin:8080/with space",
        "http://admin:8080/\tcontrol",
        "http://admin:8080/\x7fcontrol",
    ],
)
def test_unsafe_admin_url_components_raise(address):
    with pytest.raises(XXLJobConfigError, match="XXL_JOB_ADMIN_ADDRESSES"):
        XXLJobConfig.from_mapping(
            base_mapping(XXL_JOB_ADMIN_ADDRESSES=[address])
        )


@pytest.mark.parametrize(
    "address",
    [
        "http://user:pass@executor:5001",
        "http://executor:5001/root?tenant=a",
        "http://executor:5001/root#fragment",
        " http://executor:5001",
    ],
)
def test_unsafe_executor_url_components_raise(address):
    with pytest.raises(XXLJobConfigError, match="XXL_JOB_EXECUTOR_ADDRESS"):
        XXLJobConfig.from_mapping(
            base_mapping(XXL_JOB_EXECUTOR_ADDRESS=address)
        )


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
        ("/", ""),
        ("/xxl-job", "/xxl-job"),
        ("/xxl-job/", "/xxl-job"),
        ("xxl-job", "/xxl-job"),
        ("internal/xxl", "/internal/xxl"),
    ],
)
def test_route_prefix_normalization_variants(prefix, expected):
    config = XXLJobConfig.from_mapping(base_mapping(XXL_JOB_ROUTE_PREFIX=prefix))
    assert config.route_prefix == expected


@pytest.mark.parametrize(
    "prefix",
    [
        "   ",
        "///",
        "//xxl-job//",
        "/xxl?tenant=a",
        "/xxl#fragment",
        "/a\\b",
        "/<path:anything>",
        "/a//b",
        "/a/../b",
        "/a/./b",
        "/a b",
        "/a\x7fb",
    ],
)
def test_invalid_static_route_prefix_rejected(prefix):
    with pytest.raises(XXLJobConfigError, match="XXL_JOB_ROUTE_PREFIX"):
        XXLJobConfig.from_mapping(
            base_mapping(XXL_JOB_ROUTE_PREFIX=prefix)
        )


@pytest.mark.parametrize("value", [None, 1, [], {}])
def test_disabled_route_prefix_still_requires_string_type(value):
    with pytest.raises(XXLJobConfigError, match="XXL_JOB_ROUTE_PREFIX"):
        XXLJobConfig.from_mapping(
            {"XXL_JOB_ENABLED": False, "XXL_JOB_ROUTE_PREFIX": value}
        )


@pytest.mark.parametrize("value", [None, 1, [], {}])
def test_disabled_executor_address_still_requires_string_type(value):
    with pytest.raises(XXLJobConfigError, match="XXL_JOB_EXECUTOR_ADDRESS"):
        XXLJobConfig.from_mapping(
            {"XXL_JOB_ENABLED": False, "XXL_JOB_EXECUTOR_ADDRESS": value}
        )
