from fluent_pages.admin import HtmlPageAdmin
from fluent_pages.integrations.django_reversion import enable_reversion_support


class FlatPageAdmin(HtmlPageAdmin):
    readonly_shared_fields = HtmlPageAdmin.readonly_shared_fields + ('template_name', 'content')

    # Implicitly loaded:
    #change_form_template = "admin/fluent_pages/pagetypes/flatpage/change_form.html"
    # Not defined here explicitly, so other templates can override this function.
    # and use {% extends default_change_form_template %} instead.


if enable_reversion_support():
    # Add reversion-compatible mixing as superclass of admin class
    # TODO Should probably find a better or more elegant way to do this
    from fluent_pages.integration.django_reversion.admin import ReversionFlatPageAdminMixin
    FlatPageAdmin.__bases__ += (ReversionFlatPageAdminMixin,)
