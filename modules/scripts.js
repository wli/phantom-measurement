phantom.modules = phantom.modules || {};
phantom.modules.scripts = {
  run: function() {
    return phantom.util.forAllChildFrames(function(doc) {
      var result = [];
      _.each(doc.scripts, function(scriptElem) {
        if (scriptElem && scriptElem.src)
          result.push(scriptElem.src);
      });
      return result;
    });
  }
};
