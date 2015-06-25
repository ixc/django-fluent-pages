from fluent_pages import appsettings


# Detect whether django-reversion is installed and set flag
try:
    import reversion
    IS_REVERSION_INSTALLED = True
except:
    IS_REVERSION_INSTALLED = False


def enable_reversion_support():
    """
    Return True if django-reversion is installed and should be enabled.
    """
    return IS_REVERSION_INSTALLED \
        and not appsettings.FLUENT_PAGES_DISABLE_REVERSION
