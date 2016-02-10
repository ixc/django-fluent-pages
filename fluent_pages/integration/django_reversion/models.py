import django.dispatch


pre_revisionform_view = django.dispatch.Signal(providing_args=["request", "version"])
post_revisionform_view = django.dispatch.Signal(providing_args=["request", "version", "response"])
