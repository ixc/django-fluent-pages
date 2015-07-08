from django.conf.urls import patterns, url
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import get_language

from reversion.admin import VersionAdmin

from fluent_pages.integration.fluent_contents.admin import FluentContentsPageAdmin
from fluent_pages.pagetypes.fluentpage.admin import FluentPageAdmin
from fluent_pages.pagetypes.flatpage.admin import FlatPageAdmin
from fluent_pages.models import PageLayout
from fluent_contents.models import ContentItem, Placeholder

from .utils import fluent_revision_manager


class BaseFluentVersionAdmin(VersionAdmin):
    """
    Base class for customizing django-reversion's VersionAdmin for Fluent
    page types.
    """

    revision_manager = fluent_revision_manager

    strict_revert = True

    # Override VersionAdmin get_urls to return extra fake-ish URLs necessary
    # to support url reversal for "parent"-specific URL paths through this
    # admin which operates in context of a "child" admin.
    def get_urls(self):
        urls = super(BaseFluentVersionAdmin, self).get_urls()

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

    def _perform_strict_revert(self, request, obj, version, context,
                               revert=False, recover=False):
        """
        Override handling of strict revert: delete object in advance to clean
        up obsolete relationships rather than relying on django-reversion's
        `delete=True` flag to `version.revision.revert()` which does not
        properly handle the complex object reltionships for versioned Fluent
        pages.
        """
        obj.delete()
        version.revision.revert()

    def _dict_fields(self, data, *field_names):
        """
        Return a dict subset of the given data dict populated with only
        the specified field names.
        """
        return dict((n, v) for (n, v) in data.items() if n in field_names)

    def get_revision_form_data(self, request, obj, version):
        """
        Override default django-reversion implementation to retrieve form data
        from versioned object relationships it doesn't traverse itself, in
        particular from proxy objects and django-parler translated fields.
        """
        obj_data = super(BaseFluentVersionAdmin, self) \
            .get_revision_form_data(request, obj, version)
        lang = get_language()

        # Retrieve data from all related version objects stored with a revision
        # to collect all the "top-level" initial data to properly display the
        # versioned object.
        for rel_ver in version.revision.version_set.all():
            ctype_key = rel_ver.content_type.natural_key()
            data = rel_ver.field_dict

            # UrlNode superclass - nothing to do, as we already have all this
            # data in the `obj_data` provided by django-reversion.
            if ctype_key == (u'fluent_pages', u'urlnode'):
                pass
            # Translations - get translated field values for current language
            elif ctype_key == (u'fluent_pages', u'urlnode_translation'):
                if data.get('language_code') == lang:
                    obj_data.update(self._dict_fields(
                        data, 'title', 'slug', 'override_url'))
            elif ctype_key == (u'fluent_pages', u'htmlpagetranslation'):
                if data.get('language_code') == lang:
                    obj_data.update(self._dict_fields(
                        data, 'meta_title', 'meta_keywords',
                        'meta_description'))

            # Brute-force copy of any data from other top-level items where the
            # data are not already present in our form data.
            # TODO This is a somewhat naive merge of all data into a single
            # overall dict which could overwrite good data with bad, or ignore
            # good data that comes after bad. Is there a better way to do this?
            else:
                # Skip items that aren't at the "top" level to avoid polluting
                # the main object's data, which means we skip placeholder or
                # content items, since these are handled by form inlines.
                rel_ver_model = rel_ver.content_type.model_class()
                if issubclass(rel_ver_model, (ContentItem, Placeholder)):
                    continue

                additional_data = dict([
                    (k, v) for k, v in data.items()
                    # Key is not present in obj_data, or value differs
                    if k not in obj_data or v != obj_data[k]
                ])
                obj_data.update(additional_data)

        return obj_data

    class Media:
        js = ('fluent_pages/admin/integration/reversion/fix-reversion-form.js',)


class ReversionFlatPageAdmin(BaseFluentVersionAdmin, FlatPageAdmin):

    revision_form_template = 'admin/fluent_pages/pagetypes/flatpage/reversion/revision_form.html'
    recover_form_template = 'admin/fluent_pages/pagetypes/flatpage/reversion/recover_form.html'


class ReversionFluentContentsPageAdmin(BaseFluentVersionAdmin,
                                       FluentContentsPageAdmin):

    revision_form_template = 'admin/fluentpage/reversion/revision_form.html'
    recover_form_template = 'admin/fluentpage/reversion/recover_form.html'

    #: The default template name, which is available in the template context.
    #: Use ``{% extend base_change_form_template %}`` in templates to inherit from it.
    base_change_form_template = "admin/fluent_pages/page/base_change_form.html"

    def get_revision_form_data(self, request, obj, version):
        obj_data = super(ReversionFluentContentsPageAdmin, self) \
            .get_revision_form_data(request, obj, version)

        # Hack to add required 'layout' foreign key field to deserialised
        # object when restoring deleted items, in which case we don't have
        # a real object to start with.
        if not getattr(obj, 'layout', None):
            try:
                obj.layout = PageLayout.objects.get(pk=obj_data['layout'])
            except Exception:
                obj.layout = None

        return obj_data

    # Extend VersionAdmin#_introspect_inline_admin
    def _introspect_inline_admin(self, inline):
        inline_model, follow_field = \
            super(ReversionFluentContentsPageAdmin, self) \
                ._introspect_inline_admin(inline)

        # Hack to always include ContentItem inlines available via
        # 'contentitem_set' attribute
        if follow_field is None and hasattr(self.model, 'contentitem_set'):
            follow_field = 'contentitem_set'

        return inline_model, follow_field

    # Re-implemented code to obtain extra context data following Fluent's
    # DefaultPageChildAdmin#render_change_form
    def render_revision_form(self, request, obj, version, context,
                             revert=False, recover=False):
        context.update({
            'base_change_form_template': self.base_change_form_template,
            'default_change_form_template': self.change_form_template,
            # HACK for polymorphic admin
            'ct_id': int(ContentType.objects.get_for_model(obj).pk),
        })
        result = super(ReversionFluentContentsPageAdmin, self) \
            .render_revision_form(request, obj, version, context,
                                  revert=revert, recover=recover)
        return result


class ReversionFluentPageAdmin(ReversionFluentContentsPageAdmin,
                               FluentPageAdmin):
    pass
