import typing

import pytest
from django.core import checks
from django.test import override_settings
from django.urls import clear_url_caches, resolve

from health_check.system_checks import check_anonymous_view_cache


@pytest.fixture(autouse=True)
def use_system_check_urlconf() -> typing.Iterator[None]:
    """Load the system check URL configuration for each test."""
    clear_url_caches()
    with override_settings(ROOT_URLCONF="tests.testapp.urls_system_checks"):
        clear_url_caches()
        yield
    clear_url_caches()


def get_warning_callbacks() -> set[typing.Callable]:
    """Return the view callbacks that receive a warning."""
    return {warning.obj for warning in check_anonymous_view_cache()}


def test_check_anonymous_view_cache__anonymous_without_max_age():
    """Warn about an anonymous view without max_age."""
    assert resolve("/anonymous/").func in get_warning_callbacks()


def test_check_anonymous_view_cache__anonymous_with_max_age():
    """Skip an anonymous view with max_age."""
    assert resolve("/anonymous-cached/").func not in get_warning_callbacks()


def test_check_anonymous_view_cache__authenticated_without_max_age():
    """Skip an authenticated view without max_age."""
    assert resolve("/authenticated/").func not in get_warning_callbacks()


def test_check_anonymous_view_cache__plain_view():
    """Skip a callback that is not a view class."""
    assert resolve("/plain/").func not in get_warning_callbacks()


def test_check_anonymous_view_cache__other_view_class():
    """Skip a view class that is not a health check view."""
    assert resolve("/template/").func not in get_warning_callbacks()


def test_check_anonymous_view_cache__nested_include():
    """Find anonymously accessible views in included URL patterns."""
    callbacks = get_warning_callbacks()
    assert resolve("/nested/inner/anonymous/").func in callbacks
    assert resolve("/nested/inner/cached/").func not in callbacks


def test_check_anonymous_view_cache__initkwargs_allow_anonymous():
    """Prefer allow_anonymous from as_view over the class attribute."""
    callbacks = get_warning_callbacks()
    assert resolve("/initkwargs-anonymous/").func in callbacks
    assert resolve("/initkwargs-authentication-required/").func not in callbacks


def test_check_anonymous_view_cache__initkwargs_zero_max_age():
    """Prefer max_age from as_view over the class attribute."""
    assert resolve("/initkwargs-zero-max-age/").func in get_warning_callbacks()


def test_check_anonymous_view_cache__warning_details():
    """Report the view, check ID, message, and hint."""
    callback = resolve("/anonymous/").func
    warning = next(
        warning for warning in check_anonymous_view_cache() if warning.obj is callback
    )
    assert warning.id == "health_check.W001"
    assert warning.msg == "Anonymous health check view disables caching."
    assert (
        warning.hint
        == "Set max_age to a positive duration to cache successful responses."
    )


def test_check_anonymous_view_cache__registered():
    """Run the check through the Django check framework."""
    assert "health_check.W001" in {message.id for message in checks.run_checks()}


def test_check_anonymous_view_cache__warning_count():
    """Return one warning per anonymous view without max_age."""
    assert len(check_anonymous_view_cache()) == 4
