phantom.modules = phantom.modules || {};
phantom.modules.stylesheets = {
  run: function() {
    return phantom.util.forAllChildFrames(function(doc) {
      var result = [];
      _.each(doc.styleSheets, function(styleElem) {
        if (styleElem && styleElem.href)
          result.push(styleElem.href);
      });
      return result;
    });
  }
};
