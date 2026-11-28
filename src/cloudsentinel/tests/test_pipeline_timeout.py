from cloudsentinel.pipeline import _redis_socket_timeout


def test_redis_socket_timeout_exceeds_xread_block() -> None:
    assert _redis_socket_timeout(5.0) == 7.0
    assert _redis_socket_timeout(0.0) == 2.0
