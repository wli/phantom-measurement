phantom.modules = phantom.modules || {};
phantom.modules.jquery_version = {
  run: function() {
    if (window.jQuery && jQuery.fn && jQuery.fn.jquery) {
      return jQuery.fn.jquery;
    } else {
      return '';
    }
  }
};
