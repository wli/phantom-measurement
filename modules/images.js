phantom.modules = phantom.modules || {};
phantom.modules.images = {
  run: function() {
    return phantom.util.forAllChildFrames(function(doc) {
      var result = [];
      _.each(doc.getElementsByTagName('img'), function(imgElem) {
        if (imgElem && imgElem.src)
          result.push(imgElem.src);
      });
      return result;
    });
  }
};
