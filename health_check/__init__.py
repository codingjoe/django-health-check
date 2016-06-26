# This file is heavily inspired from the django admin autodiscover

__version_info__ = {
    'major': 1,
    'minor': 1,
    'micro': 0,
    'releaselevel': 'final',
    'serial': 0
}


def autodiscover():
    """
    Auto-discover INSTALLED_APPS admin.py modules and fail silently when not present.

    This forces an import on them to register any admin bits they may want.
    """
    import copy
    from django.conf import settings
    from importlib import import_module
    from django.utils.module_loading import module_has_submodule
    from health_check.plugins import plugin_dir

    for app in settings.INSTALLED_APPS:
        mod = import_module(app)
        # Attempt to import the app's admin module.
        try:
            before_import_registry = copy.copy(plugin_dir._registry)
            import_module('%s.plugin_health_check' % app)
        except:
            # Reset the model registry to the state before the last import as
            # this import will have to reoccur on the next request and this
            # could raise NotRegistered and AlreadyRegistered exceptions
            # (see #8245).
            plugin_dir._registry = before_import_registry

            # Decide whether to bubble up this error. If the app just
            # doesn't have an admin module, we can ignore the error
            # attempting to import it, otherwise we want it to bubble up.
            if module_has_submodule(mod, 'plugin_health_check'):
                raise


def get_version(short=False):
    assert __version_info__['releaselevel'] in ('alpha', 'beta', 'final')
    vers = ["%(major)i.%(minor)i" % __version_info__, ]
    if __version_info__['micro']:
        vers.append(".%(micro)i" % __version_info__)
    if __version_info__['releaselevel'] != 'final' and not short:
        vers.append('%s%i' % (__version_info__['releaselevel'][0], __version_info__['serial']))
    return ''.join(vers)


__version__ = get_version()
