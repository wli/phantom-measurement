phantom.modules = phantom.modules || {};
phantom.modules.frames = {
  run: function() {
    return phantom.util.forAllChildFrames(function(doc) {
      var result = [];
      phantom.util.forEachFrame(doc, function(elem) {
        if (elem.src) result.push(elem.src);
      });
      return result;
    });
  }
};
