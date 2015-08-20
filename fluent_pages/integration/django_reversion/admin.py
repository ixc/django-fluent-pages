from django.conf.urls import patterns, url

from reversion.admin import VersionAdmin

from django.contrib.admin.utils import quote
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http.response import HttpResponseRedirect

from fluent_contents.models import ContentItem, Placeholder
from fluent_contents.extensions import plugin_pool

from .utils import FluentVersionAdapter


class BaseFluentVersionAdmin(VersionAdmin):
    """
    Base class for customizing django-reversion's VersionAdmin for Fluent
    page types.
    """
    # If this flag is set `get_urls` is hacked to add URL pattern names like
    # 'fluent_pages_page_recoverlist' etc normally required to show pages in
    # a polymorphic page listing. Set to false if you have a customised admin
    # for pages which do not appear in the '/admin/fluent_pages/page/' section.
    is_grouped_under_fluent_pages_page = True

    revision_form_template = \
        'admin/fluent_pages/integration/django_reversion/revision_form.html'
    recover_form_template = \
        'admin/fluent_pages/integration/django_reversion/recover_form.html'
    change_list_template = 'reversion/change_list.html'

    # Override VersionAdmin._autoregister with customisations to:
    # * register django-parler translation fields and follow relationships
    # * register ContentItems exposed as plugins
    # * register Placeholder
    def _autoregister(self, model, follow=None):
        # Skip pre-registered models
        if not self.revision_manager.is_registered(model):
            follow = follow or []
            # Use model_meta.concrete_model to catch proxy models
            for parent_cls, field in \
                    model._meta.concrete_model._meta.parents.items():
                follow.append(field.name)
                self._autoregister(parent_cls)
            # Process django-parler translations, if any
            if hasattr(model, '_parler_meta'):
                for parler_meta in model._parler_meta:
                    follow.append(parler_meta.rel_name)
                    self._autoregister(parler_meta.model)
            self.revision_manager.register(model, follow=follow,
                                           format=self.reversion_format,
                                           adapter_cls=FluentVersionAdapter)
        # Register all ContentItem models registered as plugin
        if not issubclass(model, ContentItem):
            for content_item_model in plugin_pool.get_model_classes():
                if not self.revision_manager.is_registered(content_item_model):
                    self._autoregister(content_item_model)
            # Register Placeholder
            if not self.revision_manager.is_registered(Placeholder):
                self._autoregister(Placeholder)

    # Override VersionAdmin get_urls to return extra fake-ish URLs necessary
    # to support url reversal for "parent"-specific URL paths through this
    # admin which operates in context of a "child" admin.
    def get_urls(self):
        urls = super(BaseFluentVersionAdmin, self).get_urls()

        if not self.is_grouped_under_fluent_pages_page:
            return urls

        # Hack to also register alternate 'fluent_pages_page_XYZ' URL names to
        # work with URL lookups on history/recovery pages from *parent* admin
        # class, since this polymorphic admin generates
        # 'fluentpage_fluentpage_XYZ' URL names instead.
        # TODO Can we avoid this hack somehow?
        admin_site = self.admin_site
        reversion_urls = patterns(
            "",
            url("^recover/$",
                admin_site.admin_view(self.recoverlist_view),
                name='fluent_pages_page_recoverlist'),
            url("^recover/([^/]+)/$",
                admin_site.admin_view(self.recover_view),
                name='fluent_pages_page_recover'),
            url("^([^/]+)/history/([^/]+)/$",
                admin_site.admin_view(self.revision_view),
                name='fluent_pages_page_revision'),
        )
        return reversion_urls + urls

    def revisionform_view(self, request, version, template_name,
                          extra_context=None):
        """
        Override handling of reversion's revert-with-delete to instead delete
        entire object. We must do this to clean up obsolete relationships
        rather than relying on django-reversion's `delete=True` flag to
        `version.revision.revert()` which does not properly handle the unusual
        polymorphic content type IDs assigned to MarkupItem variants.
        """
        # Flag request as being in context of a revert/recover operation, for
        # lookup later when `changeform_view` is called.
        request.IS_REVERSION_REQUEST = True

        def hack_revision_revert(delete=True):
            obj = version.object
            if obj:
                obj.delete()
            version.revision._original_revert()
        version.revision._original_revert = version.revision.revert
        version.revision.revert = hack_revision_revert

        return super(BaseFluentVersionAdmin, self).revisionform_view(
            request, version, template_name, extra_context=extra_context)

    @transaction.atomic
    def changeform_view(self, request, object_id, *args, **kwargs):
        """
        Override processing of change form when a revert/recover request is
        submitted to perform a "strict" operation, in order to:
            * prevent user-submitted form data from causing changes to the data
              that has just been restored or recovered by
              `VersionAdmin.revisionform_view`
            * redirect to the change form of the just reverted/recovered object
              rather than to the listing page.
        """
        # If user is submitting a revert/recover request do not really process
        # the form data, instead return a redirect back to object's change form
        if getattr(request, 'IS_REVERSION_REQUEST', False) \
                and request.method == 'POST':
            # Seemingly unnecessary save is required here to trigger
            # reversion's context manager to complete the restore/revert
            self.model.objects.get(pk=object_id).save()

            opts = self.model._meta
            object_changeform_url = reverse(
                "%s:%s_%s_change" % (
                    self.admin_site.name, opts.app_label, opts.model_name),
                args=(quote(object_id),))
            return HttpResponseRedirect(object_changeform_url)

        return super(BaseFluentVersionAdmin, self) \
            .changeform_view(request, object_id, *args, **kwargs)


class ReversionFlatPageAdminMixin(BaseFluentVersionAdmin):
    pass


class ReversionFluentContentsPageAdminMixin(BaseFluentVersionAdmin):

    #: The default template name, which is available in the template context.
    #: Use ``{% extend base_change_form_template %}`` in templates to inherit.
    base_change_form_template = "admin/fluent_pages/page/base_change_form.html"


class ReversionFluentContentsParentPageAdminMixin(
        ReversionFluentContentsPageAdminMixin):

    def changeform_view(self, request, object_id, *args, **kwargs):
        """
        Look up "real" admin when rendering the change form for a polymorphic
        parent model, per the logic used for default Django views in
        PolymorphicParentModelAdmin.

        This is helpful for Fluent Contentes parent classes that do not use the
        standard Fluent/Flat page admins directly, in which case they seem to
        lack the ability to use the appropriate polymorphic child admin class
        when appropriate.
        """
        if object_id:
            real_admin = self._get_real_admin(object_id)
            return real_admin.changeform_view(
                request, object_id, *args, **kwargs)
        else:
            return super(ReversionFluentContentsPageAdminMixin, self) \
                .changeform_view(request, object_id, *args, **kwargs)
