/**
 * Disable user-editable form fields in revert/recover forms -- as flagged with
 * `window.is_reversion_form` -- to prevent user from editing form fields in
 * the mistaken belief that any in-form changes will be respected when a prior
 * version is reverted/restored.
 */
(function($) {
  $(document).ready(function() {

    // Do nothing if we are not on a reversion-specific form, to
    // avoid disabling normal add/edit admin forms.
    if (! window.is_reversion_form) {
        return;
    }

    var form = $("form");

    // Disable all form input fields except csrf/submit fields
    form.find(":input").not(":submit").attr("disabled", true);
    form.find(":input[name='csrfmiddlewaretoken']").attr("disabled", false);

    // Remove dynamically generated controls and widgets
    setTimeout(function() {
      form.find(".datetimeshortcuts").remove();
      form.find(".related-lookup").remove();
      form.find(".redactor-toolbar").remove();

      // Hide inline Fluent Page content items flagged as deleted
      form.find(".inline-related").each(function() {
          var self = $(this);
          var id = self.attr("id");
          var delete_field_name = id + "-DELETE";
          if (self.find(":input[name='" + delete_field_name + "']:checked").length > 0) {
              self.hide();
          }
      });

      // Remove item controls *after* we have hidden deleted items.
      form.find(".cp-item-controls").remove();
    }, 250);

  });
})(django.jQuery);

